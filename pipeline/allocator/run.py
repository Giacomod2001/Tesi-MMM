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
from results_xlsx import write_sheet, add_images, WORKBOOK, MONEY


def _parse_kv(items: list[str] | None) -> dict[str, float]:
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        out[k.strip()] = float(v)
    return out


def _readable_canali(alloc, summary, hist, rev_per_conv) -> pd.DataFrame:
    """Tabella canale in chiaro: spesa attuale/consigliata, variazione, e
    candidature attese del canale (incrementali) ora vs con la raccomandazione."""
    curves = Q.build_curves(summary, hist)
    rows = []
    for _, r in alloc.iterrows():
        ch = r["channel"]; c = curves[ch]
        def cand(x, c=c):
            rev = c["beta"] * Q._steady_response(x, c["lam"], c["ec"],
                                                 c["slope"], c["scale"])
            return rev / max(rev_per_conv, 1e-9) * Q.WEEKS
        now, reco = cand(r["hist_weekly_spend"]), cand(r["weekly_spend"])
        rows.append({
            "canale": ch,
            "spesa attuale (EUR)": r["hist_weekly_spend"] * Q.WEEKS,
            "spesa consigliata (EUR)": r["budget_quarter"],
            "variazione spesa": r["weekly_spend"]
                                / max(r["hist_weekly_spend"], 1e-9) - 1,
            "candidature ora": now,
            "candidature attese": reco,
            "candidature in piu": reco - now,
        })
    df = pd.DataFrame(rows)
    tot = {"canale": "TOTALE",
           "spesa attuale (EUR)": df["spesa attuale (EUR)"].sum(),
           "spesa consigliata (EUR)": df["spesa consigliata (EUR)"].sum(),
           "variazione spesa": (df["spesa consigliata (EUR)"].sum()
                                / max(df["spesa attuale (EUR)"].sum(), 1e-9) - 1),
           "candidature ora": df["candidature ora"].sum(),
           "candidature attese": df["candidature attese"].sum(),
           "candidature in piu": df["candidature in piu"].sum()}
    return pd.concat([df, pd.DataFrame([tot])], ignore_index=True)


def _readable_campagne(camp, canali) -> pd.DataFrame:
    """Campagne in chiaro: budget consigliato e candidature attese (quota
    proposta x candidature attese del canale)."""
    cand_ch = dict(zip(canali["canale"], canali["candidature attese"]))
    return pd.DataFrame({
        "canale": camp["channel"].values,
        "campagna": camp["campaign"].values,
        "spesa attuale (EUR)": camp["spend"].values,
        "budget consigliato (EUR)": camp["budget_proposed"].values,
        "quota attuale": camp["share_hist"].values,
        "quota consigliata": camp["share_proposed"].values,
        "candidature attese": camp["channel"].map(cand_ch).fillna(0).values
                              * camp["share_proposed"].values,
    })


def _legend() -> pd.DataFrame:
    rows = [
        ("Canali", "spesa attuale (EUR)", "quanto spendi oggi sul canale, sul trimestre"),
        ("Canali", "spesa consigliata (EUR)", "quanto dovresti spendere secondo il modello"),
        ("Canali", "variazione spesa", "di quanto cambia la spesa, in percentuale"),
        ("Canali", "candidature ora", "candidature portate da QUESTO canale con la spesa attuale (sono quelle in piu' rispetto a chi arriva da solo)"),
        ("Canali", "candidature attese", "candidature portate dal canale con la spesa consigliata"),
        ("Canali", "candidature in piu", "candidature aggiuntive grazie alla riallocazione; la riga TOTALE e' il guadagno netto a parita' di budget"),
        ("Campagne", "budget consigliato (EUR)", "quanto spendere su ogni singola campagna"),
        ("Campagne", "quota attuale / consigliata", "peso della campagna dentro il canale, prima e dopo"),
        ("Campagne", "candidature attese", "candidature attese dalla campagna (stima per quota)"),
        ("Settimane / Mesi", "spend", "come si distribuisce nel tempo la spesa consigliata"),
        ("Grafici", "-", "i due grafici: budget per canale e per campagna"),
        ("Recovery / Deconfound", "-", "verifiche di tesi su dati finti (quanto il modello azzecca la verita'); non servono per il budget"),
    ]
    return pd.DataFrame(rows, columns=["foglio", "voce", "cosa significa"])


def _write_excel(canali, campagne, plan, monthly) -> None:
    """Scrive i fogli dell'allocator nel workbook unico, in chiaro + legenda."""
    write_sheet("Legenda", _legend())
    write_sheet("Canali", canali.round(0),
                {"spesa attuale (EUR)": MONEY, "spesa consigliata (EUR)": MONEY,
                 "variazione spesa": "0.0%", "candidature ora": "#,##0",
                 "candidature attese": "#,##0", "candidature in piu": "#,##0"})
    write_sheet("Campagne", campagne.round(2),
                {"spesa attuale (EUR)": MONEY, "budget consigliato (EUR)": MONEY,
                 "quota attuale": "0.0%", "quota consigliata": "0.0%",
                 "candidature attese": "#,##0"})
    write_sheet("Settimane", plan.round(2), {"spend": MONEY})
    write_sheet("Mesi", monthly.round(0), {"spend": MONEY})


