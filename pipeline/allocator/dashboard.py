"""
Cruscotto Excel direzionale (MMM Budget Optimizer).

Genera un workbook formattato per la lettura manageriale, con grafici nativi
Excel e formattazione condizionale (non immagini):

  Sintesi_Strategica      KPI + allocazione per campagna + grafici Mix/Confronto
  Pianificazione_Mensile  piano mensile con stagionalita' (scala colori) e azione
  Metriche_Storiche       storico per campagna

Costruito con openpyxl. Entry point: build_dashboard(...).
"""
from __future__ import annotations

import os

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from . import quarter as Q

# --------------------------------------------------------------- stile
NAVY, BLUE, LIGHT = "1F4E79", "2E75B6", "DDEBF7"
GREEN, GREEN_T = "C6EFCE", "006100"
RED, RED_T = "FFC7CE", "9C0006"
YELLOW, YELLOW_T = "FFEB9C", "9C6500"
WHITE = "FFFFFF"
_TH = Side(style="thin", color="BFBFBF")
BORDER = Border(left=_TH, right=_TH, top=_TH, bottom=_TH)
EUR, PCT, NUM, EUR2 = "#,##0 €", "0.0%", "#,##0", "#,##0.00 €"
MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio",
        "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]


def _title(ws, text, ncols, row=1):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row, 1, text)
    c.font = Font(b=True, size=15, color=WHITE)
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row].height = 28


def _band(ws, text, ncols, row):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row, 1, text)
    c.font = Font(b=True, color=WHITE)
    c.fill = PatternFill("solid", fgColor=BLUE)
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 20


def _headers(ws, headers, row):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row, j, h)
        c.font = Font(b=True, color=WHITE)
        c.fill = PatternFill("solid", fgColor=BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center",
                                wrap_text=True)
        c.border = BORDER
    ws.row_dimensions[row].height = 32


def _fill(hexc):
    return PatternFill("solid", fgColor=hexc)


# --------------------------------------------------------------- dati
def _campaign_table(canali, campagne, curves) -> pd.DataFrame:
    cand_now_ch = dict(zip(canali["canale"], canali["candidature ora"]))
    tot_bud = campagne["budget consigliato (EUR)"].sum()
    rows = []
    for _, r in campagne.iterrows():
        ch = r["canale"]
        bud = float(r["budget consigliato (EUR)"])
        sp = float(r["spesa attuale (EUR)"])
        conv_att = float(r["candidature attese"])
        conv_sto = float(cand_now_ch.get(ch, 0.0)) * float(r["quota attuale"])
        cpa_sto = sp / conv_sto if conv_sto > 0 else 0.0
        cpa_prev = bud / conv_att if conv_att > 0 else 0.0
        c = curves[ch]
        sat = Q._steady_response(bud / Q.WEEKS, c["lam"], c["ec"],
                                 c["slope"], c["scale"])
        livello = "ALTO" if sat > 0.6 else ("MEDIO" if sat > 0.3 else "BASSO")
        rows.append({
            "Campagna": f"{ch.upper()}_{r['campagna'].upper()}",
            "Budget Consigliato": bud,
            "Mix %": bud / tot_bud if tot_bud else 0.0,
            "Spesa Storica": sp,
            "Var. Budget EUR": bud - sp,
            "Var. Budget %": (bud / sp - 1) if sp > 0 else 0.0,
            "Conv Storiche": conv_sto,
            "Conv Attese": conv_att,
            "Var. Conv %": (conv_att / conv_sto - 1) if conv_sto > 0 else 0.0,
            "CPA Storico": cpa_sto,
            "CPA Previsto": cpa_prev,
            "Var. CPA %": (cpa_prev / cpa_sto - 1) if cpa_sto > 0 else 0.0,
            "Saturazione": livello,
        })
    return pd.DataFrame(rows).sort_values("Budget Consigliato", ascending=False)


