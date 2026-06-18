"""
Entry point dell'ingestion:  python -m pipeline.ingestion.run [raw_dir]

Interattivo per costruzione: propone la mappatura e chiede conferma
(human-in-the-middle). Per i rilanci batch:

    python -m pipeline.ingestion.run --plan data/canonical/mapping_confirmed.json
"""
from __future__ import annotations

import argparse

from .. import config
from . import build, mapping


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingestion -> fatti canonici")
    ap.add_argument("raw_dir", nargs="?", default=config.RAW_DIR)
    ap.add_argument("--plan", help="mapping_confirmed.json di un run precedente")
    ap.add_argument("--out", default=config.CANON_DIR)
    args = ap.parse_args()

    plan = mapping.load_plan(args.plan) if args.plan else None
    res = build.ingest(args.raw_dir, plan=plan,
                       interactive=plan is None, out_dir=args.out)

    print("\n=== LOG INGESTION ===")
    for line in res["log"]:
        print(" ", line)
    print("\nFatti canonici scritti in", args.out)
    for name, df in res["facts"].items():
        print(f"  {name:<12} {len(df):>8,} righe")
    if any(not r.ok for r in res["reports"].values()):
        raise SystemExit("\nERRORI di validazione: vedi log sopra.")


if __name__ == "__main__":
    main()
