"""
Livello individuale: ~850k candidature con dati personali FINTI.

Una riga per conversione del panel (coerenza esatta con l'aggregato):
anagrafica sintetica (nome, codice fiscale verosimile ma invalido),
regione di residenza, data candidatura, ultimo touchpoint, ricavo.

Scopo: testare la pseudonimizzazione GDPR e l'aggregazione dell'ingestion.
L'assunzione dichiarata residenza ≈ luogo di esposizione è incorporata:
la regione dell'individuo è la regione del panel da cui proviene.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import config
from . import world

FIRST = ["Marco", "Giulia", "Luca", "Sara", "Andrea", "Elena", "Francesco",
         "Chiara", "Davide", "Anna", "Simone", "Laura", "Matteo", "Paola",
         "Alessandro", "Martina", "Stefano", "Federica", "Giorgio", "Ilaria"]
LAST = ["Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano",
        "Colombo", "Ricci", "Marino", "Greco", "Bruno", "Gallo", "Conti",
        "De Luca", "Mancini", "Costa", "Giordano", "Rizzo", "Lombardi",
        "Moretti"]
_CONS = list("BCDFGHLMNPRST")
_VOW = list("AEIOU")


def _fake_cf(rng: np.random.Generator, n: int) -> np.ndarray:
    """Codici fiscali dall'aspetto plausibile ma sintatticamente inventati."""
    L = rng.choice(_CONS, (n, 7))
    V = rng.choice(_VOW, (n, 2))
    d = rng.integers(0, 10, (n, 7)).astype(str)
    return np.array([
        f"{L[i,0]}{L[i,1]}{L[i,2]}{L[i,3]}{L[i,4]}{V[i,0]}{d[i,0]}{d[i,1]}"
        f"{L[i,5]}{d[i,2]}{d[i,3]}{V[i,1]}{d[i,4]}{d[i,5]}{d[i,6]}{L[i,6]}"
        for i in range(n)])


def generate(panel: dict, seed: int = world.SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1)
    weeks = panel["weeks"]
    regions = config.REGION_LIST
    conv = panel["internals"]["conv"]            # (n, R) conversioni vere
    camp_conv = panel["internals"]["camp_conv"]  # camp -> (n, R)
    camps = list(camp_conv)
    resp_tot = sum(camp_conv[c] for c in camps)  # proxy del contributo media

    rows_w, rows_r, rows_touch = [], [], []
    for ti in range(conv.shape[0]):
        for j in range(conv.shape[1]):
            k = int(round(conv[ti, j]))
            if k == 0:
                continue
            # ultimo touchpoint: organico per la quota baseline, campagne in
            # proporzione alle conversioni di piattaforma della cella
            p_camp = np.array([camp_conv[c][ti, j] for c in camps], float)
            p_media = min(float(resp_tot[ti, j] / max(conv[ti, j], 1e-9)), 0.95)
            if p_camp.sum() <= 0:
                probs = np.array([1.0] + [0.0] * len(camps))
            else:
                probs = np.concatenate(
                    [[1 - p_media], p_media * p_camp / p_camp.sum()])
            counts = rng.multinomial(k, probs)
            labels = ["organico"] + camps
            for lbl, c in zip(labels, counts):
                if c:
                    rows_w.append(np.full(c, ti))
                    rows_r.append(np.full(c, j))
                    rows_touch.append(np.array([lbl] * c))

    wi = np.concatenate(rows_w)
    ri = np.concatenate(rows_r)
    touch = np.concatenate(rows_touch)
    n = len(wi)

    day_off = rng.integers(0, 7, n)
    dates = pd.DatetimeIndex(weeks)[wi] + pd.to_timedelta(day_off, unit="D")
    rev = rng.gamma(1 / world.REVENUE_PER_CONVERSION["cv"] ** 2,
                    world.REVENUE_PER_CONVERSION["mean"]
                    * world.REVENUE_PER_CONVERSION["cv"] ** 2, n)

    df = pd.DataFrame({
        "id_candidato": np.arange(1, n + 1),
        "nome": rng.choice(FIRST, n),
        "cognome": rng.choice(LAST, n),
        "codice_fiscale": _fake_cf(rng, n),
        "eta": rng.integers(18, 62, n),
        "regione_residenza": np.array(config.REGION_LIST, dtype=object)[ri],
        "data_candidatura": dates.strftime("%d/%m/%Y"),
        "ultimo_touchpoint": touch,
        "ricavo_missione_eur": np.round(rev, 2),
    })
    return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