# --------------------------------------------------------------- fogli
def _sheet_sintesi(wb, tab, tot_conv_att):
    ws = wb.active
    ws.title = "Sintesi_Strategica"
    ncol = len(tab.columns)
    _title(ws, "MMM Budget Optimizer - Cruscotto Strategico", ncol)

    tot_bud = tab["Budget Consigliato"].sum()
    kpi = [("Investimento Settimanale", tot_bud / Q.WEEKS, EUR),
           ("Investimento Mensile", tot_bud / 3.0, EUR),
           ("Conversioni Previste / sett.", tot_conv_att / Q.WEEKS, NUM),
           ("CPA Medio Previsto", tot_bud / max(tot_conv_att, 1), EUR2)]
    _band(ws, "KPI PRINCIPALI", ncol, 3)
    for i, (label, val, fmt) in enumerate(kpi):
        r = 4 + i
        a = ws.cell(r, 1, label); a.font = Font(b=True); a.fill = _fill(LIGHT)
        b = ws.cell(r, 2, val); b.number_format = fmt
        b.font = Font(b=True, color=NAVY)

    band_row = 4 + len(kpi) + 1
    _band(ws, "ANALISI DI ALLOCAZIONE E VARIAZIONI PERCENTUALI", ncol, band_row)
    hdr = band_row + 1
    _headers(ws, list(tab.columns), hdr)

    fmts = {"Budget Consigliato": EUR, "Mix %": PCT, "Spesa Storica": EUR,
            "Var. Budget EUR": EUR, "Var. Budget %": PCT, "Conv Storiche": NUM,
            "Conv Attese": NUM, "Var. Conv %": PCT, "CPA Storico": EUR2,
            "CPA Previsto": EUR2, "Var. CPA %": PCT}
    sat_fill = {"ALTO": (RED, RED_T), "MEDIO": (YELLOW, YELLOW_T),
                "BASSO": (GREEN, GREEN_T)}
    for i, (_, row) in enumerate(tab.iterrows()):
        rr = hdr + 1 + i
        for j, col in enumerate(tab.columns, 1):
            c = ws.cell(rr, j, row[col]); c.border = BORDER
            if col in fmts:
                c.number_format = fmts[col]
            if col == "Saturazione":
                fg, tx = sat_fill[row[col]]
                c.fill = _fill(fg); c.font = Font(b=True, color=tx)
                c.alignment = Alignment(horizontal="center")
            if col in ("Var. Conv %", "Var. Budget %"):
                good = row[col] >= 0
                c.font = Font(color=GREEN_T if good else RED_T)
            if col == "Var. CPA %":          # CPA: scendere e' buono
                c.font = Font(color=GREEN_T if row[col] <= 0 else RED_T)
    last = hdr + len(tab)

    # larghezze
    widths = [22, 16, 8, 14, 14, 12, 12, 12, 11, 12, 12, 11, 12]
    for j, w in enumerate(widths[:ncol], 1):
        ws.column_dimensions[chr(64 + j)].width = w

    # grafico torta: Mix Budget
    pie = PieChart(); pie.title = "Mix Budget"; pie.height = 8; pie.width = 13
    data = Reference(ws, min_col=2, min_row=hdr, max_row=last)        # Budget Consigliato
    cats = Reference(ws, min_col=1, min_row=hdr + 1, max_row=last)    # Campagna
    pie.add_data(data, titles_from_data=True); pie.set_categories(cats)
    ws.add_chart(pie, f"{chr(64 + ncol + 2)}3")

    # grafico barre: Confronto Spesa (storica vs consigliato)
    bar = BarChart(); bar.title = "Confronto Spesa"; bar.type = "col"
    bar.height = 8; bar.width = 13
    d1 = Reference(ws, min_col=4, min_row=hdr, max_row=last)          # Spesa Storica
    d2 = Reference(ws, min_col=2, min_row=hdr, max_row=last)          # Budget Consigliato
    bar.add_data(d1, titles_from_data=True); bar.add_data(d2, titles_from_data=True)
    bar.set_categories(cats)
    ws.add_chart(bar, f"{chr(64 + ncol + 2)}20")


