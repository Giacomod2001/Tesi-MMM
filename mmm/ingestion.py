"""
Ingestione universale di serie storiche esterne (cap. 4 — preparazione dati).

Obiettivo: leggere file in QUALSIASI formato ragionevole (Excel, CSV, PDF
con tabelle, JSON) contenenti serie storiche — es. richieste di fulfillment
dai clienti, intensita' di ricerca lavoro dei candidati — e restituirle
come DataFrame settimanale pronto per il join con il dataset MMM.

Strategia:
  1. estrazione grezza delle tabelle (per Excel: tutti i fogli;
     per PDF: tutte le tabelle di tutte le pagine via pdfplumber)
  2. rilevamento automatico della colonna temporale (date esplicite,
     mesi italiani/inglesi, formati "2024-01", "gen 2024", anno+mese)
  3. coercizione numerica robusta (separatori migliaia, virgola decimale)
  4. riallineamento alla griglia settimanale W-MON con interpolazione
     temporale (i dati mensili vengono distribuiti sulle settimane)
"""
import os
import re

import numpy as np
import pandas as pd

MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5,
    "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10,
    "novembre": 11, "dicembre": 12,
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7,
    "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
    "jan": 1, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "dec": 12,
}


# ---------------------------------------------------------------- estrazione
def _read_raw_tables(path: str) -> list[pd.DataFrame]:
    ext = os.path.splitext(path)[1].lower()
    tables = []
    if ext in (".xlsx", ".xls", ".xlsm"):
        sheets = pd.read_excel(path, sheet_name=None, header=None)
        tables = list(sheets.values())
    elif ext in (".csv", ".txt", ".tsv"):
        tables = [pd.read_csv(path, sep=None, engine="python", header=None,
                              skip_blank_lines=True)]
    elif ext == ".json":
        tables = [pd.read_json(path)]
        tables[0] = pd.concat(
            [tables[0].columns.to_frame().T, tables[0]], ignore_index=True)
    elif ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                for tab in page.extract_tables():
                    if tab and len(tab) > 1:
                        tables.append(pd.DataFrame(tab))
            if not tables:  # fallback: PDF senza griglia, parsing del testo
                rows = []
                for page in pdf.pages:
                    for line in (page.extract_text() or "").splitlines():
                        toks = re.split(r"\s{2,}|\t", line.strip())
                        if len(toks) < 2:
                            toks = line.strip().split()
                        if len(toks) >= 2:
                            rows.append(toks)
                if len(rows) > 1:
                    ncol = max(len(r) for r in rows)
                    rows = [r + [None] * (ncol - len(r)) for r in rows]
                    tables.append(pd.DataFrame(rows))
    else:
        raise ValueError(f"Formato non supportato: {ext}")
    return [t for t in tables if t is not None and t.shape[0] > 1]


def _promote_header(df: pd.DataFrame) -> pd.DataFrame:
    """Usa la prima riga non vuota come intestazione."""
    df = df.dropna(how="all").reset_index(drop=True)
    header = df.iloc[0].astype(str).str.strip().str.lower()
    out = df.iloc[1:].reset_index(drop=True)
    out.columns = [h if h not in ("nan", "none", "") else f"col{i}"
                   for i, h in enumerate(header)]
    return out


# ------------------------------------------------------------ parsing date
def _parse_date_value(v) -> pd.Timestamp | None:
    if pd.isna(v):
        return None
    if isinstance(v, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(v)
    s = str(v).strip().lower()
    # "gennaio 2024", "gen-24", "settembre '23"
    m = re.match(r"^([a-zà-ù]+)[\s\-_/']*(\d{2,4})$", s)
    if m and m.group(1) in MONTHS:
        yr = int(m.group(2))
        yr += 2000 if yr < 100 else 0
        return pd.Timestamp(yr, MONTHS[m.group(1)], 1)
    # "2024-01", "01/2024"
    m = re.match(r"^(\d{4})[\-/](\d{1,2})$", s)
    if m:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)
    m = re.match(r"^(\d{1,2})[\-/](\d{4})$", s)
    if m:
        return pd.Timestamp(int(m.group(2)), int(m.group(1)), 1)
    try:  # date standard
        d = pd.to_datetime(s, dayfirst=True, errors="coerce")
        return None if pd.isna(d) else d
    except Exception:
        return None


