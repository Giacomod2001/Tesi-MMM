"""
MMM Budget Allocator — interfaccia Streamlit (human-in-the-middle).
Avvio:  streamlit run app.py
"""
import json
import os
import tempfile

import numpy as np
import pandas as pd
import streamlit as st

import allocator
import config
import data_generator
import ingestion
import model
from transforms import channel_response, steady_state_response

st.set_page_config(page_title="MMM Budget Allocator", layout="wide")

CH = config.CHANNELS
LABEL = {"google": "Google", "meta": "Meta", "linkedin": "LinkedIn", "indeed": "Indeed"}
HERE = os.path.dirname(os.path.abspath(__file__))

st.title("Budget Allocator — Marketing Mix Modeling")
st.markdown(
    "Questo strumento analizza lo storico di **spesa pubblicitaria e candidature** "
    "e ti dice **come distribuire il budget tra i canali** (Google, Meta, LinkedIn, Indeed) "
    "per ottenere il massimo numero di candidature. "
    "*I dati mostrati sono sintetici: simulano un'agenzia per il lavoro.*")

with st.expander("Come si usa (3 passi)", expanded=False):
    st.markdown("""
1. **Dati** — guarda lo storico. Se hai i tuoi file (spesa, richieste clienti, ricerche dei lavoratori) caricali dalla barra a sinistra: vengono letti in automatico anche da Excel o PDF.
2. **Modello** — premi *Stima il modello*: il sistema impara, per ogni canale, quanto rende e quando si saturera.
3. **Budget** — imposta il budget annuale, gli eventuali limiti per canale, e premi *Ottimizza*: ottieni il piano consigliato. **La decisione finale resta tua**: il piano è un consiglio basato sui dati, non un ordine.
""")

# ---------------------------------------------------------------- sidebar
st.sidebar.header("I tuoi dati (opzionale)")
st.sidebar.caption("Senza caricare nulla, l'app usa il dataset dimostrativo.")
up_main = st.sidebar.file_uploader(
    "Storico spesa e candidature (CSV)", type=["csv"],
    help="Colonne richieste: week, spend_<canale>, applications")
ups_ext = st.sidebar.file_uploader(
    "Serie esterne: richieste clienti, ricerche lavoratori…",
    type=["xlsx", "xls", "xlsm", "csv", "txt", "tsv", "pdf", "json"],
    accept_multiple_files=True,
    help="Qualsiasi formato: il sistema riconosce da solo date (anche 'Gennaio 2024') e numeri (anche '2.150')")


@st.cache_data
def load_main(file) -> pd.DataFrame:
    return pd.read_csv(file) if file is not None else data_generator.generate()


df = load_main(up_main)

if ups_ext:
    paths = []
    for f in ups_ext:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.name)[1])
        tmp.write(f.getbuffer()); tmp.close()
        paths.append(tmp.name)
    try:
        df = ingestion.merge_controls(df, paths)
        st.sidebar.success("Serie riconosciute e agganciate: "
                           + ", ".join(c[5:] for c in df.columns if c.startswith("ctrl_")))
    except ValueError as e:
        st.sidebar.error(str(e))

tab_dati, tab_modello, tab_alloc = st.tabs(["1 · Dati", "2 · Modello", "3 · Budget"])

# ---------------------------------------------------------------- tab Dati
with tab_dati:
    st.subheader("Lo storico su cui ragiona il modello")
    c1, c2, c3 = st.columns(3)
    c1.metric("Settimane di storico", len(df))
    c2.metric("Spesa media settimanale",
              f"{sum(df[f'spend_{ch}'].mean() for ch in CH):,.0f} €")
    c3.metric("Candidature medie a settimana", f"{df['applications'].mean():,.0f}")

    plot_df = df.set_index("week")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Quanto spendiamo, per canale** (€/settimana)")
        spese = plot_df[[f"spend_{ch}" for ch in CH]]
        spese.columns = [LABEL[ch] for ch in CH]
        st.line_chart(spese)
        st.caption("I 'buchi' sono pause campagna: aiutano il modello a capire "
                   "cosa succede quando un canale si spegne.")
    with c2:
        st.markdown("**Quante candidature arrivano**")
        st.line_chart(plot_df[["applications"]])
        ctrl_cols = [c for c in df.columns if c in config.CONTROLS or c.startswith("ctrl_")]
        if ctrl_cols:
            st.markdown("**La domanda esterna** (richieste clienti, ricerche lavoratori)")
            st.line_chart(plot_df[ctrl_cols])
            st.caption("Il modello usa queste serie per non confondere i picchi "
                       "di domanda con l'effetto della pubblicità.")

