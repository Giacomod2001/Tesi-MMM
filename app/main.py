"""
MMM + MTA Decision Suite — app Dash multi-pagina (tema scuro).

Avvio:  python -m app.main    ->  http://127.0.0.1:8050

Architettura: tre fasi decisionali (Descrittiva / Predittiva / Prescrittiva)
piu' il livello tattico MTA. Il fit bayesiano gira come background callback
(diskcache): l'utente lancia il ricalcolo e continua a navigare.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dash
import dash_bootstrap_components as dbc
import diskcache
from dash import Dash, DiskcacheManager, dcc, html

from app import store

store.get()  # warm-up dati

cache = diskcache.Cache(os.path.join(os.path.dirname(__file__), ".cache"))
background_manager = DiskcacheManager(cache)

app = Dash(
    __name__, use_pages=True,
    pages_folder=os.path.join(os.path.dirname(__file__), "pages"),
    external_stylesheets=[dbc.themes.CYBORG, dbc.icons.BOOTSTRAP],
    background_callback_manager=background_manager,
    suppress_callback_exceptions=True,
    title="MMM + MTA Decision Suite",
)
server = app.server

NAV = [("Descrittiva", "/", "bi-graph-up"),
       ("Predittiva", "/predittiva", "bi-activity"),
       ("Prescrittiva", "/prescrittiva", "bi-sliders"),
       ("MTA Campagne", "/mta", "bi-diagram-3")]

navbar = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand([html.Span("MMM", className="fw-bold text-info"),
                         html.Span(" + "),
                         html.Span("MTA", className="fw-bold text-warning"),
                         html.Span(" Decision Suite", className="ms-1")], href="/"),
        dbc.Nav([dbc.NavLink([html.I(className=f"bi {ic} me-1"), lab],
                             href=href, active="exact")
                 for lab, href, ic in NAV], navbar=True, className="ms-auto"),
    ], fluid=True),
    color="dark", dark=True, sticky="top", className="border-bottom border-secondary",
)

app.layout = html.Div([
    navbar,
    dcc.Store(id="global-refresh"),
    dbc.Container(dash.page_container, fluid=True, className="py-4 px-4"),
    html.Footer(dbc.Container(html.Small(
        "Dati sintetici — caso di studio ispirato al recruiting digitale. "
        "Le raccomandazioni sono supporto alla decisione, non sostituiscono "
        "il giudizio del manager (human-in-the-middle).",
        className="text-secondary"), fluid=True), className="py-3"),
])

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