def _charts(alloc: pd.DataFrame, camp: pd.DataFrame, outdir: str) -> list[str]:
    """Due grafici PNG: budget per canale (attuale vs consigliato) e budget
    consigliato per campagna (colore per canale)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
        import numpy as np
    except Exception as exc:                          # pragma: no cover
        print("matplotlib non disponibile, salto i grafici:", exc)
        return []
    PALETTE = {"google": "#E07A5F", "indeed": "#4C9F70",
               "linkedin": "#3D5A80", "meta": "#E8B04B"}
    paths = []

    # 1) canale: attuale vs consigliato (budget trimestre)
    a = alloc.sort_values("budget_quarter", ascending=False)
    chans = a["channel"].tolist()
    attuale = (a["hist_weekly_spend"] * Q.WEEKS).to_numpy() / 1000
    consigliato = a["budget_quarter"].to_numpy() / 1000
    x = np.arange(len(chans)); w = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x - w / 2, attuale, w, label="attuale", color="#B0B7C3")
    ax.bar(x + w / 2, consigliato, w, label="consigliato", color="#3D5A80")
    for i, d in enumerate(a["delta_pct"].to_numpy()):
        ax.text(x[i] + w / 2, consigliato[i], f"{d:+.0%}",
                ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(chans)
    ax.set_ylabel("budget trimestre (k€)"); ax.legend()
    ax.set_title("Budget per canale: attuale vs consigliato")
    p = os.path.join(outdir, "alloc_canali.png")
    fig.tight_layout(); fig.savefig(p, dpi=130); plt.close(fig); paths.append(p)

    # 2) campagna: budget consigliato, colore per canale
    c = camp.sort_values("budget_proposed", ascending=True)
    cols = [PALETTE.get(ch, "#888888") for ch in c["channel"]]
    labels = [f"{ch}: {cp}" for ch, cp in zip(c["channel"], c["campaign"])]
    y = np.arange(len(c))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(y, c["budget_proposed"].to_numpy() / 1000, color=cols)
    for i, v in enumerate(c["budget_proposed"].to_numpy()):
        ax.text(v / 1000, i, f" {v/1000:.0f}k", va="center", fontsize=8)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("budget consigliato (k€)")
    ax.set_title("Budget consigliato per campagna")
    used = [k for k in PALETTE if k in set(c["channel"])]
    ax.legend(handles=[Patch(color=PALETTE[k], label=k) for k in used], fontsize=8)
    p = os.path.join(outdir, "alloc_campagne.png")
    fig.tight_layout(); fig.savefig(p, dpi=130); plt.close(fig); paths.append(p)
    return paths


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

    rev_per_conv = float(outcome["revenue"].sum()
                         / max(outcome["conversions"].sum(), 1))
    canali = _readable_canali(alloc, summary, hist, rev_per_conv)
    disp = canali.copy()
    disp["variazione spesa"] = disp["variazione spesa"].map(lambda v: f"{v:+.0%}")
    for col in ("spesa attuale (EUR)", "spesa consigliata (EUR)", "candidature ora",
                "candidature attese", "candidature in piu"):
        disp[col] = disp[col].map(lambda v: f"{v:,.0f}")
    print("\n=== ALLOCAZIONE PER CANALE ===")
    print(disp.to_string(index=False))

    # ---------------- spaccato settimane/mesi
    plan = SC.build_schedule(alloc, summary, seas, args.quarter_start)
    monthly = SC.monthly_rollup(plan)
    print("\n=== SPACCATO MENSILE ===")
    print(monthly.round(0).to_string(index=False))

    # ---------------- stage 2: riparto per campagna
    roas = C2.campaign_roas(media, rev_per_conv)
    roi = {ch: e["roi"]["q50"] for ch, e in summary["channels"].items()}
    budget_ch = dict(zip(alloc["channel"], alloc["budget_quarter"]))
    camp = C2.allocate_campaigns(budget_ch, roas, roi,
                                 max_shift=args.max_shift)
    campagne = _readable_campagne(camp, canali)
    dispc = campagne.copy()
    for col in ("quota attuale", "quota consigliata"):
        dispc[col] = dispc[col].map(lambda v: f"{v:.0%}")
    for col in ("spesa attuale (EUR)", "budget consigliato (EUR)", "candidature attese"):
        dispc[col] = dispc[col].map(lambda v: f"{v:,.0f}")
    print("\n=== RIPARTO PER CAMPAGNA ===")
    print(dispc.to_string(index=False))

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    _write_excel(canali, campagne, plan, monthly)
    print(f"\nFogli Canali/Settimane/Mesi/Campagne aggiornati in {WORKBOOK}")
    pngs = _charts(alloc, camp, config.OUTPUT_DIR)
    if pngs:
        try:
            add_images("Grafici", pngs)
            print("Grafici nel foglio 'Grafici' dell'Excel + PNG:",
                  [os.path.basename(p) for p in pngs])
        except Exception as exc:                      # pragma: no cover
            print("Grafici nell'Excel saltati:", exc)
    print("NB: è una raccomandazione — la validazione finale spetta al "
          "manager (human-in-the-middle).")


if __name__ == "__main__":
    main()
