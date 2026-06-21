"""
Serializzazione "sporca": gli export sintetici imitano i formati reali.

Ogni piattaforma ha i suoi vizi, riprodotti deliberatamente per testare
l'ingestion (formati data misti, virgole decimali, righe di metadati,
celle vuote, encoding con BOM). La gerarchia di qualità geografica del
documento di progetto è incorporata:

  meta_ads.csv             breakdown regionale per TUTTE le campagne Meta
  google_ads.csv           nazionale, con metadati in testa e riga Totale
  google_ads_geografia.csv impression per regione (+ costo per le geo)
  linkedin_campaigns.xlsx  SOLO nazionale (fallback popolazione in ingestion)
  indeed_export.csv        regionale per sponsored_jobs, nazionale display
  crm_candidature.csv.gz   individuale, con PII finte (test GDPR)
  richieste_clienti.xlsx   domanda clienti, settimana x regione (wide)
  ricerche_candidati.csv   ricerche candidati, long, ';' e virgola decimale
  stagionalita.csv         indice stagionale esogeno dell'utente
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from .. import config
from . import world


# ------------------------------------------------------------ formattatori
def _it_num(x: float, dec: int = 2) -> str:
    """1234567.89 -> '1.234.567,89' (formato italiano)."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _ddmmyyyy(d) -> str:
    return pd.Timestamp(d).strftime("%d/%m/%Y")


def _en_date(d) -> str:
    return pd.Timestamp(d).strftime("%b %-d, %Y") if os.name != "nt" \
        else pd.Timestamp(d).strftime("%b %d, %Y")


def _camp_label(camp: str) -> str:
    """Nome campagna come appare in piattaforma."""
    ch = world.CAMPAIGNS[camp]["channel"]
    return f"RND_IT_{ch.upper()}_{camp.upper()}"


# ------------------------------------------------------------ singoli export
def write_meta(panel: dict, rng: np.random.Generator, path: str) -> None:
    rows = []
    weeks, regions = panel["weeks"], config.REGION_LIST
    ints = panel["internals"]
    for camp, c in world.CAMPAIGNS.items():
        if c["channel"] != "meta":
            continue
        for ti, w in enumerate(weeks):
            for j, r in enumerate(regions):
                impr = ints["camp_impr"][camp][ti, j]
                rows.append({
                    "Inizio della settimana": _ddmmyyyy(w),
                    "Nome della campagna": _camp_label(camp),
                    "Regione": r,
                    "Importo speso (EUR)": _it_num(ints["camp_spend"][camp][ti, j]),
                    "Impression": "" if rng.random() < 0.004 else int(impr),
                    "Clic sul link": int(ints["camp_clicks"][camp][ti, j]),
                    "Risultati": _it_num(ints["camp_conv"][camp][ti, j], 1),
                })
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def write_google(panel: dict, path_nat: str, path_geo: str) -> None:
    weeks, regions = panel["weeks"], config.REGION_LIST
    ints = panel["internals"]
    g_camps = [cp for cp, c in world.CAMPAIGNS.items() if c["channel"] == "google"]

    # nazionale, con righe di metadati e riga Totale
    rows = []
    for camp in g_camps:
        for ti, w in enumerate(weeks):
            rows.append({
                "Settimana": _ddmmyyyy(w),
                "Campagna": _camp_label(camp),
                "Costo": _it_num(ints["camp_spend"][camp][ti].sum()),
                "Impressioni": _it_num(ints["camp_impr"][camp][ti].sum(), 0),
                "Clic": _it_num(ints["camp_clicks"][camp][ti].sum(), 0),
                "Conversioni": _it_num(ints["camp_conv"][camp][ti].sum(), 1),
            })
    df = pd.DataFrame(rows)
    tot = {"Settimana": "Totale: account", "Campagna": "",
           "Costo": _it_num(sum(ints["camp_spend"][c].sum() for c in g_camps)),
           "Impressioni": "", "Clic": "", "Conversioni": ""}
    df = pd.concat([df, pd.DataFrame([tot])], ignore_index=True)
    with open(path_nat, "w", encoding="utf-8") as f:
        f.write("Rapporto Campagne\n")
        f.write(f"\"{_ddmmyyyy(weeks[0])} - {_ddmmyyyy(weeks[-1])}\"\n")
        df.to_csv(f, index=False)

    # report Geografia: impression per regione; costo solo per le geo-target
    rows = []
    for camp in g_camps:
        geo = world.CAMPAIGNS[camp]["geo"]
        for ti, w in enumerate(weeks):
            for j, r in enumerate(regions):
                rows.append({
                    "Settimana": _ddmmyyyy(w),
                    "Campagna": _camp_label(camp),
                    "Regione": r,
                    "Impressioni": int(ints["camp_impr"][camp][ti, j]),
                    "Costo": _it_num(ints["camp_spend"][camp][ti, j]) if geo else "",
                })
    pd.DataFrame(rows).to_csv(path_geo, index=False, encoding="utf-8")


