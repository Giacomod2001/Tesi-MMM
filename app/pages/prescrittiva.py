"""Fase 3 — PRESCRITTIVA: ottimizzatore del budget inter-canale (livello strategico).

I vincoli min/max per canale sono PRE-COMPILATI dallo storico (nessuna
configurazione manuale richiesta) ma restano modificabili: e' il punto di
ingresso della conoscenza del manager (human-in-the-middle).
"""
import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dash_table, dcc, html

from app import store, theme

dash.register_page(__name__, path="/prescrittiva", name="Prescrittiva")

TBL_STYLE = dict(
    style_header={"backgroundColor": "#1a1d24", "color": "#e8e9ed",
                  "border": "1px solid #2a2e3a"},
    style_cell={"backgroundColor": "#12141a", "color": "#e8e9ed",
                "border": "1px solid #2a2e3a", "fontSize": 14,
                "fontFamily": "inherit"},
)


def layout():
    st = store.get()
    cons = st["constraints"]
    weekly = sum(c["mean"] for c in cons.values())
    rows = [{"canale": ch, "spesa media": round(c["mean"]),
             "min": c["min"], "max": c["max"]} for ch, c in cons.items()]
    return html.Div([
        html.H2("Ottimizzazione del budget (livello strategico)"),
        html.P("Quanto budget a ciascun CANALE per massimizzare i risultati. "
               "Il riparto tattico tra le campagne avviene nella pagina MTA.",
               className="text-secondary"),
        dbc.Row([
            dbc.Col([
                dbc.Label("Budget settimanale (€)"),
                dbc.Input(id="opt-budget", type="number", value=round(weekly),
                          min=1000, step=500),
            ], md=3),
            dbc.Col([
                dbc.Label("Variazione massima per canale vs storico"),
                dcc.Slider(id="opt-maxchange", min=0.1, max=1.0, step=0.05,
                           value=0.5, marks={.1: "±10%", .5: "±50%", 1: "libero"}),
            ], md=5),
            dbc.Col(dbc.Button([html.I(className="bi bi-magic me-2"),
                                "Ottimizza"], id="btn-opt", color="primary",
                               size="lg", className="mt-4"), md=2),
        ], className="g-3 mb-3"),
        dbc.Card([
            dbc.CardHeader("Vincoli per canale — pre-compilati dallo storico, "
                           "modificabili"),
            dbc.CardBody(dash_table.DataTable(
                id="constraints-table", data=rows,
                columns=[{"name": c, "id": c,
                          "editable": c in ("min", "max"),
                          "type": "numeric"} for c in rows[0]],
                editable=True, **TBL_STYLE)),
        ], className="border-secondary mb-4"),
        html.Div(id="opt-result"),
    ])


@callback(Output("opt-result", "children"),
          Input("btn-opt", "n_clicks"),
          State("opt-budget", "value"), State("opt-maxchange", "value"),
          State("constraints-table", "data"), prevent_initial_call=True,
          running=[(Output("btn-opt", "disabled"), True, False)])
def optimize(_, budget, max_change, rows):
    st = store.get()
    if not st.get("fit"):
        return dbc.Alert("Stima prima il modello nella pagina Predittiva.",
                         color="warning")
    import allocator
    channels = st["channels"]
    cur = {ch: st["constraints"][ch]["mean"] for ch in channels}
    min_sp = {r["canale"]: float(r["min"]) for r in rows if r.get("min")}
    max_sp = {r["canale"]: float(r["max"]) for r in rows if r.get("max")}
    try:
        table = allocator.optimize_budget(
            st["fit"]["channels"], cur, total_budget=float(budget),
            min_spend=min_sp or None, max_spend=max_sp or None,
            max_change_pct=max_change if max_change < 1 else None,
            channels=channels)
    except (ValueError, RuntimeError) as e:
        return dbc.Alert(f"Vincoli incompatibili: {e}", color="danger")

    st["plan"] = {r["canale"]: float(r["spesa_ottimale"])
                  for _, r in table.iterrows()}
    s = table.attrs["summary"]

    fig = go.Figure()
    labels = [c.replace("_", " ").capitalize() for c in table["canale"]]
    fig.add_bar(x=labels, y=table["spesa_corrente"],
                name="spesa attuale", marker_color="#64748b")
    fig.add_bar(x=labels, y=table["spesa_ottimale"],
                name="spesa ottimale", marker_color=theme.ACCENT)
    fig.update_layout(barmode="group", yaxis_title="€/settimana")

    fig2 = go.Figure(go.Bar(
        x=labels, y=table["roas_marg_ottimale_x1000"],
        marker_color="#93c5fd", name="ROAS marginale post"))
    fig2.add_hline(y=float(table["roas_marg_ottimale_x1000"].mean()),
                   line_dash="dot", line_color="#aaa",
                   annotation_text="rendimenti marginali pareggiati")
    fig2.update_layout(yaxis_title="risultati / 1.000 € marginali")

    detail = table[["canale", "spesa_corrente", "spesa_ottimale",
                    "variazione_pct", "candidature_ottimali"]].copy()
    detail.columns = ["canale", "attuale €", "ottimale €", "Δ%", "risultati att."]
    detail = detail.round({"attuale €": 0, "ottimale €": 0, "risultati att.": 1})
    detail["Δ%"] = (table["variazione_pct"] * 100).round(1)

    return html.Div([
        dbc.Row([
            dbc.Col(dbc.Alert([
                html.H5(f"Risultati attesi: {s['candidature_correnti']:,.0f} → "
                        f"{s['candidature_ottimali']:,.0f} a settimana "
                        f"({s['efficiency_gain']:+.1%})", className="mb-1"),
                html.Small("Raccomandazione del modello: valuta contratti e "
                           "obiettivi di brand prima di applicarla."),
                html.Div(dbc.Button(["Riparti il budget tra le campagne ",
                                     html.I(className="bi bi-arrow-right ms-1")],
                                    href="/mta", color="primary", outline=True,
                                    size="sm", className="mt-2"))],
                color="dark", className="border border-secondary"), md=12),
        ]),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardHeader("Attuale vs ottimale"),
                              dbc.CardBody(dcc.Graph(figure=theme.dark(fig)))],
                             className="border-secondary"), md=7),
            dbc.Col(dbc.Card([dbc.CardHeader("Firma dell'ottimo"),
                              dbc.CardBody(dcc.Graph(figure=theme.dark(fig2)))],
                             className="border-secondary"), md=5),
        ], className="g-3 mb-3"),
        dbc.Card([dbc.CardHeader("Dettaglio"),
                  dbc.CardBody(dash_table.DataTable(
                      data=detail.to_dict("records"),
                      columns=[{"name": c, "id": c} for c in detail.columns],
                      **TBL_STYLE))], className="border-secondary"),
    ])
