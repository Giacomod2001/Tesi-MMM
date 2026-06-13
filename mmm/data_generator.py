"""
Generatore del dataset sintetico settimanale (cap. 4).

Simula 3 anni di attivita' media di un'agenzia per il lavoro:
- spesa per canale con stagionalita', rumore e pause campagna
- variabili di controllo: domanda clienti (fulfillment) e intensita'
  di ricerca lavoro lato candidati, con ciclicita' macro e stagionale
- candidature = baseline + effetto controlli + contributi canale + rumore

Il processo generativo usa esattamente le trasformazioni del modello
(adstock geometrico + Hill), cosi' da poter verificare il parameter
recovery in fase di validazione.
"""
import json
import os

import numpy as np
import pandas as pd

from mmm import config
from mmm.transforms import channel_response


def generate(seed: int = config.SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = config.N_WEEKS
    t = np.arange(n)
    woy = t % 52

    # --- Spesa per canale -------------------------------------------------
    spend = {}
    for ch in config.CHANNELS:
        base = config.MEAN_WEEKLY_SPEND[ch]
        seas = 1.0 + 0.25 * np.sin(2 * np.pi * (woy - 8) / 52)
        noise = rng.normal(1.0, 0.18, n).clip(0.4, 1.8)
        x = base * seas * noise
        for _ in range(rng.integers(2, 4)):
            start = rng.integers(0, n - 4)
            x[start:start + rng.integers(2, 5)] *= rng.uniform(0.0, 0.25)
        spend[ch] = x.round(2)

    # --- Variabili di controllo --------------------------------------------
    # Richieste clienti (fulfillment): trend + picchi pre-estate e Q4
    richieste = (2_000 + 3.0 * t
                 + 320 * np.sin(2 * np.pi * (woy - 20) / 52)
                 + 140 * np.sin(4 * np.pi * woy / 52)
                 + rng.normal(0, 80, n)).round(0)
    # Ricerche lavoratori: picchi gennaio e settembre
    ricerche = (5_000 - 1.5 * t
                + 550 * np.sin(2 * np.pi * (woy - 2) / 52)
                + 260 * np.sin(4 * np.pi * (woy - 35) / 52)
                + rng.normal(0, 150, n)).round(0)
    controls = {"richieste_clienti": richieste, "ricerche_lavoratori": ricerche}

    # --- Baseline organica -------------------------------------------------
    b = config.BASELINE
    baseline = (
        b["alpha"]
        + b["trend_per_week"] * t
        + b["seas_amp"] * np.sin(2 * np.pi * (woy - 12) / 52)
        + b["seas_amp2"] * np.sin(4 * np.pi * woy / 52)
    )

    # --- Contributi e variabile obiettivo -----------------------------------
    contrib = {
        ch: channel_response(spend[ch], **config.TRUE_PARAMS[ch])
        for ch in config.CHANNELS
    }
    control_effect = sum(
        config.TRUE_CONTROL_COEF[c] * (controls[c] - controls[c].mean())
        for c in config.CONTROLS
    )
    applications = (
        baseline + control_effect + sum(contrib.values())
        + rng.normal(0, config.NOISE_SD, n)
    ).round(0)

    df = pd.DataFrame({
        "week": pd.date_range("2023-01-02", periods=n, freq="W-MON"),
        **{f"spend_{ch}": spend[ch] for ch in config.CHANNELS},
        **controls,
        "applications": applications,
        # colonne di audit (note solo perche' i dati sono sintetici)
        "baseline_true": baseline.round(1),
        **{f"contrib_{ch}_true": contrib[ch].round(1) for ch in config.CHANNELS},
    })
    return df


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(here, "data"), exist_ok=True)

    df = generate()
    csv_path = os.path.join(here, config.DATA_CSV)
    df.to_csv(csv_path, index=False)

    with open(os.path.join(here, config.TRUE_PARAMS_JSON), "w") as f:
        json.dump({"channels": config.TRUE_PARAMS,
                   "baseline": config.BASELINE,
                   "control_coef": config.TRUE_CONTROL_COEF}, f, indent=2)

    print(f"Dataset salvato: {csv_path}  ({len(df)} settimane)")


if __name__ == "__main__":
    main()
