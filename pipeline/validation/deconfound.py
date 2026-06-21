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


def main() -> None:
    ap = argparse.ArgumentParser(description="Esperimento controllo diretto")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    args = ap.parse_args()

    data = pd.concat([run_seed(s) for s in args.seeds], ignore_index=True)

    print(f"\n{'=' * 16} SENZA vs CON controllo 'candidature dirette' {'=' * 16}")
    show = data.assign(err_senza=(data["err_senza"] * 100).round(0),
                       err_con=(data["err_con"] * 100).round(0))
    print(show[["seed", "channel", "roi_true", "roi_senza", "err_senza",
                "roi_con", "err_con", "cop_senza", "cop_con"]]
          .round(2).to_string(index=False))

    g = data[data.channel == "google"]
    print("\nGOOGLE (il canale problematico):")
    print(f"  errore medio   SENZA: {g['err_senza'].mean():+.0%}   "
          f"CON: {g['err_con'].mean():+.0%}")
    print(f"  copertura 90%  SENZA: {g['cop_senza'].mean():.0%}   "
          f"CON: {g['cop_con'].mean():.0%}")
    print(f"\nErrore mediano (tutti i canali)  SENZA: "
          f"{data['err_senza'].abs().median():.1%}   "
          f"CON: {data['err_con'].abs().median():.1%}")

    out = os.path.join(config.OUTPUT_DIR, "deconfound_recovery.csv")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    data.to_csv(out, index=False)
    print(f"\nDettaglio salvato in {out}")


if __name__ == "__main__":
    main()
