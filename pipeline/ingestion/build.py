"""
Orchestrazione dell'ingestion: dai file grezzi ai fatti canonici validati.

    ingest(raw_dir)  →  {media, outcome, demand, seasonality} + report

La conferma umana della mappatura avviene una volta sola: il piano
confermato viene salvato in `mapping_confirmed.json` accanto ai dati
canonici e riusato nei rilanci (riproducibilità + audit trail GDPR).
"""
from __future__ import annotations

import os
import re

import numpy as np
import pandas as pd

from .. import config, schema
from . import geo_split, mapping, parsers, privacy

SUPPORTED = (".csv", ".tsv", ".txt", ".xlsx", ".xls", ".xlsm", ".pdf",
             ".json", ".gz")


# --------------------------------------------------------------- scoperta file
def discover(raw_dir: str) -> list[str]:
    return sorted(
        os.path.join(raw_dir, f) for f in os.listdir(raw_dir)
        if f.lower().endswith(SUPPORTED) and not f.startswith("."))


def propose_plan(raw_dir: str) -> tuple[list[mapping.SourceMap],
                                        dict[str, pd.DataFrame]]:
    """Legge tutti i file e propone la mappatura. Collega i report
    geografici al file nazionale dello stesso canale."""
    plans, tables = [], {}
    for path in discover(raw_dir):
        tabs = parsers.read_tables(path)
        if not tabs:
            continue
        df = max(tabs, key=len)             # tabella principale del file
        sm = mapping.propose_source(df, path)
        tables[sm.file] = df
        plans.append(sm)

    # report geografici: stesso canale di un file media nazionale
    media = [p for p in plans if p.kind == "media"]
    for p in media:
        if any("report geografico" in nta for nta in p.notes):
            target = next((q.file for q in media if q is not p
                           and q.channel == p.channel
                           and "region" not in q.fields()), None)
            if target:
                p.geo_breakdown_of = target
    return plans, tables


# --------------------------------------------------------------- fatto media
def _normalize_media(df: pd.DataFrame, sm: mapping.SourceMap) -> pd.DataFrame:
    out = pd.DataFrame()
    out["week"] = schema.to_week_start(parsers.coerce_date(df[sm.get("week")]))
    rcol = sm.get("region")
    out["region"] = (mapping.normalize_region(df[rcol]) if rcol else "")
    ccol = sm.get("campaign")
    out["campaign"] = (mapping.normalize_campaign(df[ccol], sm.channel)
                       if ccol else sm.channel or "campagna_unica")
    out["channel"] = sm.channel or "sconosciuto"
    for fld in geo_split.VALUE_COLS:
        col = sm.get(fld)
        out[fld] = parsers.coerce_number(df[col]) if col else np.nan
    cur = sm.get("currency")
    if cur:
        bad = set(df[cur].dropna().astype(str).str.upper()) - {config.CURRENCY}
        if bad:
            raise ValueError(f"{sm.file}: valute non in {config.CURRENCY}: {bad}")
    return out.dropna(subset=["week"])