def _detect_date_column(df: pd.DataFrame) -> str | None:
    best, best_score = None, 0.0
    for col in df.columns:
        parsed = df[col].map(_parse_date_value)
        score = parsed.notna().mean()
        if score > 0.7 and parsed.dropna().nunique() > 2 and score > best_score:
            best, best_score = col, score
    return best


def _coerce_numeric(s: pd.Series) -> pd.Series:
    def conv(v):
        if pd.isna(v) or isinstance(v, (int, float, np.number)):
            return v
        x = re.sub(r"[^\d,.\-]", "", str(v))
        if "," in x and "." in x:      # 1.234,56 -> 1234.56
            x = x.replace(".", "").replace(",", ".")
        elif "," in x:                 # 1234,56 -> 1234.56
            x = x.replace(",", ".")
        elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", x):
            x = x.replace(".", "")     # 2.150 -> 2150 (migliaia italiane)
        try:
            return float(x)
        except ValueError:
            return np.nan
    return s.map(conv).astype(float)


# ---------------------------------------------------------------- pipeline
def load(path: str) -> pd.DataFrame:
    """Carica un file qualsiasi e restituisce le serie con indice temporale.

    Ritorna un DataFrame con DatetimeIndex e una colonna numerica per
    ciascuna serie rilevata.
    """
    frames = []
    for raw in _read_raw_tables(path):
        df = _promote_header(raw)
        date_col = _detect_date_column(df)
        if date_col is None:
            continue
        idx = df[date_col].map(_parse_date_value)
        body = df.drop(columns=[date_col])
        num = {}
        for col in body.columns:
            vals = _coerce_numeric(body[col])
            if vals.notna().mean() > 0.6:
                num[str(col)] = vals
        if not num:
            continue
        out = pd.DataFrame(num)
        out.index = pd.DatetimeIndex(idx)
        out = out[out.index.notna()].sort_index()
        frames.append(out)
    if not frames:
        raise ValueError(
            f"Nessuna serie temporale riconosciuta in {os.path.basename(path)}. "
            "Il file deve contenere una colonna data/mese e almeno una colonna numerica.")
    return pd.concat(frames, axis=1)


def to_weekly(series_df: pd.DataFrame, weeks: pd.DatetimeIndex) -> pd.DataFrame:
    """Riallinea le serie alla griglia settimanale del dataset MMM.

    Dati mensili o irregolari vengono interpolati linearmente nel tempo;
    dati gia' settimanali vengono riallineati alla settimana piu' vicina.
    """
    out = {}
    for col in series_df.columns:
        s = series_df[col].dropna()
        if s.empty:
            continue
        # unione della griglia originale e di quella target, interpolazione
        combined = s.reindex(s.index.union(weeks)).interpolate(method="time")
        aligned = combined.reindex(weeks).ffill().bfill()
        out[col] = aligned.to_numpy()
    return pd.DataFrame(out, index=weeks)


def merge_controls(mmm_df: pd.DataFrame, paths: list[str]) -> pd.DataFrame:
    """Carica i file esterni e li aggiunge al dataset MMM come ctrl_*."""
    df = mmm_df.copy()
    weeks = pd.DatetimeIndex(pd.to_datetime(df["week"]))
    for path in paths:
        weekly = to_weekly(load(path), weeks)
        for col in weekly.columns:
            name = re.sub(r"\W+", "_", col.strip().lower()).strip("_")
            df[f"ctrl_{name}"] = weekly[col].to_numpy()
    return df


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        print(f"\n=== {p} ===")
        print(load(p).head(8))
