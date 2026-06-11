"""Pagina 4 — BUDGET PER CAMPAGNA: dal budget di canale al budget di campagna.

Attribution multi-touch sui percorsi utente (rimozione di un touchpoint dal
grafo = suo contributo reale). Ottimizzabile per volume o valore economico.
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

dash.register_page(__name__, path="/mta",
                   name="4. Attribuzione per campagna", order=3)

CAPTION = "text-secondary small mt-2 mb-0"

TBL_STYLE = dict(
    style_header={"backgroundColor": "#14202F", "color": "#E8ECF1",
                  "border": "1px solid #2D3848"},
    style_cell={"backgroundColor": "#1A2332", "color": "#E8ECF1",
                "border": "1px solid #2D3848", "fontSize": 14,
                "fontFamily": "Tahoma, Geneva, Verdana, sans-serif"},
)
_cache: dict = {}


def layout():
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("4. Attribuzione per campagna"), md=8),
            dbc.Col(dcc.Upload(
                id="upload-mta",
                children=dbc.Button("Carica percorsi (CSV)",
                                    outline=True, color="info"),
                multiple=False), md=4, className="text-end"),
        ], align="center"),
        html.P("Le pagine precedenti decidono quanto budget dare a ogni canale. "
               "Qui scendi di un livello: quanto budget dare a ogni singola "
               "campagna, in base a quanto ciascuna contribuisce davvero alle "
               "conversioni lungo i percorsi degli utenti.",
               className="text-secondary"),
        html.Div(id="mta-feedback"),
        dbc.Row([
            dbc.Col([dbc.Label("Cosa vuoi massimizzare?"),
                     dbc.RadioItems(id="mta-metric", inline=True, value="volume",
                                    options=[{"label": " Numero di conversioni",
                                              "value": "volume"},
                                             {"label": " Valore economico (EUR)",
                                              "value": "utility"}])], md=5),
            dbc.Col([dbc.Label("Mostra solo un canale"),
                     dcc.Dropdown(id="mta-channel", value="ALL",
                                  clearable=False)], md=3),
            dbc.Col(html.Div(id="mta-source", className="text-secondary pt-4"),
                    md=4, className="text-end"),
        ], className="mb-3 g-3"),
        dbc.Row(id="mta-kpi", className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Contributo reale di ogni campagna alle "
                               "conversioni"),
                dbc.CardBody([
                    dcc.Graph(id="fig-attr"),
                    html.P("Ogni barra è una campagna, colorata per canale: più è "
                           "lunga, più la campagna è decisiva nel portare le "
                           "persone alla conversione. Usa il filtro in alto per "
                           "vedere un canale alla volta.", className=CAPTION)])],
                className="border-secondary"), md=6),
            dbc.Col(dbc.Card([
                dbc.CardHeader("Come dividere il budget del canale tra le "
                               "campagne"),
                dbc.CardBody([
                    dcc.Graph(id="fig-split"),
                    html.P("Il budget di ogni canale (deciso nella pagina "
                           "Ottimizzazione del budget) viene ripartito tra le "
                           "sue campagne in proporzione al loro contributo.",
                           className=CAPTION)])],
                className="border-secondary"), md=6),
        ], className="g-3 mb-3"),
        dbc.Card([dbc.CardHeader("Piano per campagna (€/settimana)"),
                  dbc.CardBody(html.Div(id="mta-table"))],
                 className="border-secondary"),
        html.Div(dcc.Link("<- Torna ad Analisi dei dati", href="/",
                          className="text-info"),
                 className="text-end mt-4"),
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


def _channel_of(tp: str) -> str:
    return tp.split(":", 1)[0] if ":" in tp else tp


@callback(Output("mta-kpi", "children"), Output("fig-attr", "figure"),
          Output("fig-split", "figure"), Output("mta-table", "children"),
          Output("mta-source", "children"), Output("mta-feedback", "children"),
          Output("mta-channel", "options"),
          Input("mta-metric", "value"), Input("mta-channel", "value"),
          Input("upload-mta", "contents"), State("upload-mta", "filename"))
def render(metric, ch_filter, contents, filename):
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

    tp_channels = sorted({_channel_of(tp) for tp in attr["touchpoint"]})
    ch_options = ([{"label": "Tutti i canali", "value": "ALL"}]
                  + [{"label": c, "value": c} for c in tp_channels])
    color_of = {c: theme.COLORS[i % len(theme.COLORS)]
                for i, c in enumerate(tp_channels)}
    if ch_filter and ch_filter != "ALL" and ch_filter in tp_channels:
        attr_view = attr[attr["touchpoint"].map(_channel_of) == ch_filter]
        split_view = (split[split["canale"] == ch_filter]
                      if not split.empty else split)
    else:
        attr_view, split_view = attr, split

    unit = "€" if metric == "utility" else "conversioni"
    kpis = [
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("Percorsi analizzati", className="text-secondary small"),
            html.H4(f"{agg['n_paths']:,}"),
            html.Small("sequenze di contatti utente", className="text-secondary"),
        ]), className="border-secondary h-100"), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("Conversioni complete", className="text-secondary small"),
            html.H4(f"{agg['total_conversions']:,}"),
            html.Small("percorsi finiti in conversione",
                       className="text-secondary"),
        ]), className="border-secondary h-100"), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("Valore economico totale", className="text-secondary small"),
            html.H4(f"{agg['total_utility']:,.0f} €"),
            html.Small("generato dalle conversioni", className="text-secondary"),
        ]), className="border-secondary h-100"), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div("Tasso di conversione medio", className="text-secondary small"),
            html.H4(f"{attr.attrs['base_conversion_prob']:.2%}"),
            html.Small("quota di percorsi che converte",
                       className="text-secondary"),
        ]), className="border-secondary h-100"), md=3),
    ]

    top = attr_view.head(12).iloc[::-1]
    f1 = go.Figure(go.Bar(
        x=top["attribuito"], y=top["touchpoint"], orientation="h",
        marker_color=[color_of[_channel_of(tp)] for tp in top["touchpoint"]]))
    f1.update_layout(xaxis_title=f"contributo reale ({unit})", height=420)
    if attr_view.empty:
        f1.add_annotation(text="Nessuna campagna per questo canale",
                          showarrow=False, font=dict(color=theme.AXIS))

    f2 = go.Figure()
    if not split_view.empty:
        for ch, grp in split_view.groupby("canale"):
            f2.add_bar(x=grp["campagna"].str.split(":").str[-1],
                       y=grp["budget_campagna"], name=ch,
                       marker_color=color_of.get(ch, theme.COLORS[0]))
        f2.update_layout(yaxis_title="budget campagna (€/sett.)",
                         barmode="group", height=420)
    else:
        f2.add_annotation(text="Nessuna corrispondenza tra i canali del piano "
                               "e le campagne dei percorsi",
                          showarrow=False, font=dict(color=theme.AXIS))

    tbl = split_view.copy()
    if not tbl.empty:
        tbl["quota_intra_canale"] = (tbl["quota_intra_canale"] * 100).round(1)
        tbl["budget_campagna"] = tbl["budget_campagna"].round(0)
        tbl["attribuito"] = tbl["attribuito"].round(1)
        tbl.columns = ["canale", "campagna", "quota del canale %",
                       "budget €/sett.", f"contributo reale ({unit})"]
        table = dash_table.DataTable(
            data=tbl.to_dict("records"),
            columns=[{"name": c, "id": c} for c in tbl.columns], **TBL_STYLE)
    else:
        table = html.Div("—", className="text-secondary")

    src = html.Small([html.I(className="bi bi-database me-1"), source,
                      "  ·  budget canale: ",
                      html.Em("piano ottimizzato" if st.get("plan")
                              else "spesa media storica (per il piano vai a "
                                   "Ottimizzazione del budget)")])
    return (kpis, theme.dark(f1, 420), theme.dark(f2, 420), table, src,
            feedback, ch_options)
