"""
Stato condiviso dell'app Dash: dati correnti, fit in cache, piano MMM.

Il dataset attivo e' completamente agnostico: viene standardizzato da
core/schema.py (auto-detect di date, spese, target, controlli) sia per
il dataset dimostrativo sia per qualunque CSV caricato dall'utente.
"""
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "mmm")):
    if p not in sys.path:
        sys.path.insert(0, p)

from core import schema as _schema                       # noqa: E402
from core import mta_markov as _mta                      # noqa: E402

DATA_DIR = os.path.join(ROOT, "data")
BAYES_PATH = os.path.join(DATA_DIR, "bayes_dash.json")

_state: dict = {}


def _demo_df() -> pd.DataFrame:
    demo = os.path.join(ROOT, "mmm", "data", "synthetic_weekly.csv")
    if os.path.exists(demo):
        return pd.read_csv(demo)
    import data_generator                                  # genera al volo
    return data_generator.generate()


def load(df_raw: pd.DataFrame | None = None) -> dict:
    """(Ri)carica il dataset attivo e ne deriva schema e vincoli."""
    raw = df_raw if df_raw is not None else _demo_df()
    std, sch = _schema.standardize(raw)
    channels = sch["channels_clean"]
    _state.clear()
    _state.update({
        "df": std, "schema": sch, "channels": channels,
        "constraints": _schema.default_constraints(std, channels),
        "fit": None, "plan": None,
    })
    return _state


def get() -> dict:
    if not _state:
        load()
    return _state


def mta_aggregates(df_paths: pd.DataFrame | None = None) -> dict:
    if df_paths is not None:
        return _mta.to_aggregates(df_paths)
    agg_path = os.path.join(DATA_DIR, "mta_aggregates.json")
    if os.path.exists(agg_path):
        return _mta.load_aggregates(agg_path)
    sample = os.path.join(DATA_DIR, "mta_sample.csv")
    return _mta.to_aggregates(pd.read_csv(sample))


def bayes_results() -> dict | None:
    if os.path.exists(BAYES_PATH):
        with open(BAYES_PATH) as f:
            return json.load(f)
    # fallback: risultati pre-calcolati della pipeline legacy
    legacy = os.path.join(ROOT, "mmm", "output", "bayes_curves.json")
    if os.path.exists(legacy):
        with open(legacy) as f:
            return {"curves": json.load(f), "summary": {}}
    return None
