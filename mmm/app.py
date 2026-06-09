"""
Budget Allocator MMM — interfaccia Streamlit (paradigma human-in-the-middle).

Avvio:  streamlit run app.py

Flusso:
  1. Dati      — dataset principale (sintetico o CSV proprio) + import di
                 serie esterne in qualsiasi formato (Excel, CSV, PDF, JSON):
                 richieste clienti, ricerche dei lavoratori, ecc.
  2. Modello   — stima MMM, diagnostiche, decomposizione dei contributi
  3. Allocator — budget annuale gestibile per anno/quarter/mese, vincoli
                 per canale, ottimizzazione e tabella di riallocazione
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
st.title("MMM Budget Allocator — Randstad Italia (dati sintetici)")
st.caption("Pipeline Marketing Mix Modeling + ottimizzazione del budget. "
           "L'output e' una raccomandazione: la decisione resta al manager "
           "(human-in-the-middle).")

CH = config.CHANNELS

# ---------------------------------------------------------------- sidebar
st.sidebar.header("1) Dati")
up_main = st.sidebar.file_uploader(
    "Dataset principale (CSV con colonne week, spend_<canale>, applications)",
    type=["csv"])
ups_ext = st.sidebar.file_uploader(
    "Serie esterne: richieste clienti, ricerche lavoratori... "
    "(Excel / CSV / PDF / JSON)",
    type=["xlsx", "xls", "xlsm", "csv", "txt", "tsv", "pdf", "json"],
    accept_multiple_files=True)


@st.cache_data
def load_main(file) -> pd.DataFrame:
    if file is not None:
        return pd.read_csv(file)
    return data_generator.generate()


df = load_main(up_main)

# serie esterne -> colonne ctrl_*
if ups_ext:
    paths = []
    for f in ups_ext:
        suffix = os.path.splitext(f.name)[1]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(f.getbuffer())
        tmp.close()
        paths.append(tmp.name)
    try:
        df = ingestion.merge_controls(df, paths)
        st.sidebar.success(
            f"Serie importate: {[c for c in df.columns if c.startswith('ctrl_')]}")
    except ValueError as e:
        st.sidebar.error(str(e))

tab_dati, tab_modello, tab_alloc = st.tabs(["Dati", "Modello", "Allocator"])

# ---------------------------------------------------------------- tab Dati
with tab_dati:
    st.subheader("Anteprima del dataset settimanale")
    show_cols = [c for c in df.columns if not c.endswith("_true")]
    st.dataframe(df[show_cols].head(30), use_container_width=True)

    c1, c2 = st.columns(2)
    plot_df = df.set_index("week")
    with c1:
        st.markdown("**Spesa per canale (EUR/settimana)**")
        st.line_chart(plot_df[[f"spend_{ch}" for ch in CH]])
    with c2:
        st.markdown("**Candidature e variabili di controllo**")
        ctrl_cols = [c for c in df.columns
                     if c in config.CONTROLS or c.startswith("ctrl_")]
        st.line_chart(plot_df[["applications"] + ctrl_cols])

# ------------------------------------------------------------- tab Modello
with tab_modello:
    st.subheader("Stima del modello MMM")
    st.markdown(
        "Modello: `candidature = baseline + controlli + somma per canale di "
        "beta * Hill(Adstock(spesa))`. Il fit stima per ogni canale l'effetto "
        "massimo (beta), la persistenza (lambda), la half-saturation (K) e "
        "la pendenza (s).")
    if st.button("Stima il modello", type="primary"):
        with st.spinner("Stima in corso (1-2 minuti)..."):
            st.session_state["fit"] = model.fit(df)

    fit_res = st.session_state.get("fit")
    if fit_res:
        d = fit_res["diagnostics"]
        m1, m2, m3 = st.columns(3)
        m1.metric("R²", f"{d['r2']:.3f}")
        m2.metric("NRMSE", f"{d['nrmse']:.3f}")
        m3.metric("MAPE", f"{d['mape']:.2%}")

        st.markdown("**Parametri per canale**")
        st.dataframe(pd.DataFrame(fit_res["channels"]).T.round(3),
                     use_container_width=True)
        if fit_res["controls"]:
            st.markdown("**Coefficienti delle variabili di controllo** "
                        "(candidature per unita' della serie)")
            st.json({k: round(v, 4) for k, v in fit_res["controls"].items()})

        # Decomposizione dei contributi
        st.markdown("**Decomposizione: contributo settimanale dei canali**")
        dec = pd.DataFrame({"week": df["week"]})
        for ch in CH:
            dec[ch] = channel_response(
                df[f"spend_{ch}"].to_numpy(float), **fit_res["channels"][ch])
        st.area_chart(dec.set_index("week"))

        # Curve di risposta a regime
        st.markdown("**Curve di risposta a regime** (spesa settimanale -> "
                    "candidature/settimana)")
        grid = np.linspace(0, 2.5 * max(df[f"spend_{ch}"].mean() for ch in CH), 80)
        curves = pd.DataFrame({"spesa": grid})
        for ch in CH:
            curves[ch] = [steady_state_response(x, **fit_res["channels"][ch])
                          for x in grid]
        st.line_chart(curves.set_index("spesa"))
    else:
        st.info("Premi *Stima il modello* per procedere.")

# ------------------------------------------------------------ tab Allocator
with tab_alloc:
    st.subheader("Ottimizzazione del budget")
    fit_res = st.session_state.get("fit")
    if not fit_res:
        st.warning("Stima prima il modello nella scheda *Modello*.")
        st.stop()

    cur = {ch: float(df[f"spend_{ch}"].mean()) for ch in CH}

    c1, c2, c3 = st.columns(3)
    budget_annuale = c1.number_input(
        "Budget annuale (EUR)", min_value=50_000.0, value=float(sum(cur.values()) * 52),
        step=50_000.0, format="%.0f")
    gran = c2.radio("Gestione del budget", ["anno", "quarter", "mese"],
                    horizontal=True, index=1)
    max_change = c3.slider(
        "Variazione massima per canale vs status quo", 0.0, 1.0, 0.5, 0.05,
        help="0.5 = ogni canale puo' variare al massimo del +/-50% "
             "rispetto alla spesa media storica. 1.0 = nessun vincolo pratico.")

    # pesi dei periodi (editabili: es. piu' budget in Q4)
    n_per = allocator.PERIODS[gran]["n"]
    labels = allocator.PERIODS[gran]["label"]
    st.markdown("**Distribuzione del budget tra i periodi** (pesi relativi, "
                "normalizzati automaticamente)")
    wdf = st.data_editor(
        pd.DataFrame({"periodo": labels, "peso": [1.0] * n_per}),
        hide_index=True, disabled=["periodo"], key=f"pesi_{gran}",
        use_container_width=True)

    # vincoli per canale
    st.markdown("**Vincoli per canale** (EUR/settimana; lascia 0 / vuoto per "
                "nessun vincolo). Qui entra la conoscenza del manager: "
                "minimi contrattuali, presidi di employer branding, tetti di spesa.")
    vdf = st.data_editor(
        pd.DataFrame({"canale": CH,
                      "spesa media storica": [round(cur[ch]) for ch in CH],
                      "minimo": [0.0] * len(CH),
                      "massimo": [0.0] * len(CH)}),
        hide_index=True, disabled=["canale", "spesa media storica"],
        key="vincoli", use_container_width=True)

    if st.button("Ottimizza l'allocazione", type="primary"):
        min_sp = {r["canale"]: float(r["minimo"]) for _, r in vdf.iterrows()
                  if r["minimo"] and r["minimo"] > 0}
        max_sp = {r["canale"]: float(r["massimo"]) for _, r in vdf.iterrows()
                  if r["massimo"] and r["massimo"] > 0}
        try:
            plan = allocator.plan_periods(
                fit_res["channels"], total_budget=budget_annuale,
                granularity=gran, period_weights=wdf["peso"].to_numpy(float),
                current_spend=cur, min_spend=min_sp or None,
                max_spend=max_sp or None,
                max_change_pct=max_change if max_change < 1.0 else None)
        except (ValueError, RuntimeError) as e:
            st.error(str(e))
            st.stop()

        s = plan.attrs["summary"]
        m1, m2 = st.columns(2)
        m1.metric("Budget pianificato", f"{s['budget_totale']:,.0f} EUR")
        m2.metric("Candidature attese (totale piano)",
                  f"{s['candidature_totali']:,.0f}")

        st.markdown("**Piano di allocazione ottimale**")
        pivot = plan.pivot(index="periodo", columns="canale",
                           values="budget_periodo").loc[labels][CH]
        st.dataframe(pivot.round(0), use_container_width=True)
        st.bar_chart(pivot)

        st.markdown("**Dettaglio per periodo e canale**")
        st.dataframe(plan.round(1), use_container_width=True)
        st.download_button(
            "Scarica il piano (CSV)", plan.to_csv(index=False).encode(),
            file_name="piano_budget.csv", mime="text/csv")

        st.info("Il piano e' una raccomandazione del modello: valuta vincoli "
                "contrattuali, obiettivi qualitativi e contesto di mercato "
                "prima di attuarla (human-in-the-middle).")
