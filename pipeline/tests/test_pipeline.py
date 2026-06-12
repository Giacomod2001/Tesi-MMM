"""
Test della pipeline (senza fit MCMC: quello è coperto dallo smoke del
modulo model su macchina con GPU).

Esecuzione:  python -m pytest pipeline/tests -q
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import pytest

from pipeline import config, schema
from pipeline.allocator import campaigns as C2
from pipeline.allocator import quarter as Q
from pipeline.allocator import schedule as SC
from pipeline.generator import individuals, panel, run as gen_run
from pipeline.ingestion import build, mapping, parsers

N_WEEKS_TEST = 26


# ------------------------------------------------------------------ fixtures
@pytest.fixture(scope="module")
def world_small(tmp_path_factory):
    """Mondo sintetico ridotto (26 settimane) generato in una tmp dir."""
    root = str(tmp_path_factory.mktemp("data"))
    p = gen_run.main(seed=7, n_weeks=N_WEEKS_TEST, out_root=root)
    return {"panel": p, "root": root}


@pytest.fixture(scope="module")
def ingested(world_small):
    raw = os.path.join(world_small["root"], "raw")
    out = os.path.join(world_small["root"], "canonical")
    plans, tables = build.propose_plan(raw)
    for pl in plans:
        pl.confirmed = True          # conferma simulata (nei test)
    return build.ingest(raw, plan=plans, interactive=False,
                        out_dir=out, tables=tables)


# ------------------------------------------------------------------ schema
def test_week_grid_lunedi():
    g = schema.week_grid("2024-01-03", 10)
    assert (g.dayofweek == 0).all() and len(g) == 10


def test_validate_segnala_errori():
    df = schema.MEDIA.empty()
    rep = schema.validate(df, schema.MEDIA)
    assert not rep.ok


def test_validate_regione_sconosciuta(world_small):
    media = world_small["panel"]["media"].copy()
    media.loc[0, "region"] = "Padania"
    rep = schema.validate(media, schema.MEDIA)
    assert any("fuori anagrafica" in e for e in rep.errors)


# ------------------------------------------------------------------ parser
def test_coerce_number_formati_misti():
    s = pd.Series(["1.234,56", "5,7", "", None, "12"])
    out = parsers.coerce_number(s)
    assert out.tolist()[:2] == [1234.56, 5.7]
    assert np.isnan(out[2]) and np.isnan(out[3]) and out[4] == 12


def test_coerce_number_migliaia_vere_vs_decimali():
    # colonna di sole migliaia all'italiana
    thous = parsers.coerce_number(pd.Series(["1.234", "178.259"]))
    assert thous.tolist() == [1234.0, 178259.0]
    # colonna con decimali a 3 cifre MISTI ad altri: i punti sono decimali
    dec = parsers.coerce_number(pd.Series(["1.101", "0.9523", "1.2"]))
    assert abs(dec[0] - 1.101) < 1e-9


def test_coerce_date_misti():
    s = pd.Series(["01/01/2024", "2024-01-08", "Jan 15, 2024", "feb 2024"])
    d = parsers.coerce_date(s)
    assert d[0] == pd.Timestamp("2024-01-01")
    assert d[2] == pd.Timestamp("2024-01-15")


# ------------------------------------------------------------------ generator
def test_generator_fatti_canonici_validi(world_small):
    p = world_small["panel"]
    for name in ("media", "outcome", "demand", "seasonality"):
        rep = schema.validate(p[name], schema.FACTS[name])
        assert rep.ok, str(rep)


def test_generator_ground_truth_separata(world_small):
    gt = json.load(open(os.path.join(world_small["root"],
                                     "ground_truth.json")))
    assert "roi_true" in str(gt)
    # la ground truth non deve mai apparire nei fatti canonici
    media_cols = set(world_small["panel"]["media"].columns)
    assert not any("true" in c for c in media_cols)


def test_individuals_coerenti(world_small):
    p = world_small["panel"]
    ind = individuals.generate(p, seed=7)
    assert abs(len(ind) - p["outcome"]["conversions"].sum()) < 1
    assert set(ind["regione_residenza"]) <= set(config.REGION_LIST)


# ------------------------------------------------------------------ ingestion
def test_ingestion_validazione_ok(ingested):
    assert all(r.ok for r in ingested["reports"].values()), \
        "\n".join(str(r) for r in ingested["reports"].values())


def test_ingestion_spesa_canale_esatta(ingested, world_small):
    ing = ingested["facts"]["media"].groupby("channel")["spend"].sum()
    tru = world_small["panel"]["media"].groupby("channel")["spend"].sum()
    assert np.allclose(ing.sort_index(), tru.sort_index(), rtol=1e-3)


def test_ingestion_outcome_esatto(ingested, world_small):
    ing = ingested["facts"]["outcome"]["conversions"].sum()
    tru = world_small["panel"]["outcome"]["conversions"].sum()
    assert abs(ing - tru) < 1


def test_gdpr_nessuna_pii_nei_fatti(ingested):
    for name, df in ingested["facts"].items():
        cols = " ".join(df.columns).lower()
        for token in ("nome", "cognome", "fiscale", "codice"):
            assert token not in cols, f"PII '{token}' in {name}"


def test_conferma_umana_non_aggirabile(world_small):
    raw = os.path.join(world_small["root"], "raw")
    plans, tables = build.propose_plan(raw)   # nessuno confermato
    with pytest.raises(ValueError, match="conferma"):
        build.ingest(raw, plan=plans, interactive=False, tables=tables,
                     out_dir=os.path.join(world_small["root"], "x"))


# ------------------------------------------------------------------ allocator
@pytest.fixture(scope="module")
def mock_fit(world_small):
    gt = json.load(open(os.path.join(world_small["root"],
                                     "ground_truth.json")))
    s = {"channels": {}}
    for ch, p in gt["channels"].items():
        roi = p["roi_true"]
        s["channels"][ch] = {
            "roi": {"q05": roi * .7, "q50": roi, "q95": roi * 1.3},
            "adstock_lam": {"q05": .05, "q50": p["adstock_lam"], "q95": .9},
            "hill_ec": {"q05": .8, "q50": 1.2, "q95": 1.8},
            "hill_slope": {"q05": .8, "q50": p["hill_slope"], "q95": 2.2},
        }
    return s


def test_stage1_budget_e_vincoli(mock_fit, ingested):
    media = ingested["facts"]["media"]
    n = media["week"].nunique()
    hist = (media.groupby("channel")["spend"].sum() / n).to_dict()
    cons = Q.Constraints(total_budget=400_000,
                         min_spend={"linkedin": 60_000},
                         max_spend={"meta": 120_000})
    t = Q.optimize_from_summary(mock_fit, hist, cons)
    assert abs(t["budget_quarter"].sum() - 400_000) < 1
    lk = t.set_index("channel")
    assert lk.loc["linkedin", "budget_quarter"] >= 60_000 - 1
    assert lk.loc["meta", "budget_quarter"] <= 120_000 + 1


def test_stage1_vincoli_incompatibili():
    with pytest.raises(ValueError, match="incompatibili"):
        Q.Constraints(total_budget=100,
                      min_spend={"a": 80, "b": 50}).bounds(["a", "b"])


def test_spaccato_settimanale_conserva_budget(mock_fit, ingested):
    media = ingested["facts"]["media"]
    n = media["week"].nunique()
    hist = (media.groupby("channel")["spend"].sum() / n).to_dict()
    cons = Q.Constraints(total_budget=400_000)
    t = Q.optimize_from_summary(mock_fit, hist, cons)
    plan = SC.build_schedule(t, mock_fit, ingested["facts"]["seasonality"],
                             "2026-01-05")
    per_ch = plan.groupby("channel")["spend"].sum()
    assert np.allclose(per_ch.sort_index(),
                       t.set_index("channel")["budget_quarter"].sort_index(),
                       rtol=1e-6)
    assert plan["week"].nunique() == config.QUARTER_WEEKS


def test_stage2_riscala_e_conserva(mock_fit, ingested):
    media = ingested["facts"]["media"]
    out = ingested["facts"]["outcome"]
    rev = out["revenue"].sum() / out["conversions"].sum()
    roas = C2.campaign_roas(media, rev)
    roi = {ch: e["roi"]["q50"] for ch, e in mock_fit["channels"].items()}
    budget = {ch: 100_000.0 for ch in roi}
    t = C2.allocate_campaigns(budget, roas, roi)
    per_ch = t.groupby("channel")["budget_proposed"].sum()
    assert np.allclose(per_ch, 100_000.0)
    shares = t.groupby("channel")["share_proposed"].sum()
    assert np.allclose(shares, 1.0)
    # il fattore k corregge il livello: ROI mmm / ROAS piattaforma
    g = t[t["channel"] == "meta"].iloc[0]
    assert g["k_channel"] < 1     # meta sovra-attribuisce nel mondo sintetico
