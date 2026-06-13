"""
Stress test (cap. validazione): la pipeline regge quando i dati peggiorano?

Scenari (documento di progetto §4.5):
    rumore_x2     rumore osservazionale raddoppiato
    storico_1anno 52 settimane invece di 104
    collineari    piani spesa dei canali quasi paralleli (correlazione
                  forzata: tutti seguono la stessa stagionalità marcata)

Ogni scenario rigenera il mondo sintetico, ricostruisce i fatti canonici
e lascia un dataset pronto per il fit in `pipeline/data/stress/<nome>/`.
Il fit (GPU) e il recovery si lanciano poi con:

    python -m pipeline.model.run --canon pipeline/data/stress/<nome>/canonical_true
    python -m pipeline.validation.recovery   (con i path dello scenario)

Esecuzione:  python -m pipeline.validation.stress [scenario ...]
"""
from __future__ import annotations

import json
import os
import sys
from unittest import mock

from .. import config
from ..generator import panel, run as gen_run, world

SCENARIOS = ("rumore_x2", "storico_1anno", "collineari")


def _apply(scenario: str):
    """Ritorna i context manager di patch dei parametri del mondo."""
    if scenario == "rumore_x2":
        return [mock.patch.object(world, "NOISE_SD_PC",
                                  world.NOISE_SD_PC * 2)]
    if scenario == "storico_1anno":
        return [mock.patch.object(world, "N_WEEKS", 52)]
    if scenario == "collineari":
        # stessa stagionalità marcata per tutti i piani spesa: il generatore
        # usa seasonal_curve nel planning; amplificandola i canali si muovono
        # insieme → collinearità
        orig = world.seasonal_curve

        def amplified(woy):
            s = orig(woy)
            return 1.0 + 2.5 * (s - 1.0)
        return [mock.patch.object(world, "seasonal_curve", amplified)]
    raise ValueError(f"scenario sconosciuto: {scenario}")


def run_scenario(scenario: str) -> str:
    out_root = os.path.join(config.DATA_DIR, "stress", scenario)
    patches = _apply(scenario)
    for p in patches:
        p.start()
    try:
        n = world.N_WEEKS
        gen_run.main(seed=world.SEED, n_weeks=n, out_root=out_root)
    finally:
        for p in patches:
            p.stop()
    with open(os.path.join(out_root, "scenario.json"), "w") as f:
        json.dump({"scenario": scenario}, f)
    return out_root


def main() -> None:
    names = sys.argv[1:] or list(SCENARIOS)
    for s in names:
        print(f"\n=== STRESS: {s} ===")
        path = run_scenario(s)
        print("dataset scenario in:", path)


if __name__ == "__main__":
    main()