def build_media(plans: list[mapping.SourceMap],
                tables: dict[str, pd.DataFrame],
                report: list[str]) -> pd.DataFrame:
    regional, national, breakdowns = [], [], {}
    for sm in plans:
        if sm.kind != "media" or not sm.confirmed:
            continue
        df = _normalize_media(tables[sm.file], sm)
        if sm.geo_breakdown_of:
            # split: righe con spesa = campagne geo (tier 1);
            # righe senza spesa = breakdown impression delle nazionali
            has_spend = df["spend"].notna() & (df["spend"] > 0)
            regional.append(df[has_spend & (df["region"] != "")])
            breakdowns.setdefault(sm.geo_breakdown_of, []).append(
                df[~has_spend][["week", "campaign", "region", "impressions"]])
            continue
        is_reg = df["region"] != ""
        regional.append(df[is_reg])
        national.append(df[~is_reg])

    reg = (pd.concat(regional, ignore_index=True)
           if regional else schema.MEDIA.empty())
    nat = (pd.concat(national, ignore_index=True)
           if national else schema.MEDIA.empty())

    # precedenza tier 1: se una campagna ha già righe regionali con spesa,
    # le sue righe nazionali (stessa spesa aggregata) vengono scartate
    covered = set(reg.loc[reg["spend"] > 0, "campaign"].unique())
    dup = nat["campaign"].isin(covered)
    if dup.any():
        dropped = sorted(nat.loc[dup, "campaign"].unique())
        report.append(f"righe nazionali scartate (già coperte da dati "
                      f"regionali tier-1): {dropped}")
        # ...ma le metriche presenti SOLO a livello nazionale (es. le
        # conversioni di un report geografico senza quella colonna) vengono
        # recuperate e distribuite proporzionalmente alla spesa regionale
        for camp in dropped:
            nrows = nat[nat["campaign"] == camp]
            rmask = reg["campaign"] == camp
            for colv in ("impressions", "clicks", "platform_conversions"):
                if reg.loc[rmask, colv].fillna(0).sum() > 0:
                    continue
                nat_w = nrows.groupby("week")[colv].sum()
                if nat_w.fillna(0).sum() <= 0:
                    continue
                sp = reg.loc[rmask, ["week", "spend"]]
                tot_w = sp.groupby("week")["spend"].transform("sum")
                shares = (sp["spend"] / tot_w.replace(0, np.nan)).fillna(0)
                reg.loc[rmask, colv] = (
                    shares * sp["week"].map(nat_w).fillna(0)).to_numpy()
                report.append(f"'{camp}': {colv} nazionali ripartite "
                              "sulla spesa regionale")
        nat = nat[~dup]

    bk_frames = [b for lst in breakdowns.values() for b in lst]
    bk = pd.concat(bk_frames, ignore_index=True) if bk_frames else None
    nat_split, tiers = geo_split.split_national(nat, bk)
    for camp, tier in sorted(tiers.items()):
        report.append(f"geo-split campagna '{camp}': {tier}")

    media = pd.concat([reg, nat_split], ignore_index=True)
    media[geo_split.VALUE_COLS] = media[geo_split.VALUE_COLS].fillna(0.0)
    media = (media.groupby(["week", "region", "channel", "campaign"],
                           as_index=False)[geo_split.VALUE_COLS].sum())
    return media[config.MEDIA_COLS].sort_values(
        ["week", "region", "channel", "campaign"]).reset_index(drop=True)


# --------------------------------------------------------------- fatti controllo
def _demand_variable_from_filename(fname: str) -> str:
    # 'dirett' PRIMA di 'candidat': "candidature dirette" e' traffico diretto,
    # non ricerche candidati.
    if re.search(r"(?i)dirett|direct|organic|traffico", fname):
        return "direct_apps"
    if re.search(r"(?i)richiest|client|fulfillment|ordini", fname):
        return "client_requests"
    if re.search(r"(?i)ricerch|search|candidat", fname):
        return "candidate_searches"
    return "client_requests"


def _normalize_demand(df: pd.DataFrame, sm: mapping.SourceMap,
                      report: list[str]) -> pd.DataFrame:
    """Ritorna long: week, region, variable, value. Gestisce sia il formato
    long (colonna regione) sia il wide (una colonna per regione)."""
    wcol = sm.get("week")
    if wcol is None:    # prova la prima colonna
        wcol = df.columns[0]
    week = schema.to_week_start(parsers.coerce_date(df[wcol]))

    region_cols = [c for c in df.columns
                   if mapping.normalize_region(pd.Series([c])).iloc[0]
                   in config.REGION_LIST]
    if len(region_cols) >= 5:           # formato wide settimana x regione
        var = _demand_variable_from_filename(sm.file)
        long = df[region_cols].apply(parsers.coerce_number)
        long.index = week
        long = long.stack().rename("value").reset_index()
        long.columns = ["week", "region", "value"]
        long["region"] = mapping.normalize_region(long["region"])
        long["variable"] = var
        report.append(f"{sm.file}: formato wide -> {var}")
        return long

    rcol = sm.get("region")
    var_field = next((f for f in ("client_requests", "candidate_searches")
                      if sm.get(f)), None)
    vcol = sm.get(var_field) if var_field else None
    if vcol is None:    # ultima colonna numerica
        nums = [c for c in df.columns if c not in (wcol, rcol)
                and parsers.coerce_number(df[c]).notna().mean() > 0.6]
        vcol = nums[-1] if nums else None
        var_field = _demand_variable_from_filename(sm.file)
    if vcol is None:
        raise ValueError(f"{sm.file}: nessuna serie numerica riconosciuta")
    out = pd.DataFrame({
        "week": week,
        "region": (mapping.normalize_region(df[rcol]) if rcol else "*"),
        "value": parsers.coerce_number(df[vcol]),
        "variable": var_field or _demand_variable_from_filename(sm.file)})
    return out.dropna(subset=["week"])


