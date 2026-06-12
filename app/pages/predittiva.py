"""Fase 2 — PREDITTIVA: curve di risposta, saturazione, previsto vs reale.

Il fit rapido (frequentista) gira in un callback sincrono (~30-60 s);
il ricalcolo bayesiano gira come BACKGROUND CALLBACK (diskcache): non
blocca la navigazione e al termine aggiorna le bande di incertezza HDI 90%.
"""
import json
import os

import dash
import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html

from app import store, theme

dash.register_page(__name__, path="/predittiva", name="Predittiva")


def layout():
    return html.Div([
        html.H2("Analisi predittiva"),
        html.P("Il modello stima, per ogni canale, la curva spesa → risultati "
               "(rendimenti decrescenti) e il livello di saturazione attuale.",
               className="text-secondary"),
        dbc.Row([
            dbc.Col(dbc.Button([html.I(className="bi bi-lightning-charge me-2"),
                                "Stima il modello"],
                               id="btn-fit", color="primary"), width="auto"),
            dbc.Col(dbc.Button([html.I(className="bi bi-cpu me-2"),
                                "Ricalcola con incertezza (background)"],
                               id="btn-bayes", color="primary", outline=True),
                    width="auto"),
            dbc.Col(html.Div(id="fit-status", className="pt-2"), width="auto"),
            dbc.Col(html.Div(id="bayes-status", className="pt-2")),
        ], className="g-2 mb-4", align="center"),
        dcc.Store(id="fit-done"), dcc.Store(id="bayes-done"),
        dbc.Row(id="saturation-row", className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Ritorno sull'investimento — previsione "
                               "candidature per livello di spesa"),
                dbc.CardBody(dcc.Graph(id="fig-curves"))],
                className="border-secondary"), md=7),
            dbc.Col(dbc.Card([
                dbc.CardHeader("Previsto vs reale (validazione del fit)"),
                dbc.CardBody(dcc.Graph(id="fig-fitted"))],
                className="border-secondary"), md=5),
        ], className="g-3"),
    ])


@callback(Output("fit-done", "data"), Output("fit-status", "children"),
          Input("btn-fit", "n_clicks"), prevent_initial_call=True,
          running=[(Output("btn-fit", "disabled"), True, False)])
def run_fit(_):
    st = store.get()
    import model as mmm_model                       # mmm/ e' nel sys.path
    st["fit"] = mmm_model.fit(st["df"], channels=st["channels"], controls=[])
    d = st["fit"]["diagnostics"]
    return True, html.Span([html.I(className="bi bi-check-circle me-2 text-success"),
                            f"Modello stimato · R² {d['r2']:.2f} · errore {d['mape']:.1%}"],
                           className="text-secondary")


@callback(Output("bayes-done", "data"), Output("bayes-status", "children"),
          Input("btn-bayes", "n_clicks"),
          background=True, prevent_initial_call=True,
          running=[(Output("btn-bayes", "disabled"), True, False),
                   (Output("bayes-status", "children"),
                    dbc.Spinner(size="sm", spinner_style={"marginRight": "8px"}),
                    "")])
def run_bayes(_):
    st = store.get()
    from core.mmm_bayes import fit_bayes
    anchor = st["fit"]["channels"] if st.get("fit") else None
    res = fit_bayes(st["df"], st["channels"], anchor=anchor)
    with open(store.BAYES_PATH, "w") as f:
        json.dump(res, f)
    return True, html.Span([html.I(className="bi bi-check-circle me-2 text-success"),
                            "Incertezza aggiornata — bande attive"],
                           className="text-secondary")


@callback(Output("saturation-row", "children"), Output("fig-curves", "figure"),
          Output("fig-fitted", "figure"),
          Input("fit-done", "data"), Input("bayes-done", "data"),
          Input("global-refresh", "data"))
def render(_f, _b, _r):
    st = store.get()
    df, channels = st["df"], st["channels"]
    fit = st.get("fit")
    bayes = store.bayes_results()

    from transforms import steady_state_response, channel_response

    # --- card di saturazione ------------------------------------------------
    cards = []
    if fit:
        for ch in channels:
            p = fit["channels"][ch]
            m = df[f"spend_{ch}"].mean()
            sat = steady_state_response(m, **p) / p["beta"] if p["beta"] else 0
            color = "success" if sat < .5 else "warning" if sat < .75 else "danger"
            cards.append(dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(ch.replace("_", " ").capitalize(), className="fw-bold"),
                dbc.Progress(value=sat * 100, color=color,
                             className="my-2", style={"height": "10px"}),
                html.Small(f"saturazione {sat:.0%} alla spesa media "
                           f"({m:,.0f} €/sett.)", className="text-secondary"),
            ]), className="border-secondary"), md=3))
    else:
        cards.append(dbc.Col(dbc.Alert(
            "Premi “Stima il modello” per calcolare curve e saturazione.",
            color="secondary"), md=12))

    # --- curve di risposta (+ bande HDI bayesiane) ----------------------------
    fig = go.Figure()
    for i, ch in enumerate(channels):
        col = theme.COLORS[i % len(theme.COLORS)]
        if bayes and ch in bayes.get("curves", {}):
            c = bayes["curves"][ch]
            r, g, b = (int(col[i:i + 2], 16) for i in (1, 3, 5))
            fig.add_scatter(x=c["spend"] + c["spend"][::-1],
                            y=c["p95"] + c["p05"][::-1],
                            fill="toself", line=dict(width=0),
                            fillcolor=f"rgba({r},{g},{b},0.18)",
                            name=f"{ch} (HDI 90%)", showlegend=False,
                            hoverinfo="skip")
            fig.add_scatter(x=c["spend"], y=c["p50"],
                            name=ch.replace("_", " ").capitalize(),
                            line=dict(color=col, width=2,
                                      dash=theme.DASHES[i % len(theme.DASHES)]))
        elif fit:
            grid = np.linspace(0, 2.5 * df[f"spend_{ch}"].mean(), 60)
            y = [steady_state_response(x, **fit["channels"][ch]) for x in grid]
            fig.add_scatter(x=grid, y=y,
                            name=ch.replace("_", " ").capitalize(),
                            line=dict(color=col, width=2,
                                      dash=theme.DASHES[i % len(theme.DASHES)]))
    fig.update_layout(xaxis_title="spesa settimanale (€)",
                      yaxis_title="risultati attesi / settimana")

    # --- previsto vs reale -----------------------------------------------------
    fig2 = go.Figure()
    if fit:
        pred = np.full(len(df), fit["baseline"]["alpha"], dtype=float)
        t = np.arange(len(df), dtype=float)
        w = 2 * np.pi * (t % 52) / 52
        fr = fit["baseline"]["fourier"]
        pred += fit["baseline"]["trend_per_week"] * t
        pred += fr[0] * np.sin(w) + fr[1] * np.cos(w)
        pred += fr[2] * np.sin(2 * w) + fr[3] * np.cos(2 * w)
        for c, g in fit.get("controls", {}).items():
            col_name = c if c in df.columns else f"ctrl_{c}"
            if col_name in df.columns:
                z = df[col_name].to_numpy(float)
                pred += g * (z - z.mean())
        for ch in channels:
            pred += channel_response(df[f"spend_{ch}"].to_numpy(float),
                                     **fit["channels"][ch])
        fig2.add_scatter(x=df["week"], y=df["applications"], name="reale",
                         mode="lines", line=dict(color="#888"))
        fig2.add_scatter(x=df["week"], y=pred, name="previsto",
                         mode="lines", line=dict(color=theme.ACCENT))
    return cards, theme.dark(fig, 420), theme.dark(fig2, 420)
