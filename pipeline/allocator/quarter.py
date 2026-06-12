"""
Stage 1 — allocazione trimestrale per canale con vincoli min/max in EUR.

Due percorsi con lo stesso contratto di output:

1. `optimize_with_meridian(mmm, ...)` usa il BudgetOptimizer nativo
   (response curve posterior complete). I vincoli EUR vengono tradotti
   nei vincoli relativi richiesti dall'API e ri-verificati sull'output.

2. `optimize_from_summary(summary, ...)` ricostruisce le curve di
   risposta a regime dalle mediane posterior (adstock + Hill + ROI) e
   ottimizza con SLSQP. Serve quando si riparte dal `model_fit.json`
   senza ricaricare il modello (es. nei rilanci trimestrali leggeri) e
   per i test; in produzione il percorso primario è il n.1.

Vincoli: budget totale del quarter; min/max EUR per canale (es. "canale
strategico mai sotto il 70% della spesa attuale"). Nessun canale
vincolato può essere azzerato.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import config

WEEKS = config.QUARTER_WEEKS


@dataclass
class Constraints:
    """Paletti dell'allocator (input manageriale, human-in-the-middle)."""
    total_budget: float                        # EUR sul quarter (13 settimane)
    min_spend: dict[str, float] = field(default_factory=dict)   # EUR/quarter
    max_spend: dict[str, float] = field(default_factory=dict)   # EUR/quarter

    def bounds(self, channels: list[str]) -> tuple[np.ndarray, np.ndarray]:
        lo = np.array([self.min_spend.get(c, 0.0) for c in channels])
        hi = np.array([self.max_spend.get(c, self.total_budget)
                       for c in channels])
        if lo.sum() > self.total_budget + 1e-6:
            raise ValueError("Vincoli incompatibili: somma dei minimi "
                             f"({lo.sum():,.0f}) > budget "
                             f"({self.total_budget:,.0f})")
        if np.any(hi < lo):
            raise ValueError("Vincoli incompatibili: max < min per "
                             "almeno un canale")
        return lo, hi


# ------------------------------------------------------- curve dal summary
def _steady_response(weekly_spend, lam, ec_scaled, slope, scale):
    """Risposta a regime: adstock di spesa costante = x/(1-lam), Hill."""
    A = np.asarray(weekly_spend, float) / max(1.0 - lam, 1e-6) / scale
    return A ** slope / (ec_scaled ** slope + A ** slope + 1e-12)


def build_curves(summary: dict, hist_weekly_spend: dict[str, float]) -> dict:
    """Curve EUR/settimana → EUR di ricavo incrementale a settimana, per
    canale, calibrate in modo che alla spesa storica il ROI della curva
    coincida con il ROI posterior mediano."""
    curves = {}
    for ch, e in summary["channels"].items():
        lam = e.get("adstock_lam", {}).get("q50", 0.3)
        ec = e.get("hill_ec", {}).get("q50", 1.0)
        slope = e.get("hill_slope", {}).get("q50", 1.0)
        roi = e["roi"]["q50"]
        x0 = max(hist_weekly_spend.get(ch, 1.0), 1e-6)
        # scala dell'adstock: ec è in unità di media scalata per Meridian;
        # usiamo x0/(1-lam) come unità → la forma resta, il livello viene
        # ancorato al ROI posterior alla spesa storica
        scale = x0 / max(1.0 - lam, 1e-6)
        base = _steady_response(x0, lam, ec, slope, scale)
        beta = roi * x0 / max(base, 1e-9)      # EUR di ricavo a regime
        curves[ch] = {"lam": lam, "ec": ec, "slope": slope,
                      "scale": scale, "beta": beta, "x0": x0}
    return curves


def _revenue(weekly_x: np.ndarray, curves: dict, channels: list[str]) -> float:
    return float(sum(
        curves[ch]["beta"] * _steady_response(
            weekly_x[i], curves[ch]["lam"], curves[ch]["ec"],
            curves[ch]["slope"], curves[ch]["scale"])
        for i, ch in enumerate(channels)))