def build_demand(plans, tables, report) -> pd.DataFrame:
    frames = [_normalize_demand(tables[sm.file], sm, report)
              for sm in plans if sm.kind == "demand" and sm.confirmed]
    if not frames:
        return schema.DEMAND.empty()
    long = pd.concat(frames, ignore_index=True)
    wide = (long.pivot_table(index=["week", "region"], columns="variable",
                             values="value", aggfunc="sum").reset_index())
    for c in ("client_requests", "candidate_searches"):
        if c not in wide.columns:
            wide[c] = np.nan
    # direct_apps (candidature dirette / traffico organico) e' un controllo
    # OPZIONALE: se presente lo si porta avanti, altrimenti si ignora.
    extra = [c for c in ("direct_apps",) if c in wide.columns]
    return wide[list(config.DEMAND_COLS) + extra]


def build_seasonality(plans, tables, report) -> pd.DataFrame:
    frames = []
    for sm in plans:
        if sm.kind != "seasonality" or not sm.confirmed:
            continue
        df = tables[sm.file]
        wcol = sm.get("week") or df.columns[0]
        scol = sm.get("seasonal_index") or df.columns[-1]
        rcol = sm.get("region")
        frames.append(pd.DataFrame({
            "week": schema.to_week_start(parsers.coerce_date(df[wcol])),
            "region": (mapping.normalize_region(df[rcol]) if rcol else "*"),
            "seasonal_index": parsers.coerce_number(df[scol])}))
    if not frames:
        return schema.SEASONALITY.empty()
    return (pd.concat(frames, ignore_index=True)
            .dropna(subset=["week"])[config.SEASONALITY_COLS])


# --------------------------------------------------------------- entry point
def ingest(raw_dir: str | None = None,
           plan: list[mapping.SourceMap] | None = None,
           interactive: bool = True,
           out_dir: str | None = None,
           salt: str | None = None,
           tables: dict[str, pd.DataFrame] | None = None) -> dict:
    """Esegue l'intera ingestion.

    Args:
        raw_dir: cartella degli export (default pipeline/data/raw).
        plan: piano di mappatura già confermato (da load_plan); se None
            viene proposto e, se interactive, sottoposto all'utente.
        interactive: False solo per esecuzioni batch CON piano confermato.
        out_dir: dove scrivere i fatti canonici (default data/canonical).
        salt: sale per la pseudonimizzazione (default: casuale).

    Returns:
        {"facts": {...}, "reports": {...}, "plan": [...], "log": [...]}
    """
    raw_dir = raw_dir or config.RAW_DIR
    out_dir = out_dir or config.CANON_DIR
    os.makedirs(out_dir, exist_ok=True)
    log: list[str] = []

    if tables is None:
        proposed, tables = propose_plan(raw_dir)
    else:
        proposed = plan or []
    if plan is not None:
        by_file = {p.file: p for p in plan}
        plans = [by_file.get(p.file, p) for p in proposed]
        missing = [p.file for p in plans if not p.confirmed]
        if missing and not interactive:
            raise ValueError(
                "File senza mappatura confermata in modalità batch: "
                f"{missing}. La conferma umana non è aggirabile.")
    else:
        plans = proposed
    if interactive and any(not p.confirmed for p in plans):
        plans = mapping.confirm_interactive(plans)
    if not any(p.confirmed for p in plans):
        raise ValueError("Nessun file confermato: ingestion interrotta.")

    facts: dict[str, pd.DataFrame] = {}
    facts["media"] = build_media(plans, tables, log)
    facts["demand"] = build_demand(plans, tables, log)
    facts["seasonality"] = build_seasonality(plans, tables, log)

    ind_plans = [p for p in plans if p.kind == "individual" and p.confirmed]
    if ind_plans:
        sm = ind_plans[0]
        pseudo = privacy.pseudonymize(tables[sm.file], sm, salt=salt)
        facts["outcome"] = privacy.aggregate_outcome(pseudo)
        log.append(f"{sm.file}: pseudonimizzato ({len(pseudo):,} record) "
                   "e aggregato a regione x settimana")

    reports = schema.validate_all(facts)
    for name, rep in reports.items():
        log.append(str(rep))

    mapping.save_plan(plans, os.path.join(out_dir, "mapping_confirmed.json"))
    for name, df in facts.items():
        df.to_csv(os.path.join(out_dir, f"{name}.csv"), index=False)

    return {"facts": facts, "reports": reports, "plan": plans, "log": log}
