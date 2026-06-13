"""
Fit bayesiano agnostico (PyMC) con prior EMPIRICAL BAYES.

Regola di agnosticismo totale: nessun "numero magico" legato alle unita'
di misura. I parametri dei prior sono derivati dinamicamente dai dati:

- se e' disponibile un fit frequentista (anchor), le sue stime puntuali
  diventano i CENTRI dei prior (Empirical Bayes in senso stretto), con
  dispersioni proporzionali — abbastanza larghe da lasciare ai dati
  l'ultima parola, abbastanza informative da risolvere l'identificabilita';
- in assenza di anchor, centri e scale derivano dalle statistiche del
  dataset (media della spesa per canale, deviazione standard del target),
  quindi il modello e' invariante per cambio di unita' (da centinaia a
  milioni di euro cambia tutto coerentemente).

Le UNICHE costanti fisse sono ADIMENSIONALI e documentate: rapporti di
dispersione relativa e concentrazioni di distribuzioni su [0,1]. Non
dipendono dalle unita' dei dati per costruzione.
"""
import numpy as np
import pandas as pd

L_ADSTOCK = 12

# Iperparametri ADIMENSIONALI (non dipendono dalle unita' di misura)
REL_SD = {
    "beta": 0.50,    # sd del prior su beta = 50% del centro
    "K_log": 0.50,   # sd in scala log per K (moltiplicativa)
    "s": 0.35,       # sd relativa della slope
}
LAM_CONCENTRATION = 6.0   # "peso" del prior Beta su lambda (in pseudo-osservazioni)
FALLBACK = {              # centri adimensionali usati SENZA anchor frequentista
    "lam": 1 / 3,         # ritenzione media plausibile
    "K_mult": 1.5,        # K ~ 1.5x la spesa media del canale
    "s": 1.3,             # slope moderatamente concava
    "beta_mult": 1.5,     # beta ~ 1.5x la sd del target
}


def _lag_matrix(x: np.ndarray, L: int) -> np.ndarray:
    n = len(x)
    out = np.zeros((n, L + 1))
    for l in range(L + 1):
        out[l:, l] = x[: n - l]
    return out


def _anchors(df, channels, anchor):
    """Centri dei prior per canale: dal fit frequentista se c'e', altrimenti
    dalle scale del dataset."""
    y_sd = max(float(df["applications"].std()), 1e-9)
    out = {}
    for ch in channels:
        m = max(float(df[f"spend_{ch}"].mean()), 1e-9)
        a = (anchor or {}).get(ch, {})
        out[ch] = {
            "beta": float(a.get("beta", FALLBACK["beta_mult"] * y_sd)),
            "lam": float(np.clip(a.get("lam", FALLBACK["lam"]), 0.05, 0.90)),
            "K": float(a.get("K", FALLBACK["K_mult"] * m)),
            "s": float(np.clip(a.get("s", FALLBACK["s"]), 0.8, 2.5)),
        }
    return out