# ------------------------------------------------------------- tab Modello
with tab_modello:
    st.subheader("Il modello impara le curve di rendimento dei canali")
    st.markdown(
        "Per ogni canale il modello stima **quanto può rendere al massimo** e "
        "**quanto in fretta si satura** (oltre una certa spesa, ogni euro in più rende sempre meno).")
    if st.button("Stima il modello", type="primary"):
        with st.spinner("Stima in corso (circa 1 minuto)…"):
            st.session_state["fit"] = model.fit(df)

    fit_res = st.session_state.get("fit")
    if not fit_res:
        st.info("Premi **Stima il modello** per iniziare.")
    else:
        d = fit_res["diagnostics"]
        c1, c2 = st.columns(2)
        c1.metric("Qualità del fit (R²)", f"{d['r2']:.2f}",
                  help="Quanta parte dell'andamento delle candidature il modello spiega. Sopra 0,9 è ottimo.")
        c2.metric("Errore medio", f"{d['mape']:.1%}",
                  help="Di quanto sbaglia in media la previsione settimanale.")

        st.markdown("**Cosa ha imparato su ogni canale** (in parole semplici)")
        rows = []
        for ch in CH:
            p = fit_res["channels"][ch]
            m = df[f"spend_{ch}"].mean()
            rows.append({
                "Canale": LABEL[ch],
                "Tetto massimo (candidature/sett.)": round(p["beta"]),
                "Spesa per arrivare a metà tetto": f"{p['K']*(1-p['lam']):,.0f} €",
                "Effetto nel tempo": ("immediato" if p["lam"] < 0.25 else
                                      "dura qualche settimana" if p["lam"] < 0.55 else
                                      "lungo (brand)"),
                "Alla spesa attuale rende ancora?": (
                    "sì, c'è margine" if steady_state_response(m, **p) < 0.6 * p["beta"]
                    else "poco: vicino alla saturazione"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown("**Le curve di rendimento** — più la curva si piega, più il canale è saturo")
        grid = np.linspace(0, 2.5 * max(df[f"spend_{ch}"].mean() for ch in CH), 80)
        curves = pd.DataFrame({"spesa settimanale (€)": grid})
        for ch in CH:
            curves[LABEL[ch]] = [steady_state_response(x, **fit_res["channels"][ch]) for x in grid]
        st.line_chart(curves.set_index("spesa settimanale (€)"))
        st.caption("Lettura: a sinistra (poca spesa) ogni euro rende molto; "
                   "dove la curva si appiattisce, aggiungere budget serve a poco.")

        st.markdown("**Da dove arrivano le candidature, settimana per settimana**")
        dec = pd.DataFrame({"week": df["week"]})
        for ch in CH:
            dec[LABEL[ch]] = channel_response(df[f"spend_{ch}"].to_numpy(float),
                                              **fit_res["channels"][ch])
        st.area_chart(dec.set_index("week"))

        # risultati bayesiani, se disponibili (fit offline con model_bayes.py)
        bpath = os.path.join(HERE, "output", "bayes_curves.json")
        if os.path.exists(bpath):
            st.markdown("---")
            st.markdown("**Versione bayesiana: quanto sono sicure queste curve?**")
            st.caption("Il fit bayesiano (eseguito offline) stima anche l'incertezza: "
                       "la banda mostra dove la curva vera si trova con probabilità 90%.")
            with open(bpath) as f:
                bc = json.load(f)
            ch_sel = st.selectbox("Canale", CH, format_func=lambda c: LABEL[c])
            bdf = pd.DataFrame({
                "spesa (€)": bc[ch_sel]["spend"],
                "stima bassa (5%)": bc[ch_sel]["p05"],
                "mediana": bc[ch_sel]["p50"],
                "stima alta (95%)": bc[ch_sel]["p95"],
            }).set_index("spesa (€)")
            st.line_chart(bdf)
            apath = os.path.join(HERE, "output", "bayes_alloc.json")
            if os.path.exists(apath):
                with open(apath) as f:
                    ba = json.load(f)
                st.success(
                    f"Riallocazione consigliata: guadagno mediano "
                    f"{ba['gain_p50']:+.1%} (tra {ba['gain_p05']:+.1%} e {ba['gain_p95']:+.1%}), "
                    f"probabilità che sia un miglioramento: {ba['prob_gain_positivo']:.0%}.")

# ------------------------------------------------------------ tab Budget
with tab_alloc:
    st.subheader("Trova la distribuzione migliore del budget")
    fit_res = st.session_state.get("fit")
    if not fit_res:
        st.warning("Prima stima il modello nella scheda **2 · Modello**.")
        st.stop()

    cur = {ch: float(df[f"spend_{ch}"].mean()) for ch in CH}

    c1, c2, c3 = st.columns(3)
    budget_annuale = c1.number_input(
        "Budget annuale (€)", min_value=50_000.0,
        value=float(sum(cur.values()) * 52), step=50_000.0, format="%.0f",
        help="Il totale che hai a disposizione per l'anno, su tutti i canali")
    gran = c2.radio("Come lo gestisci?", ["anno", "quarter", "mese"], horizontal=True, index=1,
                    help="Il piano viene calcolato per ciascun periodo scelto")
    max_change = c3.slider(
        "Quanto può cambiare ogni canale?", 0.0, 1.0, 0.5, 0.05,
        help="Prudenza: 0,3 = ogni canale può variare al massimo del ±30% rispetto a oggi. "
             "1,0 = il modello è libero di stravolgere il mix.")

    n_per = allocator.PERIODS[gran]["n"]
    labels = allocator.PERIODS[gran]["label"]
    if n_per > 1:
        st.markdown("**Quanto budget a ogni periodo?** (pesi relativi — es. metti 1,3 a Q4 "
                    "se ti aspetti il picco natalizio della logistica)")
        wdf = st.data_editor(pd.DataFrame({"periodo": labels, "peso": [1.0] * n_per}),
                             hide_index=True, disabled=["periodo"],
                             key=f"pesi_{gran}", use_container_width=True)
        pesi = wdf["peso"].to_numpy(float)
    else:
        pesi = None

    st.markdown("**Limiti per canale** (€/settimana — 0 = nessun limite). "
                "Qui entra la tua conoscenza: contratti minimi, presidi di brand, tetti di rischio.")
    vdf = st.data_editor(
        pd.DataFrame({"canale": [LABEL[ch] for ch in CH],
                      "spesa attuale": [round(cur[ch]) for ch in CH],
                      "minimo": [0.0] * len(CH), "massimo": [0.0] * len(CH)}),
        hide_index=True, disabled=["canale", "spesa attuale"],
        key="vincoli", use_container_width=True)
    inv = {v: k for k, v in LABEL.items()}

    if st.button("Ottimizza l'allocazione", type="primary"):
        min_sp = {inv[r["canale"]]: float(r["minimo"]) for _, r in vdf.iterrows() if r["minimo"] > 0}
        max_sp = {inv[r["canale"]]: float(r["massimo"]) for _, r in vdf.iterrows() if r["massimo"] > 0}
        try:
            plan = allocator.plan_periods(
                fit_res["channels"], total_budget=budget_annuale, granularity=gran,
                period_weights=pesi, current_spend=cur,
                min_spend=min_sp or None, max_spend=max_sp or None,
                max_change_pct=max_change if max_change < 1.0 else None)
        except (ValueError, RuntimeError) as e:
            st.error(f"Vincoli incompatibili: {e}")
            st.stop()

        s = plan.attrs["summary"]
        st.markdown("### Il piano consigliato")
        c1, c2 = st.columns(2)
        c1.metric("Budget pianificato", f"{s['budget_totale']:,.0f} €")
        c2.metric("Candidature attese sul piano", f"{s['candidature_totali']:,.0f}")

        # sintesi in linguaggio naturale
        tot = plan.groupby("canale")["budget_periodo"].sum()
        base = {ch: cur[ch] * 52 * (1 if pesi is None else 1) for ch in CH}
        su = [LABEL[ch] for ch in CH if tot[ch] > cur[ch] * 52 * 1.03]
        giu = [LABEL[ch] for ch in CH if tot[ch] < cur[ch] * 52 * 0.97]
        frase = "Rispetto a oggi il modello consiglia di "
        if su: frase += "**aumentare " + ", ".join(su) + "**"
        if su and giu: frase += " e "
        if giu: frase += "**ridurre " + ", ".join(giu) + "**"
        st.markdown(frase + ". Valuta se è compatibile con contratti e obiettivi di brand: "
                    "la scelta finale è tua.")

        pivot = plan.pivot(index="periodo", columns="canale",
                           values="budget_periodo").loc[labels][CH]
        pivot.columns = [LABEL[ch] for ch in CH]
        st.markdown("**Budget per periodo e canale (€)**")
        st.dataframe(pivot.round(0), use_container_width=True)
        st.bar_chart(pivot)

        with st.expander("Dettaglio completo (per periodo e canale)"):
            det = plan.copy()
            det["canale"] = det["canale"].map(LABEL)
            st.dataframe(det.round(1), use_container_width=True, hide_index=True)
        st.download_button("Scarica il piano (CSV)", plan.to_csv(index=False).encode(),
                           file_name="piano_budget.csv", mime="text/csv")
