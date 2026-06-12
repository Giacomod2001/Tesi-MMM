"""
Parser robusti per formato: CSV/TSV, Excel, PDF, (gz inclusi).

Restituiscono tabelle GREZZE con intestazione individuata euristicamente
(gli export reali hanno righe di metadati in testa, righe di totale in
coda, encoding con BOM, delimitatori variabili). Nessuna interpretazione
semantica: quella è compito di mapping.py.
"""
from __future__ import annotations

import os
import re

import numpy as np
import pandas as pd

# token che indicano una probabile riga di intestazione
HEADER_HINTS = re.compile(
    r"(?i)settimana|week|data|date|campagna|campaign|regione|region|"
    r"costo|cost|spesa|spent|spend|importo|impression|clic|click|"
    r"conversion|risultati|lead|candidat|ricavo|nome|cognome|codice")

# righe di riepilogo da scartare
TOTAL_ROW = re.compile(r"(?i)^\s*total[ei]?\b")

MONTHS_EN = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"])}


def _read_csv_robust(path: str) -> pd.DataFrame:
    """CSV/TSV con metadati in testa, larghezze di riga variabili, BOM,
    eventuale compressione gzip. Il delimitatore è scelto contando le
    occorrenze nel corpo del file (lo sniffing standard fallisce quando
    la prima riga è una riga di titolo senza separatori)."""
    import csv
    import gzip
    import io

    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", errors="replace") as f:
        head = [f.readline() for _ in range(80)]
        head = [ln for ln in head if ln.strip()]
        if not head:
            return pd.DataFrame()
        delim = max((",", ";", "\t", "|"),
                    key=lambda d: sum(ln.count(d) for ln in head))
        # fast path: file regolare (prima riga già con il delimitatore)
        if head[0].count(delim) > 0:
            try:
                return pd.read_csv(path, sep=delim, header=None, dtype=str,
                                   encoding="utf-8-sig",
                                   skip_blank_lines=True)
            except pd.errors.ParserError:
                pass                      # larghezze variabili: percorso lento
        f.seek(0)
        text = f.read()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delim))
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    return pd.DataFrame(rows, dtype=str).replace("", None)


def read_tables(path: str) -> list[pd.DataFrame]:
    """Legge un file qualsiasi e restituisce le tabelle con header corretto."""
    ext = os.path.splitext(path.replace(".gz", ""))[1].lower()
    raw: list[pd.DataFrame] = []
    if ext in (".csv", ".txt", ".tsv"):
        raw = [_read_csv_robust(path)]
    elif ext in (".xlsx", ".xls", ".xlsm"):
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=str)
        raw = list(sheets.values())
    elif ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                for tab in page.extract_tables():
                    if tab and len(tab) > 1:
                        raw.append(pd.DataFrame(tab, dtype=str))
    elif ext == ".json":
        raw = [pd.read_json(path, dtype=str)]
        raw[0] = pd.concat([raw[0].columns.to_frame().T.astype(str), raw[0]],
                           ignore_index=True)
    else:
        raise ValueError(f"Formato non supportato: {path}")
    return [t for df in raw if (t := _promote_header(df)) is not None]


def _promote_header(df: pd.DataFrame) -> pd.DataFrame | None:
    """Trova la riga di intestazione (la prima con più hit di vocabolario)
    e scarta metadati in testa e righe di totale in coda."""
    df = df.dropna(how="all").reset_index(drop=True)
    if df.empty:
        return None
    best_i, best_hits = 0, -1
    for i in range(min(8, len(df))):
        cells = df.iloc[i].astype(str)
        hits = int(cells.str.contains(HEADER_HINTS).sum())
        filled = int((cells.str.strip() != "").sum() - (cells == "nan").sum())
        score = hits * 10 + filled
        if hits > 0 and score > best_hits:
            best_i, best_hits = i, score
    if best_hits <= 0:
        return None
    header = [str(h).strip() if str(h).strip() not in ("nan", "None", "")
              else f"col{i}" for i, h in enumerate(df.iloc[best_i])]
    out = df.iloc[best_i + 1:].reset_index(drop=True)
    out.columns = header
    first = out.iloc[:, 0].astype(str)
    out = out[~first.str.match(TOTAL_ROW)].reset_index(drop=True)
    return out if len(out) else None


# ----------------------------------------------------------- coercizioni valori
def coerce_number(s: pd.Series) -> pd.Series:
    """Numeri in formato misto italiano/inglese → float (vettoriale).
    '1.234,56'→1234.56, '178.259'→178259, '5,7'→5.7, ''→NaN."""
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float)
    x = (s.astype(str).str.strip()
         .str.replace(r"[^\d,.\-]", "", regex=True)
         .replace({"": None, "-": None, ".": None, ",": None,
                   "nan": None, "None": None}))
    has_dot = x.str.contains(".", regex=False, na=False)
    has_com = x.str.contains(",", na=False)
    both = has_dot & has_com
    x = x.mask(both, x.str.replace(".", "", regex=False)
                      .str.replace(",", ".", regex=False))
    only_c = ~both & has_com
    x = x.mask(only_c, x.str.replace(",", ".", regex=False))
    thous_like = x.str.fullmatch(r"-?\d{1,3}(\.\d{3})+", na=False)
    if not has_com.any():
        # nessuna virgola nell'intera colonna: i punti sono separatori
        # decimali, A MENO CHE tutti i valori puntati abbiano gruppi da 3
        # cifre (vere migliaia all'italiana, es. '178.259').
        dotted = has_dot & x.notna()
        if dotted.any() and not thous_like[dotted].all():
            thous_like &= False
    thous = ~both & ~only_c & thous_like
    x = x.mask(thous, x.str.replace(".", "", regex=False))
    return pd.to_numeric(x, errors="coerce")


def coerce_date(s: pd.Series) -> pd.Series:
    """Date in formato misto -> Timestamp. Percorso vettoriale per i formati
    standard (dd/mm/yyyy, ISO, 'Jan 06, 2024'); fallback riga per riga per
    i formati esotici ('gen 2024', '2024-01')."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return pd.to_datetime(s)
    d = pd.to_datetime(s, dayfirst=True, errors="coerce", format="mixed")
    hard = d.isna() & s.notna()
    if hard.any():
        def conv(v):
            import re as _re
            x = str(v).strip()
            m = _re.match(r"^([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})$", x)
            if m and m.group(1).lower() in MONTHS_EN:
                return pd.Timestamp(int(m.group(3)),
                                    MONTHS_EN[m.group(1).lower()],
                                    int(m.group(2)))
            m = _re.match(r"^(\d{4})[\-/](\d{1,2})$", x)
            if m:
                return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)
            return pd.NaT
        d.loc[hard] = s.loc[hard].map(conv)
    return d
