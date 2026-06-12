"""
Pseudonimizzazione GDPR del fatto individuale.

Principi applicati (minimizzazione, art. 5.1.c GDPR):
- gli identificativi diretti (nome, cognome, codice fiscale) vengono
  sostituiti da uno pseudonimo = SHA-256 con sale segreto, troncato;
  il sale NON viene salvato insieme ai dati;
- l'età diventa fascia quinquennale;
- a valle dell'ingestion il modello vede SOLO aggregati regione x settimana:
  il fatto individuale pseudonimizzato serve unicamente per audit e per
  l'aggregazione stessa.
"""
from __future__ import annotations

import hashlib
import secrets

import pandas as pd

from . import mapping, parsers
from .. import schema

PII_DIRECT = ("pii_name", "pii_surname", "pii_cf")


def pseudonymize(df: pd.DataFrame, smap: "mapping.SourceMap",
                 salt: str | None = None) -> pd.DataFrame:
    """Rimuove i dati personali diretti e restituisce il fatto individuale
    pseudonimizzato (pseudo_id, fascia_eta, regione, settimana, ricavo...)."""
    salt = salt or secrets.token_hex(16)

    parts = []
    for fld in PII_DIRECT + ("pii_id",):
        col = smap.get(fld)
        if col is not None and col in df.columns:
            parts.append(df[col].astype(str))
    if not parts:
        raise ValueError("nessuna colonna identificativa trovata: "
                         "impossibile pseudonimizzare in sicurezza")
    joined = parts[0].str.cat(parts[1:], sep="|") if len(parts) > 1 else parts[0]
    pseudo = joined.map(
        lambda v: hashlib.sha256((salt + v).encode()).hexdigest()[:16])

    out = pd.DataFrame({"pseudo_id": pseudo})
    age_col = smap.get("pii_age")
    if age_col and age_col in df.columns:
        age = parsers.coerce_number(df[age_col])
        out["fascia_eta"] = pd.cut(
            age, bins=[17, 24, 29, 34, 39, 44, 49, 54, 59, 120],
            labels=["18-24", "25-29", "30-34", "35-39", "40-44",
                    "45-49", "50-54", "55-59", "60+"]).astype(str)

    region_col = smap.get("region")
    if region_col and region_col in df.columns:
        out["region"] = mapping.normalize_region(df[region_col])

    date_col = smap.get("pii_date") or smap.get("week")
    if date_col and date_col in df.columns:
        out["week"] = schema.to_week_start(parsers.coerce_date(df[date_col]))

    rev_col = smap.get("revenue")
    if rev_col and rev_col in df.columns:
        out["revenue"] = parsers.coerce_number(df[rev_col])

    touch_col = smap.get("pii_touch")
    if touch_col and touch_col in df.columns:
        out["last_touchpoint"] = df[touch_col].astype(str)
    return out


def aggregate_outcome(individual: pd.DataFrame) -> pd.DataFrame:
    """Fatto individuale pseudonimizzato → fatto canonico outcome
    (conversioni e ricavi per regione x settimana)."""
    g = (individual.dropna(subset=["week"])
         .groupby(["week", "region"], as_index=False)
         .agg(conversions=("pseudo_id", "count"),
              revenue=("revenue", "sum")))
    return g[["week", "region", "conversions", "revenue"]]
