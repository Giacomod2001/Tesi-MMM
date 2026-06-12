"""
Spaccato temporale dell'ottimo trimestrale: settimane e mesi (mai giorni).

Il budget di canale del quarter viene distribuito sulle 13 settimane
seguendo l'indice stagionale esogeno, con uno smorzamento che evita di
concentrare la spesa oltre la zona efficiente della curva di saturazione:
l'esponente di smorzamento deriva dalla pendenza marginale della curva
del canale (canali già vicini alla saturazione → profilo più piatto).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config, schema
from . import quarter as Q


def weekly_profile(seasonality: pd.DataFrame,
                   quarter_weeks: pd.DatetimeIndex) -> np.ndarray:
    """Indice stagionale normalizzato (media 1) sulle settimane del quarter."""
    nat = seasonality[seasonality["region"] == "*"]
    s = nat.set_index(pd.to_datetime(nat["week"]))["seasonal_index"]
    # proietta sulla settimana dell'anno se il quarter è futuro
    woy = pd.Index(quarter_weeks.isocalendar().week)
    s_woy = (s.groupby(s.index.isocalendar().week).mean())
    prof = s_woy.reindex(woy).ffill().bfill().to_numpy()
    return prof / prof.mean()


def damping_exponent(curve: dict, weekly_spend: float) -> float:
    """Smorzamento ∈ [0,1]: elasticità locale della curva di risposta.
    1 = segue piena stagionalità (curva ancora ripida);
    →0 = profilo piatto (canale in saturazione)."""
    eps = max(weekly_spend * 1e-3, 0.1)
    f = lambda x: Q._steady_response(x, curve["lam"], curve["ec"],
                                     curve["slope"], curve["scale"])
    m1 = (f(weekly_spend + eps) - f(weekly_spend)) / eps
    avg = f(weekly_spend) / max(weekly_spend, 1e-9)
    if avg <= 0:
        return 1.0
    return float(np.clip(m1 / avg, 0.0, 1.0))     # marginale/medio

def build_schedule(alloc: pd.DataFrame, summary: dict,
                   seasonality: pd.DataFrame,
                   quarter_start: str) -> pd.DataFrame:
    """Piano settimana × canale del quarter + rollup mensile.

    Args:
        alloc: output dello stage 1 (budget_quarter per canale).
        summary: model_fit.json (per le curve di saturazione).
        seasonality: fatto canonico stagionalità (indice esogeno).
        quarter_start: lunedì di inizio quarter (ISO).
    """
    weeks = schema.week_grid(quarter_start, config.QUARTER_WEEKS)
    prof = weekly_profile(seasonality, weeks)

    hist = {r.channel: (r.hist_weekly_spend
                        if "hist_weekly_spend" in alloc.columns
                        and not np.isnan(r.hist_weekly_spend)
                        else r.weekly_spend)
            for r in alloc.itertuples()}
    curves = Q.build_curves(summary, hist)

    rows = []
    for r in alloc.itertuples():
        d = damping_exponent(curves[r.channel], r.weekly_spend)
        w = prof ** d
        w = w / w.sum()
        for week, wi in zip(weeks, w):
            rows.append({"week": week, "channel": r.channel,
                         "spend": r.budget_quarter * wi,
                         "damping": round(d, 3)})
    plan = pd.DataFrame(rows)
    plan = schema.add_calendar(plan)
    return plan


def monthly_rollup(plan: pd.DataFrame) -> pd.DataFrame:
    return (plan.groupby(["month", "channel"], as_index=False)["spend"]
            .sum().sort_values(["month", "channel"]).reset_index(drop=True))
