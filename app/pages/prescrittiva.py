"""Pagina 3 — OTTIMIZZAZIONE: quanto budget a ogni canale.

I vincoli min/max per canale sono PRE-COMPILATI dallo storico (nessuna
configurazione manuale richiesta) ma restano modificabili: e' il punto di
ingresso della conoscenza del manager (human-in-the-middle).
"""
import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dash_table, dcc, html

from app import store, theme

dash.register_page(__name__, path="/prescrittiva", name="3 · Ottimizzazione",
                   order=2)

CAPTION = "text-secondary small mt-2 mb-0"
SAT_VERDE, SAT_GIALLO = 0.70, 0.90


def saturazione(p: dict, spesa_media: float):
    """Quota dell'effetto massimo raggiunta alla spesa media corrente."""
    from transforms import steady_state_response
    quota = steady_state_response(spesa_media, **p) / p["beta"] if p["beta"] else 0.0
    if quota < SAT_VERDE:
        return quota, "🟢", "Margine di crescita", "success"
    if quota < SAT_GIALLO:
        return quota, "🟡", "Si sta saturando", "warning"
    return quota, "🔴", "Saturato", "danger"

TBL_STYLE = dict(
    style_header={"backgroundColor": "#1a1d24", "color": "#e8e9ed",
                  "border": "1px solid #2a2e3a"},
    style_cell={"backgroundColor": "#12141a", "color": "#e8e9ed",
                "border": "1px solid #2a2e3a", "fontSize": 14,
                "fontFamily": "inherit"},
)


def _metric(label, value, sub="", color="info"):
    return dbc.Card(dbc.CardBody([
        html.Div(label, className="text-secondary small"),
        html.H3(value, className=f"text-{color} mb-0"),
        html.Div(sub, className="text-secondary small"),
    ]), className="border-secondary h-100")


def layout():
    st = store.get()
    cons = st["constraints"]
    weekly = sum(c["mean"] for c in cons.values())
    rows = [{"canale": ch, "spesa media": round(c["mean"]),
             "min": c["min"], "max": c["max"]} for ch, c in cons.items()]
    return html.Div([
        html.H2("3 · Ottimizzazione — quanto budget a ogni canale"),
        html.P("Imposta il budget e i tuoi vincoli: il modello propone come "
               "ridistribuire la spesa tra i canali per ottenere più risultati "
               "a parità di budget. I valori sono pre-compilati dal tuo storico.",
               className="text-secondary"),
        dbc.Row([
            dbc.Col([
                dbc.Label("Budget settimanale (€)"),
                dbc.Input(id="opt-budget", type="number", value=round(weekly),
                          min=1000, step=500),
                html.Small("Pre-compilato: la tua spesa media storica.",
                           className="text-secondary"),
            ], md=3),
            dbc.Col([
                dbc.Label("Di quanto può cambiare ogni canale rispetto a oggi"),
                dcc.Slider(id="opt-maxchange", min=0.1, max=1.0, step=0.05,
                           value=0.5, marks={.1: "±10%", .5: "±50%", 1: "libero"}),
                html.Small("Un limite basso = piano prudente, vicino al mix "
                           "attuale.", className="text-secondary"),
            ], md=5),
            dbc.Col(dbc.Button([html.I(className="bi bi-magic me-2"),
                                "Trova il mix migliore"], id="btn-opt",
                               color="info", size="lg", className="mt-4"), md=3),
        ], className="g-3 mb-3"),
        dbc.Card([
            dbc.CardHeader("✋ I tuoi limiti per canale (contratti, presidi di "
                           "brand…) — modificabili"),
            dbc.CardBody([
                dash_table.DataTable(
                    id="constraints-table", data=rows,
                    columns=[{"name": c, "id": c,
                              "editable": c in ("min", "max"),
                              "type": "numeric"} for c in rows[0]],
                    editable=True, **TBL_STYLE),
                html.P("“min” e “max” sono la spesa settimanale minima e massima "
                       "che ammetti per ogni canale: il piano proposto li "
                       "rispetterà sempre.", className=CAPTION)]),
        ], className="border-secondary mb-4"),
        html.Div(id="opt-result"),
        dcc.Download(id="opt-download"),
        html.Div(dbc.Button(["Prossimo passo: 4 · Budget per Campagna",
                             html.I(className="bi bi-arrow-right ms-2")],
                            href="/mta", color="info", outline=True),
                 className="text-end mt-4"),
    ])


