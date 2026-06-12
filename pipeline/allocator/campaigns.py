"""
Stage 2 — riparto del budget di canale tra le campagne.

Metodo (documento di progetto §4.4): i ROAS di piattaforma forniscono il
RANKING relativo intra-canale (le piattaforme confrontano bene le proprie
campagne tra loro), il MMM fornisce il LIVELLO assoluto corretto (le
piattaforme sovra/sotto-attribuiscono in modo sistematico). Quindi:

    roas_adj(campagna) = roas_piattaforma(campagna) × k_canale
    k_canale = ROI_MMM(canale) / ROAS_piattaforma(canale)

e il budget di canale si ripartisce in proporzione alla spesa recente
"riponderata" dai ROAS aggiustati, con un limite di variazione per
campagna (default ±50%) che evita riallocazioni traumatiche su un solo
ciclo: la convergenza avviene su più trimestri (human-in-the-middle).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def campaign_roas(media: pd.DataFrame, revenue_per_conversion: float,
                  window_weeks: int = 13) -> pd.DataFrame:
    """ROAS di piattaforma per campagna sull'ultima finestra osservata."""
    media = media.copy()
    media["week"] = pd.to_datetime(media["week"])
    last = media["week"].max()
    win = media[media["week"] > last - pd.Timedelta(weeks=window_weeks)]
    g = (win.groupby(["channel", "campaign"], as_index=False)
         .agg(spend=("spend", "sum"),
              platform_conversions=("platform_conversions", "sum")))
    g["platform_roas"] = (g["platform_conversions"] * revenue_per_conversion
                          / g["spend"].clip(lower=1e-9))
    return g


def allocate_campaigns(channel_budget: dict[str, float],
                       roas_table: pd.DataFrame,
                       mmm_roi: dict[str, float],
                       max_shift: float = 0.5) -> pd.DataFrame:
    """Riparto del budget di canale tra le campagne.

    Args:
        channel_budget: budget di quarter per canale (stage 1).
        roas_table: output di campaign_roas().
        mmm_roi: ROI posterior mediano per canale (model_fit.json).
        max_shift: variazione massima della quota campagna vs storico
            (0.5 = ±50%). I residui si redistribuiscono pro-quota.

    Returns:
        Tabella campagna × (quota storica, ROAS aggiustato, budget proposto).
    """
    out = []
    for ch, budget in channel_budget.items():
        t = roas_table[roas_table["channel"] == ch].copy()
        if t.empty:
            continue
        ch_spend = t["spend"].sum()
        ch_roas = float((t["platform_roas"] * t["spend"]).sum()
                        / max(ch_spend, 1e-9))
        k = mmm_roi.get(ch, ch_roas) / max(ch_roas, 1e-9)
        t["roas_adjusted"] = t["platform_roas"] * k
        t["share_hist"] = t["spend"] / max(ch_spend, 1e-9)

        # riponderazione: quota storica × ROAS aggiustato (normalizzato)
        raw = t["share_hist"] * t["roas_adjusted"]
        t["share_target"] = raw / raw.sum()
        # paletto anti-trauma per campagna
        lo = t["share_hist"] * (1 - max_shift)
        hi = t["share_hist"] * (1 + max_shift)
        s = t["share_target"].clip(lo, hi)
        t["share_proposed"] = s / s.sum()
        t["budget_proposed"] = t["share_proposed"] * budget
        t["k_channel"] = k
        out.append(t)

    res = pd.concat(out, ignore_index=True)
    cols = ["channel", "campaign", "spend", "platform_roas", "k_channel",
            "roas_adjusted", "share_hist", "share_proposed",
            "budget_proposed"]
    return res[cols].sort_values(["channel", "budget_proposed"],
                                 ascending=[True, False]).reset_index(drop=True)
