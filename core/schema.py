"""
Layer dati agnostico: nessun nome di canale, campagna o colonna hardcodato.

Dato un CSV qualsiasi, riconosce automaticamente:
- la colonna temporale (date in qualunque formato comune)
- le colonne di SPESA (le leve): per nome (spend/spesa/cost/budget/adv) o,
  in mancanza, per euristica statistica
- la colonna TARGET (kpi): per nome (application/candidature/conversion/
  lead/sales/target) o, in mancanza, la serie numerica non-spesa con
  maggiore correlazione con la spesa totale
- le colonne di CONTROLLO: tutte le altre numeriche

Dallo storico deriva inoltre i vincoli di default per l'ottimizzatore
(min = 25% del minimo storico attivo, max = 2x il massimo storico),
cosi' che l'app non richieda alcuna configurazione manuale.
"""
import re

import numpy as np
import pandas as pd

SPEND_PAT = re.compile(r"spend|spesa|cost|costo|budget|invest|adv", re.I)
TARGET_PAT = re.compile(r"application|candidat|conversion|conversioni|lead|"
                        r"sales|vendite|target|kpi|signup|iscrizioni", re.I)
DATE_PAT = re.compile(r"date|data|week|settimana|giorno|day|periodo|month|mese", re.I)


def _parse_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", dayfirst=True,
                          format="mixed")


def detect(df: pd.DataFrame) -> dict:
    """Classifica le colonne. Ritorna {date, spend, target, controls, channels}."""
    df = df.copy()

    # --- colonna temporale ---------------------------------------------------
    date_col, best = None, 0.0
    for col in df.columns:
        score = _parse_dates(df[col]).notna().mean()
        if DATE_PAT.search(str(col)):
            score += 0.3
        if score > best and score > 0.7:
            date_col, best = col, score

    numeric = [c for c in df.columns if c != date_col
               and pd.to_numeric(df[c], errors="coerce").notna().mean() > 0.8]

    # --- colonne di spesa ------------------------------------------------------
    spend_cols = [c for c in numeric if SPEND_PAT.search(str(c))]
    if not spend_cols:
        # euristica: gruppi di colonne con scala simile e molti valori distinti
        cand = [c for c in numeric if not TARGET_PAT.search(str(c))]
        med = {c: float(pd.to_numeric(df[c], errors="coerce").median()) for c in cand}
        if med:
            ref = float(np.median(list(med.values())))
            spend_cols = [c for c, v in med.items() if 0.1 * ref <= v <= 10 * ref][: max(2, len(cand) - 2)]

    # --- target -----------------------------------------------------------------
    target_candidates = [c for c in numeric if c not in spend_cols]
    target = next((c for c in target_candidates if TARGET_PAT.search(str(c))), None)
    if target is None and target_candidates and spend_cols:
        tot = sum(pd.to_numeric(df[c], errors="coerce").fillna(0) for c in spend_cols)
        corr = {c: abs(pd.to_numeric(df[c], errors="coerce").corr(tot))
                for c in target_candidates}
        target = max(corr, key=corr.get)

    controls = [c for c in target_candidates
                if c != target and not str(c).endswith("_true")]

    def clean(name: str) -> str:
        # rimuove solo i token interi che indicano "spesa", non le sottostringhe
        tokens = re.split(r"[\W_]+", str(name))
        kept = [t for t in tokens if t and not re.fullmatch(
            r"(?i)(spend|spesa|cost[oi]?|costs|budget|investiment[oi]|invest|adv)", t)]
        return "_".join(kept) or str(name)

    return {
        "date": date_col,
        "spend": spend_cols,
        "target": target,
        "controls": controls,
        "channels": {c: clean(c) for c in spend_cols},  # colonna -> etichetta
    }


def standardize(df: pd.DataFrame, schema: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Normalizza il dataframe nel formato interno della pipeline:
    week, spend_<canale>, applications, ctrl_<nome>. Tutto derivato, nulla
    hardcodato."""
    schema = schema or detect(df)
    if not schema["spend"] or schema["target"] is None:
        raise ValueError(
            "Struttura non riconosciuta: servono almeno una colonna di spesa "
            "e una colonna risultato (es. candidature). "
            f"Rilevato: spesa={schema['spend']}, target={schema['target']}")
    out = pd.DataFrame()
    out["week"] = (_parse_dates(df[schema["date"]])
                   if schema["date"] else pd.RangeIndex(len(df)))
    channels = []
    for col, label in schema["channels"].items():
        out[f"spend_{label}"] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        channels.append(label)
    out["applications"] = pd.to_numeric(df[schema["target"]], errors="coerce")
    for c in schema["controls"]:
        name = re.sub(r"\W+", "_", str(c)).strip("_").lower()
        out[f"ctrl_{name}"] = pd.to_numeric(df[c], errors="coerce")
    out = out.dropna(subset=["applications"]).reset_index(drop=True)
    schema["channels_clean"] = channels
    return out, schema


def default_constraints(df_std: pd.DataFrame, channels: list[str]) -> dict:
    """Vincoli di default per l'ottimizzatore, derivati dallo storico:
    minimo = 25% della spesa minima attiva, massimo = 2x il massimo storico."""
    cons = {}
    for ch in channels:
        s = df_std[f"spend_{ch}"]
        active = s[s > 0.05 * s.mean()] if s.mean() > 0 else s
        cons[ch] = {
            "min": round(0.25 * float(active.min())) if len(active) else 0.0,
            "max": round(2.0 * float(s.max())),
            "mean": float(s.mean()),
        }
    return cons
