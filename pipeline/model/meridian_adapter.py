"""
Adapter: fatti canonici → InputData Meridian → fit → riepilogo posterior.

Scelte modellistiche (documento di progetto §4.3):
- panel regione × settimana: ~20 geo × 104 settimane (geo-gerarchia);
- KPI = conversioni (kpi_type='non_revenue') con revenue_per_kpi:
  il ROI stimato è in EUR di ricavo per EUR di spesa;
- calibrazione: prior LogNormale sul ROI di canale centrato sul ROAS di
  piattaforma (che misura il *livello percepito* dal canale) con sigma
  largo: informa senza vincolare;
- stagionalità ESOGENA come control variable; per evitare il doppio
  conteggio la flessibilità temporale interna è ridotta (un knot per
  trimestre invece del default un knot per settimana).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from .. import config, schema

ITALY_POPULATION = 58_990_000


# ------------------------------------------------------------------ dati
def load_facts(canon_dir: str | None = None) -> dict[str, pd.DataFrame]:
    """Carica e valida i fatti canonici scritti dall'ingestion."""
    canon_dir = canon_dir or config.CANON_DIR
    facts = {}
    for name in ("media", "outcome", "demand", "seasonality"):
        path = os.path.join(canon_dir, f"{name}.csv")
        if os.path.exists(path):
            facts[name] = pd.read_csv(path, parse_dates=["week"])
    reports = schema.validate_all(facts)
    bad = [str(r) for r in reports.values() if not r.ok]
    if bad:
        raise ValueError("Fatti canonici non validi:\n" + "\n".join(bad))
    return facts


def build_frame(facts: dict[str, pd.DataFrame],
                channels: list[str] | None = None) -> tuple[pd.DataFrame,
                                                            list[str]]:
    """Costruisce il dataframe largo geo × settimana per Meridian."""
    media = facts["media"]
    channels = channels or sorted(media["channel"].unique())

    spend = (media.pivot_table(index=["week", "region"], columns="channel",
                               values="spend", aggfunc="sum")
             .reindex(columns=channels).fillna(0.0))
    spend.columns = [f"spend_{c}" for c in channels]
    df = spend.reset_index()

    out = facts["outcome"].copy()
    df = df.merge(out, on=["week", "region"], how="inner")
    df["revenue_per_kpi"] = np.where(df["conversions"] > 0,
                                     df["revenue"] / df["conversions"], 0.0)

    if "demand" in facts:
        df = df.merge(facts["demand"], on=["week", "region"], how="left")

    if "seasonality" in facts:
        seas = facts["seasonality"]
        nat = seas[seas["region"] == "*"][["week", "seasonal_index"]]
        reg = seas[seas["region"] != "*"]
        if len(reg):
            df = df.merge(reg, on=["week", "region"], how="left")
            if len(nat):
                df = df.merge(nat, on="week", how="left",
                              suffixes=("", "_nat"))
                df["seasonal_index"] = df["seasonal_index"].fillna(
                    df.pop("seasonal_index_nat"))
        elif len(nat):
            df = df.merge(nat, on="week", how="left")

    df["population"] = df["region"].map(config.REGIONS) * ITALY_POPULATION
    df["time"] = pd.to_datetime(df["week"]).dt.strftime("%Y-%m-%d")

    ctrl = [c for c in ("client_requests", "candidate_searches",
                        "seasonal_index", "direct_apps") if c in df.columns]
    df[ctrl] = df[ctrl].ffill().bfill()
    return df.sort_values(["time", "region"]).reset_index(drop=True), channels


def platform_roas(facts: dict[str, pd.DataFrame]) -> dict[str, float]:
    """ROAS di piattaforma per canale = conversioni attribuite dalla
    piattaforma × valore medio conversione / spesa. È il prior di
    calibrazione: cattura il ranking percepito, il posterior corregge
    il livello (sovra/sotto-attribuzione)."""
    media, out = facts["media"], facts["outcome"]
    rev_per_conv = float(out["revenue"].sum() / max(out["conversions"].sum(), 1))
    g = media.groupby("channel").agg(spend=("spend", "sum"),
                                     pconv=("platform_conversions", "sum"))
    return {ch: float(r.pconv * rev_per_conv / max(r.spend, 1e-9))
            for ch, r in g.iterrows()}


