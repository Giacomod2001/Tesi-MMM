"""
Generatore del dataset sintetico MTA: ~800.000 percorsi utente.

Simula il funnel del recruiting digitale a tre stadi:
    OJA (visualizzazione/clic annuncio) -> DJA_Register -> DJA_Application
con dimensioni demografiche (eta', area geografica, categoria lavorativa)
e utility economica (ricavo atteso) per le conversioni complete.

NOTA SUL DESIGN: i nomi di canali e campagne compaiono SOLO qui, come
configurazione del mondo sintetico (GEN_SPEC) — sono dati, non codice.
La pipeline di analisi (core/mta_markov.py) e' completamente agnostica:
scopre stati, canali e campagne dai dati che riceve.

Output:
    data/mta_paths.csv.gz       percorso completo per utente (compresso)
    data/mta_sample.csv         campione 50k per la demo nell'app
    data/mta_aggregates.json    transizioni aggregate (input leggero per Markov)
"""
import gzip
import json
import os

import numpy as np
import pandas as pd

SEED = 7
N_USERS = 800_000
MAX_TOUCH = 8

# ----------------------------------------------------------------- mondo sintetico
# campagna -> (canale, peso_traffico, forza_attrazione, forza_chiusura)
GEN_SPEC = {
    "google:search_jobs":   ("google",   .14, .9, 1.30),
    "google:search_brand":  ("google",   .08, .5, 1.55),
    "google:pmax":          ("google",   .07, 1.1, .80),
    "meta:daba":            ("meta",     .13, 1.5, .65),
    "meta:dpa":             ("meta",     .09, 1.2, .95),
    "meta:lead_gen":        ("meta",     .08, .8, 1.25),
    "meta:job_alerts":      ("meta",     .05, .6, 1.10),
    "linkedin:sponsored":   ("linkedin", .06, 1.0, .70),
    "linkedin:inmail":      ("linkedin", .04, .6, 1.05),
    "linkedin:lead_forms":  ("linkedin", .05, .7, 1.20),
    "indeed:sponsored_jobs":("indeed",   .12, .8, 1.45),
    "indeed:display":       ("indeed",   .04, 1.1, .55),
    "organico:direct":      ("organico", .05, .4, 1.35),
}
AGE = (["18-24", "25-34", "35-44", "45-54", "55+"], [.22, .32, .22, .16, .08])
REGION = (["Nord", "Centro", "Sud e Isole"], [.45, .25, .30])
CATEGORY = (["logistica", "manifatturiero", "gdo_retail", "impiegatizio", "ict"],
            [.28, .24, .20, .18, .10])
# utility media (EUR di ricavo atteso da un inserimento) per categoria
UTILITY = {"logistica": 380, "manifatturiero": 420, "gdo_retail": 300,
           "impiegatizio": 520, "ict": 900}


def generate(n_users: int = N_USERS, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    camps = list(GEN_SPEC)
    w = np.array([GEN_SPEC[c][1] for c in camps]); w = w / w.sum()
    attract = np.array([GEN_SPEC[c][2] for c in camps])
    close = np.array([GEN_SPEC[c][3] for c in camps])

    # demografia
    age = rng.choice(AGE[0], n_users, p=AGE[1])
    region = rng.choice(REGION[0], n_users, p=REGION[1])
    cat = rng.choice(CATEGORY[0], n_users, p=CATEGORY[1])

    # lunghezza percorso ~ 1 + geometrica
    n_touch = np.minimum(1 + rng.geometric(0.45, n_users), MAX_TOUCH)

    # tocchi: primo tocco pesato per attrazione, successivi per peso traffico
    w_first = w * attract; w_first /= w_first.sum()
    touches = np.empty((n_users, MAX_TOUCH), dtype=np.int16)
    touches[:, 0] = rng.choice(len(camps), n_users, p=w_first)
    for j in range(1, MAX_TOUCH):
        touches[:, j] = rng.choice(len(camps), n_users, p=w)

    # probabilita' di avanzamento nel funnel: dipende dalla forza di
    # chiusura dell'ULTIMO tocco e dal numero di tocchi (assist)
    last = touches[np.arange(n_users), n_touch - 1]
    base_reg = 0.10 * close[last] * (1 + 0.08 * (n_touch - 1))
    reg = rng.random(n_users) < np.clip(base_reg, 0, .9)
    base_app = 0.38 * close[last]
    app = reg & (rng.random(n_users) < np.clip(base_app, 0, .9))

    stage = np.where(app, "DJA_Application", np.where(reg, "DJA_Register", "OJA"))
    util_mean = np.vectorize(UTILITY.get)(cat)
    utility = np.where(app, rng.gamma(4, 1, n_users) / 4 * util_mean, 0.0).round(2)

    paths = [">".join(camps[touches[i, j]] for j in range(n_touch[i]))
             for i in range(n_users)]

    return pd.DataFrame({
        "user_id": np.arange(n_users), "path": paths, "stage": stage,
        "utility": utility, "age": age, "region": region, "job_category": cat,
    })


def aggregate_transitions(df: pd.DataFrame) -> dict:
    """Riduce gli 800k percorsi alle statistiche sufficienti per il modello
    di Markov: conteggi di transizione, conversioni e utility per stato."""
    trans: dict = {}
    conv_count: dict = {}
    conv_util: dict = {}
    converted = df["stage"] == "DJA_Application"
    for path, conv, util in zip(df["path"], converted, df["utility"]):
        steps = path.split(">")
        prev = "START"
        for s in steps:
            trans.setdefault(prev, {}).setdefault(s, 0)
            trans[prev][s] += 1
            prev = s
        end = "CONV" if conv else "NULL"
        trans.setdefault(prev, {}).setdefault(end, 0)
        trans[prev][end] += 1
        if conv:
            conv_count[prev] = conv_count.get(prev, 0) + 1
            conv_util[prev] = conv_util.get(prev, 0.0) + float(util)
    return {"transitions": trans,
            "total_conversions": int(converted.sum()),
            "total_utility": float(df.loc[converted, "utility"].sum()),
            "n_paths": len(df)}


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(os.path.join(here, "data"), exist_ok=True)
    df = generate()
    df.to_csv(os.path.join(here, "data", "mta_paths.csv.gz"),
              index=False, compression="gzip")
    df.sample(50_000, random_state=SEED).to_csv(
        os.path.join(here, "data", "mta_sample.csv"), index=False)
    agg = aggregate_transitions(df)
    with open(os.path.join(here, "data", "mta_aggregates.json"), "w") as f:
        json.dump(agg, f)
    conv = (df["stage"] == "DJA_Application").mean()
    print(f"{len(df):,} percorsi | conv. complete: {conv:.2%} | "
          f"utility totale: {df['utility'].sum():,.0f} EUR")


if __name__ == "__main__":
    main()
