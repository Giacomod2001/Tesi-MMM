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
    title="Randstad · Budget Media",
)
server = app.server

NAV = [("1. Analisi dei dati", "/", "bi-graph-up"),
       ("2. Stima e risposta dei canali", "/predittiva", "bi-activity"),
       ("3. Ottimizzazione del budget", "/prescrittiva", "bi-sliders"),
       ("4. Attribuzione per campagna", "/mta", "bi-diagram-3")]

navbar = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand([html.Span("Randstad", className="fw-bold rs-brand"),
                         html.Span("Budget Media", className="ms-2 rs-brand-sub")],
                        href="/"),
        dbc.Nav([dbc.NavLink([html.I(className=f"bi {ic} me-1"), lab],
                             href=href, active="exact")
                 for lab, href, ic in NAV], navbar=True,
                className="ms-auto flex-nowrap"),
    ], fluid=True),
    dark=True, sticky="top", className="rs-navbar",
)

guida = dbc.Accordion([
    dbc.AccordionItem([
        html.P("Tre passi per ottimizzare il tuo budget media:",
               className="mb-2"),
        html.P([html.B("Passo 1 — Analisi dei dati: "),
                "esplora la spesa per canale e l'andamento delle candidature "
                "nel tempo."], className="mb-2"),
        html.P([html.B("Passo 2 — Stima e risposta dei canali: "),
                "il modello calcola quanto ogni euro investito produce in "
                "termini di candidature. Vedrai le curve di risposta e i punti "
                "di saturazione."], className="mb-2"),
        html.P([html.B("Passo 3 — Ottimizzazione del budget: "),
                "il modello propone una riallocazione del budget per "
                "massimizzare le candidature a parità di spesa totale."],
               className="mb-2"),
        html.P([html.B("Opzionale: "), "la sezione Attribuzione per campagna "
                "mostra il contributo di ogni singola campagna nel percorso "
                "di conversione."], className="mb-0"),
    ], title="Come funziona questo strumento", item_id="guida"),
], active_item="guida", className="mb-3")

app.layout = html.Div([
    navbar,
    dcc.Store(id="global-refresh"),
    dbc.Container([guida, dash.page_container], fluid=True,
                  className="py-4 px-4"),
    html.Footer(dbc.Container(html.Small(
        "Dati sintetici — caso di studio ispirato al recruiting digitale. "
        "Le raccomandazioni sono supporto alla decisione, non sostituiscono "
        "il giudizio del manager.",
        className="text-secondary"), fluid=True), className="py-3"),
])

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
