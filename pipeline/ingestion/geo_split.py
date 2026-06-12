"""
Ripartizione geografica della spesa media — gerarchia di qualità:

  1. campagne geo-targettizzate  → spesa regionale REALE (nessuna stima)
  2. campagne nazionali con breakdown impression → split proporzionale
     alle impression regionali della stessa campagna/settimana
  3. nessun breakdown → split per popolazione (fallback, identificazione
     più debole — segnalato nel report di ingestion)

Assunzione dichiarata: residenza ≈ luogo di esposizione.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config

VALUE_COLS = ["spend", "impressions", "clicks", "platform_conversions"]


def split_national(national: pd.DataFrame,
                   breakdown: pd.DataFrame | None) -> tuple[pd.DataFrame, dict]:
    """Trasforma righe nazionali in righe regionali.

    Args:
        national: righe media con region='' (una per settimana x campagna).
        breakdown: righe (week, campaign, region, impressions) con le
            impression regionali delle campagne nazionali, se disponibili.

    Returns:
        (df regionale, statistiche {campagna: tier}) dove tier è
        'impressions' o 'population'.
    """
    if national.empty:
        return national, {}
    regions = config.REGION_LIST
    pop = np.array([config.REGIONS[r] for r in regions])
    tiers: dict[str, str] = {}
    out = []

    bk = None
    if breakdown is not None and not breakdown.empty:
        bk = (breakdown.groupby(["campaign", "week", "region"], as_index=False)
              ["impressions"].sum())

    for (camp, week), grp in national.groupby(["campaign", "week"]):
        row = grp[VALUE_COLS].sum()
        shares, impr_reg = None, None
        if bk is not None:
            sub = bk[(bk["campaign"] == camp) & (bk["week"] == week)]
            if len(sub) and sub["impressions"].sum() > 0:
                sub = sub.set_index("region")["impressions"]
                impr_reg = sub.reindex(regions).fillna(0.0).to_numpy()
                shares = impr_reg / impr_reg.sum()
                tiers[camp] = "impressions"
        if shares is None:
            shares = pop
            tiers.setdefault(camp, "population")

        block = pd.DataFrame({
            "week": week, "region": regions,
            "channel": grp["channel"].iloc[0], "campaign": camp,
            "spend": row["spend"] * shares,
            "impressions": (impr_reg if impr_reg is not None
                            else row["impressions"] * shares),
            "clicks": row["clicks"] * shares,
            "platform_conversions": row["platform_conversions"] * shares,
        })
        out.append(block)
    return pd.concat(out, ignore_index=True), tiers
