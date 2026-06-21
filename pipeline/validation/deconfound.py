"""
Esperimento di deconfondimento del search (google).

Aggiunge un controllo "candidature dirette/organiche" — una misura
RUMOROSA della domanda organica vera (baseline + effetto domanda, SENZA
la parte media) — e confronta il parameter recovery SENZA e CON questo
controllo, sullo stesso seed.

Scopo: mostrare in modo principiato (non tarando sulla verita') che dare
al modello un buon segnale di domanda organica — es. il traffico diretto
che Randstad gia' traccia — riduce la sovra-attribuzione di google.

Serve GPU: fa 2 fit per seed (senza e con il controllo).

Esecuzione:  python -m pipeline.validation.deconfound --seeds 42
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from .. import config
from ..generator import run as gen_run
from ..ingestion import build as ing_build
from ..model import meridian_adapter as MA
from . import recovery as rec

FIT = dict(chains=4, adapt=500, burnin=500, keep=1000,
           roi_sigma=0.7, roi_discount=1.3, knots=3)


def _ingest_auto() -> None:
    proposed, tables = ing_build.propose_plan(config.RAW_DIR)
    for p in proposed:
        p.confirmed = True
    ing_build.ingest(config.RAW_DIR, plan=proposed,
                     interactive=False, tables=tables)


def _direct_series(panel: dict, seed: int) -> pd.DataFrame:
    """Serie 'candidature dirette': osservazione rumorosa della domanda
    organica vera (baseline + effetto domanda), senza la parte media.
    Proxy realistico — imperfetto — del traffico diretto/organico."""
    organic = panel["internals"]["organic"]            # (settimane, regioni)
    da = pd.DataFrame(organic, index=pd.to_datetime(panel["weeks"]),
                      columns=config.REGION_LIST)
    da = da.stack().rename("direct_apps").reset_index()
    da.columns = ["week", "region", "direct_apps"]
    rng = np.random.default_rng(seed + 999)
    da["direct_apps"] = (da["direct_apps"]
                         * rng.lognormal(0.0, 0.20, len(da))).round(0)
    return da


def _fit_recovery(df, channels, facts, *, extra_controls, seed) -> pd.DataFrame:
    roas = MA.platform_roas(facts)
    mmm = MA.build_meridian(df, channels, roas_prior=roas,
                            roi_prior_sigma=FIT["roi_sigma"],
                            roi_prior_discount=FIT["roi_discount"],
                            knots_per_quarter=FIT["knots"],
                            extra_controls=extra_controls)
    MA.fit(mmm, n_chains=FIT["chains"], n_adapt=FIT["adapt"],
           n_burnin=FIT["burnin"], n_keep=FIT["keep"], seed=seed)
    summary = MA.summarize(mmm, channels)
    MA.save_summary(summary)
    fit, truth = rec.load()
    media = pd.read_csv(os.path.join(config.CANON_DIR, "media.csv"),
                        parse_dates=["week"])
    hist = (media.groupby("channel")["spend"].sum()
            / media["week"].nunique()).to_dict()
    return rec.roi_recovery(fit, truth)


def run_seed(seed: int) -> pd.DataFrame:
    panel = gen_run.main(seed=seed)        # scrive i file + ritorna il panel
    _ingest_auto()
    facts = MA.load_facts()
    df, channels = MA.build_frame(facts)

    print(f"\n--- seed {seed}: fit SENZA controllo diretto ---")
    base = _fit_recovery(df, channels, facts, extra_controls=(), seed=seed)

    print(f"\n--- seed {seed}: fit CON controllo diretto ---")
    df2 = df.merge(_direct_series(panel, seed), on=["week", "region"], how="left")
    df2["direct_apps"] = df2["direct_apps"].ffill().bfill()
    withd = _fit_recovery(df2, channels, facts,
                          extra_controls=("direct_apps",), seed=seed)

    out = base[["channel", "roi_true", "roi_q50", "rel_error", "covered_90"]].rename(
        columns={"roi_q50": "roi_senza", "rel_error": "err_senza",
                 "covered_90": "cop_senza"})
    out = out.merge(
        withd[["channel", "roi_q50", "rel_error", "covered_90"]].rename(
            columns={"roi_q50": "roi_con", "rel_error": "err_con",
                     "covered_90": "cop_con"}), on="channel")
    out["seed"] = seed
    return out


CH_ORDER = ["google", "indeed", "linkedin", "meta"]   # google in cima


def _comparison(data: pd.DataFrame) -> pd.DataFrame:
    """Tabella confronto per canale (media sui seed): prima vs dopo,
    in valori assoluti e percentuali."""
    a = data.groupby("channel").agg(
        ROI_vero=("roi_true", "mean"), ROI_prima=("roi_senza", "mean"),
        ROI_dopo=("roi_con", "mean"), err_prima=("err_senza", "mean"),
        err_dopo=("err_con", "mean"), cop_prima=("cop_senza", "mean"),
        cop_dopo=("cop_con", "mean"))
    a = a.reindex([c for c in CH_ORDER if c in a.index])
    return pd.DataFrame({
        "canale": a.index,
        "ROI_vero": a["ROI_vero"].round(2).values,
        "ROI_prima": a["ROI_prima"].round(2).values,
        "ROI_dopo": a["ROI_dopo"].round(2).values,
        "Var_assoluta": (a["ROI_dopo"] - a["ROI_prima"]).round(2).values,
        "Var_%": ((a["ROI_dopo"] - a["ROI_prima"]) / a["ROI_prima"] * 100).round(0).values,
        "Errore_prima_%": (a["err_prima"] * 100).round(0).values,
        "Errore_dopo_%": (a["err_dopo"] * 100).round(0).values,
        "Miglioramento_pp": ((a["err_prima"].abs() - a["err_dopo"].abs()) * 100).round(0).values,
        "Copertura_prima_%": (a["cop_prima"] * 100).round(0).values,
        "Copertura_dopo_%": (a["cop_dopo"] * 100).round(0).values,
    }).reset_index(drop=True)


def _charts(comp: pd.DataFrame, outdir: str) -> list[str]:
    """Due grafici PNG: ROI (vero/prima/dopo) e |errore| prima vs dopo."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:                          # pragma: no cover
        print("matplotlib non disponibile, salto i grafici:", exc)
        return []
    chans = comp["canale"].tolist()
    x = np.arange(len(chans))
    paths = []

    fig, ax = plt.subplots(figsize=(8, 4.5))
    w = 0.27
    ax.bar(x - w, comp["ROI_vero"], w, label="vero", color="#4C9F70")
    ax.bar(x, comp["ROI_prima"], w, label="prima (senza)", color="#E07A5F")
    ax.bar(x + w, comp["ROI_dopo"], w, label="dopo (con diretto)", color="#3D5A80")
    ax.axhline(1.0, ls="--", c="grey", lw=1)
    ax.set_xticks(x); ax.set_xticklabels(chans); ax.set_ylabel("ROI")
    ax.legend(); ax.set_title("ROI stimato: vero vs prima vs dopo il controllo diretto")
    p = os.path.join(outdir, "deconfound_roi.png")
    fig.tight_layout(); fig.savefig(p, dpi=130); plt.close(fig); paths.append(p)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    w = 0.35
    ax.bar(x - w / 2, comp["Errore_prima_%"].abs(), w, label="prima", color="#E07A5F")
    ax.bar(x + w / 2, comp["Errore_dopo_%"].abs(), w, label="dopo", color="#3D5A80")
    ax.set_xticks(x); ax.set_xticklabels(chans); ax.set_ylabel("|errore| sul ROI (%)")
    ax.legend(); ax.set_title("Errore assoluto sul ROI: prima vs dopo")
    p = os.path.join(outdir, "deconfound_errore.png")
    fig.tight_layout(); fig.savefig(p, dpi=130); plt.close(fig); paths.append(p)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description="Esperimento controllo diretto")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    args = ap.parse_args()

    data = pd.concat([run_seed(s) for s in args.seeds], ignore_index=True)
    comp = _comparison(data)

    print(f"\n{'=' * 12} CONFRONTO prima/dopo (controllo 'candidature dirette') {'=' * 12}")
    print(comp.to_string(index=False))
    g = comp[comp["canale"] == "google"]
    if len(g):
        r = g.iloc[0]
        print(f"\nGOOGLE: ROI {r['ROI_prima']} -> {r['ROI_dopo']} (vero {r['ROI_vero']}) | "
              f"errore {r['Errore_prima_%']:+.0f}% -> {r['Errore_dopo_%']:+.0f}% | "
              f"copertura {r['Copertura_prima_%']:.0f}% -> {r['Copertura_dopo_%']:.0f}%")

    outdir = config.OUTPUT_DIR
    os.makedirs(outdir, exist_ok=True)
    comp.to_csv(os.path.join(outdir, "deconfound_confronto.csv"), index=False)
    data.to_csv(os.path.join(outdir, "deconfound_dettaglio_seed.csv"), index=False)
    try:
        from results_xlsx import write_sheet
        write_sheet("Deconfound", comp, {
            "ROI_vero": "0.00", "ROI_prima": "0.00", "ROI_dopo": "0.00",
            "Var_assoluta": "0.00", "Var_%": '0"%"',
            "Errore_prima_%": '0"%"', "Errore_dopo_%": '0"%"',
            "Miglioramento_pp": '0" pp"',
            "Copertura_prima_%": '0"%"', "Copertura_dopo_%": '0"%"'})
    except Exception as exc:                          # pragma: no cover
        print("Excel saltato:", exc)
    pngs = _charts(comp, outdir)

    print("\nFile prodotti (in pipeline/data/output):")
    print("  - deconfound_confronto.csv  (tabella prima/dopo: assoluti + %)")
    print("  - risultati.xlsx  (foglio 'Deconfound')")
    for p in pngs:
        print(f"  - {os.path.basename(p)}  (grafico)")


if __name__ == "__main__":
    main()
