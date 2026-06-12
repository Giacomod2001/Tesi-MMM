"""
Schema canonico: definizione formale dei fatti e validatori.

È il contratto dati dell'intera pipeline. Tutto ciò che entra nel modello
passa da qui: l'ingestion PRODUCE questi fatti, il modello li CONSUMA.
Il modello non sa mai se i dati sono sintetici o reali — conosce solo
questo schema.

Fatti (una riga = settimana × regione [× canale × campagna]):
    media        spesa, impression, click, conversioni di piattaforma
    outcome      conversioni reali e ricavi
    demand       controlli di domanda (richieste clienti, ricerche candidati)
    seasonality  indice stagionale esogeno (region="*" se nazionale)

Convenzioni: settimane W-MON (lunedì), date ISO 8601, EUR.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config


# ----------------------------------------------------------------- definizione
@dataclass(frozen=True)
class FactSchema:
    """Definizione dichiarativa di un fatto canonico."""
    name: str
    columns: list[str]
    key: list[str]                       # chiave di unicità
    numeric: list[str]                   # colonne numeriche >= 0
    region_required: bool = True         # se False ammette region="*"

    def empty(self) -> pd.DataFrame:
        return pd.DataFrame(columns=self.columns)


MEDIA = FactSchema(
    name="media",
    columns=config.MEDIA_COLS,
    key=["week", "region", "channel", "campaign"],
    numeric=["spend", "impressions", "clicks", "platform_conversions"],
)
OUTCOME = FactSchema(
    name="outcome",
    columns=config.OUTCOME_COLS,
    key=["week", "region"],
    numeric=["conversions", "revenue"],
)
DEMAND = FactSchema(
    name="demand",
    columns=config.DEMAND_COLS,
    key=["week", "region"],
    numeric=["client_requests", "candidate_searches"],
)
SEASONALITY = FactSchema(
    name="seasonality",
    columns=config.SEASONALITY_COLS,
    key=["week", "region"],
    numeric=["seasonal_index"],
    region_required=False,
)

FACTS = {f.name: f for f in (MEDIA, OUTCOME, DEMAND, SEASONALITY)}


# ----------------------------------------------------------------- helper tempo
def to_week_start(dates: pd.Series | pd.DatetimeIndex) -> pd.Series:
    """Allinea date qualsiasi al lunedì della loro settimana ISO."""
    d = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    return (d - pd.to_timedelta(d.dt.dayofweek, unit="D")).dt.normalize()


def week_grid(start: str | pd.Timestamp, n_weeks: int) -> pd.DatetimeIndex:
    """Griglia settimanale canonica (lunedì) di n_weeks settimane."""
    start = to_week_start(pd.Series([pd.Timestamp(start)])).iloc[0]
    return pd.date_range(start, periods=n_weeks, freq=config.WEEK_FREQ)


def add_calendar(df: pd.DataFrame, week_col: str = "week") -> pd.DataFrame:
    """Aggiunge mese e trimestre (per aggregazione, mai per stima)."""
    out = df.copy()
    w = pd.to_datetime(out[week_col])
    out["month"] = w.dt.to_period("M").astype(str)
    out["quarter"] = w.dt.to_period("Q").astype(str)
    return out


# ----------------------------------------------------------------- validazione
@dataclass
class ValidationReport:
    """Esito della validazione di un fatto: errori bloccanti e avvisi."""
    fact: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def __str__(self) -> str:
        lines = [f"[{self.fact}] {'OK' if self.ok else 'ERRORI'}"]
        lines += [f"  ERRORE: {e}" for e in self.errors]
        lines += [f"  avviso: {w}" for w in self.warnings]
        return "\n".join(lines)


def validate(df: pd.DataFrame, fact: FactSchema) -> ValidationReport:
    """Valida un fatto contro lo schema canonico.

    Controlli bloccanti: colonne mancanti, settimane non-lunedì, regioni
    fuori anagrafica, chiavi duplicate, valori numerici negativi/non numerici.
    Avvisi: buchi nella griglia settimanale, valori mancanti.
    """
    rep = ValidationReport(fact.name)

    missing = [c for c in fact.columns if c not in df.columns]
    if missing:
        rep.errors.append(f"colonne mancanti: {missing}")
        return rep
    if df.empty:
        rep.errors.append("fatto vuoto")
        return rep

    # --- settimane --------------------------------------------------------
    week = pd.to_datetime(df["week"], errors="coerce")
    if week.isna().any():
        rep.errors.append(f"{int(week.isna().sum())} date non interpretabili")
    elif (week.dt.dayofweek != 0).any():
        n = int((week.dt.dayofweek != 0).sum())
        rep.errors.append(f"{n} settimane non allineate al lunedì (W-MON)")

    # --- regioni ----------------------------------------------------------
    regions = set(df["region"].astype(str))
    allowed = set(config.REGION_LIST) | ({"*"} if not fact.region_required else set())
    unknown = sorted(regions - allowed)
    if unknown:
        rep.errors.append(f"regioni fuori anagrafica: {unknown}")

    # --- chiave -----------------------------------------------------------
    dup = df.duplicated(subset=fact.key).sum()
    if dup:
        rep.errors.append(f"{int(dup)} righe duplicate sulla chiave {fact.key}")

    # --- numerici ---------------------------------------------------------
    for c in fact.numeric:
        v = pd.to_numeric(df[c], errors="coerce")
        bad = int(v.isna().sum() - df[c].isna().sum())
        if bad:
            rep.errors.append(f"{c}: {bad} valori non numerici")
        if (v < 0).any():
            rep.errors.append(f"{c}: {int((v < 0).sum())} valori negativi")
        if df[c].isna().any():
            rep.warnings.append(f"{c}: {int(df[c].isna().sum())} valori mancanti")

    # --- continuità temporale (avviso: i buchi veri sono spese a zero) -----
    if not week.isna().any():
        full = pd.date_range(week.min(), week.max(), freq=config.WEEK_FREQ)
        holes = len(full.difference(pd.DatetimeIndex(week.unique())))
        if holes:
            rep.warnings.append(
                f"griglia settimanale con {holes} settimane assenti tra "
                f"{week.min().date()} e {week.max().date()}")
    return rep


def validate_all(facts: dict[str, pd.DataFrame]) -> dict[str, ValidationReport]:
    """Valida un insieme di fatti; chiave = nome del fatto canonico."""
    return {name: validate(df, FACTS[name]) for name, df in facts.items()
            if name in FACTS}
