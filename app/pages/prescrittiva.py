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

dash.register_page(__name__, path="/prescrittiva",
                   name="3. Ottimizzazione del budget", order=2)

CAPTION = "text-secondary small mt-2 mb-0"
SAT_VERDE, SAT_GIALLO = 0.50, 0.80


def saturazione(p: dict, spesa_media: float):
    """Quota dell'effetto massimo raggiunta alla spesa media corrente."""
    from transforms import steady_state_response
    quota = steady_state_response(spesa_media, **p) / p["beta"] if p["beta"] else 0.0
    if quota < SAT_VERDE:
        return quota, "ha ancora margine di crescita"
    if quota < SAT_GIALLO:
        return quota, "si sta saturando"
    return quota, "è vicino alla saturazione"


TBL_STYLE = dict(
    style_header={"backgroundColor": "#EEF2F8", "color": "#1A2332",
                  "border": "1px solid #E3E1DA", "fontWeight": "600"},
    style_cell={"backgroundColor": "#FFFFFF", "color": "#1A2332",
                "border": "1px solid #E3E1DA", "fontSize": 14,
                "fontFamily": "Tahoma, Geneva, Verdana, sans-serif"},
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
        html.H2("3. Ottimizzazione del budget"),
        html.P([
            "Usando il modello stimato nel ",
            dcc.Link("Passo 2 (Stima e risposta dei canali)",
                     href="/predittiva", className="text-info"),
            ", questa pagina propone come ridistribuire la spesa tra i canali "
            "per massimizzare le candidature a parità di spesa totale. "
            "I valori sono pre-compilati dal tuo storico."],
            className="text-secondary"),
        dbc.Row([
            dbc.Col([
                dbc.Label("Budget settimanale (€)"),
                dbc.Input(id="opt-budget", type="number", value=round(weekly),
                          min=1000, step=500),
                html.Small("Pre-compilato con la tua spesa media storica. Di "
                           "quanto può variare ogni canale lo decidi con i "
                           "limiti min/max nella tabella qui sotto.",
                           className="text-secondary"),
            ], md=6),
            dbc.Col(dbc.Button("Ottimizza il budget", id="btn-opt",
                               color="info", size="lg", className="mt-4"),
                    md="auto"),
        ], className="g-3 mb-3 align-items-start"),
        dbc.Card([
            dbc.CardHeader("I tuoi limiti per canale (contratti, presidi di "
                           "brand) — modificabili"),
            dbc.CardBody([
                dash_table.DataTable(
                    id="constraints-table", data=rows,
                    columns=[{"name": c, "id": c,
                              "editable": c in ("min", "max"),
                              "type": "numeric"} for c in rows[0]],
                    editable=True, **TBL_STYLE),
                html.P("min e max sono la spesa settimanale minima e massima "
                       "che ammetti per ogni canale: il piano proposto li "
                       "rispetterà sempre.", className=CAPTION)]),
        ], className="border-secondary mb-4"),
        html.Div(id="opt-result"),
        dcc.Download(id="opt-download"),
        dbc.Accordion([
            dbc.AccordionItem([
                html.P("Inserisci il tuo budget annuale totale. Il modello dividerà "
                       "l'anno in 4 trimestri, allocando più budget nei periodi "
                       "con maggiore domanda storica, e ottimizzerà il mix di canali "
                       "per ciascun trimestre.", className="text-secondary"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Budget Annuale (€)"),
                        dbc.Input(id="opt-annual-budget", type="number", value=round(weekly * 52), step=5000),
                    ], md=4),
                    dbc.Col(dbc.Button("Genera Piano Trimestrale", id="btn-annual-opt",
                                       color="primary", className="mt-4"), md="auto"),
                ], className="g-3 mb-3 align-items-start"),
                html.Div(id="annual-opt-result")
            ], title="Pianificazione Multi-Periodo (Annuale/Trimestrale)")
        ], start_collapsed=True, className="mb-4"),
        html.Div(dcc.Link("Vuoi vedere il dettaglio per campagna? -> "
                          "Attribuzione per campagna",
                          href="/mta", className="text-info"),
                 className="text-end mt-4"),
    ])


