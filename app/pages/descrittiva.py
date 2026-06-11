"""Fase 1 — DESCRITTIVA: esplorazione storica di KPI, leve e fattori esterni."""
import base64
import io

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html

from app import store, theme

dash.register_page(__name__, path="/", name="Descrittiva")


def _kpi(label, value, sub="", color="info"):
    return dbc.Card(dbc.CardBody([
        html.Div(label, className="text-secondary small"),
        html.H3(value, className=f"text-{color} mb-0"),
        html.Div(sub, className="text-secondary small"),
    ]), className="border-secondary h-100")


def layout():
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("Analisi descrittiva"), md=8),
            dbc.Col(dcc.Upload(
                id="upload-mmm",
                children=dbc.Button([html.I(className="bi bi-upload me-2"),
                                     "Carica il tuo CSV"], outline=True, color="info"),
                multiple=False), md=4, className="text-end"),
        ], align="center"),
        html.P("Cosa e' successo: spesa per leva, risultati e fattori esterni. "
               "La struttura del file viene riconosciuta automaticamente.",
               className="text-secondary"),
        html.Div(id="upload-feedback"),
        dbc.Row(id="kpi-row", className="g-3 mb-4"),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardHeader("Le leve: spesa per canale"),
                              dbc.CardBody(dcc.Graph(id="fig-spend"))],
                             className="border-secondary"), md=7),
            dbc.Col(dbc.Card([dbc.CardHeader("Il KPI: risultati nel tempo"),
                              dbc.CardBody(dcc.Graph(id="fig-target"))],
                             className="border-secondary"), md=5),
        ], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardHeader("Fattori esterni (variabili di controllo)"),
                              dbc.CardBody(dcc.Graph(id="fig-controls"))],
                             className="border-secondary"), md=7),
            dbc.Col(dbc.Card([dbc.CardHeader("Mix di spesa storico"),
                              dbc.CardBody(dcc.Graph(id="fig-mix"))],
                             className="border-secondary"), md=5),
        ], className="g-3"),
    ])


@callback(
    Output("kpi-row", "children"), Output("fig-spend", "figure"),
    Output("fig-target", "figure"), Output("fig-controls", "figure"),
    Output("fig-mix", "figure"), Output("upload-feedback", "children"),
    Output("global-refresh", "data"),
    Input("upload-mmm", "contents"), State("upload-mmm", "filename"),
)
def render(contents, filename):
    feedback = None
    if contents:
        try:
            raw = base64.b64decode(contents.split(",", 1)[1])
            df_raw = pd.read_csv(io.BytesIO(raw))
            store.load(df_raw)
            feedback = dbc.Alert(
                f"File '{filename}' riconosciuto: "
                f"{len(store.get()['channels'])} canali, "
                f"{len(store.get()['df'])} periodi.", color="success",
                dismissable=True)
        except Exception as e:
            feedback = dbc.Alert(f"File non riconosciuto: {e}", color="danger",
                                 dismissable=True)
    st = store.get()
    df, channels = st["df"], st["channels"]
    spend_cols = [f"spend_{c}" for c in channels]
    tot_spend = float(df[spend_cols].sum().sum())
    tot_target = float(df["applications"].sum())
    cpa = tot_spend / tot_target if tot_target else 0

    kpis = [
        dbc.Col(_kpi("Periodi analizzati", f"{len(df)}",
                     "settimane di storico"), md=3),
        dbc.Col(_kpi("Spesa totale", f"{tot_spend:,.0f} €",
                     f"{len(channels)} canali"), md=3),
        dbc.Col(_kpi("Risultati totali", f"{tot_target:,.0f}",
                     "conversioni (KPI)"), md=3),
        dbc.Col(_kpi("Costo per risultato", f"{cpa:,.2f} €",
                     "medio sull'intero periodo", "warning"), md=3),
    ]

    f1 = go.Figure()
    for c in channels:
        f1.add_scatter(x=df["week"], y=df[f"spend_{c}"], name=c, mode="lines")
    f2 = go.Figure(go.Scatter(x=df["week"], y=df["applications"],
                              mode="lines", name="KPI",
                              line=dict(color="#4cc9f0", width=2)))
    f3 = go.Figure()
    ctrl = [c for c in df.columns if c.startswith("ctrl_")]
    for c in ctrl:
        f3.add_scatter(x=df["week"], y=df[c], name=c[5:], mode="lines")
    if not ctrl:
        f3.add_annotation(text="Nessun fattore esterno nel dataset",
                          showarrow=False, font=dict(color="#888"))
    f4 = go.Figure(go.Pie(labels=channels,
                          values=[df[f"spend_{c}"].sum() for c in channels],
                          hole=.55))
    return (kpis, theme.dark(f1), theme.dark(f2), theme.dark(f3),
            theme.dark(f4, 380), feedback, len(df))
