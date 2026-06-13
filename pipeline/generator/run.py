"""
Entry point del generatore:  python -m pipeline.generator.run

Produce:
  pipeline/data/raw/             export "sporchi" stile piattaforme
  pipeline/data/canonical_true/  fatti canonici VERI (riferimento per
                                 validare l'ingestion, non per il modello)
  pipeline/data/ground_truth.json  parametri e grandezze nascoste
                                 (il modello non lo legge MAI)
"""
from __future__ import annotations

import json
import os

import numpy as np

from .. import config
from . import exporters, individuals, panel, world


def build_ground_truth(p: dict) -> dict:
    h = p["hidden"]
    return {
        "seed": world.SEED,
        "n_weeks": world.N_WEEKS,
        "start_week": world.START_WEEK,
        "channels": {
            ch: {"beta": prm["beta"], "adstock_lam": prm["lam"],
                 "hill_K_pc": prm["K_pc"], "hill_slope": prm["slope"],
                 "misattribution": prm["misattr"],
                 "roi_true": h["roi_true"][ch],
                 "incremental_conversions": h["incremental_conversions"][ch],
                 "spend_total": h["spend_total"][ch]}
            for ch, prm in world.CHANNELS.items()},
        "baseline": world.BASELINE,
        "revenue_per_conversion": world.REVENUE_PER_CONVERSION,
        "demand_coefficients": {k: v["coef_true"]
                                for k, v in world.DEMAND.items()},
        "noise_sd_pc": world.NOISE_SD_PC,
        "region_multipliers": h["region_multipliers"],
        "seasonal_index_by_week": h["seasonal_index_by_week"],
        "campaign_true_split": h["campaign_true_split"],
        "campaigns": {cp: {k: c[k] for k in
                           ("channel", "share", "geo", "quality")}
                      for cp, c in world.CAMPAIGNS.items()},
    }


def main(seed: int = world.SEED, n_weeks: int = world.N_WEEKS,
         out_root: str | None = None) -> dict:
    data_dir = out_root or config.DATA_DIR
    raw_dir = os.path.join(data_dir, "raw")
    true_dir = os.path.join(data_dir, "canonical_true")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(true_dir, exist_ok=True)

    print(f"Generazione mondo sintetico (seed={seed}, {n_weeks} settimane)...")
    p = panel.generate(seed=seed, n_weeks=n_weeks)

    print("Livello individuale (~850k candidature)...")
    ind = individuals.generate(p, seed=seed)
    print(f"  {len(ind):,} individui")

    print("Fatti canonici veri (riferimento ingestion)...")
    for name in ("media", "outcome", "demand", "seasonality", "campaigns"):
        p[name].to_csv(os.path.join(true_dir, f"{name}.csv"), index=False)

    print("Export sporchi stile piattaforme...")
    files = exporters.write_all(p, ind, raw_dir, seed=seed)
    for f in files:
        print(f"  raw/{f}")

    gt_path = os.path.join(data_dir, "ground_truth.json")
    with open(gt_path, "w") as f:
        json.dump(build_ground_truth(p), f, indent=2, ensure_ascii=False)
    print(f"Ground truth: {gt_path}")

    tot_conv = p["outcome"]["conversions"].sum()
    tot_spend = p["media"]["spend"].sum()
    print(f"\nRiepilogo: {tot_conv:,.0f} conversioni totali | "
          f"{tot_spend:,.0f} EUR spesa media totale")
    for ch, v in p["hidden"]["roi_true"].items():
        print(f"  ROI vero {ch:<10}: {v:5.2f}")
    return p


if __name__ == "__main__":
    main()
