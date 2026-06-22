"""
Cruscotto Excel direzionale (MMM Budget Optimizer).

Workbook formattato per la lettura manageriale, con grafici nativi Excel e
formattazione condizionale (non immagini):

  Sintesi_Strategica      KPI a riquadri + allocazione per campagna + 4 grafici
                          (Mix Budget, Confronto Spesa, CPA, Conversioni)
  Pianificazione_Mensile  piano 12 mesi: stagionalita' (scala colori), azione,
                          budget, conversioni + grafico combinato
  Metriche_Storiche       storico per campagna + grafico spesa

Entry point: build_dashboard(...).
"""
from __future__ import annotations

import os

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, DoughnutChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import quarter as Q

# --------------------------------------------------------------- stile
NAVY, BLUE, LIGHT, BAND = "1F4E79", "2E75B6", "DDEBF7", "F2F7FC"
GREEN, GREEN_T = "C6EFCE", "006100"
RED, RED_T = "FFC7CE", "9C0006"
YELLOW, YELLOW_T = "FFEB9C", "9C6500"
WHITE = "FFFFFF"
_TH = Side(style="thin", color="D9D9D9")
BORDER = Border(left=_TH, right=_TH, top=_TH, bottom=_TH)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
EUR, PCT, NUM, EUR2 = "#,##0 €", "0.0%", "#,##0", "#,##0.00 €"
MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio",
        "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]


def _fill(c):
    return PatternFill("solid", fgColor=c)


def _title(ws, text, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(1, 1, text)
    c.font = Font(b=True, size=16, color=WHITE)
    c.fill = _fill(NAVY); c.alignment = CENTER
    ws.row_dimensions[1].height = 30


def _band(ws, text, ncols, row):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row, 1, text)
    c.font = Font(b=True, color=WHITE, size=11); c.fill = _fill(BLUE)
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 20


def _headers(ws, headers, row):
    for j, h in enumerate(headers, 1):
        c = ws.cell(row, j, h)
        c.font = Font(b=True, color=WHITE); c.fill = _fill(BLUE)
        c.alignment = CENTER; c.border = BORDER
    ws.row_dimensions[row].height = 30


# --------------------------------------------------------------- dati
def _campaign_table(canali, campagne, curves) -> pd.DataFrame:
    cand_now_ch = dict(zip(canali["canale"], canali["candidature ora"]))
    tot_bud = campagne["budget consigliato (EUR)"].sum()
    rows = []
    for _, r in campagne.iterrows():
        ch = r["canale"]
        bud, sp = float(r["budget consigliato (EUR)"]), float(r["spesa attuale (EUR)"])
        conv_att = float(r["candidature attese"])
        conv_sto = float(cand_now_ch.get(ch, 0.0)) * float(r["quota attuale"])
        cpa_sto = sp / conv_sto if conv_sto > 0 else 0.0
        cpa_prev = bud / conv_att if conv_att > 0 else 0.0
        c = curves[ch]
        sat = Q._steady_response(bud / Q.WEEKS, c["lam"], c["ec"], c["slope"], c["scale"])
        rows.append({
            "Campagna": f"{ch.upper()}_{r['campagna'].upper()}",
            "Budget Consigliato": bud, "Mix %": bud / tot_bud if tot_bud else 0.0,
            "Spesa Storica": sp, "Var. Budget EUR": bud - sp,
            "Var. Budget %": (bud / sp - 1) if sp > 0 else 0.0,
            "Conv Storiche": conv_sto, "Conv Attese": conv_att,
            "Var. Conv %": (conv_att / conv_sto - 1) if conv_sto > 0 else 0.0,
            "CPA Storico": cpa_sto, "CPA Previsto": cpa_prev,
            "Var. CPA %": (cpa_prev / cpa_sto - 1) if cpa_sto > 0 else 0.0,
            "Saturazione": "ALTO" if sat > 0.6 else ("MEDIO" if sat > 0.3 else "BASSO"),
        })
    return pd.DataFrame(rows).sort_values("Budget Consigliato", ascending=False)


