"""
Fit bayesiano del modello MMM (PyMC) — affianca model.py, non lo sostituisce.

Stessa equazione del fit frequentista (cap. 3.1); cambiano:
- i bound rigidi diventano PRIOR informativi (es. K ~ LogNormale centrata
  su 1,5 volte la spesa media del canale): conoscenza di dominio elicitabile
- l'output non e' un numero per parametro ma una DISTRIBUZIONE a posteriori:
  intervalli credibili su parametri, curve di risposta e guadagno atteso
  della riallocazione

Esecuzione (offline, ~10-20 minuti):
    python model_bayes.py

Output (letti dall'app Streamlit se presenti):
    output/bayes_summary.json   - parametri: media, sd, intervallo HDI 90%
    output/bayes_curves.json    - curve di risposta: mediana e banda 90%
    output/bayes_alloc.json     - distribuzione del guadagno della riallocazione

Nota tecnica: l'adstock geometrico e' troncato a L=12 settimane e
vettorizzato come prodotto matrice-lags x potenze di lambda, per evitare
lo scan simbolico e tenere il campionamento veloce.
"""
import json
import os

import numpy as np
import pandas as pd

import config

L_ADSTOCK = 12          # troncamento dell'adstock (settimane)
DRAWS, TUNE, CHAINS = 500, 500, 2
CURVE_GRID_N = 40
SEED = 42


def lag_matrix(x: np.ndarray, L: int) -> np.ndarray:
    """Matrice (n, L+1) dei ritardi di x: colonna l = x ritardata di l."""
    n = len(x)
    out = np.zeros((n, L + 1))
    for l in range(L + 1):
        out[l:, l] = x[: n - l]
    return out


