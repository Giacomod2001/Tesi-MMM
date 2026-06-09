"""
Pipeline end-to-end (cap. 4-6):
  1. genera il dataset sintetico
  2. stima il modello MMM
  3. valida il parameter recovery (stima vs ground truth)
  3b. valida le curve di risposta a regime (metrica decisionale)
  4. ottimizza l'allocazione del budget

Esecuzione:  python run_pipeline.py
"""
import json
import os

import numpy as np
import pandas as pd

import config
import data_generator
import model
import allocator
from transforms import steady_state_response

HERE = os.path.dirname(os.path.abspath(__file__))


def step(title):
    print(f"\n{'=' * 64}\n{title}\n{'=' * 64}")


def main():
    step("1. GENERAZIONE DATASET SINTETICO")
    data_generator.main()

    step("2. FIT DEL MODELLO MMM")
    model.main()

    step("3. PARAMETER RECOVERY (stima vs vero)")
    with open(os.path.join(HERE, config.FIT_JSON)) as f:
        fitted = json.load(f)["channels"]
    rows = []
    for ch in config.CHANNELS:
        t, e = config.TRUE_PARAMS[ch], fitted[ch]
        for par in ("beta", "lam", "K", "s"):
            rows.append({"canale": ch, "parametro": par,
                         "vero": t[par], "stimato": round(e[par], 3),
                         "errore_rel": round((e[par] - t[par]) / t[par], 3)})
    rec = pd.DataFrame(rows)
    print(rec.to_string(index=False))
    rec.to_csv(os.path.join(HERE, "output", "parameter_recovery.csv"), index=False)

    # Validazione sulle curve di risposta a regime: e' la metrica decisionale
    # rilevante per l'allocator (i singoli parametri possono compensarsi,
    # ma cio' che conta e' la curva spesa -> candidature nel range osservato).
    step("3b. CURVE RECOVERY (risposta a regime, vero vs stimato)")
    df = pd.read_csv(os.path.join(HERE, config.DATA_CSV))
    print(f"{'canale':<10}{'MAE% sulla curva (0.5x-1.5x spesa media)':>45}")
    for ch in config.CHANNELS:
        m = df[f"spend_{ch}"].mean()
        grid = np.linspace(0.5 * m, 1.5 * m, 21)
        true_c = np.array([steady_state_response(x, **config.TRUE_PARAMS[ch]) for x in grid])
        est_c = np.array([steady_state_response(x, **fitted[ch]) for x in grid])
        mae_pct = float(np.mean(np.abs(est_c - true_c) / true_c))
        print(f"{ch:<10}{mae_pct:>44.2%}")

    step("4. OTTIMIZZAZIONE DEL BUDGET")
    allocator.main()


if __name__ == "__main__":
    main()