def write_linkedin(panel: dict, path: str) -> None:
    weeks = panel["weeks"]
    ints = panel["internals"]
    rows = []
    for camp, c in world.CAMPAIGNS.items():
        if c["channel"] != "linkedin":
            continue
        for ti, w in enumerate(weeks):
            rows.append({
                "Start Date (in UTC)": pd.Timestamp(w).strftime("%b %d, %Y"),
                "Campaign Name": _camp_label(camp),
                "Currency": "EUR",
                "Total Spent": round(float(ints["camp_spend"][camp][ti].sum()), 2),
                "Impressions": int(ints["camp_impr"][camp][ti].sum()),
                "Clicks": int(ints["camp_clicks"][camp][ti].sum()),
                "Leads": round(float(ints["camp_conv"][camp][ti].sum()), 1),
            })
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Campaign Performance",
                    index=False, startrow=2)
        ws = xl.sheets["Campaign Performance"]
        ws.cell(1, 1, "Campaign Performance Report")
        ws.cell(2, 1, "LinkedIn Campaign Manager")


def write_indeed(panel: dict, path: str) -> None:
    weeks, regions = panel["weeks"], config.REGION_LIST
    ints = panel["internals"]
    rows = []
    for camp, c in world.CAMPAIGNS.items():
        if c["channel"] != "indeed":
            continue
        for ti, w in enumerate(weeks):
            if c["geo"]:
                for j, r in enumerate(regions):
                    rows.append((
                        _ddmmyyyy(w), _camp_label(camp), r,
                        _it_num(ints["camp_spend"][camp][ti, j]),
                        int(ints["camp_impr"][camp][ti, j]),
                        int(ints["camp_clicks"][camp][ti, j]),
                        _it_num(ints["camp_conv"][camp][ti, j], 1)))
            else:
                rows.append((
                    _ddmmyyyy(w), _camp_label(camp), "",
                    _it_num(ints["camp_spend"][camp][ti].sum()),
                    int(ints["camp_impr"][camp][ti].sum()),
                    int(ints["camp_clicks"][camp][ti].sum()),
                    _it_num(ints["camp_conv"][camp][ti].sum(), 1)))
    df = pd.DataFrame(rows, columns=["Settimana", "Campagna", "Regione",
                                     "Spesa", "Impressioni", "Clic",
                                     "Candidature avviate"])
    df.to_csv(path, index=False, sep=";", encoding="utf-8")


def write_demand_and_seasonality(panel: dict, dir_raw: str) -> None:
    demand = panel["demand"]

    # richieste clienti: Excel wide (settimana x regione), date vere
    wide = demand.pivot(index="week", columns="region",
                        values="client_requests")
    wide.index = [_ddmmyyyy(w) for w in wide.index]
    wide.index.name = "Settimana"
    with pd.ExcelWriter(os.path.join(dir_raw, "richieste_clienti.xlsx"),
                        engine="openpyxl") as xl:
        wide.to_excel(xl, sheet_name="Richieste")

    # ricerche candidati: CSV long, ';', virgola decimale
    rc = demand[["week", "region", "candidate_searches"]].copy()
    rc["week"] = rc["week"].map(_ddmmyyyy)
    rc.columns = ["Settimana", "Regione", "Ricerche"]
    rc.to_csv(os.path.join(dir_raw, "ricerche_candidati.csv"),
              index=False, sep=";", decimal=",", encoding="utf-8")

    # indice stagionale esogeno (quello "già calcolato dall'utente")
    se = panel["seasonality"][["week", "seasonal_index"]].copy()
    se["week"] = pd.to_datetime(se["week"]).dt.strftime("%Y-%m-%d")
    se.columns = ["settimana", "indice_stagionale"]
    se.to_csv(os.path.join(dir_raw, "stagionalita.csv"), index=False)

    # candidature dirette / traffico organico: CSV long (proxy domanda organica
    # che l'azienda gia' traccia). L'ingestion lo mappa sul controllo direct_apps.
    di = panel["direct"][["week", "region", "candidature_dirette"]].copy()
    di["week"] = di["week"].map(_ddmmyyyy)
    di.columns = ["Settimana", "Regione", "Candidature dirette"]
    di.to_csv(os.path.join(dir_raw, "candidature_dirette.csv"), index=False)


def write_crm(individuals: pd.DataFrame, path: str) -> None:
    individuals.to_csv(path, index=False, sep=";", decimal=",",
                       compression="gzip", encoding="utf-8")


def write_all(panel: dict, individuals: pd.DataFrame, dir_raw: str,
              seed: int = world.SEED) -> list[str]:
    os.makedirs(dir_raw, exist_ok=True)
    rng = np.random.default_rng(seed + 2)
    write_meta(panel, rng, os.path.join(dir_raw, "meta_ads.csv"))
    write_google(panel, os.path.join(dir_raw, "google_ads.csv"),
                 os.path.join(dir_raw, "google_ads_geografia.csv"))
    write_linkedin(panel, os.path.join(dir_raw, "linkedin_campaigns.xlsx"))
    write_indeed(panel, os.path.join(dir_raw, "indeed_export.csv"))
    write_demand_and_seasonality(panel, dir_raw)
    write_crm(individuals, os.path.join(dir_raw, "crm_candidature.csv.gz"))
    return sorted(os.listdir(dir_raw))
