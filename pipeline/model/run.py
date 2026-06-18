"""
Entry point del modello:  python -m pipeline.model.run [opzioni]

Fit completo (consigliato su GPU / Colab Pro, ~20-40 min):
    python -m pipeline.model.run
Smoke test di pipeline (CPU, pochi draw — NON usare le stime):
    python -m pipeline.model.run --smoke
"""
from __future__ import annotations

import argparse
import os
import pickle

from .. import config
from . import meridian_adapter as MA


def main() -> None:
    ap = argparse.ArgumentParser(description="Fit MMM Meridian")
    ap.add_argument("--canon", default=config.CANON_DIR)
    ap.add_argument("--chains", type=int, default=4)
    ap.add_argument("--adapt", type=int, default=500)
    ap.add_argument("--burnin", type=int, default=500)
    ap.add_argument("--keep", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--roi-sigma", type=float, default=0.7)
    ap.add_argument("--roi-discount", type=float, default=1.3,
                    help="sconto di attribuzione sul prior ROAS di piattaforma")
    ap.add_argument("--knots-per-quarter", type=int, default=3,
                    help="flessibilita' della baseline: nodi temporali per trimestre")
    ap.add_argument("--smoke", action="store_true",
                    help="fit minuscolo di verifica meccanica")
    args = ap.parse_args()
    if args.smoke:
        args.chains, args.adapt, args.burnin, args.keep = 1, 50, 50, 50

    facts = MA.load_facts(args.canon)
    df, channels = MA.build_frame(facts)
    roas = MA.platform_roas(facts)
    print("Canali:", channels)
    print("ROAS di piattaforma (prior):",
          {k: round(v, 2) for k, v in roas.items()})
    print(f"Sconto attribuzione prior: /{args.roi_discount} | "
          f"nodi baseline per trimestre: {args.knots_per_quarter}")

    mmm = MA.build_meridian(df, channels, roas_prior=roas,
                            roi_prior_sigma=args.roi_sigma,
                            roi_prior_discount=args.roi_discount,
                            knots_per_quarter=args.knots_per_quarter)
    MA.fit(mmm, n_chains=args.chains, n_adapt=args.adapt,
           n_burnin=args.burnin, n_keep=args.keep, seed=args.seed)

    summary = MA.summarize(mmm, channels)
    path = MA.save_summary(summary)
    print("Riepilogo posterior:", path)
    for ch, e in summary["channels"].items():
        r = e["roi"]
        print(f"  ROI {ch:<10} {r['q50']:.2f}  [{r['q05']:.2f}, {r['q95']:.2f}]")
    print("max R-hat:", summary.get("diagnostics"))

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(config.OUTPUT_DIR, "meridian_model.pkl"), "wb") as f:
        pickle.dump(mmm, f)
    print("Modello serializzato per l'allocator: output/meridian_model.pkl")


if __name__ == "__main__":
    main()
