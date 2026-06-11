"""Pagina 2 — STIMA & RISPOSTA: quanto rende ogni canale e dove satura.

Il fit rapido (frequentista) gira in un callback sincrono (~30-60 s);
il ricalcolo bayesiano gira come BACKGROUND CALLBACK (diskcache): non
blocca la navigazione e al termine aggiunge la fascia di incertezza.
"""
import json

import dash
import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from app import store, theme

dash.register_page(__name__, path="/predittiva", name="2 · Stima & Risposta",
                   order=1)

CAPTION = "text-secondary small mt-2 mb-0"

# Soglie di saturazione: quota dell'effetto massimo (beta) raggiunta alla
# spesa media corrente.
SAT_VERDE, SAT_GIALLO = 0.50, 0.80


def saturazione(p: dict, spesa_media: float):
    """Quota dell'effetto massimo raggiunta alla spesa media corrente.

    Ritorna (quota, etichetta, colore_bootstrap).
    """
    from transforms import steady_state_response
    quota = steady_state_response(spesa_media, **p) / p["beta"] if p["beta"] else 0.0
    if quota < SAT_VERDE:
        return quota, "Margine di crescita", "success"
    if quota < SAT_GIALLO:
        return quota, "Si sta saturando", "warning"
    return quota, "Saturato", "danger"


def layout():
    st = store.get()
    channels = st["channels"]
    return html.Div([
        html.H2("2. Stima e risposta dei canali"),
        html.P("Premi il bottone: il modello impara dallo storico quante "
               "candidature porta ogni euro speso su ciascun canale e quando un "
               "canale è vicino alla saturazione.",
               className="text-secondary"),
        dbc.Row([
            dbc.Col(dbc.Button("Stima il modello",
                               id="btn-fit", color="info", size="lg"),
                    width="auto"),
            dbc.Col(html.Div(id="fit-status", className="pt-2")),
        ], className="g-2 mb-4", align="center"),
        dcc.Store(id="fit-done"), dcc.Store(id="bayes-done"),
        html.H5("Saturazione dei canali", className="mt-2"),
        dbc.Row(id="saturation-row", className="g-3 mb-1"),
        html.P("Più la barra è piena, meno rende spendere di più su quel canale. "
               "Verde: c'è ancora margine di crescita. Ambra: i rendimenti "
               "stanno calando. Rosso: il canale è vicino al suo massimo.",
               className=CAPTION + " mb-3"),
        dbc.Card([
            dbc.CardHeader("Curve di risposta dei canali"),
            dbc.CardBody([
                dbc.Checklist(id="curve-channels", inline=True,
                              options=[{"label": c, "value": c}
                                       for c in channels],
                              value=channels, className="mb-2"),
                dcc.Graph(id="fig-curves"),
                html.P("Il punto Spesa attuale indica la tua spesa media di "
                       "oggi. La linea tratteggiata è il massimo raggiungibile "
                       "del canale; il rombo è la metà saturazione, dove i "
                       "rendimenti iniziano a calare. Dove la curva si piega, "
                       "ogni euro in più rende sempre meno.",
                       className=CAPTION)])],
            className="border-secondary mb-3"),
        dbc.Accordion([
            dbc.AccordionItem([
                html.P("Le curve qui sopra sono la stima più probabile. Questa "
                       "analisi (più lenta, gira in background mentre continui a "
                       "navigare) calcola anche quanto sono affidabili: aggiunge "
                       "alle curve una fascia di incertezza (90%) — più la fascia "
                       "è stretta, più la stima è solida.",
                       className="text-secondary"),
                dbc.Row([
                    dbc.Col(dbc.Button("Calcola l'incertezza (in background)",
                                       id="btn-bayes", color="info",
                                       outline=True), width="auto"),
                    dbc.Col(html.Div(id="bayes-status", className="pt-1")),
                ], className="g-2", align="center"),
            ], title="Analisi avanzata (incertezza)"),
        ], start_collapsed=True, className="mb-3"),
        html.Div(dcc.Link("Prossimo passo: Ottimizzazione del budget ->",
                          href="/prescrittiva", className="text-info"),
                 className="text-end mt-4"),
    ])


@callback(Output("fit-done", "data"), Output("fit-status", "children"),
          Input("btn-fit", "n_clicks"), prevent_initial_call=True,
          running=[(Output("btn-fit", "disabled"), True, False),
                   (Output("fit-status", "children"),
                    html.Div([
                        html.Div("Stima frequentista in corso (pochi secondi)...", className="text-secondary small mb-1"),
                        dbc.Progress(value=100, animated=True, striped=True, color="info", style={"height": "10px"})
                    ]), "")])
def run_fit(_):
    st = store.get()
    import model as mmm_model                       # mmm/ e' nel sys.path
    st["fit"] = mmm_model.fit(st["df"], channels=st["channels"], controls=[])
    d = st["fit"]["diagnostics"]
    return True, html.Span([
        html.B("Modello stimato con successo. ", className="text-success"),
        f"Il modello spiega il {d['r2']:.0%} dell'andamento reale "
        f"(errore medio: {d['mape']:.1%}).",
    ])


@callback(Output("bayes-done", "data"), Output("bayes-status", "children"),
          Input("btn-bayes", "n_clicks"),
          background=True, prevent_initial_call=True,
          running=[(Output("btn-bayes", "disabled"), True, False),
                   (Output("bayes-status", "children"),
                    html.Div([
                        html.Div("Calcolo Bayesiano in background (può richiedere alcuni minuti). Puoi navigare altrove.", className="text-secondary small mb-1"),
                        dbc.Progress(value=100, animated=True, striped=True, color="success", style={"height": "10px"})
                    ]), "")])