# ------------------------------------------------------------------ modello
def build_meridian(df: pd.DataFrame, channels: list[str],
                   roas_prior: dict[str, float] | None = None,
                   roi_prior_sigma: float = 0.7,
                   roi_prior_discount: float = 1.3,
                   knots_per_quarter: int = 3,
                   extra_controls: tuple[str, ...] = (),
                   max_lag: int = 8):
    """InputData + ModelSpec + Meridian (non ancora campionato)."""
    import tensorflow_probability as tfp
    from meridian import constants as C
    from meridian.data import data_frame_input_data_builder as B
    from meridian.model import model as M
    from meridian.model import prior_distribution as P
    from meridian.model import spec as S

    ctrl = [c for c in ("client_requests", "candidate_searches",
                        "seasonal_index", "direct_apps", *extra_controls)
            if c in df.columns]
    builder = (B.DataFrameInputDataBuilder(kpi_type="non_revenue",
                                           default_geo_column="region")
               .with_kpi(df, kpi_col="conversions")
               .with_revenue_per_kpi(df, revenue_per_kpi_col="revenue_per_kpi")
               .with_population(df)
               .with_controls(df, control_cols=ctrl)
               .with_media(df,
                           media_cols=[f"spend_{c}" for c in channels],
                           media_spend_cols=[f"spend_{c}" for c in channels],
                           media_channels=channels))
    data = builder.build()

    # prior ROI: LogNormale centrata sul ROAS di piattaforma per canale,
    # scontato di un fattore di sovra-attribuzione: l'attribuzione di
    # piattaforma (last-click) e' un tetto, non l'effetto incrementale vero.
    if roas_prior:
        centers = [max(roas_prior.get(c, 1.0) / roi_prior_discount, 0.05)
                   for c in channels]
        mu = np.log(centers)
        roi_m = tfp.distributions.LogNormal(
            mu.astype(np.float32), np.float32(roi_prior_sigma),
            name=C.ROI_M)
        prior = P.PriorDistribution(roi_m=roi_m)
    else:
        prior = P.PriorDistribution()

    # stagionalità esogena nel modello → pochi knot interni (anti doppio
    # conteggio): 1 per trimestre invece del default settimanale
    n_times = df["time"].nunique()
    knots = max(2, int(np.ceil(n_times / 13)) * knots_per_quarter)

    mspec = S.ModelSpec(prior=prior, knots=knots, max_lag=max_lag,
                        paid_media_prior_type="roi")
    return M.Meridian(input_data=data, model_spec=mspec)


def fit(mmm, n_chains: int = 4, n_adapt: int = 500, n_burnin: int = 500,
        n_keep: int = 1000, seed: int = 42):
    """Campionamento prior + posterior (MCMC NUTS)."""
    mmm.sample_prior(500, seed=seed)
    mmm.sample_posterior(n_chains=n_chains, n_adapt=n_adapt,
                         n_burnin=n_burnin, n_keep=n_keep, seed=seed)
    return mmm


# ------------------------------------------------------------------ riepilogo
def summarize(mmm, channels: list[str]) -> dict:
    """Posterior dei parametri decisionali: ROI, adstock, saturazione."""
    from meridian.analysis import analyzer as A
    az_data = mmm.inference_data

    def post(name):
        return az_data.posterior[name].values  # (chain, draw, ...)

    def stats(x):
        return {"mean": float(np.mean(x)), "sd": float(np.std(x)),
                "q05": float(np.quantile(x, .05)),
                "q50": float(np.quantile(x, .50)),
                "q95": float(np.quantile(x, .95))}

    an = A.Analyzer(mmm)
    roi = an.roi()                                   # (chain, draw, channel)
    out = {"channels": {}}
    for i, ch in enumerate(channels):
        entry = {"roi": stats(np.asarray(roi)[..., i])}
        for par, key in (("alpha_m", "adstock_lam"),
                         ("ec_m", "hill_ec"), ("slope_m", "hill_slope")):
            if par in az_data.posterior:
                entry[key] = stats(post(par)[..., i])
        out["channels"][ch] = entry

    # diagnostica di convergenza: max R-hat sui SOLI valori finiti.
    # Alcune variabili deterministiche hanno varianza intra-catena nulla →
    # R-hat indefinito (NaN): vanno ignorate, non devono inquinare il max
    # (e np.nanmax su una slice tutta-NaN emette warning fuorvianti).
    try:
        import warnings
        import arviz as az
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rh = az.rhat(az_data.posterior)
        vals = []
        for v in rh.data_vars:
            arr = np.asarray(rh[v], dtype=float)
            arr = arr[np.isfinite(arr)]
            if arr.size:
                vals.append(float(arr.max()))
        out["diagnostics"] = {"max_rhat": max(vals) if vals else None,
                              "rhat_params": len(vals)}
    except Exception as exc:                         # pragma: no cover
        out["diagnostics"] = {"rhat_error": str(exc)}
    return out


def save_summary(summary: dict, path: str | None = None) -> str:
    path = path or os.path.join(config.OUTPUT_DIR, "model_fit.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return path
