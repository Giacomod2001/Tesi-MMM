"""
Robustezza del parameter recovery su piu' seed.

Per ogni seed esegue l'intera catena su dati sintetici nuovi:
generazione (verita' nota) -> ingestion -> fit Meridian -> recovery.
Aggrega copertura 90%, errore ROI mediano e medie per canale, cosi' si
mostra che il metodo funziona IN GENERALE e non per un caso fortunato.

Serve GPU (fa N fit Meridian, ~30-40 min ciascuno).

Esecuzione:
    python -m pipeline.validation.multiseed --seeds 42 7 123
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from .. import config
from ..generator import run as gen_run
from ..ingestion import build as ing_build
from ..model import meridian_adapter as MA
from . import recovery as rec


def _ingest_auto() -> None:
    """Ingestion non interattiva: propone la mappatura e la auto-conferma
    (sui dati sintetici puliti la proposta e' corretta; vedi recovery)."""
    proposed, tables = ing_build.propose_plan(config.RAW_DIR)
    for p in proposed:
        p.confirmed = True
    ing_build.ingest(config.RAW_DIR, plan=proposed,
                     interactive=False, tables=tables)


def run_one(seed: int, *, chains: int, adapt: int, burnin: int, keep: int,
            roi_sigma: float, roi_discount: float, knots: int) -> pd.DataFrame:
    """gen -> ingestion -> fit -> recovery per un singolo seed.
    Ritorna il DataFrame ROI con anche curve_mae_pct e max_rhat."""
    gen_run.main(seed=seed)            # dati sintetici + ground_truth.json del seed
    _ingest_auto()                     # 4 fatti canonici

    facts = MA.load_facts()
    df, channels = MA.build_frame(facts)
    roas = MA.platform_roas(facts)
    mmm = MA.build_meridian(df, channels, roas_prior=roas,
                            roi_prior_sigma=roi_sigma,
                            roi_prior_discount=roi_discount,
                            knots_per_quarter=knots)
    MA.fit(mmm, n_chains=chains, n_adapt=adapt, n_burnin=burnin,
           n_keep=keep, seed=seed)
    summary = MA.summarize(mmm, channels)
    MA.save_summary(summary)

    fit, truth = rec.load()
    media = pd.read_csv(os.path.join(config.CANON_DIR, "media.csv"),
                        parse_dates=["week"])
    n_weeks = media["week"].nunique()
    hist = (media.groupby("channel")["spend"].sum() / n_weeks).to_dict()

    roi = rec.roi_recovery(fit, truth).merge(
        rec.curve_recovery(fit, truth, hist), on="channel")
    roi["seed"] = seed
    roi["max_rhat"] = summary.get("diagnostics", {}).get("max_rhat")
    return roi


def main() -> None:
    ap = argparse.ArgumentParser(description="Parameter recovery multi-seed")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 7, 123])
    ap.add_argument("--chains", type=int, default=4)
    ap.add_argument("--adapt", type=int, default=500)
    ap.add_argument("--burnin", type=int, default=500)
    ap.add_argument("--keep", type=int, default=1000)
    ap.add_argument("--roi-sigma", type=float, default=0.7)
    ap.add_argument("--roi-discount", type=float, default=1.3)
    ap.add_argument("--knots-per-quarter", type=int, default=3)
    args = ap.parse_args()

    frames = []
    for s in args.seeds:
        print(f"\n{'#' * 18} SEED {s} {'#' * 18}")
        roi = run_one(s, chains=args.chains, adapt=args.adapt,
                      burnin=args.burnin, keep=args.keep,
                      roi_sigma=args.roi_sigma, roi_discount=args.roi_discount,
                      knots=args.knots_per_quarter)
        frames.append(roi)
        cols = ["channel", "roi_true", "roi_q50", "rel_error",
                "covered_90", "curve_mae_pct"]
        print(roi[cols].round(3).to_string(index=False))
        print(f"copertura 90%: {roi['covered_90'].mean():.0%} | "
              f"errore mediano |.|: {roi['rel_error'].abs().median():.1%} | "
              f"max R-hat: {roi['max_rhat'].iloc[0]:.3f}")

    data = pd.concat(frames, ignore_index=True)

    print(f"\n{'=' * 16} SINTESI MULTI-SEED {'=' * 16}")
    print(f"Seed testati: {args.seeds}")
    print(f"Copertura 90% media (tutti i canali x seed): "
          f"{data['covered_90'].mean():.0%}")
    print(f"Errore ROI mediano: {data['rel_error'].abs().median():.1%}")
    print(f"Canali sotto break-even correttamente identificati: vedi tabella\n")

    g = data.groupby("channel").agg(
        roi_true_mean=("roi_true", "mean"),
        roi_q50_mean=("roi_q50", "mean"),
        rel_error_mean=("rel_error", "mean"),
        copertura=("covered_90", "mean"),
        curve_mae=("curve_mae_pct", "mean"))
    print("Per canale (media sui seed):")
    print(g.round(3).to_string())

    out = os.path.join(config.OUTPUT_DIR, "multiseed_recovery.csv")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    data.to_csv(out, index=False)
    print(f"\nDettaglio per seed salvato in {out}")


if __name__ == "__main__":
    main()