@callback(Output("opt-result", "children"),
          Input("btn-opt", "n_clicks"),
          State("opt-budget", "value"), State("opt-maxchange", "value"),
          State("constraints-table", "data"), prevent_initial_call=True,
          running=[(Output("btn-opt", "disabled"), True, False)])
def optimize(_, budget, max_change, rows):
    st = store.get()
    if not st.get("fit"):
        return dbc.Alert(["Prima serve il modello: vai alla pagina ",
                          dcc.Link("2 · Stima & Risposta", href="/predittiva"),
                          " e premi “Stima il modello”."], color="warning")
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
    prima = float(s["candidature_correnti"])
    dopo = float(s["candidature_ottimali"])
    delta = dopo - prima

    # --- PRIMA vs DOPO -------------------------------------------------------
    metriche = dbc.Row([
        dbc.Col(_metric("Risultati col mix attuale", f"{prima:,.0f}",
                        "a settimana, stesso budget", "secondary"), md=4),
        dbc.Col(_metric("Risultati col piano nuovo", f"{dopo:,.0f}",
                        "a settimana, stesso budget"), md=4),
        dbc.Col(_metric("Differenza", f"{delta:+,.0f}",
                        f"{delta / prima:+.1%} a parità di spesa" if prima
                        else "", "success" if delta >= 0 else "danger"), md=4),
    ], className="g-3 mb-3")

    # --- spiegazione automatica della raccomandazione ------------------------
    delta_sp = {r["canale"]: float(r["spesa_ottimale"] - r["spesa_corrente"])
                for _, r in table.iterrows()}
    ch_giu = min(delta_sp, key=delta_sp.get)
    ch_su = max(delta_sp, key=delta_sp.get)
    soglia = 0.01 * float(budget)  # spostamenti sotto l'1% non si commentano
    if delta_sp[ch_su] > soglia and delta_sp[ch_giu] < -soglia:
        q_giu, ic_giu, lab_giu, _c = saturazione(st["fit"]["channels"][ch_giu],
                                                 cur[ch_giu])
        q_su, ic_su, lab_su, _c = saturazione(st["fit"]["channels"][ch_su],
                                              cur[ch_su])
        spiegazione = [
            html.B("Perché questa raccomandazione? "),
            f"Il modello suggerisce di spostare budget da ", html.B(ch_giu),
            f" verso ", html.B(ch_su), f": alla spesa attuale {ch_giu} è al "
            f"{q_giu:.0%} del suo effetto massimo ({ic_giu} {lab_giu.lower()}), "
            f"mentre {ch_su} è al {q_su:.0%} ({ic_su} {lab_su.lower()}): lì ogni "
            "euro in più rende ancora."]
    else:
        spiegazione = [
            html.B("Il piano resta vicino al mix attuale: "),
            "secondo il modello l'allocazione di oggi è già quasi ottimale "
            "rispetto ai vincoli impostati."]

    # --- grafico attuale vs proposto, con variazione % sopra le barre --------
    fig = go.Figure()
    fig.add_bar(x=table["canale"], y=table["spesa_corrente"],
                name="spesa attuale", marker_color="#5c677d")
    fig.add_bar(x=table["canale"], y=table["spesa_ottimale"],
                name="spesa proposta", marker_color="#4cc9f0")
    for _, r in table.iterrows():
        v = float(r["variazione_pct"])
        fig.add_annotation(
            x=r["canale"],
            y=max(float(r["spesa_corrente"]), float(r["spesa_ottimale"])),
            text=f"{v:+.0%}", yshift=14, showarrow=False,
            font=dict(color="#06d6a0" if v >= 0 else "#ef476f", size=13))
    fig.update_layout(barmode="group", yaxis_title="€/settimana")

    fig2 = go.Figure(go.Bar(
        x=table["canale"], y=table["roas_marg_ottimale_x1000"],
        marker_color="#ffd166", name="resa dell'ultimo euro"))
    fig2.add_hline(y=float(table["roas_marg_ottimale_x1000"].mean()),
                   line_dash="dot", line_color="#aaa",
                   annotation_text="resa pareggiata tra i canali")
    fig2.update_layout(yaxis_title="risultati ogni 1.000 € aggiuntivi")

    detail = table[["canale", "spesa_corrente", "spesa_ottimale",
                    "variazione_pct", "candidature_ottimali"]].copy()
    detail.columns = ["canale", "attuale €", "proposta €", "Δ%", "risultati att."]
    detail = detail.round({"attuale €": 0, "proposta €": 0, "risultati att.": 1})
    detail["Δ%"] = (table["variazione_pct"] * 100).round(1)

    # dati per l'export CSV
    st["opt_export"] = pd.DataFrame({
        "Canale": table["canale"],
        "Spesa attuale (EUR/sett)": table["spesa_corrente"].round(0),
        "Spesa proposta (EUR/sett)": table["spesa_ottimale"].round(0),
        "Variazione (%)": (table["variazione_pct"] * 100).round(1),
        "Risultati attesi (a sett)": table["candidature_ottimali"].round(1),
    })

    return html.Div([
        html.H4("Prima vs Dopo", className="mt-2"),
        html.P("“Prima” = stesso budget distribuito come oggi. "
               "“Dopo” = il piano proposto dal modello.",
               className="text-secondary small"),
        metriche,
        dbc.Alert(spiegazione, color="info", className="mb-2"),
        dbc.Alert(["⚠️ Questa è una ", html.B("RACCOMANDAZIONE"),
                   " basata sul modello: valuta contratti e obiettivi di brand. "
                   "La decisione finale resta tua."],
                  color="warning", className="mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("📊 Spesa attuale vs proposta, canale per canale"),
                dbc.CardBody([
                    dcc.Graph(figure=theme.dark(fig)),
                    html.P("La percentuale sopra le barre indica di quanto il "
                           "piano propone di alzare (verde) o tagliare (rosso) "
                           "ogni canale.", className=CAPTION)])],
                className="border-secondary"), md=7),
            dbc.Col(dbc.Card([
                dbc.CardHeader("⚖️ Quanto rende l'ultimo euro su ogni canale"),
                dbc.CardBody([
                    dcc.Graph(figure=theme.dark(fig2)),
                    html.P("Cosa guardare: dopo l'ottimizzazione le barre sono "
                           "circa alla stessa altezza. Significa che non conviene "
                           "più spostare budget: l'ultimo euro rende uguale "
                           "ovunque, ed è il segno di un piano ben bilanciato.",
                           className=CAPTION)])],
                className="border-secondary"), md=5),
        ], className="g-3 mb-3"),
        dbc.Card([dbc.CardHeader("Dettaglio del piano"),
                  dbc.CardBody(dash_table.DataTable(
                      data=detail.to_dict("records"),
                      columns=[{"name": c, "id": c} for c in detail.columns],
                      **TBL_STYLE))], className="border-secondary mb-3"),
        dbc.Button([html.I(className="bi bi-download me-2"),
                    "📥 Scarica piano (CSV)"], id="btn-export-plan",
                   color="success", outline=True),
    ])


@callback(Output("opt-download", "data"),
          Input("btn-export-plan", "n_clicks"), prevent_initial_call=True)
def download_plan(_):
    exp = store.get().get("opt_export")
    if exp is None:
        return dash.no_update
    return dcc.send_data_frame(exp.to_csv, "piano_riallocazione.csv",
                               index=False, encoding="utf-8-sig")