@callback(Output("opt-result", "children"),
          Input("btn-opt", "n_clicks"),
          State("opt-budget", "value"),
          State("constraints-table", "data"), prevent_initial_call=True,
          running=[(Output("btn-opt", "disabled"), True, False)])
def optimize(_, budget, rows):
    st = store.get()
    if not st.get("fit"):
        return dbc.Alert(["Prima serve il modello: vai alla pagina ",
                          dcc.Link("Stima e risposta dei canali",
                                   href="/predittiva"),
                          " e premi Stima il modello."], color="warning")
    import allocator
    channels = st["channels"]
    cur = {ch: st["constraints"][ch]["mean"] for ch in channels}
    min_sp = {r["canale"]: float(r["min"]) for r in rows if r.get("min")}
    max_sp = {r["canale"]: float(r["max"]) for r in rows if r.get("max")}
    try:
        table = allocator.optimize_budget(
            st["fit"]["channels"], cur, total_budget=float(budget),
            min_spend=min_sp or None, max_spend=max_sp or None,
            max_change_pct=None, channels=channels)
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
        dbc.Col(_metric("Candidature con il mix attuale", f"{prima:,.0f}",
                        "a settimana, stesso budget", "secondary"), md=4),
        dbc.Col(_metric("Candidature con il piano ottimizzato", f"{dopo:,.0f}",
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
        _q_giu, _ = saturazione(st["fit"]["channels"][ch_giu], cur[ch_giu])
        _q_su, _ = saturazione(st["fit"]["channels"][ch_su], cur[ch_su])
        
        motivo_giu = "è vicino alla saturazione" if _q_giu >= SAT_GIALLO else "ha rendimenti marginali inferiori"
        motivo_su = "ha ancora ampio margine di crescita" if _q_su < SAT_VERDE else "offre un potenziale di resa migliore"

        pct = f" del {delta / prima:.0%}" if prima else ""
        spiegazione = [
            "Il modello suggerisce di spostare budget da ", html.B(ch_giu),
            f" (che {motivo_giu}) verso ", html.B(ch_su),
            f" (che {motivo_su}), aumentando le candidature stimate{pct}."]
    else:
        spiegazione = [
            "Il piano resta vicino al mix attuale: secondo il modello "
            "l'allocazione di oggi è già quasi ottimale rispetto ai vincoli "
            "impostati."]

    # --- grafico attuale vs proposto, con variazione % sopra le barre --------
    fig = go.Figure()
    fig.add_bar(x=table["canale"], y=table["spesa_corrente"],
                name="spesa attuale", marker_color=theme.AXIS,
                hovertemplate="Attuale: %{y:,.0f} €<extra></extra>")
    fig.add_bar(x=table["canale"], y=table["spesa_ottimale"],
                name="spesa ottimale", marker_color=theme.COLORS[0],
                hovertemplate="Ottimale: %{y:,.0f} €<extra></extra>")
    for _, r in table.iterrows():
        v = float(r["variazione_pct"])
        fig.add_annotation(
            x=r["canale"],
            y=max(float(r["spesa_corrente"]), float(r["spesa_ottimale"])),
            text=f"{v:+.0%}", yshift=14, showarrow=False,
            font=dict(color=theme.POSITIVE if v >= 0 else theme.NEGATIVE,
                      size=13))
    fig.update_layout(barmode="group", yaxis_title="€/settimana")

    fig2 = go.Figure(go.Bar(
        x=table["canale"], y=table["roas_marg_ottimale_x1000"],
        marker_color=theme.WARNING, name="resa dell'ultimo euro"))
    fig2.add_hline(y=float(table["roas_marg_ottimale_x1000"].mean()),
                   line_dash="dot", line_color=theme.AXIS,
                   annotation_text="resa pareggiata tra i canali")
    fig2.update_layout(yaxis_title="candidature ogni 1.000 € aggiuntivi")

    detail = table[["canale", "spesa_corrente", "spesa_ottimale",
                    "variazione_pct", "candidature_ottimali"]].copy()
    detail.columns = ["canale", "attuale €", "ottimale €", "Δ%",
                      "candidature att."]
    detail = detail.round({"attuale €": 0, "ottimale €": 0,
                           "candidature att.": 1})
    detail["Δ%"] = (table["variazione_pct"] * 100).round(1)

    # dati per l'export CSV
    st["opt_export"] = pd.DataFrame({
        "Canale": table["canale"],
        "Spesa attuale (EUR/sett)": table["spesa_corrente"].round(0),
        "Spesa ottimale (EUR/sett)": table["spesa_ottimale"].round(0),
        "Variazione (%)": (table["variazione_pct"] * 100).round(1),
        "Candidature attese (a sett)": table["candidature_ottimali"].round(1),
    })

    return html.Div([
        html.H4("Confronto Prima vs Dopo", className="mt-2"),
        html.P("Prima = stesso budget distribuito come oggi. "
               "Dopo = il piano ottimizzato dal modello.",
               className="text-secondary small"),
        metriche,
        dbc.Alert(spiegazione, color="info", className="mb-2"),
        dbc.Alert(["Attenzione: questa è una raccomandazione basata sul "
                   "modello. La decisione finale spetta a te."],
                  color="warning", className="mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Spesa attuale vs ottimale, canale per canale"),
                dbc.CardBody([
                    dcc.Graph(figure=theme.dark(fig)),
                    html.P("La percentuale sopra le barre indica di quanto il "
                           "piano propone di alzare (verde) o tagliare (rosso) "
                           "ogni canale.", className=CAPTION)])],
                className="border-secondary"), md=7),
            dbc.Col(dbc.Card([
                dbc.CardHeader("Come leggere i rendimenti marginali"),
                dbc.CardBody([
                    dcc.Graph(figure=theme.dark(fig2)),
                    html.P("Questo grafico mostra quanto produce ogni euro "
                           "aggiuntivo per canale. Quando tutte le barre sono "
                           "alla stessa altezza, il budget è distribuito nel "
                           "modo più efficiente.", className=CAPTION)])],
                className="border-secondary"), md=5),
        ], className="g-3 mb-3"),
        dbc.Card([dbc.CardHeader("Dettaglio del piano"),
                  dbc.CardBody(dash_table.DataTable(
                      data=detail.to_dict("records"),
                      columns=[{"name": c, "id": c} for c in detail.columns],
                      **TBL_STYLE))], className="border-secondary mb-3"),
        dbc.Button("Scarica piano (CSV)", id="btn-export-plan",
                   color="success"),
    ])


