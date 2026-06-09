"""
Fit del modello MMM (cap. 5) — minimi quadrati non lineari (scipy).

Specificazione (eq. generale, cap. 3.1):
    y(t) = baseline(t) + sum_j gamma_j * z_j(t)
           + sum_k beta_k * Hill(Adstock(x_k,t)) + eps(t)

baseline(t) = alpha + trend*t + 2 armoniche di Fourier annuali (sin+cos).
z_j = variabili di controllo (domanda clienti, ricerche lavoratori, ...),
centrate sulla media per stabilita' numerica.
Per ogni canale si stimano congiuntamente beta, lam (adstock), K e s (Hill).

Nota metodologica: approccio frequentista (stime puntuali) per trasparenza
e velocita'; struttura del modello identica a quella dei framework
bayesiani, quindi sostituibile con PyMC-Marketing senza cambiare il resto
della pipeline.
"""
import json
import os

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

import config
from transforms import channel_response

N_BASE = 6  # alpha, trend, sin1, cos1, sin2, cos2


def _unpack(theta, channels, controls):
    base = theta[:N_BASE]
    nc = len(controls)
    gammas = dict(zip(controls, theta[N_BASE:N_BASE + nc]))
    params = {}
    for i, ch in enumerate(channels):
        off = N_BASE + nc + 4 * i
        b, lam, K, s = theta[off:off + 4]
        params[ch] = {"beta": b, "lam": lam, "K": K, "s": s}
    return base, gammas, params


def _predict(theta, t, spend, z, channels, controls):
    base, gammas, params = _unpack(theta, channels, controls)
    alpha, trend, a1, b1, a2, b2 = base
    w = 2 * np.pi * (t % 52) / 52
    y = (alpha + trend * t
         + a1 * np.sin(w) + b1 * np.cos(w)
         + a2 * np.sin(2 * w) + b2 * np.cos(2 * w))
    for c in controls:
        y = y + gammas[c] * z[c]
    for ch in channels:
        y = y + channel_response(spend[ch], **params[ch])
    return y


def fit(df: pd.DataFrame, channels=None, controls=None) -> dict:
    channels = channels or config.CHANNELS
    if controls is None:
        controls = [c for c in config.CONTROLS if c in df.columns]
    # accetta anche controlli extra caricati dall'utente (colonne ctrl_*)
    controls = list(controls) + [c[5:] for c in df.columns if c.startswith("ctrl_")]
    t = np.arange(len(df), dtype=float)
    spend = {ch: df[f"spend_{ch}"].to_numpy(float) for ch in channels}
    z = {}
    for c in controls:
        col = c if c in df.columns else f"ctrl_{c}"
        v = df[col].to_numpy(float)
        z[c] = v - np.nanmean(v)  # centratura
    y = df["applications"].to_numpy(float)

    # --- Inizializzazione e bound ------------------------------------------
    theta0, lo, hi = [], [], []
    # baseline
    theta0 += [y.mean() * 0.6, 0.0, 0.0, 0.0, 0.0, 0.0]
    lo += [0.0, -10.0, -400.0, -400.0, -400.0, -400.0]
    hi += [y.mean() * 1.5, 10.0, 400.0, 400.0, 400.0, 400.0]
    # controlli: coefficiente lineare libero
    for c in controls:
        sd = max(np.nanstd(z[c]), 1e-9)
        theta0 += [0.0]
        lo += [-10 * y.std() / sd]
        hi += [10 * y.std() / sd]
    # Bound informativi sui parametri di canale: l'equivalente frequentista
    # dei prior bayesiani (cap. 1.4). Senza vincoli, beta e K non sono
    # identificabili quando la spesa osservata non raggiunge la saturazione.
    for ch in channels:
        m = spend[ch].mean()
        theta0 += [y.std() * 1.5, 0.3, 1.5 * m, 1.3]   # beta, lam, K, s
        lo += [0.0, 0.0, 0.3 * m, 0.8]
        hi += [y.mean() * 0.6, 0.9, 5.0 * m, 2.5]

    res = least_squares(
        lambda th: _predict(th, t, spend, z, channels, controls) - y,
        x0=theta0, bounds=(lo, hi), x_scale="jac", max_nfev=20_000,
    )
    base, gammas, params = _unpack(res.x, channels, controls)
    y_hat = _predict(res.x, t, spend, z, channels, controls)

    rmse = float(np.sqrt(np.mean((y - y_hat) ** 2)))
    return {
        "baseline": {"alpha": base[0], "trend_per_week": base[1],
                     "fourier": list(base[2:])},
        "controls": {c: float(g) for c, g in gammas.items()},
        "channels": params,
        "diagnostics": {
            "rmse": rmse,
            "nrmse": rmse / float(y.max() - y.min()),
            "r2": float(1 - np.sum((y - y_hat) ** 2) / np.sum((y - y.mean()) ** 2)),
            "mape": float(np.mean(np.abs((y - y_hat) / y))),
        },
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    df = pd.read_csv(os.path.join(here, config.DATA_CSV))
    result = fit(df)

    os.makedirs(os.path.join(here, "output"), exist_ok=True)
    with open(os.path.join(here, config.FIT_JSON), "w") as f:
        json.dump(result, f, indent=2)

    d = result["diagnostics"]
    print(f"Fit completato - R2={d['r2']:.4f}  NRMSE={d['nrmse']:.4f}  MAPE={d['mape']:.3%}")
    print(f"{'canale':<10}{'beta':>9}{'lam':>7}{'K':>10}{'s':>7}")
    for ch, p in result["channels"].items():
        print(f"{ch:<10}{p['beta']:>9.1f}{p['lam']:>7.2f}{p['K']:>10.0f}{p['s']:>7.2f}")
    if result["controls"]:
        print("coefficienti controlli:",
              {c: round(g, 4) for c, g in result["controls"].items()})


if __name__ == "__main__":
    main()
