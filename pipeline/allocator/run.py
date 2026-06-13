"""
Entry point dell'allocator:  python -m pipeline.allocator.run [opzioni]

Esempio (budget 450k EUR sul quarter, LinkedIn mai sotto 50k):

    python -m pipeline.allocator.run --budget 450000 \\
        --min linkedin=50000 --max meta=250000 \\
        --quarter-start 2026-01-05

Usa il riepilogo posterior (output/model_fit.json). Se è disponibile il
modello serializzato (output/meridian_model.pkl) e --use-meridian, lo
stage 1 passa per il BudgetOptimizer nativo.
"""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd

from .. import config
from . import campaigns as C2
from . import quarter as Q
from . import schedule as SC
from results_xlsx import write_sheet, WORKBOOK, MONEY


def _parse_kv(items: list[str] | None) -> dict[str, float]:
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        out[k.strip()] = float(v)
    return out


def _write_excel(alloc, plan, monthly, camp) -> None:
    """Scrive i quattro fogli dell'allocator nel workbook unico
    (Canali / Settimane / Mesi / Campagne), con formato valuta."""
    write_sheet("Canali", alloc.round(2),
                {"budget_quarter": MONEY, "weekly_spend": MONEY,
                 "hist_weekly_spend": MONEY, "expected_weekly_revenue": MONEY,
                 "constraint_min": MONEY, "constraint_max": MONEY,
                 "delta_pct": "0.0%", "marginal_roi": "0.00"})
    write_sheet("Settimane", plan.round(2), {"spend": MONEY})
    write_sheet("Mesi", monthly.round(0), {"spend": MONEY})
    write_sheet("Campagne", camp.round(3),
                {"spend": MONEY, "budget_proposed": MONEY,
                 "share_hist": "0.0%", "share_proposed": "0.0%",
                 "platform_roas": "0.00", "roas_adjusted": "0.00",
                 "k_channel": "0.00"})


def main() -> None:
    ap = argparse.ArgumentParser(description="Budget allocator trimestrale")
    ap.add_argument("--budget", type=float, required=True,
                    help="budget totale del quarter (EUR)")
    ap.add_argument("--min", nargs="*", help="vincoli minimi canale=EUR")
    ap.add_argument("--max", nargs="*", help="vincoli massimi canale=EUR")
    ap.add_argument("--quarter-start", required=True,
                    help="lunedì di inizio quarter (ISO, es. 2026-01-05)")
    ap.add_argument("--canon", default=config.CANON_DIR)
    ap.add_argument("--fit", default=os.path.join(config.OUTPUT_DIR,
                                                  "model_fit.json"))
    ap.add_argument("--use-meridian", action="store_true",
                    help="stage 1 con BudgetOptimizer nativo (richiede "
                         "output/meridian_model.pkl)")
    ap.add_argument("--max-shift", type=float, default=0.5,
                    help="variazione massima quota campagna (stage 2)")
    args = ap.parse_args()

    with open(args.fit) as f:
        summary = json.load(f)
    media = pd.read_csv(os.path.join(args.canon, "media.csv"),
                        parse_dates=["week"])
    outcome = pd.read_csv(os.path.join(args.canon, "outcome.csv"))
    seas = pd.read_csv(os.path.join(args.canon, "seasonality.csv"),
                       parse_dates=["week"])

    cons = Q.Constraints(total_budget=args.budget,
                         min_spend=_parse_kv(args.min),
                         max_spend=_parse_kv(args.max))
    n_weeks = media["week"].nunique()
    hist = (media.groupby("channel")["spend"].sum() / n_weeks).to_dict()

    # ---------------- stage 1
    if args.use_meridian:
        import pickle
        with open(os.path.join(config.OUTPUT_DIR, "meridian_model.pkl"),
                  "rb") as f:
            mmm = pickle.load(f)
        alloc = Q.optimize_with_meridian(mmm, cons)
        alloc["hist_weekly_spend"] = alloc["channel"].map(hist)
    else:
        alloc = Q.optimize_from_summary(summary, hist, cons)
    print("\n=== STAGE 1: allocazione per canale (quarter) ===")
    print(alloc.round(2).to_string(index=False))

    # ---------------- spaccato settimane/mesi
    plan = SC.build_schedule(alloc, summary, seas, args.quarter_start)
    monthly = SC.monthly_rollup(plan)
    print("\n=== SPACCATO MENSILE ===")
    print(monthly.round(0).to_string(index=False))

    # ---------------- stage 2
    rev_per_conv = float(outcome["revenue"].sum()
                         / max(outcome["conversions"].sum(), 1))
    roas = C2.campaign_roas(media, rev_per_conv)
    roi = {ch: e["roi"]["q50"] for ch, e in summary["channels"].items()}
    budget_ch = dict(zip(alloc["channel"], alloc["budget_quarter"]))
    camp = C2.allocate_campaigns(budget_ch, roas, roi,
                                 max_shift=args.max_shift)
    print("\n=== STAGE 2: riparto per campagna ===")
    print(camp.round(3).to_string(index=False))

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    _write_excel(alloc, plan, monthly, camp)
    print(f"\nFogli Canali/Settimane/Mesi/Campagne aggiornati in {WORKBOOK}")
    print("NB: è una raccomandazione — la validazione finale spetta al "
          "manager (human-in-the-middle).")


if __name__ == "__main__":
    main()
