"""Livello tattico — MTA: dal budget di canale (MMM) al budget di campagna.

Attribution multi-touch con catene di Markov (removal effect) sui percorsi
utente. Ottimizzabile per VOLUME (conversioni) o per UTILITY (fatturato).
Completamente agnostico: stati e campagne scoperti dai dati.
"""
import base64
import io

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dash_table, dcc, html

from app import store, theme
from core import mta_markov as mk

dash.register_page(__name__, path="/mta", name="MTA")

TBL_STYLE = dict(
    style_header={"backgroundColor": "#1a1d24", "color": "#e8e9ed",
                  "border": "1px solid #2a2e3a"},
    style_cell={"backgroundColor": "#12141a", "color": "#e8e9ed",
                "border": "1px solid #2a2e3a", "fontSize": 14},
)
_cache: dict = {}


def layout():
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("MTA — riparto tattico per campagna"), md=8),
            dbc.Col(dcc.Upload(
                id="upload-mta",
                children=dbc.Button([html.I(className="bi bi-upload me-2"),
                                     "Carica percorsi (CSV)"],
                                    outline=True, color="primary"),
                multiple=False), md=4, className="text-end"),
        ], align="center"),
        html.P(["Livello 1 (MMM) decide quanto budget al canale; "
                "Livello 2 (MTA, catene di Markov) decide come dividerlo "
                "tra le campagne, in base al contributo reale di ciascun "
                "touchpoint nei percorsi utente (removal effect)."],
               className="text-secondary"),
        html.Div(id="mta-feedback"),
        dbc.Row([
            dbc.Col([dbc.Label("Ottimizza per:"),
                     dbc.RadioItems(id="mta-metric", inline=True, value="volume",
                                    options=[{"label": " Volume (conversioni)",
                                              "value": "volume"},
                                             {"label": " Utility (fatturato)",
                                              "value": "utility"}])], md=6),
            dbc.Col(html.Div(id="mta-source", className="text-secondary pt-3"),
                    md=6, className="text-end"),
        ], className="mb-3"),
        dbc.Row(id="mta-kpi", className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Contributo dei touchpoint (removal effect)"),
                dbc.CardBody(dcc.Graph(id="fig-attr"))],
                className="border-secondary"), md=6),
            dbc.Col(dbc.Card([
                dbc.CardHeader("Riparto del budget di canale tra le campagne"),
                dbc.CardBody(dcc.Graph(id="fig-split"))],
                className="border-secondary"), md=6),
        ], className="g-3 mb-3"),
        dbc.Card([dbc.CardHeader("Piano tattico per campagna"),
                  dbc.CardBody(html.Div(id="mta-table"))],
                 className="border-secondary"),
    ])


def _aggregates(contents=None, filename=None):
    if contents:
        raw = base64.b64decode(contents.split(",", 1)[1])
        df = pd.read_csv(io.BytesIO(raw))
        _cache["agg"] = mk.to_aggregates(df)
        _cache["source"] = f"file caricato: {filename} ({len(df):,} percorsi)"
    if "agg" not in _cache:
        _cache["agg"] = store.mta_aggregates()
        _cache["source"] = (f"dataset dimostrativo "
                            f"({_cache['agg']['n_paths']:,} percorsi sintetici)")
    return _cache["agg"], _cache["source"]


@callback(Output("mta-kpi", "children"), Output("fig-attr", "figure"),
          Output("fig-split", "figure"), Output("mta-table", "children"),
          Output("mta-source", "children"), Output("mta-feedback", "children"),
          Input("mta-metric", "value"), Input("upload-mta", "contents"),
          State("upload-mta", "filename"))
def render(metric, contents, filename):
    feedback = None
    try:
        agg, source = _aggregates(contents, filename)
    except Exception as e:
        _cache.pop("agg", None)
        agg, source = _aggregates()
        feedback = dbc.Alert(f"File non riconosciuto: {e}", color="danger",
                             dismissable=True)

    attr = mk.attribution(agg, metric)
    st = store.get()
    plan = st.get("plan") or {ch: st["constraints"][ch]["mean"]
                              for ch in st["channels"]}
    split = mk.split_channel_budget(attr, plan)

    unit = "€" if metric == "utility" else "conv."
    kpis = [
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("Percorsi analizzati", className="text-secondary small"),
            html.H4(f"{agg['n_paths']:,}")]), className="border-secondary"), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("Conversioni complete", className="text-secondary small"),
            html.H4(f"{agg['total_conversions']:,}")]),
            className="border-secondary"), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("Utility totale", className="text-secondary small"),
            html.H4(f"{agg['total_utility']:,.0f} €")]),
            className="border-secondary"), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("P(conversione) del grafo", className="text-secondary small"),
            html.H4(f"{attr.attrs['base_conversion_prob']:.2%}")]),
            className="border-secondary"), md=3),
    ]

    top = attr.head(12).iloc[::-1]
    f1 = go.Figure(go.Bar(x=top["attribuito"], y=top["touchpoint"],
                          orientation="h", marker_color=theme.ACCENT))
    f1.update_layout(xaxis_title=f"valore attribuito ({unit})", height=420)

    f2 = go.Figure()
    if not split.empty:
        for i, (ch, grp) in enumerate(split.groupby("canale")):
            f2.add_bar(x=grp["campagna"].str.split(":").str[-1],
                       y=grp["budget_campagna"], name=ch,
                       marker_color=theme.COLORS[i % len(theme.COLORS)])
        f2.update_layout(yaxis_title="budget campagna (€/sett.)",
                         barmode="group", height=420)
    else:
        f2.add_annotation(text="Nessuna corrispondenza tra i canali del piano "
                               "MMM e i touchpoint dei percorsi",
                          showarrow=False, font=dict(color="#888"))

    tbl = split.copy()
    if not tbl.empty:
        tbl["quota_intra_canale"] = (tbl["quota_intra_canale"] * 100).round(1)
        tbl["budget_campagna"] = tbl["budget_campagna"].round(0)
        tbl["attribuito"] = tbl["attribuito"].round(1)
        tbl.columns = ["canale", "campagna", "quota %", "budget €/sett.",
                       f"attribuito ({unit})"]
        table = dash_table.DataTable(
            data=tbl.to_dict("records"),
            columns=[{"name": c, "id": c} for c in tbl.columns], **TBL_STYLE)
    else:
        table = html.Div("—", className="text-secondary")

    src = html.Small([html.I(className="bi bi-database me-1"), source,
                      "  ·  budget canale: ",
                      html.Em("piano ottimizzato" if st.get("plan")
                              else "spesa media storica (ottimizza nella "
                                   "pagina Prescrittiva)")])
    return kpis, theme.dark(f1, 420), theme.dark(f2, 420), table, src, feedback
