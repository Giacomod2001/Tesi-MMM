"""
Budget allocator vincolato (cap. 3.5) — il cuore decisionale della pipeline.

Problema: dato un budget settimanale B, distribuirlo tra i canali per
massimizzare le candidature attese a regime, soggetto a:
  - vincolo di budget totale: sum x_k <= B
  - bound min/max per canale (impegni contrattuali, employer branding)
  - vincolo opzionale di variazione massima vs allocazione corrente
    (per evitare riallocazioni traumatiche)

L'ottimizzatore (SLSQP) lavora sulle curve di risposta a regime stimate
dal modello: sottrae euro dove il ROAS marginale e' basso (zona piatta
della Hill) e li sposta dove e' ancora elevato (zona ripida).

Output: tabella di riallocazione con spesa corrente vs ottimale, ROAS
marginale e budget efficiency gain — una RACCOMANDAZIONE, non una
decisione (paradigma human-in-the-middle, cap. 3.6).
"""
import json
import os

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from mmm import config
from mmm.transforms import steady_state_response, marginal_response


def total_response(x: np.ndarray, params: dict, channels) -> float:
    """Candidature settimanali attese a regime per il vettore di spesa x."""
    return sum(
        steady_state_response(x[i], **params[ch])
        for i, ch in enumerate(channels)
    )


def optimize_budget(
    params: dict,
    current_spend: dict,
    total_budget: float | None = None,
    min_spend: dict | None = None,
    max_spend: dict | None = None,
    max_change_pct: float | None = None,
    channels=config.CHANNELS,
) -> pd.DataFrame:
    """Ottimizza l'allocazione e restituisce la tabella di riallocazione.

    Args:
        params: parametri stimati per canale {ch: {beta, lam, K, s}}.
        current_spend: spesa settimanale corrente per canale (status quo).
        total_budget: budget totale; default = somma dello status quo
            (riallocazione a parita' di budget).
        min_spend / max_spend: vincoli operativi per canale (EUR/settimana).
        max_change_pct: se valorizzato (es. 0.3), ogni canale puo' variare
            al massimo del +/-30% rispetto allo status quo.
    """
    x0 = np.array([current_spend[ch] for ch in channels], dtype=float)
    B = float(total_budget if total_budget is not None else x0.sum())

    lo = np.array([(min_spend or {}).get(ch, 0.0) for ch in channels])
    hi = np.array([(max_spend or {}).get(ch, B) for ch in channels])
    if max_change_pct is not None:
        lo = np.maximum(lo, x0 * (1 - max_change_pct))
        hi = np.minimum(hi, x0 * (1 + max_change_pct))

    if lo.sum() > B:
        raise ValueError("Vincoli incompatibili: la spesa minima supera il budget.")

    res = minimize(
        lambda x: -total_response(x, params, channels),
        x0=np.clip(B * x0 / x0.sum(), lo, hi),
        method="SLSQP",
        bounds=list(zip(lo, hi)),
        constraints=[{"type": "eq", "fun": lambda x: x.sum() - B}],
        options={"maxiter": 500, "ftol": 1e-10},
    )
    if not res.success:
        raise RuntimeError(f"Ottimizzazione non riuscita: {res.message}")
    x_opt = res.x

    # --- Tabella di riallocazione ------------------------------------------
    rows = []
    for i, ch in enumerate(channels):
        p = params[ch]
        rows.append({
            "canale": ch,
            "spesa_corrente": x0[i],
            "spesa_ottimale": x_opt[i],
            "variazione_eur": x_opt[i] - x0[i],
            "variazione_pct": (x_opt[i] - x0[i]) / x0[i] if x0[i] else np.nan,
            "candidature_correnti": steady_state_response(x0[i], **p),
            "candidature_ottimali": steady_state_response(x_opt[i], **p),
            "roas_marg_corrente_x1000": marginal_response(x0[i], **p) * 1000,
            "roas_marg_ottimale_x1000": marginal_response(x_opt[i], **p) * 1000,
        })
    table = pd.DataFrame(rows)

    cur = table["candidature_correnti"].sum()
    opt = table["candidature_ottimali"].sum()
    table.attrs["summary"] = {
        "budget_settimanale": B,
        "candidature_correnti": cur,
        "candidature_ottimali": opt,
        "efficiency_gain": (opt - cur) / cur,
    }
    return table