def fit_bayes(df: pd.DataFrame, channels: list[str],
              anchor: dict | None = None,
              draws: int = 300, tune: int = 300, chains: int = 2,
              seed: int = 42) -> dict:
    """Fit MCMC. `anchor` = stime frequentiste {ch: {beta, lam, K, s}}
    usate come centri dei prior (Empirical Bayes). Ritorna {summary, curves}."""
    import pymc as pm
    import pytensor.tensor as pt
    import arviz as az

    if anchor is None:
        try:                                   # fit frequentista come ancora
            from model import fit as _freq_fit
            anchor = _freq_fit(df, channels=channels, controls=[])["channels"]
        except Exception:
            anchor = None                      # fallback: scale del dataset

    ctrl_cols = [c for c in df.columns if c.startswith("ctrl_")]
    n = len(df)
    t = np.arange(n, dtype=float)
    w = 2 * np.pi * (t % 52) / 52
    y = df["applications"].to_numpy(float)
    y_sd = max(float(y.std()), 1e-9)
    spend = {ch: df[f"spend_{ch}"].to_numpy(float) for ch in channels}
    lags = {ch: _lag_matrix(spend[ch], L_ADSTOCK) for ch in channels}
    z = {c: df[c].to_numpy(float) - np.nanmean(df[c].to_numpy(float))
         for c in ctrl_cols}
    centers = _anchors(df, channels, anchor)

    with pm.Model():
        # baseline: tutte le scale derivano da y
        alpha = pm.Normal("alpha", mu=float(y.mean()), sigma=y_sd)
        trend = pm.Normal("trend", mu=0, sigma=3 * y_sd / n)
        mu = alpha + trend * t
        for k in (1, 2):
            mu = mu + pm.Normal(f"f_sin{k}", 0, y_sd) * np.sin(k * w) \
                    + pm.Normal(f"f_cos{k}", 0, y_sd) * np.cos(k * w)
        for c in ctrl_cols:
            sd_z = max(float(np.nanstd(z[c])), 1e-9)
            mu = mu + pm.Normal(f"gamma_{c[5:]}", 0, y_sd / sd_z) * z[c]

        for ch in channels:
            c0 = centers[ch]
            beta = pm.TruncatedNormal(
                f"beta_{ch}", mu=c0["beta"],
                sigma=REL_SD["beta"] * c0["beta"], lower=0)
            # Beta con media = ancora e concentrazione fissa (adimensionale)
            a_l = c0["lam"] * LAM_CONCENTRATION
            b_l = (1 - c0["lam"]) * LAM_CONCENTRATION
            lam = pm.Beta(f"lam_{ch}", alpha=a_l, beta=b_l)
            K = pm.LogNormal(f"K_{ch}", mu=np.log(c0["K"]),
                             sigma=REL_SD["K_log"])
            sd_s = REL_SD["s"] * c0["s"]
            s = pm.Gamma(f"s_{ch}", alpha=(c0["s"] / sd_s) ** 2,
                         beta=c0["s"] / sd_s**2)
            A = pt.dot(lags[ch], lam ** pt.arange(L_ADSTOCK + 1))
            mu = mu + beta * A**s / (K**s + A**s + 1e-9)

        sigma = pm.HalfNormal("sigma", sigma=y_sd)
        pm.Normal("obs", mu=mu, sigma=sigma, observed=y)
        idata = pm.sample(draws=draws, tune=tune, chains=chains, cores=chains,
                          target_accept=0.9, random_seed=seed,
                          progressbar=False)

    summ = az.summary(idata, ci_prob=0.90, ci_kind="hdi")
    summary = {i: {"mean": float(r["mean"]), "sd": float(r["sd"]),
                   "hdi_5%": float(r["hdi90_lb"]), "hdi_95%": float(r["hdi90_ub"]),
                   "r_hat": float(r["r_hat"])} for i, r in summ.iterrows()}

    post = idata.posterior.to_dataset().stack(sample=("chain", "draw"))
    take = np.linspace(0, post.sizes["sample"] - 1, 300).astype(int)
    curves = {}
    for ch in channels:
        b = post[f"beta_{ch}"].values[take]
        lam = post[f"lam_{ch}"].values[take]
        K = post[f"K_{ch}"].values[take]
        s = post[f"s_{ch}"].values[take]
        grid = np.linspace(0, 2.5 * max(spend[ch].mean(), 1e-9), 40)
        A = grid[None, :] / (1 - lam[:, None])
        resp = b[:, None] * A**s[:, None] / (K[:, None]**s[:, None] + A**s[:, None])
        curves[ch] = {"spend": grid.tolist(),
                      "p05": np.percentile(resp, 5, axis=0).tolist(),
                      "p50": np.percentile(resp, 50, axis=0).tolist(),
                      "p95": np.percentile(resp, 95, axis=0).tolist()}
    return {"summary": summary, "curves": curves,
            "anchored": anchor is not None}