def _sheet_mensile(wb, tot_bud, tot_conv_att, seas):
    ws = wb.create_sheet("Pianificazione_Mensile")
    _title(ws, "Piano Operativo Mensile", 5)
    _headers(ws, ["Mese", "Indice Stagionalita", "Azione Strategica",
                  "Budget Suggerito", "Conv. Stimate"], 3)

    s = seas.copy()
    s = s[s["region"].astype(str) == "*"] if "region" in s.columns else s
    s["m"] = pd.to_datetime(s["week"]).dt.month
    idx = s.groupby("m")["seasonal_index"].mean()
    idx = (idx / idx.mean()).reindex(range(1, 13)).fillna(1.0)
    avg_month = tot_bud / 3.0
    conv_per_eur = tot_conv_att / max(tot_bud, 1)
    for i, m in enumerate(range(1, 13)):
        rr = 4 + i
        v = float(idx[m])
        budget = avg_month * v
        azione = ("PUSH" if v > 1.03 else ("RIDUCI" if v < 0.97 else "MANTIENI"))
        vals = [MESI[i], round(v, 2), azione, budget, budget * conv_per_eur]
        for j, x in enumerate(vals, 1):
            c = ws.cell(rr, j, x); c.border = BORDER
        ws.cell(rr, 4).number_format = EUR
        ws.cell(rr, 5).number_format = NUM
        ws.cell(rr, 3).alignment = Alignment(horizontal="center")
        ws.cell(rr, 3).font = Font(b=True)
    # scala colori sulla stagionalita'
    ws.conditional_formatting.add(
        f"B4:B15",
        ColorScaleRule(start_type="min", start_color="F8696B",
                       mid_type="percentile", mid_value=50, mid_color="FFEB84",
                       end_type="max", end_color="63BE7B"))
    for j, w in enumerate([14, 18, 18, 18, 16], 1):
        ws.column_dimensions[chr(64 + j)].width = w


def _sheet_storico(wb, media):
    ws = wb.create_sheet("Metriche_Storiche")
    _title(ws, "Dettaglio Storico Canali", 5)
    _headers(ws, ["Campagna", "Spend Tot EUR", "Spend Medio Sett",
                  "Click Medio Sett", "CPA Medio Storico"], 3)
    nw = media["week"].nunique()
    g = media.groupby(["channel", "campaign"]).agg(
        spend=("spend", "sum"), clicks=("clicks", "sum"),
        conv=("platform_conversions", "sum")).reset_index()
    g["name"] = (g["channel"].str.upper() + "_" + g["campaign"].str.upper())
    g = g.sort_values("spend", ascending=False)
    for i, (_, r) in enumerate(g.iterrows()):
        rr = 4 + i
        cpa = r["spend"] / r["conv"] if r["conv"] > 0 else 0.0
        vals = [r["name"], r["spend"], r["spend"] / nw, r["clicks"] / nw, cpa]
        for j, x in enumerate(vals, 1):
            c = ws.cell(rr, j, x); c.border = BORDER
        ws.cell(rr, 2).number_format = EUR
        ws.cell(rr, 3).number_format = EUR
        ws.cell(rr, 4).number_format = NUM
        ws.cell(rr, 5).number_format = EUR2
    for j, w in enumerate([26, 16, 16, 16, 16], 1):
        ws.column_dimensions[chr(64 + j)].width = w


# --------------------------------------------------------------- entry point
def build_dashboard(canali, campagne, summary, media, seas, rev_per_conv,
                    path) -> str:
    nw = media["week"].nunique()
    hist = (media.groupby("channel")["spend"].sum() / nw).to_dict()
    curves = Q.build_curves(summary, hist)
    tab = _campaign_table(canali, campagne, curves)
    tot_conv_att = float(tab["Conv Attese"].sum())
    tot_bud = float(tab["Budget Consigliato"].sum())

    wb = Workbook()
    _sheet_sintesi(wb, tab, tot_conv_att)
    _sheet_mensile(wb, tot_bud, tot_conv_att, seas)
    _sheet_storico(wb, media)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)
    return path
