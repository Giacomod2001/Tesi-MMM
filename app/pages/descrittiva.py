"""Pagina 1 — ANALISI: cosa è successo (spesa, risultati, fattori esterni)."""
import base64
import io

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html

from app import store, theme

dash.register_page(__name__, path="/", name="1 · Analisi", order=0)

CAPTION = "text-secondary small mt-2 mb-0"
RULE = {"settimanale": None, "mensile": "ME", "trimestrale": "QE"}


def _kpi(label, value, sub="", color="info"):
    return dbc.Card(dbc.CardBody([
        html.Div(label, className="text-secondary small"),
        html.H3(value, className=f"text-{color} mb-0"),
        html.Div(sub, className="text-secondary small"),
    ]), className="border-secondary h-100")


def _aggrega(d: pd.DataFrame, vista: str) -> pd.DataFrame:
    rule = RULE.get(vista)
    if not rule:
        return d
    return d.set_index("week").resample(rule).mean().reset_index()


def layout():
    return html.Div([
        dbc.Row([
            dbc.Col(html.H2("1 · Analisi — cosa è successo"), md=8),
            dbc.Col(dcc.Upload(
                id="upload-mmm",
                children=dbc.Button([html.I(className="bi bi-upload me-2"),
                                     "Carica il tuo CSV"], outline=True, color="info"),
                multiple=False), md=4, className="text-end"),
        ], align="center"),
        html.P("Per cominciare: guarda quanto hai speso su ogni canale, che "
               "risultati hai ottenuto e quali fattori esterni hanno influito. "
               "Senza caricare nulla, l'app usa un dataset dimostrativo.",
               className="text-secondary"),
        html.Div(id="upload-feedback"),
        dbc.Row(id="kpi-row", className="g-3 mb-4"),
        dbc.Row([
            dbc.Col([
                dbc.Label("Canali da mostrare", className="small text-secondary"),
                dbc.Checklist(id="ana-channels", inline=True, value=[], options=[]),
            ], md=7),
            dbc.Col([
                dbc.Label("Vista temporale", className="small text-secondary"),
                dbc.RadioItems(
                    id="ana-vista", inline=True, value="mensile",
                    options=[{"label": v.capitalize(), "value": v}
                             for v in ("settimanale", "mensile", "trimestrale")]),
            ], md=5, className="text-md-end"),
        ], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("🎛️ Le tue Leve — spesa per canale"),
                dbc.CardBody([
                    dcc.Graph(id="fig-spend"),
                    html.P("Suggerimento: usa le caselle qui sopra (o clicca la "
                           "legenda) per mostrare/nascondere i canali. Nella vista "
                           "settimanale i “buchi” sono pause campagna.",
                           className=CAPTION)])],
                className="border-secondary"), md=7),
            dbc.Col(dbc.Card([
                dbc.CardHeader("🎯 Il tuo KPI — risultati nel tempo"),
                dbc.CardBody([
                    dcc.Graph(id="fig-target"),
                    html.P("La linea tratteggiata è la media mobile a 4 settimane: "
                           "segui quella per leggere il trend senza il rumore "
                           "settimanale.", className=CAPTION)])],
                className="border-secondary"), md=5),
        ], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("🌍 Fattori Esterni — non dipendono dal tuo budget"),
                dbc.CardBody([
                    dcc.Graph(id="fig-controls"),
                    html.P("Queste variabili (es. domanda di mercato) influenzano i "
                           "risultati ma non le controlli tu: il modello le usa per "
                           "non attribuire ai canali meriti non loro.",
                           className=CAPTION)])],
                className="border-secondary"), md=7),
            dbc.Col(dbc.Card([
                dbc.CardHeader("🥧 Com'è diviso il budget oggi"),
                dbc.CardBody([
                    dcc.Graph(id="fig-mix"),
                    html.P("Quota di spesa storica per canale: è il punto di "
                           "partenza che l'ottimizzazione proverà a migliorare.",
                           className=CAPTION)])],
                className="border-secondary"), md=5),
        ], className="g-3"),
        html.Div(dbc.Button(["Prossimo passo: 2 · Stima & Risposta",
                             html.I(className="bi bi-arrow-right ms-2")],
                            href="/predittiva", color="info", outline=True),
                 className="text-end mt-4"),
    ])


@callback(
    Output("kpi-row", "children"), Output("upload-feedback", "children"),
    Output("ana-channels", "options"), Output("ana-channels", "value"),
    Output("global-refresh", "data"),
    Input("upload-mmm", "contents"), State("upload-mmm", "filename"),
)
def load_data(contents, filename):
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
                     f"su {len(channels)} canali"), md=3),
        dbc.Col(_kpi("Risultati totali", f"{tot_target:,.0f}",
                     "conversioni ottenute (KPI)"), md=3),
        dbc.Col(_kpi("Costo per risultato", f"{cpa:,.2f} €",
                     "in media: quanto è costata ogni conversione",
                     "warning"), md=3),
    ]
    options = [{"label": c, "value": c} for c in channels]
    return kpis, feedback, options, channels, len(df)


@callback(
    Output("fig-spend", "figure"), Output("fig-target", "figure"),
    Output("fig-controls", "figure"), Output("fig-mix", "figure"),
    Input("ana-channels", "value"), Input("ana-vista", "value"),
    Input("global-refresh", "data"),
)
def figures(sel, vista, _refresh):
    st = store.get()
    df, channels = st["df"], st["channels"]
    sel = [c for c in (sel or channels) if c in channels] or channels

    agg = _aggrega(df, vista)

    f1 = go.Figure()
    for c in sel:
        f1.add_scatter(x=agg["week"], y=agg[f"spend_{c}"], name=c, mode="lines")
    f1.update_layout(yaxis_title="spesa (€/settimana, media)", xaxis_title="")

    # KPI + media mobile 4 settimane (calcolata sul dato settimanale)
    ma = df["applications"].rolling(4, min_periods=1).mean()
    kpi = pd.DataFrame({"week": df["week"], "kpi": df["applications"], "ma": ma})
    kpi_agg = _aggrega(kpi, vista)
    f2 = go.Figure([
        go.Scatter(x=kpi_agg["week"], y=kpi_agg["kpi"], mode="lines",
                   name="Risultati", line=dict(color="#4cc9f0", width=2)),
        go.Scatter(x=kpi_agg["week"], y=kpi_agg["ma"], mode="lines",
                   name="Trend (media mobile 4 sett.)",
                   line=dict(color="#ffd166", width=2, dash="dash")),
    ])
    f2.update_layout(yaxis_title="risultati / settimana", xaxis_title="")

    f3 = go.Figure()
    ctrl = [c for c in df.columns if c.startswith("ctrl_")]
    for c in ctrl:
        f3.add_scatter(x=agg["week"], y=agg[c], name=c[5:].replace("_", " "),
                       mode="lines")
    if not ctrl:
        f3.add_annotation(text="Nessun fattore esterno nel dataset: puoi "
                               "caricarlo insieme al CSV",
                          showarrow=False, font=dict(color="#888"))

    f4 = go.Figure(go.Pie(labels=sel,
                          values=[df[f"spend_{c}"].sum() for c in sel],
                          hole=.55))
    return theme.dark(f1), theme.dark(f2), theme.dark(f3), theme.dark(f4, 380)
