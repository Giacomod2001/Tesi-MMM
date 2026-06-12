"""
Mappatura semi-automatica sul vocabolario canonico, con conferma umana.

Il sistema PROPONE (riconoscimento per alias multilingua + euristiche),
l'utente CONFERMA o corregge — punto human-in-the-middle del documento di
progetto: nessuna automazione totale silenziosa. La mappatura confermata
viene serializzata in JSON (audit trail) e riusata nei rilanci.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field

import pandas as pd

from .. import config

# ------------------------------------------------------------- vocabolario
# campo canonico -> alias (regex, case-insensitive) negli export reali
FIELD_ALIASES: dict[str, str] = {
    "week":      r"settimana|week|inizio della settimana|start date|data|date|periodo",
    "region":    r"regione|region|localit|geo|area",
    "campaign":  r"campagna|campaign|nome della campagna|campaign name|adset",
    "spend":     r"importo speso|costo|cost\b|spesa|total spent|spend|amount spent",
    "impressions": r"impression|impressioni|impr\b",
    "clicks":    r"clic\b|clic sul link|click|clicks",
    "platform_conversions":
        r"risultati|conversioni|conversion|lead|leads|candidature avviate|results",
    "currency":  r"valuta|currency",
    # fatti non-media
    "client_requests":   r"richieste|requests|fulfillment|ordini",
    "candidate_searches": r"ricerche|searches|ricerche candidati",
    "seasonal_index":    r"indice|index|stagional|seasonal",
    "conversions":       r"candidature|conversioni|conversions|placements",
    "revenue":           r"ricavo|revenue|fatturato|margine",
    # PII (per il riconoscimento del fatto individuale, vedi privacy.py)
    "pii_id":     r"^id|codice candidato|user_?id",
    "pii_name":   r"nome|first ?name",
    "pii_surname": r"cognome|last ?name|surname",
    "pii_cf":     r"codice.?fiscale|\bcf\b|tax ?code",
    "pii_age":    r"\beta\b|età|age|data di nascita|birth",
    "pii_touch":  r"touchpoint|ultimo[_ ]touch|canale",
    "pii_date":   r"data[_ ]candidatura|application date|data\b",
}

CHANNEL_HINTS = re.compile(r"(?i)(google|meta|facebook|linkedin|indeed)")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.strip().lower()


# ------------------------------------------------------------- strutture
@dataclass
class ColumnMap:
    source: str            # nome colonna nell'export
    field: str             # campo canonico
    confidence: float      # 0-1, solo informativa per l'utente


@dataclass
class SourceMap:
    """Mappatura proposta/confermata per un singolo file di origine."""
    file: str
    kind: str                       # media | demand | seasonality | individual
    channel: str | None = None      # solo per kind=media
    columns: list[ColumnMap] = field(default_factory=list)
    geo_breakdown_of: str | None = None   # questo file è il breakdown geo di...
    confirmed: bool = False
    notes: list[str] = field(default_factory=list)

    def get(self, fld: str) -> str | None:
        for c in self.columns:
            if c.field == fld:
                return c.source
        return None

    def fields(self) -> set[str]:
        return {c.field for c in self.columns}


# ------------------------------------------------------------- proposta
def propose_columns(df: pd.DataFrame) -> list[ColumnMap]:
    out, taken = [], set()
    for col in df.columns:
        nc = _norm(col)
        best, conf = None, 0.0
        for fld, pat in FIELD_ALIASES.items():
            if fld in taken:
                continue
            m = re.search(pat, nc, re.I)
            if m:
                c = 0.9 if m.start() == 0 else 0.7
                if c > conf:
                    best, conf = fld, c
        if best:
            out.append(ColumnMap(str(col), best, conf))
            taken.add(best)
    return out


def propose_source(df: pd.DataFrame, filename: str) -> SourceMap:
    """Propone la mappatura completa di un file: tipo di fatto, canale,
    colonne. L'utente potrà correggere tutto in fase di conferma."""
    cols = propose_columns(df)
    fields = {c.field for c in cols}

    if {"pii_cf", "pii_name"} & fields or "pii_surname" in fields:
        kind = "individual"
    elif "seasonal_index" in fields and "spend" not in fields:
        kind = "seasonality"
    elif ({"client_requests", "candidate_searches"} & fields
          and "spend" not in fields and "campaign" not in fields):
        kind = "demand"
    elif "spend" in fields or "campaign" in fields or "impressions" in fields:
        kind = "media"
    else:
        kind = "demand"     # serie esterna generica: trattata come controllo

    channel = None
    if kind == "media":
        m = CHANNEL_HINTS.search(filename)
        if not m and "campaign" in fields:
            sample = " ".join(df[next(c.source for c in cols
                                      if c.field == "campaign")]
                              .astype(str).head(20))
            m = CHANNEL_HINTS.search(sample)
        if m:
            channel = m.group(1).lower().replace("facebook", "meta")

    sm = SourceMap(file=os.path.basename(filename), kind=kind,
                   channel=channel, columns=cols)
    if kind == "media" and "region" not in fields:
        sm.notes.append("nessuna colonna regione: file nazionale "
                        "(servirà breakdown geo o fallback popolazione)")
    if re.search(r"(?i)geograf|geo|localit|region", filename) and kind == "media":
        sm.notes.append("probabile report geografico (breakdown di un "
                        "file nazionale dello stesso canale)")
    return sm


