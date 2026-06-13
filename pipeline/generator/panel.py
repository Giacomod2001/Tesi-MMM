"""
Generazione del panel "vero": fatti canonici + grandezze nascoste.

Procedimento (tutto vettoriale su 20 regioni x 104 settimane):
  1. piano spese per campagna x settimana (stagionalità, rumore, pause)
  2. ripartizione regionale: spesa reale per le campagne geo-targettizzate,
     split per impression per le nazionali (esposizione vera)
  3. risposta media per CANALE: adstock geometrico pro-capite + Hill,
     stessa curva per tutte le regioni (assunzione geo-gerarchica)
  4. outcome = baseline regionale x stagionalità + effetto domanda
     + somma risposte canale + rumore
  5. conversioni di piattaforma per campagna (con bias di attribuzione
     noto: è il dato che lo stage 2 dovrà riscalare)

Ritorna sia i fatti canonici (ciò che l'ingestion dovrà ricostruire dagli
export sporchi) sia le componenti nascoste per ground_truth.json.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config, schema
from . import world


def _campaign_weekly_national_spend(rng: np.random.Generator,
                                    n: int) -> dict[str, np.ndarray]:
    """Spesa nazionale settimanale per campagna: base x stagionalità del
    planning x rumore, con 2-3 pause campagna casuali."""
    woy = (pd.Series(schema.week_grid(world.START_WEEK, n))
           .dt.isocalendar().week.to_numpy().astype(float))
    seas_media = 1.0 + 0.5 * (world.seasonal_curve(woy) - 1.0)  # i media seguono
    out = {}                                                    # in parte la domanda
    for camp, c in world.CAMPAIGNS.items():
        base = world.MEAN_WEEKLY_SPEND[c["channel"]] * c["share"]
        x = base * seas_media * rng.normal(1.0, 0.16, n).clip(0.45, 1.7)
        for _ in range(int(rng.integers(2, 4))):                # pause
            start = int(rng.integers(0, n - 4))
            x[start:start + int(rng.integers(2, 5))] *= rng.uniform(0.0, 0.2)
        out[camp] = x.round(2)
    return out


def _regional_split(rng: np.random.Generator, camp: str,
                    n: int) -> np.ndarray:
    """Matrice (settimane x regioni) di quote regionali per la campagna.

    Quote ~ popolazione con tilt fisso di campagna (alcune campagne pesano
    di più al Nord industriale, altre al Sud) + rumore settimanale.
    """
    pop = np.array([config.REGIONS[r] for r in config.REGION_LIST])
    tilt = rng.lognormal(0.0, 0.25, len(pop))          # tilt fisso di campagna
    w = pop * tilt
    noise = rng.lognormal(0.0, 0.10, (n, len(pop)))    # variazione settimanale
    m = w[None, :] * noise
    return m / m.sum(axis=1, keepdims=True)


def generate(seed: int = world.SEED, n_weeks: int = world.N_WEEKS) -> dict:
    rng = np.random.default_rng(seed)
    weeks = schema.week_grid(world.START_WEEK, n_weeks)
    regions = config.REGION_LIST
    pop = np.array([config.REGIONS[r] for r in regions])
    n, R = n_weeks, len(regions)
    woy = pd.Series(weeks).dt.isocalendar().week.to_numpy().astype(float)
    seas = world.seasonal_curve(woy)                   # (n,)
    t = np.arange(n, dtype=float)

    # ---- 1-2. spese e impression per campagna x regione --------------------
    nat_spend = _campaign_weekly_national_spend(rng, n)
    camp_spend = {}        # camp -> (n, R) spesa regionale VERA (esposizione)
    camp_impr = {}         # camp -> (n, R) impression regionali
    camp_clicks = {}
    for camp, c in world.CAMPAIGNS.items():
        shares = _regional_split(rng, camp, n)
        s = nat_spend[camp][:, None] * shares
        impr = s / c["cpm"] * 1000.0 * rng.normal(1, 0.05, (n, R)).clip(0.8, 1.2)
        clicks = impr * c["ctr"] * rng.normal(1, 0.08, (n, R)).clip(0.6, 1.4)
        camp_spend[camp] = s
        camp_impr[camp] = np.round(impr)
        camp_clicks[camp] = np.round(clicks)

    # ---- 3. risposta per canale (pro-capite, curva unica) ------------------
    channels = sorted({c["channel"] for c in world.CAMPAIGNS.values()})
    ch_spend = {ch: sum(camp_spend[cp] for cp, c in world.CAMPAIGNS.items()
                        if c["channel"] == ch) for ch in channels}
    region_mult = rng.lognormal(0.0, world.BASELINE["region_sd"], R)
    region_mult /= (region_mult * pop).sum() / pop.sum()   # media pesata = 1
    resp = {}                                              # ch -> (n, R)
    for ch in channels:
        p = world.CHANNELS[ch]
        out = np.empty((n, R))
        for j in range(R):
            x_pc = ch_spend[ch][:, j] / pop[j]             # EUR pro-capite*
            A = world.geometric_adstock(x_pc, p["lam"])
            out[:, j] = (p["beta"] * pop[j] * region_mult[j]
                         * world.hill(A, p["K_pc"], p["slope"]))
        resp[ch] = out
    # *pro-capite = per quota di popolazione: stessa curva in ogni regione.

    # ---- controlli di domanda ----------------------------------------------
    demand = {}
    for name, d in world.DEMAND.items():
        level = (d["level"] + d["trend"] * t)[:, None] * pop[None, :]
        seas_part = 1.0 + d["seas_coupling"] * (seas[:, None] - 1.0)
        noise = rng.normal(0, d["noise_sd"] * np.sqrt(pop)[None, :], (n, R))
        demand[name] = np.maximum(level * seas_part + noise, 0.0).round(0)

    # ---- 4. outcome ---------------------------------------------------------
    base_nat = world.BASELINE["alpha_national"] + world.BASELINE["trend_per_week"] * t
    baseline = base_nat[:, None] * (pop * region_mult)[None, :] * seas[:, None]
    ctrl_effect = sum(
        world.DEMAND[name]["coef_true"]
        * (demand[name] - demand[name].mean(axis=0, keepdims=True))
        for name in demand)
    noise = rng.normal(0, world.NOISE_SD_PC * np.sqrt(pop)[None, :], (n, R))
    conv = np.maximum(baseline + ctrl_effect + sum(resp.values()) + noise, 0.0)
    rev_mult = rng.normal(world.REVENUE_PER_CONVERSION["mean"],
                          world.REVENUE_PER_CONVERSION["mean"]
                          * world.REVENUE_PER_CONVERSION["cv"] / 35, (n, R))
    revenue = conv * rev_mult

    # ---- 5. conversioni di piattaforma per campagna ------------------------
    camp_conv = {}
    for ch in channels:
        camps = [cp for cp, c in world.CAMPAIGNS.items() if c["channel"] == ch]
        qual_spend = np.stack([world.CAMPAIGNS[cp]["quality"] * camp_spend[cp]
                               for cp in camps])          # (C, n, R)
        share = qual_spend / np.maximum(qual_spend.sum(axis=0), 1e-9)
        plat_total = world.CHANNELS[ch]["misattr"] * resp[ch]
        for i, cp in enumerate(camps):
            v = plat_total * share[i] * rng.normal(1, 0.10, (n, R)).clip(0.5, 1.6)
            camp_conv[cp] = np.round(v, 1)

    # ---- fatti canonici ------------------------------------------------------
    def melt(arr_by_camp: dict, value: str) -> pd.DataFrame:
        frames = []
        for cp, arr in arr_by_camp.items():
            f = pd.DataFrame(arr, index=weeks, columns=regions)
            f = f.stack().rename(value).reset_index()
            f.columns = ["week", "region", value]
            f["campaign"] = cp
            frames.append(f)
        return pd.concat(frames, ignore_index=True)

    media = melt(camp_spend, "spend")
    for name, d in (("impressions", camp_impr), ("clicks", camp_clicks),
                    ("platform_conversions", camp_conv)):
        media = media.merge(melt(d, name), on=["week", "region", "campaign"])
    media["channel"] = media["campaign"].map(
        {cp: c["channel"] for cp, c in world.CAMPAIGNS.items()})
    media = media[config.MEDIA_COLS].sort_values(
        ["week", "region", "channel", "campaign"]).reset_index(drop=True)

    outcome = pd.DataFrame({
        "week": np.repeat(weeks, R), "region": np.tile(regions, n),
        "conversions": conv.round(0).ravel(),
        "revenue": revenue.round(2).ravel()})[config.OUTCOME_COLS]

    demand_df = pd.DataFrame({
        "week": np.repeat(weeks, R), "region": np.tile(regions, n),
        "client_requests": demand["client_requests"].ravel(),
        "candidate_searches": demand["candidate_searches"].ravel(),
    })[config.DEMAND_COLS]

    seasonality_df = pd.DataFrame({
        "week": weeks, "region": "*",
        "seasonal_index": np.round(seas, 4)})[config.SEASONALITY_COLS]

    campaigns_df = pd.DataFrame([
        {"campaign": cp, "channel": c["channel"], "objective": c["objective"],
         "funnel": c["funnel"], "geo_targeted": c["geo"]}
        for cp, c in world.CAMPAIGNS.items()])[config.CAMPAIGN_ATTR_COLS]

    # ---- grandezze nascoste (per ground_truth.json) -------------------------
    mean_rev = world.REVENUE_PER_CONVERSION["mean"]
    hidden = {
        "roi_true": {ch: float(resp[ch].sum() * mean_rev / ch_spend[ch].sum())
                     for ch in channels},
        "incremental_conversions": {ch: float(resp[ch].sum()) for ch in channels},
        "spend_total": {ch: float(ch_spend[ch].sum()) for ch in channels},
        "region_multipliers": dict(zip(regions, np.round(region_mult, 4))),
        "seasonal_index_by_week": dict(zip([str(w.date()) for w in weeks],
                                           np.round(seas, 4))),
        "campaign_true_split": {
            ch: {cp: float(world.CAMPAIGNS[cp]["quality"]
                           * camp_spend[cp].sum())
                 for cp in world.CAMPAIGNS
                 if world.CAMPAIGNS[cp]["channel"] == ch}
            for ch in channels},
        "response_by_channel": resp,        # array, non serializzato in json
    }
    # normalizza lo split vero per canale
    for ch, d in hidden["campaign_true_split"].items():
        tot = sum(d.values())
        hidden["campaign_true_split"][ch] = {k: round(v / tot, 4)
                                             for k, v in d.items()}

    return {"media": media, "outcome": outcome, "demand": demand_df,
            "seasonality": seasonality_df, "campaigns": campaigns_df,
            "weeks": weeks, "hidden": hidden,
            "internals": {"camp_spend": camp_spend, "camp_impr": camp_impr,
                          "camp_clicks": camp_clicks, "camp_conv": camp_conv,
                          "conv": conv, "revenue": revenue}}
