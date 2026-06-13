"""
Parameter recovery: stima vs verità, con intervalli di credibilità.

Metriche:
- ROI per canale: errore relativo della mediana posterior e COPERTURA
  (la verità cade nell'intervallo di credibilità 90%?) — la metrica
  decisionale principale;
- adstock (ritenzione geometrica): confronto diretto con la verità;
- saturazione: i parametri di Hill di Meridian sono in unità di media
  scalata e non sono confrontabili uno-a-uno con la ground truth →
  si confronta la CURVA di risposta a regime (MAE% nel range di spesa
  osservato, 0.5x-1.5x della spesa media), che è ciò che l'allocator
  usa davvero.

Esecuzione:  python -m pipeline.validation.recovery
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from .. import config
from ..allocator import quarter as Q
from results_xlsx import write_sheet, WORKBOOK


def load(fit_path: str | None = None,
         truth_path: str | None = None) -> tuple[dict, dict]:
    with open(fit_path or os.path.join(config.OUTPUT_DIR,
                                       "model_fit.json")) as f:
        fit = json.load(f)
    with open(truth_path or config.GROUND_TRUTH_JSON) as f:
        truth = json.load(f)
    return fit, truth


def roi_recovery(fit: dict, truth: dict) -> pd.DataFrame:
    rows = []
    for ch, e in fit["channels"].items():
        t = truth["channels"][ch]["roi_true"]
        r = e["roi"]
        rows.append({
            "channel": ch, "roi_true": t,
            "roi_q05": r["q05"], "roi_q50": r["q50"], "roi_q95": r["q95"],
            "rel_error": (r["q50"] - t) / t,
            "covered_90": bool(r["q05"] <= t <= r["q95"]),
        })
    return pd.DataFrame(rows)


def adstock_recovery(fit: dict, truth: dict) -> pd.DataFrame:
    rows = []
    for ch, e in fit["channels"].items():
        if "adstock_lam" not in e:
            continue
        t = truth["channels"][ch]["adstock_lam"]
        a = e["adstock_lam"]
        rows.append({
            "channel": ch, "lam_true": t,
            "lam_q05": a["q05"], "lam_q50": a["q50"], "lam_q95": a["q95"],
            "abs_error": a["q50"] - t,
            "covered_90": bool(a["q05"] <= t <= a["q95"]),
        })
    return pd.DataFrame(rows)


def _true_national_curve(truth: dict, ch: str, grid: np.ndarray) -> np.ndarray:
    """Curva vera nazionale a regime (EUR ricavo/sett.) per spesa costante.
    Approssimazione nazionale: regioni aggregate (Σ pop_r · mult_r ≈ 1)."""
    p = truth["channels"][ch]
    rev = truth["revenue_per_conversion"]["mean"]
    A_pc = grid / (1.0 - p["adstock_lam"])     # adstock pro-capite nazionale
    hill = (A_pc ** p["hill_slope"]
            / (p["hill_K_pc"] ** p["hill_slope"] + A_pc ** p["hill_slope"]))
    return p["beta"] * hill * rev


def curve_recovery(fit: dict, truth: dict,
                   hist_weekly_spend: dict[str, float]) -> pd.DataFrame:
    """MAE% tra curva stimata e curva vera nel range di spesa osservato."""
    curves = Q.build_curves(fit, hist_weekly_spend)
    rows = []
    for ch, c in curves.items():
        m = hist_weekly_spend[ch]
        grid = np.linspace(0.5 * m, 1.5 * m, 21)
        est = np.array([c["beta"] * Q._steady_response(
            x, c["lam"], c["ec"], c["slope"], c["scale"]) for x in grid])
        true = _true_national_curve(truth, ch, grid)
        rows.append({"channel": ch,
                     "curve_mae_pct": float(np.mean(
                         np.abs(est - true) / np.maximum(true, 1e-9)))})
    return pd.DataFrame(rows)


def main() -> None:
    fit, truth = load()
    media = pd.read_csv(os.path.join(config.CANON_DIR, "media.csv"),
                        parse_dates=["week"])
    n_weeks = media["week"].nunique()
    hist = (media.groupby("channel")["spend"].sum() / n_weeks).to_dict()

    roi = roi_recovery(fit, truth)
    ads = adstock_recovery(fit, truth)
    crv = curve_recovery(fit, truth, hist)

    print("=== PARAMETER RECOVERY: ROI ===")
    print(roi.round(3).to_string(index=False))
    print(f"\ncopertura 90%: {roi['covered_90'].mean():.0%} | "
          f"errore mediano |.|: {roi['rel_error'].abs().median():.1%}")
    if len(ads):
        print("\n=== ADSTOCK ===")
        print(ads.round(3).to_string(index=False))
    print("\n=== CURVE DI RISPOSTA (MAE% 0.5x-1.5x spesa media) ===")
    print(crv.round(3).to_string(index=False))

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    recovery = pd.concat([roi.assign(metric="roi"),
                          ads.assign(metric="adstock") if len(ads) else None,
                          crv.assign(metric="curve")])
    write_sheet("Recovery", recovery.round(4),
                {"roi_true": "0.00", "roi_q05": "0.00", "roi_q50": "0.00",
                 "roi_q95": "0.00", "rel_error": "0.0%",
                 "curve_mae_pct": "0.0%"})
    print(f"\nFoglio 'Recovery' aggiornato in {WORKBOOK}")


if __name__ == "__main__":
    main()