def print_report(table: pd.DataFrame):
    s = table.attrs["summary"]
    print(f"\nBudget settimanale: {s['budget_settimanale']:>10,.0f} EUR")
    print(f"{'canale':<10}{'corrente':>11}{'ottimale':>11}{'delta':>10}{'delta%':>8}"
          f"{'ROASm cur':>11}{'ROASm opt':>11}")
    for _, r in table.iterrows():
        print(f"{r['canale']:<10}{r['spesa_corrente']:>11,.0f}{r['spesa_ottimale']:>11,.0f}"
              f"{r['variazione_eur']:>10,.0f}{r['variazione_pct']:>8.1%}"
              f"{r['roas_marg_corrente_x1000']:>11.2f}{r['roas_marg_ottimale_x1000']:>11.2f}")
    print(f"\nCandidature/settimana attese:  {s['candidature_correnti']:,.0f} -> "
          f"{s['candidature_ottimali']:,.0f}   "
          f"(efficiency gain: {s['efficiency_gain']:+.2%})")
    print("(ROASm = candidature incrementali per 1.000 EUR marginali)")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, config.FIT_JSON)) as f:
        fitted = json.load(f)["channels"]

    df = pd.read_csv(os.path.join(here, config.DATA_CSV))
    current = {ch: float(df[f"spend_{ch}"].mean()) for ch in config.CHANNELS}

    # Scenario base: riallocazione a parita' di budget, variazione max +/-50%,
    # con presidio minimo su LinkedIn (employer branding, vincolo strategico).
    table = optimize_budget(
        fitted, current,
        min_spend={"linkedin": 2_000},
        max_change_pct=0.5,
    )
    print_report(table)

    out = os.path.join(here, config.ALLOCATION_CSV)
    table.to_csv(out, index=False)
    with open(os.path.join(here, "output", "allocation_summary.json"), "w") as f:
        json.dump(table.attrs["summary"], f, indent=2)
    print(f"\nTabella salvata: {out}")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Pianificazione multi-periodo (anno / quarter / mese)
# ---------------------------------------------------------------------------
PERIODS = {
    "anno":    {"n": 1,  "weeks": 52.0,    "label": ["Anno"]},
    "quarter": {"n": 4,  "weeks": 13.0,    "label": ["Q1 (Gen-Mar)", "Q2 (Apr-Giu)", "Q3 (Lug-Set)", "Q4 (Ott-Dic)"]},
    "mese":    {"n": 12, "weeks": 52 / 12, "label": ["Gen", "Feb", "Mar", "Apr",
                                                     "Mag", "Giu", "Lug", "Ago",
                                                     "Set", "Ott", "Nov", "Dic"]},
}


def plan_periods(params, total_budget: float, granularity: str = "quarter",
                 period_weights=None, current_spend=None,
                 min_spend=None, max_spend=None, max_change_pct=None,
                 channels=config.CHANNELS) -> pd.DataFrame:
    """Pianifica il budget annuale su piu' periodi e, per ciascun periodo,
    trova l'allocazione ottimale tra i canali.

    Args:
        total_budget: budget complessivo del piano (es. annuale).
        granularity: "anno" | "quarter" | "mese".
        period_weights: pesi relativi dei periodi (es. piu' budget in Q4);
            default uniforme. Vengono normalizzati automaticamente.
        current_spend: spesa settimanale corrente per canale (status quo,
            usato per i vincoli di variazione massima).
        min_spend/max_spend/max_change_pct: vincoli per canale (settimanali).

    Returns:
        DataFrame con una riga per (periodo, canale): budget di periodo,
        spesa settimanale, candidature attese.
    """
    spec = PERIODS[granularity]
    n, wk = spec["n"], spec["weeks"]
    w = np.asarray(period_weights if period_weights is not None else np.ones(n), float)
    w = w / w.sum()

    if current_spend is None:
        current_spend = {ch: total_budget / 52 / len(channels) for ch in channels}

    rows = []
    for i in range(n):
        weekly_budget = total_budget * w[i] / wk
        table = optimize_budget(
            params, current_spend, total_budget=weekly_budget,
            min_spend=min_spend, max_spend=max_spend,
            max_change_pct=max_change_pct, channels=channels,
        )
        for _, r in table.iterrows():
            rows.append({
                "periodo": spec["label"][i],
                "canale": r["canale"],
                "budget_periodo": r["spesa_ottimale"] * wk,
                "spesa_settimanale": r["spesa_ottimale"],
                "candidature_sett": r["candidature_ottimali"],
                "candidature_periodo": r["candidature_ottimali"] * wk,
                "roas_marg_x1000": r["roas_marg_ottimale_x1000"],
            })
    plan = pd.DataFrame(rows)
    plan.attrs["summary"] = {
        "budget_totale": float(plan["budget_periodo"].sum()),
        "candidature_totali": float(plan["candidature_periodo"].sum()),
        "granularita": granularity,
    }
    return plan


def suggest_period_weights(df: pd.DataFrame, granularity: str,
                           column: str | None = None) -> np.ndarray:
    """Pesi di periodo suggeriti dai dati (stagionalita' della domanda).

    Calcola la media per periodo dell'anno (quarter o mese) della serie di
    domanda — di default le richieste dei clienti, altrimenti le candidature —
    dopo aver rimosso il trend lineare, e la normalizza a media 1.
    Il manager puo' sempre modificare i pesi proposti (human-in-the-middle).
    """
    spec = PERIODS[granularity]
    if spec["n"] == 1:
        return np.array([1.0])

    if column is None:
        column = next((c for c in ("richieste_clienti", "ctrl_richieste_clienti")
                       if c in df.columns), "applications")
    v = df[column].to_numpy(float)
    t = np.arange(len(v), dtype=float)
    v = v - np.polyval(np.polyfit(t, v, 1), t) + v.mean()  # detrend

    week = pd.to_datetime(df["week"])
    per = (week.dt.quarter - 1) if granularity == "quarter" else (week.dt.month - 1)
    means = pd.Series(v).groupby(per.to_numpy()).mean()
    w = means.reindex(range(spec["n"])).fillna(means.mean()).to_numpy()
    w = np.clip(w / w.mean(), 0.4, 2.5)   # pesi entro un range ragionevole
    return np.round(w, 2)