@callback(Output("opt-download", "data"),
          Input("btn-export-plan", "n_clicks"), prevent_initial_call=True)
def download_plan(_):
    exp = store.get().get("opt_export")
    if exp is None:
        return dash.no_update
    return dcc.send_data_frame(exp.to_csv, "piano_riallocazione.csv",
                               index=False, encoding="utf-8-sig")

@callback(Output("annual-opt-result", "children"),
          Input("btn-annual-opt", "n_clicks"),
          State("opt-annual-budget", "value"),
          prevent_initial_call=True)
def optimize_annual(_, annual_budget):
    st = store.get()
    if not st.get("fit"):
        return dbc.Alert("Prima stima il modello nella pagina Stima e Risposta.", color="warning")
    import allocator
    try:
        df = st["df"]
        weights = allocator.suggest_period_weights(df, "quarter")
        plan = allocator.plan_periods(
            st["fit"]["channels"], total_budget=float(annual_budget),
            granularity="quarter", period_weights=weights,
            channels=st["channels"])
    except Exception as e:
        return dbc.Alert(f"Errore nella pianificazione: {e}", color="danger")
    
    plan_disp = plan.copy()
    plan_disp.columns = ["Trimestre", "Canale", "Budget Trimestre (€)", "Spesa Settimanale (€)", 
                         "Cand. Sett.", "Cand. Trimestre", "ROAS marg."]
    for c in ["Budget Trimestre (€)", "Spesa Settimanale (€)", "Cand. Sett.", "Cand. Trimestre"]:
        plan_disp[c] = plan_disp[c].round(0).apply(lambda x: f"{x:,.0f}")
    plan_disp["ROAS marg."] = plan_disp["ROAS marg."].round(2)
    
    return dash_table.DataTable(
        data=plan_disp.to_dict("records"),
        columns=[{"name": c, "id": c} for c in plan_disp.columns],
        **TBL_STYLE
    )

