"""
Report PDF direzionale (MMM Budget Optimizer) — semplice e pulito.

Pagine:
  1. Cruscotto per CANALE  : KPI + tabella + grafici (Mix Budget, Confronto Spesa)
  2. Cruscotto per CAMPAGNA : tabella + grafici (CPA, Conversioni)
  3. Piano Mensile + Storico

Costruito con matplotlib (PdfPages): nessun rischio di grafici sovrapposti.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from . import dashboard as _xl
from . import quarter as Q

NAVY, BLUE, LIGHT = "#1F4E79", "#2E75B6", "#DDEBF7"
GREENT, REDT = "#1B7A3D", "#C0392B"
SAT = {"ALTO": "#F4B6B0", "MEDIO": "#FCE3A0", "BASSO": "#BFE3C5"}
GREY_S, BLUE_S, GREEN_S = "#A6A6A6", "#2E75B6", "#4C9F70"


def _k(v):
    return f"{v/1000:,.0f}k"


def _p(v):
    return f"{v:.0%}"


def _pv(v):
    return f"{v:+.0%}"


def _eur(v):
    return f"€{v:,.0f}"


def _band(fig, rect, text, fc=NAVY, tc="white", size=15, ha="center"):
    ax = fig.add_axes(rect); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, facecolor=fc, transform=ax.transAxes))
    ax.text(0.5 if ha == "center" else 0.015, 0.5, text, transform=ax.transAxes,
            ha=ha, va="center", color=tc, fontsize=size, fontweight="bold")


def _kpis(fig, y, items):
    n = len(items); w = 1 / n
    for i, (lab, val) in enumerate(items):
        ax = fig.add_axes([0.04 + i * (0.92 * w), y, 0.92 * w - 0.012, 0.085])
        ax.axis("off")
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, facecolor=LIGHT,
                                   edgecolor=BLUE, lw=1, transform=ax.transAxes))
        ax.text(0.5, 0.72, lab, transform=ax.transAxes, ha="center", va="center",
                fontsize=8.5, color=BLUE, fontweight="bold")
        ax.text(0.5, 0.34, val, transform=ax.transAxes, ha="center", va="center",
                fontsize=15, color=NAVY, fontweight="bold")


def _table(fig, rect, headers, rows, sat_col=None, dpct_cols=(), cpa_col=None, w0=0.20):
    ax = fig.add_axes(rect); ax.axis("off")
    tb = ax.table(cellText=rows, colLabels=headers, cellLoc="center",
                  bbox=[0, 0, 1, 1])
    tb.auto_set_font_size(False); tb.set_fontsize(8)
    nc = len(headers); wo = (1 - w0) / (nc - 1)
    for (r, c), cell in tb.get_celld().items():
        cell.set_width(w0 if c == 0 else wo)
        cell.set_edgecolor("#D9D9D9")
        if r == 0:
            cell.set_facecolor(BLUE); cell.set_text_props(color="white", fontweight="bold")
        else:
            if r % 2 == 0:
                cell.set_facecolor("#F4F8FC")
            if c == 0:
                cell.set_text_props(fontweight="bold")
            if sat_col is not None and c == sat_col:
                cell.set_facecolor(SAT[rows[r - 1][c]])
                cell.set_text_props(fontweight="bold")
            if c in dpct_cols:
                good = not str(rows[r - 1][c]).startswith("-")
                if cpa_col is not None and c == cpa_col:
                    good = str(rows[r - 1][c]).startswith("-")
                cell.set_text_props(color=GREENT if good else REDT)


def _alloc_rows(tab):
    headers = ["Voce", "Budget", "Mix", "Storico", "Δ Bud", "Conv\nstor",
               "Conv\natt", "Δ Conv", "CPA\nstor", "CPA\nprev", "Δ CPA", "Satur."]
    name = tab.columns[0]
    rows = []
    for _, r in tab.iterrows():
        rows.append([r[name], _k(r["Budget Consigliato"]), _p(r["Mix %"]),
                     _k(r["Spesa Storica"]), _pv(r["Var. Budget %"]),
                     f"{r['Conv Storiche']:,.0f}", f"{r['Conv Attese']:,.0f}",
                     _pv(r["Var. Conv %"]), _eur(r["CPA Storico"]),
                     _eur(r["CPA Previsto"]), _pv(r["Var. CPA %"]), r["Saturazione"]])
    return headers, rows


def _bar_compare(fig, rect, title, names, a, b, la, lb, colb):
    ax = fig.add_axes(rect)
    y = np.arange(len(names))[::-1]; h = 0.38
    ax.barh(y + h / 2, a, h, label=la, color=GREY_S)
    ax.barh(y - h / 2, b, h, label=lb, color=colb)
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=7)
    ax.set_title(title, fontsize=10, fontweight="bold", color=NAVY)
    ax.legend(fontsize=7, loc="lower right")
    ax.tick_params(axis="x", labelsize=7)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _page_alloc(pdf, title, tab):
    fig = plt.figure(figsize=(11.69, 8.27))
    _band(fig, [0.0, 0.94, 1.0, 0.06], title)
    tot_b = tab["Budget Consigliato"].sum(); tot_ca = tab["Conv Attese"].sum()
    _kpis(fig, 0.835, [("INVEST. SETT.", _eur(tot_b / Q.WEEKS)),
                       ("INVEST. MENSILE", _eur(tot_b / 3)),
                       ("CONV. ATTESE/SETT.", f"{tot_ca/Q.WEEKS:,.0f}"),
                       ("CPA MEDIO PREV.", _eur(tot_b / max(tot_ca, 1)))])
    headers, rows = _alloc_rows(tab)
    th = 0.30 if len(rows) <= 5 else 0.40
    _table(fig, [0.03, 0.80 - th, 0.94, th], headers, rows,
           sat_col=11, dpct_cols=(4, 7, 10), cpa_col=10)
    names = list(tab[tab.columns[0]])
    _bar_compare(fig, [0.06, 0.06, 0.40, 0.33 - (th - 0.30)], "Confronto Spesa (k€)",
                 names, [v / 1000 for v in tab["Spesa Storica"]],
                 [v / 1000 for v in tab["Budget Consigliato"]],
                 "storica", "consigliata", BLUE_S)
    cw = 0.34 - (th - 0.30)
    if len(names) <= 6:
        ax = fig.add_axes([0.56, 0.05, 0.36, cw])
        ax.pie(tab["Budget Consigliato"], labels=names, autopct="%1.0f%%",
               startangle=90, counterclock=False,
               textprops={"fontsize": 8}, wedgeprops={"width": 0.45})
    else:
        ax = fig.add_axes([0.60, 0.05, 0.36, cw])
        y = np.arange(len(names))[::-1]; vals = list(tab["Mix %"])
        ax.barh(y, [v * 100 for v in vals], color=BLUE_S)
        for yi, v in zip(y, vals):
            ax.text(v * 100, yi, f" {v:.0%}", va="center", fontsize=7)
        ax.set_yticks(y); ax.set_yticklabels(names, fontsize=7)
        ax.set_xlabel("% del budget", fontsize=7); ax.tick_params(labelsize=7)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    ax.set_title("Mix Budget", fontsize=10, fontweight="bold", color=NAVY)
    pdf.savefig(fig); plt.close(fig)


def _page_campagne_charts(pdf, tab):
    fig = plt.figure(figsize=(11.69, 8.27))
    _band(fig, [0.0, 0.94, 1.0, 0.06], "Cruscotto per CAMPAGNA — efficienza")
    names = list(tab["Campagna"])
    _bar_compare(fig, [0.07, 0.10, 0.40, 0.78], "CPA: storico vs previsto (€)",
                 names, list(tab["CPA Storico"]), list(tab["CPA Previsto"]),
                 "storico", "previsto", BLUE_S)
    _bar_compare(fig, [0.57, 0.10, 0.40, 0.78], "Conversioni: storiche vs attese",
                 names, list(tab["Conv Storiche"]), list(tab["Conv Attese"]),
                 "storiche", "attese", GREEN_S)
    pdf.savefig(fig); plt.close(fig)


def _page_mensile_storico(pdf, tot_bud, tot_ca, seas, media):
    fig = plt.figure(figsize=(11.69, 8.27))
    _band(fig, [0.0, 0.94, 1.0, 0.06], "Piano Mensile  &  Storico Canali")
    # mensile
    s = seas.copy()
    if "region" in s.columns:
        s = s[s["region"].astype(str) == "*"]
    s["m"] = __import__("pandas").to_datetime(s["week"]).dt.month
    idx = s.groupby("m")["seasonal_index"].mean()
    idx = (idx / idx.mean()).reindex(range(1, 13)).fillna(1.0)
    avg = tot_bud / 3; cpe = tot_ca / max(tot_bud, 1)
    mesi = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set",
            "Ott", "Nov", "Dic"]
    budgets = [avg * float(idx[m]) for m in range(1, 13)]
    ax = fig.add_axes([0.06, 0.50, 0.88, 0.36])
    bars = ax.bar(mesi, [b / 1000 for b in budgets], color=BLUE_S)
    ax2 = ax.twinx()
    ax2.plot(mesi, [float(idx[m]) for m in range(1, 13)], color=REDT, marker="o", lw=2)
    ax2.set_ylabel("indice stagionale", fontsize=8, color=REDT)
    ax.set_ylabel("budget mensile (k€)", fontsize=8)
    ax.set_title("Budget e stagionalità per mese (azione: PUSH se indice alto)",
                 fontsize=10, fontweight="bold", color=NAVY)
    ax.tick_params(labelsize=8); ax2.tick_params(labelsize=8)
    for s_ in ("top",):
        ax.spines[s_].set_visible(False)
    # storico tabella
    nw = media["week"].nunique()
    g = media.groupby(["channel", "campaign"]).agg(
        spend=("spend", "sum"), clicks=("clicks", "sum"),
        conv=("platform_conversions", "sum")).reset_index()
    g["name"] = g["channel"].str.upper() + "_" + g["campaign"].str.upper()
    g = g.sort_values("spend", ascending=False)
    headers = ["Campagna", "Spend Tot", "Spend/sett", "Click/sett", "CPA storico"]
    rows = [[r["name"], _k(r["spend"]), _eur(r["spend"] / nw),
             f"{r['clicks']/nw:,.0f}", _eur(r["spend"] / max(r["conv"], 1))]
            for _, r in g.iterrows()]
    _band(fig, [0.0, 0.43, 1.0, 0.04], "Dettaglio Storico Canali", fc=BLUE, size=11)
    _table(fig, [0.05, 0.04, 0.90, 0.36], headers, rows, w0=0.42)
    pdf.savefig(fig); plt.close(fig)


def build_pdf(canali, campagne, summary, media, seas, rev_per_conv, path) -> str:
    nw = media["week"].nunique()
    hist = (media.groupby("channel")["spend"].sum() / nw).to_dict()
    curves = Q.build_curves(summary, hist)
    ch = _xl._channel_table(canali, curves)
    cp = _xl._campaign_table(canali, campagne, curves)
    with PdfPages(path) as pdf:
        _page_alloc(pdf, "MMM BUDGET OPTIMIZER — Cruscotto per CANALE", ch)
        _page_alloc(pdf, "MMM BUDGET OPTIMIZER — Cruscotto per CAMPAGNA", cp)
        _page_campagne_charts(pdf, cp)
        _page_mensile_storico(pdf, ch["Budget Consigliato"].sum(),
                              ch["Conv Attese"].sum(), seas, media)
    return path