def optimize_from_summary(summary: dict,
                          hist_weekly_spend: dict[str, float],
                          cons: Constraints) -> pd.DataFrame:
    """Allocazione ottima del quarter dalle mediane posterior (SLSQP)."""
    from scipy.optimize import minimize

    channels = list(summary["channels"])
    curves = build_curves(summary, hist_weekly_spend)
    lo_q, hi_q = cons.bounds(channels)
    lo, hi = lo_q / WEEKS, hi_q / WEEKS            # lavora in EUR/settimana
    B = cons.total_budget / WEEKS

    x0 = np.array([hist_weekly_spend[c] for c in channels])
    x0 = np.clip(B * x0 / max(x0.sum(), 1e-9), lo, hi)
    # ripara l'eventuale sforamento del clip mantenendo i bound
    for _ in range(10):
        gap = B - x0.sum()
        if abs(gap) < 1e-6:
            break
        room = (hi - x0) if gap > 0 else (x0 - lo)
        w = room / max(room.sum(), 1e-9)
        x0 = np.clip(x0 + gap * w, lo, hi)

    res = minimize(lambda x: -_revenue(x, curves, channels), x0,
                   method="SLSQP", bounds=list(zip(lo, hi)),
                   constraints=[{"type": "eq",
                                 "fun": lambda x: x.sum() - B}],
                   options={"maxiter": 500, "ftol": 1e-10})
    if not res.success:
        raise RuntimeError(f"Ottimizzazione fallita: {res.message}")
    return _table(res.x, channels, curves, hist_weekly_spend, cons)


def _table(weekly_x, channels, curves, hist, cons) -> pd.DataFrame:
    eps = 1.0
    rows = []
    for i, ch in enumerate(channels):
        c = curves[ch]
        f = lambda x: c["beta"] * _steady_response(x, c["lam"], c["ec"],
                                                   c["slope"], c["scale"])
        rows.append({
            "channel": ch,
            "budget_quarter": weekly_x[i] * WEEKS,
            "weekly_spend": weekly_x[i],
            "hist_weekly_spend": hist.get(ch, np.nan),
            "delta_pct": (weekly_x[i] - hist.get(ch, np.nan))
                          / max(hist.get(ch, 1e-9), 1e-9),
            "expected_weekly_revenue": f(weekly_x[i]),
            "marginal_roi": (f(weekly_x[i] + eps) - f(weekly_x[i])) / eps,
            "constraint_min": cons.min_spend.get(ch, 0.0),
            "constraint_max": cons.max_spend.get(ch, np.nan),
        })
    t = pd.DataFrame(rows)
    t.attrs["summary"] = {
        "total_budget": float(cons.total_budget),
        "expected_quarter_revenue": float(
            t["expected_weekly_revenue"].sum() * WEEKS),
    }
    return t


# ------------------------------------------------------- percorso Meridian
def optimize_with_meridian(mmm, cons: Constraints,
                           selected_times: list[str] | None = None):
    """Allocazione con il BudgetOptimizer nativo di Meridian.

    I vincoli EUR min/max vengono tradotti in lower/upper bound relativi
    all'allocazione di partenza (API Meridian) e ri-verificati a valle:
    se la traduzione non li rispetta esattamente, l'output viene
    riproiettato nei bound con redistribuzione proporzionale.
    """
    from meridian.analysis import optimizer as O

    channels = list(mmm.input_data.media_channel.values)
    lo, hi = cons.bounds(channels)
    hist = mmm.input_data.media_spend.sum(dim=("geo", "time")).values
    share = hist / hist.sum()
    base = share * cons.total_budget
    # bound relativi rispetto a base (richiesti come frazioni)
    lower = np.clip(1 - lo / np.maximum(base, 1e-9), 0.01, 0.99)
    upper = np.maximum(hi / np.maximum(base, 1e-9) - 1, 0.01)

    opt = O.BudgetOptimizer(mmm)
    res = opt.optimize(budget=cons.total_budget,
                       pct_of_spend=share,
                       spend_constraint_lower=lower,
                       spend_constraint_upper=upper,
                       selected_times=selected_times,
                       fixed_budget=True)
    spend = np.asarray(res.optimized_data.spend.values, float)
    # riproiezione difensiva nei vincoli EUR
    spend = np.clip(spend, lo, hi)
    gap = cons.total_budget - spend.sum()
    if abs(gap) > 1e-6:
        room = (hi - spend) if gap > 0 else (spend - lo)
        spend = np.clip(spend + gap * room / max(room.sum(), 1e-9), lo, hi)

    t = pd.DataFrame({"channel": channels,
                      "budget_quarter": spend,
                      "weekly_spend": spend / WEEKS,
                      "constraint_min": lo, "constraint_max": hi})
    t.attrs["summary"] = {"total_budget": float(cons.total_budget),
                          "optimizer": "meridian"}
    t.attrs["meridian_results"] = res
    return t