def main():
    import pymc as pm
    import pytensor.tensor as pt
    import arviz as az

    here = os.path.dirname(os.path.abspath(__file__))
    df = pd.read_csv(os.path.join(here, config.DATA_CSV))
    channels = config.CHANNELS
    controls = [c for c in config.CONTROLS if c in df.columns]

    n = len(df)
    t = np.arange(n, dtype=float)
    w = 2 * np.pi * (t % 52) / 52
    y = df["applications"].to_numpy(float)

    spend = {ch: df[f"spend_{ch}"].to_numpy(float) for ch in channels}
    mean_spend = {ch: spend[ch].mean() for ch in channels}
    lags = {ch: lag_matrix(spend[ch], L_ADSTOCK) for ch in channels}
    z = {c: df[c].to_numpy(float) - df[c].mean() for c in controls}

    with pm.Model() as model:
        # --- baseline -----------------------------------------------------
        alpha = pm.Normal("alpha", mu=y.mean() * 0.7, sigma=200)
        trend = pm.Normal("trend", mu=0, sigma=5)
        f_sin1 = pm.Normal("f_sin1", 0, 100)
        f_cos1 = pm.Normal("f_cos1", 0, 100)
        f_sin2 = pm.Normal("f_sin2", 0, 100)
        f_cos2 = pm.Normal("f_cos2", 0, 100)
        mu = (alpha + trend * t
              + f_sin1 * np.sin(w) + f_cos1 * np.cos(w)
              + f_sin2 * np.sin(2 * w) + f_cos2 * np.cos(2 * w))

        # --- controlli ------------------------------------------------------
        for c in controls:
            g = pm.Normal(f"gamma_{c}", mu=0, sigma=1)
            mu = mu + g * z[c]

        # --- canali media: prior informativi al posto dei bound rigidi ------
        for ch in channels:
            m = mean_spend[ch]
            beta = pm.HalfNormal(f"beta_{ch}", sigma=y.std() * 1.5)
            lam = pm.Beta(f"lam_{ch}", alpha=2, beta=4)        # media ~0.33
            K = pm.LogNormal(f"K_{ch}", mu=np.log(1.5 * m), sigma=0.6)
            s = pm.Gamma(f"s_{ch}", alpha=6, beta=4.5)         # media ~1.33

            powers = lam ** pt.arange(L_ADSTOCK + 1)
            A = pt.dot(lags[ch], powers)                       # adstock
            mu = mu + beta * A**s / (K**s + A**s + 1e-9)       # Hill

        sigma = pm.HalfNormal("sigma", sigma=60)
        pm.Normal("obs", mu=mu, sigma=sigma, observed=y)

        idata = pm.sample(draws=DRAWS, tune=TUNE, chains=CHAINS,
                          cores=CHAINS, target_accept=0.9,
                          random_seed=SEED, progressbar=False)

    os.makedirs(os.path.join(here, "output"), exist_ok=True)

    # --- 1) sintesi dei parametri -------------------------------------------
    summ = az.summary(idata, hdi_prob=0.90)
    summary = {
        idx: {"mean": float(r["mean"]), "sd": float(r["sd"]),
              "hdi_5%": float(r["hdi_5%"]), "hdi_95%": float(r["hdi_95%"]),
              "r_hat": float(r["r_hat"])}
        for idx, r in summ.iterrows()
    }
    with open(os.path.join(here, "output", "bayes_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # --- 2) curve di risposta a regime con banda 90% --------------------------
    post = idata.posterior.stack(sample=("chain", "draw"))
    n_samp = post.sizes["sample"]
    take = np.linspace(0, n_samp - 1, min(300, n_samp)).astype(int)
    curves = {}
    for ch in channels:
        b = post[f"beta_{ch}"].values[take]
        lam = post[f"lam_{ch}"].values[take]
        K = post[f"K_{ch}"].values[take]
        s = post[f"s_{ch}"].values[take]
        grid = np.linspace(0, 2.5 * mean_spend[ch], CURVE_GRID_N)
        A = grid[None, :] / (1 - lam[:, None])                  # regime
        resp = b[:, None] * A**s[:, None] / (K[:, None]**s[:, None] + A**s[:, None])
        curves[ch] = {
            "spend": grid.tolist(),
            "p05": np.percentile(resp, 5, axis=0).tolist(),
            "p50": np.percentile(resp, 50, axis=0).tolist(),
            "p95": np.percentile(resp, 95, axis=0).tolist(),
        }
    with open(os.path.join(here, "output", "bayes_curves.json"), "w") as f:
        json.dump(curves, f)

    # --- 3) incertezza sul guadagno della riallocazione ----------------------
    # confronto: mix storico vs mix ottimo frequentista, valutati su ogni draw
    try:
        with open(os.path.join(here, config.FIT_JSON)) as f:
            freq = json.load(f)["channels"]
        from allocator import optimize_budget
        cur = {ch: float(mean_spend[ch]) for ch in channels}
        opt_table = optimize_budget(freq, cur)
        x_cur = np.array([cur[ch] for ch in channels])
        x_opt = opt_table["spesa_ottimale"].to_numpy()

        gains = []
        for i in take:
            tot = {}
            for x, name in ((x_cur, "cur"), (x_opt, "opt")):
                v = 0.0
                for j, ch in enumerate(channels):
                    b = float(post[f"beta_{ch}"].values[i])
                    lam = float(post[f"lam_{ch}"].values[i])
                    K = float(post[f"K_{ch}"].values[i])
                    s = float(post[f"s_{ch}"].values[i])
                    A = x[j] / (1 - lam)
                    v += b * A**s / (K**s + A**s)
                tot[name] = v
            gains.append(tot["opt"] / tot["cur"] - 1)
        gains = np.array(gains)
        alloc = {
            "gain_p05": float(np.percentile(gains, 5)),
            "gain_p50": float(np.percentile(gains, 50)),
            "gain_p95": float(np.percentile(gains, 95)),
            "prob_gain_positivo": float((gains > 0).mean()),
        }
        with open(os.path.join(here, "output", "bayes_alloc.json"), "w") as f:
            json.dump(alloc, f, indent=2)
        print("Guadagno riallocazione:", alloc)
    except FileNotFoundError:
        print("fit frequentista assente: salto l'analisi del guadagno")

    bad = summ[summ["r_hat"] > 1.05]
    print(f"Campionamento completato. Parametri con r_hat>1.05: {len(bad)}")
    print("Output scritti in output/bayes_*.json")


if __name__ == "__main__":
    main()