# ------------------------------------------------------------- normalizzazioni
def normalize_region(s: pd.Series) -> pd.Series:
    """Nomi regione eterogenei → anagrafica canonica ('' → nazionale)."""
    canon = {_norm(r): r for r in config.REGION_LIST}
    alias = {k: v for k, v in config.REGION_ALIASES.items()}

    def conv(v):
        if v is None or str(v).strip() in ("", "nan", "None"):
            return ""
        n = _norm(v).replace("'", " ").replace("-", " ")
        n = re.sub(r"\s+", " ", n)
        for table in (canon, {_norm(k).replace("'", " "): v
                              for k, v in alias.items()}):
            if n in table:
                return table[n]
        # match parziale prudente (es. 'Lombardia (IT)')
        for key, val in canon.items():
            if key in n:
                return val
        return str(v).strip()    # sconosciuta: la validazione la segnalerà
    return s.map(conv)


def normalize_campaign(s: pd.Series, channel: str | None) -> pd.Series:
    """Etichette di piattaforma → nome campagna canonico (minuscolo,
    senza prefissi aziendali tipo 'RND_IT_META_')."""
    def conv(v):
        x = _norm(v)
        x = re.sub(r"^(rnd|randstad)[_\- ]*(it)?[_\- ]*", "", x)
        if channel:
            x = re.sub(rf"^{channel}[_\- ]*", "", x)
        return re.sub(r"[\W]+", "_", x).strip("_")
    return s.map(conv)


# ------------------------------------------------------------- persistenza
def save_plan(plans: list[SourceMap], path: str) -> None:
    with open(path, "w") as f:
        json.dump([asdict(p) for p in plans], f, indent=2, ensure_ascii=False)


def load_plan(path: str) -> list[SourceMap]:
    with open(path) as f:
        raw = json.load(f)
    plans = []
    for p in raw:
        cols = [ColumnMap(**c) for c in p.pop("columns")]
        plans.append(SourceMap(columns=cols, **p))
    return plans


# ------------------------------------------------------------- conferma umana
def confirm_interactive(plans: list[SourceMap]) -> list[SourceMap]:
    """Presenta le proposte e chiede conferma per ciascun file.

    Risposte: INVIO/s = conferma | n = escludi il file |
    campo=colonna[,campo=colonna...] = correzione puntuale.
    """
    print("\n=== CONFERMA MAPPATURA (human-in-the-middle) ===")
    out = []
    for p in plans:
        print(f"\nFile: {p.file}")
        print(f"  tipo: {p.kind}" + (f" | canale: {p.channel}" if p.channel else ""))
        if p.geo_breakdown_of:
            print(f"  breakdown geografico di: {p.geo_breakdown_of}")
        for c in p.columns:
            print(f"    {c.source!r:<35} -> {c.field:<22} ({c.confidence:.0%})")
        for nta in p.notes:
            print(f"  nota: {nta}")
        ans = input("  Confermi? [INVIO=sì | n=escludi | campo=colonna,...]: ").strip()
        if ans.lower() == "n":
            print("  -> file escluso")
            continue
        if ans and ans.lower() not in ("s", "si", "sì", "y", "yes"):
            for pair in ans.split(","):
                fld, _, src = pair.partition("=")
                fld, src = fld.strip(), src.strip()
                p.columns = [c for c in p.columns
                             if c.field != fld and c.source != src]
                if src:
                    p.columns.append(ColumnMap(src, fld, 1.0))
        p.confirmed = True
        out.append(p)
    return out