# --------------------------------------------------------------- fogli
def _sheet_sintesi(wb, tab, tot_conv_att, tot_conv_sto):
    ws = wb.active; ws.title = "Sintesi_Strategica"
    cols = list(tab.columns); ncol = len(cols)
    ci = {h: i + 1 for i, h in enumerate(cols)}
    _title(ws, "MMM BUDGET OPTIMIZER  -  Cruscotto Strategico", ncol)

    tot_bud = tab["Budget Consigliato"].sum()
    tot_sp = tab["Spesa Storica"].sum()
    kpis = [("INVESTIMENTO SETT.", tot_bud / Q.WEEKS, EUR),
            ("INVESTIMENTO MENSILE", tot_bud / 3.0, EUR),
            ("CONV. ATTESE / SETT.", tot_conv_att / Q.WEEKS, NUM),
            ("CPA MEDIO PREVISTO", tot_bud / max(tot_conv_att, 1), EUR2)]
    span = max(ncol // 4, 2)
    for i, (lab, val, fmt) in enumerate(kpis):
        c0 = 1 + i * span; c1 = c0 + span - 1
        ws.merge_cells(start_row=3, start_column=c0, end_row=3, end_column=c1)
        lc = ws.cell(3, c0, lab); lc.fill = _fill(BLUE); lc.alignment = CENTER
        lc.font = Font(b=True, color=WHITE, size=10)
        ws.merge_cells(start_row=4, start_column=c0, end_row=5, end_column=c1)
        vc = ws.cell(4, c0, val); vc.fill = _fill(LIGHT); vc.number_format = fmt
        vc.font = Font(b=True, color=NAVY, size=18); vc.alignment = CENTER
    ws.row_dimensions[4].height = 24; ws.row_dimensions[5].height = 12

    band = 7; hdr = 8
    _band(ws, "ANALISI DI ALLOCAZIONE E VARIAZIONI", ncol, band)
    _headers(ws, cols, hdr)
    fmts = {"Budget Consigliato": EUR, "Mix %": PCT, "Spesa Storica": EUR,
            "Var. Budget EUR": EUR, "Var. Budget %": PCT, "Conv Storiche": NUM,
            "Conv Attese": NUM, "Var. Conv %": PCT, "CPA Storico": EUR2,
            "CPA Previsto": EUR2, "Var. CPA %": PCT}
    sat_c = {"ALTO": (RED, RED_T), "MEDIO": (YELLOW, YELLOW_T), "BASSO": (GREEN, GREEN_T)}
    for i, (_, row) in enumerate(tab.iterrows()):
        rr = hdr + 1 + i
        base = _fill(BAND) if i % 2 else None
        for j, col in enumerate(cols, 1):
            c = ws.cell(rr, j, row[col]); c.border = BORDER
            if base:
                c.fill = base
            if col in fmts:
                c.number_format = fmts[col]
            if col == "Campagna":
                c.font = Font(b=True)
            if col == "Saturazione":
                fg, tx = sat_c[row[col]]; c.fill = _fill(fg)
                c.font = Font(b=True, color=tx); c.alignment = Alignment(horizontal="center")
            if col in ("Var. Conv %", "Var. Budget %"):
                c.font = Font(color=GREEN_T if row[col] >= 0 else RED_T)
            if col == "Var. CPA %":
                c.font = Font(color=GREEN_T if row[col] <= 0 else RED_T)
    n = len(tab); last = hdr + n
    # riga TOTALE
    tr = last + 1
    for j in range(1, ncol + 1):
        cc = ws.cell(tr, j); cc.fill = _fill(NAVY)
        cc.font = Font(b=True, color=WHITE)
    ws.cell(tr, 1, "TOTALE")
    for col, val, fmt in (("Budget Consigliato", tot_bud, EUR),
                          ("Spesa Storica", tot_sp, EUR),
                          ("Var. Budget EUR", tot_bud - tot_sp, EUR),
                          ("Conv Storiche", tot_conv_sto, NUM),
                          ("Conv Attese", tot_conv_att, NUM)):
        c = ws.cell(tr, ci[col], val); c.number_format = fmt

    widths = [24, 14, 7, 12, 13, 11, 11, 11, 10, 11, 11, 10, 12]
    for j, w in enumerate(widths[:ncol], 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = "B9"
    ws.auto_filter.ref = f"A{hdr}:{get_column_letter(ncol)}{last}"

    # ---- grafici (2x2 a destra della tabella)
    cats = Reference(ws, min_col=ci["Campagna"], min_row=hdr + 1, max_row=last)
    col1, col2 = get_column_letter(ncol + 2), get_column_letter(ncol + 9)

    do = DoughnutChart(); do.title = "Mix Budget"; do.height = 8.4; do.width = 12.5
    do.add_data(Reference(ws, min_col=ci["Budget Consigliato"], min_row=hdr, max_row=last),
                titles_from_data=True)
    do.set_categories(cats); do.dataLabels = DataLabelList(); do.dataLabels.showPercent = True
    ws.add_chart(do, f"{col1}3")

    b1 = BarChart(); b1.type = "col"; b1.title = "Confronto Spesa (storica vs consigliata)"
    b1.height = 8.4; b1.width = 13
    b1.add_data(Reference(ws, min_col=ci["Spesa Storica"], min_row=hdr, max_row=last), titles_from_data=True)
    b1.add_data(Reference(ws, min_col=ci["Budget Consigliato"], min_row=hdr, max_row=last), titles_from_data=True)
    b1.set_categories(cats); ws.add_chart(b1, f"{col2}3")

    b2 = BarChart(); b2.type = "col"; b2.title = "CPA: storico vs previsto"
    b2.height = 8.4; b2.width = 12.5
    b2.add_data(Reference(ws, min_col=ci["CPA Storico"], min_row=hdr, max_row=last), titles_from_data=True)
    b2.add_data(Reference(ws, min_col=ci["CPA Previsto"], min_row=hdr, max_row=last), titles_from_data=True)
    b2.set_categories(cats); ws.add_chart(b2, f"{col1}20")

    b3 = BarChart(); b3.type = "col"; b3.title = "Conversioni: storiche vs attese"
    b3.height = 8.4; b3.width = 13
    b3.add_data(Reference(ws, min_col=ci["Conv Storiche"], min_row=hdr, max_row=last), titles_from_data=True)
    b3.add_data(Reference(ws, min_col=ci["Conv Attese"], min_row=hdr, max_row=last), titles_from_data=True)
    b3.set_categories(cats); ws.add_chart(b3, f"{col2}20")


def _sheet_mensile(wb, tot_bud, tot_conv_att, seas):
    ws = wb.create_sheet("Pianificazione_Mensile")
    _title(ws, "Piano Operativo Mensile", 5)
    _headers(ws, ["Mese", "Indice Stagionalita", "Azione Strategica",
                  "Budget Suggerito", "Conv. Stimate"], 3)
    s = seas.copy()
    if "region" in s.columns:
        s = s[s["region"].astype(str) == "*"]
    s["m"] = pd.to_datetime(s["week"]).dt.month
    idx = s.groupby("m")["seasonal_index"].mean()
    idx = (idx / idx.mean()).reindex(range(1, 13)).fillna(1.0)
    avg = tot_bud / 3.0; cpe = tot_conv_att / max(tot_bud, 1)
    for i, m in enumerate(range(1, 13)):
        rr = 4 + i; v = float(idx[m]); budget = avg * v
        az = "PUSH" if v > 1.03 else ("RIDUCI" if v < 0.97 else "MANTIENI")
        for j, x in enumerate([MESI[i], round(v, 2), az, budget, budget * cpe], 1):
            c = ws.cell(rr, j, x); c.border = BORDER
            if i % 2:
                c.fill = _fill(BAND)
        ws.cell(rr, 1).font = Font(b=True)
        ws.cell(rr, 3).font = Font(b=True); ws.cell(rr, 3).alignment = Alignment(horizontal="center")
        ws.cell(rr, 4).number_format = EUR; ws.cell(rr, 5).number_format = NUM
    ws.conditional_formatting.add("B4:B15", ColorScaleRule(
        start_type="min", start_color="F8696B", mid_type="percentile",
        mid_value=50, mid_color="FFEB84", end_type="max", end_color="63BE7B"))
    for j, w in enumerate([14, 18, 18, 18, 16], 1):
        ws.column_dimensions[get_column_letter(j)].width = w

    bar = BarChart(); bar.type = "col"; bar.title = "Budget e stagionalita' per mese"
    bar.height = 8.5; bar.width = 20
    bar.add_data(Reference(ws, min_col=4, min_row=3, max_row=15), titles_from_data=True)
    bar.set_categories(Reference(ws, min_col=1, min_row=4, max_row=15))
    line = LineChart()
    line.add_data(Reference(ws, min_col=2, min_row=3, max_row=15), titles_from_data=True)
    line.y_axis.axId = 200; line.y_axis.title = "indice"
    bar.y_axis.title = "budget (EUR)"; bar += line
    ws.add_chart(bar, "G3")


def _sheet_storico(wb, media):
    ws = wb.create_sheet("Metriche_Storiche")
    _title(ws, "Dettaglio Storico Canali", 5)
    _headers(ws, ["Campagna", "Spend Tot EUR", "Spend Medio Sett",
                  "Click Medio Sett", "CPA Medio Storico"], 3)
    nw = media["week"].nunique()
    g = media.groupby(["channel", "campaign"]).agg(
        spend=("spend", "sum"), clicks=("clicks", "sum"),
        conv=("platform_conversions", "sum")).reset_index()
    g["name"] = g["channel"].str.upper() + "_" + g["campaign"].str.upper()
    g = g.sort_values("spend", ascending=False)
    for i, (_, r) in enumerate(g.iterrows()):
        rr = 4 + i
        cpa = r["spend"] / r["conv"] if r["conv"] > 0 else 0.0
        for j, x in enumerate([r["name"], r["spend"], r["spend"] / nw,
                               r["clicks"] / nw, cpa], 1):
            c = ws.cell(rr, j, x); c.border = BORDER
            if i % 2:
                c.fill = _fill(BAND)
        ws.cell(rr, 2).number_format = EUR; ws.cell(rr, 3).number_format = EUR
        ws.cell(rr, 4).number_format = NUM; ws.cell(rr, 5).number_format = EUR2
    last = 3 + len(g)
    for j, w in enumerate([26, 16, 16, 16, 16], 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    bar = BarChart(); bar.type = "bar"; bar.title = "Spesa totale per campagna"
    bar.height = 9; bar.width = 16
    bar.add_data(Reference(ws, min_col=2, min_row=3, max_row=last), titles_from_data=True)
    bar.set_categories(Reference(ws, min_col=1, min_row=4, max_row=last))
    ws.add_chart(bar, "G3")


# --------------------------------------------------------------- entry point
def build_dashboard(canali, campagne, summary, media, seas, rev_per_conv, path) -> str:
    nw = media["week"].nunique()
    hist = (media.groupby("channel")["spend"].sum() / nw).to_dict()
    curves = Q.build_curves(summary, hist)
    tab = _campaign_table(canali, campagne, curves)
    tot_conv_att = float(tab["Conv Attese"].sum())
    tot_conv_sto = float(tab["Conv Storiche"].sum())

    wb = Workbook()
    _sheet_sintesi(wb, tab, tot_conv_att, tot_conv_sto)
    _sheet_mensile(wb, float(tab["Budget Consigliato"].sum()), tot_conv_att, seas)
    _sheet_storico(wb, media)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)
    return path