def run_bayes(_):
    st = store.get()
    try:
        from core.mmm_bayes import fit_bayes
    except ImportError:
        return False, dbc.Alert("Libreria PyMC mancante. Se sei in locale, apri il terminale ed esegui: pip install -r requirements-bayes.txt", color="danger")
    
    try:
        anchor = st["fit"]["channels"] if st.get("fit") else None
        res = fit_bayes(st["df"], st["channels"], anchor=anchor)
        with open(store.BAYES_PATH, "w") as f:
            json.dump(res, f)
        return True, html.Span(
            "Fatto: le curve ora mostrano anche la fascia di incertezza (90%).",
            className="text-success")
    except Exception as e:
        return False, dbc.Alert(f"Errore durante il calcolo Bayesiano: {e}", color="danger")


@callback(Output("saturation-row", "children"), Output("fig-curves", "figure"),
          Input("fit-done", "data"), Input("bayes-done", "data"),
          Input("global-refresh", "data"), Input("curve-channels", "value"))
def render(_f, _b, _r, sel):
    st = store.get()
    df, channels = st["df"], st["channels"]
    fit = st.get("fit")
    # Bande d'incertezza solo se l'utente le ha calcolate in questa sessione
    # (dall'accordion "Analisi avanzata"): di default curve nette e leggibili.
    bayes = store.bayes_results() if _b else None
    sel = [c for c in (sel or channels) if c in channels] or channels

    from transforms import steady_state_response

    # --- semaforo di saturazione ---------------------------------------------
    cards = []
    if fit:
        for ch in channels:
            p = fit["channels"][ch]
            m = df[f"spend_{ch}"].mean()
            quota, stato, color = saturazione(p, m)
            cards.append(dbc.Col(dbc.Card(dbc.CardBody([
                html.Div(ch, className="fw-bold"),
                dbc.Progress(value=min(quota, 1.0) * 100, color=color,
                             className="my-2", style={"height": "10px"}),
                html.Div(f"{stato} — {quota:.0%} del potenziale",
                         className="small"),
                html.Small(f"{ch} è al {quota:.0%} del potenziale massimo, "
                           f"alla spesa attuale ({m:,.0f} €/sett.).",
                           className="text-secondary"),
            ]), className="border-secondary h-100"), md=3))
    else:
        cards.append(dbc.Col(dbc.Alert(
            "Premi Stima il modello qui sopra per calcolare curve e "
            "saturazione (serve circa un minuto).",
            color="secondary"), md=12))

    # --- curve di risposta (+ fascia di incertezza se disponibile) ------------
    fig = go.Figure()
    xmax = 2.5 * max((df[f"spend_{ch}"].mean() for ch in sel), default=1.0)
    for i, ch in enumerate(channels):
        if ch not in sel:
            continue
        col = theme.COLORS[i % len(theme.COLORS)]
        if bayes and ch in bayes.get("curves", {}):
            c = bayes["curves"][ch]
            r, g, b = (int(col[j:j + 2], 16) for j in (1, 3, 5))
            fig.add_scatter(x=c["spend"] + c["spend"][::-1],
                            y=c["p95"] + c["p05"][::-1],
                            fill="toself", line=dict(width=0),
                            fillcolor=f"rgba({r},{g},{b},0.18)",
                            name=f"{ch} (fascia di incertezza)",
                            showlegend=False, hoverinfo="skip")
            fig.add_scatter(x=c["spend"], y=c["p50"], name=ch,
                            line=dict(color=col, width=2))
        elif fit:
            grid = np.linspace(0, xmax, 60)
            y = [steady_state_response(x, **fit["channels"][ch]) for x in grid]
            fig.add_scatter(x=grid, y=y, name=ch, line=dict(color=col, width=2))
        if fit:
            p = fit["channels"][ch]
            m = float(df[f"spend_{ch}"].mean())
            y_now = steady_state_response(m, **p)
            # massimo raggiungibile del canale (linea tratteggiata)
            fig.add_scatter(x=[0, xmax], y=[p["beta"], p["beta"]],
                            mode="lines", name=f"{ch} · Massimo raggiungibile",
                            showlegend=False,
                            line=dict(color=col, width=1, dash="dot"),
                            opacity=0.5,
                            hovertemplate=(f"{ch} — Massimo raggiungibile<br>"
                                           "%{y:,.1f} candidature/sett."
                                           "<extra></extra>"))
            # punto di metà saturazione: i rendimenti iniziano a calare
            x_half = p["K"] * (1 - p["lam"])
            if x_half <= xmax:
                fig.add_scatter(
                    x=[x_half], y=[p["beta"] / 2], mode="markers",
                    marker=dict(color=col, size=9, symbol="diamond-open",
                                line=dict(width=2)),
                    showlegend=False,
                    hovertemplate=(f"{ch} — Metà saturazione<br>da qui in poi i "
                                   "rendimenti calano<br>spesa: %{x:,.0f} €/sett."
                                   "<extra></extra>"))
            # marcatore "Spesa attuale"
            fig.add_scatter(
                x=[m], y=[y_now], mode="markers+text", text=["Spesa attuale"],
                textposition="top center",
                textfont=dict(color=col, size=11),
                marker=dict(color=col, size=12, symbol="circle",
                            line=dict(color="#1A2332", width=1.5)),
                showlegend=False,
                hovertemplate=(f"{ch} — Spesa attuale<br>spesa media: "
                               "%{x:,.0f} €/sett.<br>candidature stimate: "
                               "%{y:,.1f}/sett.<extra></extra>"))
    fig.update_layout(xaxis_title="spesa settimanale (€)",
                      yaxis_title="candidature attese / settimana")

    return cards, theme.dark(fig, 540)
