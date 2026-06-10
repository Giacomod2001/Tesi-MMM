"""
MMM Budget Allocator — interfaccia Streamlit (human-in-the-middle).
Avvio:  streamlit run app.py
"""
import json
import os
import tempfile

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
COLOR = {"Google": "#4285F4", "Meta": "#E4405F", "LinkedIn": "#0A66C2", "Indeed": "#7A36C2"}
HERE = os.path.dirname(os.path.abspath(__file__))

st.title("Budget Allocator — Marketing Mix Modeling")
st.markdown(
    "Analizza lo storico di **spesa e candidature** e trova **come distribuire il budget** "
    "tra i canali per massimizzare le candidature. *Dati sintetici dimostrativi.*")

with st.expander("Come si usa (3 passi)"):
    st.markdown("""
1. **Dati** — esplora lo storico (puoi caricare i tuoi file dalla barra a sinistra, anche Excel o PDF).
2. **Modello** — premi *Stima il modello*: impara quanto rende ogni canale e quando si satura.
3. **Budget** — imposta budget e limiti, premi *Ottimizza*: vedi **quanto otterresti col piano nuovo rispetto a oggi**. La decisione finale resta tua.
""")

# ---------------------------------------------------------------- sidebar
st.sidebar.header("I tuoi dati (opzionale)")
st.sidebar.caption("Senza caricare nulla, l'app usa il dataset dimostrativo.")
up_main = st.sidebar.file_uploader("Storico spesa e candidature (CSV)", type=["csv"],
                                   help="Colonne: week, spend_<canale>, applications")
ups_ext = st.sidebar.file_uploader(
    "Serie esterne (richieste clienti, ricerche lavoratori…)",
    type=["xlsx", "xls", "xlsm", "csv", "txt", "tsv", "pdf", "json"],
    accept_multiple_files=True,
    help="Qualsiasi formato: date e numeri vengono riconosciuti da soli")


@st.cache_data
def load_main(file):
    return pd.read_csv(file) if file is not None else data_generator.generate()


df = load_main(up_main)
df["week"] = pd.to_datetime(df["week"])

if ups_ext:
    paths = []
    for f in ups_ext:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.name)[1])
        tmp.write(f.getbuffer()); tmp.close()
        paths.append(tmp.name)
    try:
        df = ingestion.merge_controls(df, paths)
        st.sidebar.success("Serie agganciate: "
                           + ", ".join(c[5:] for c in df.columns if c.startswith("ctrl_")))
    except ValueError as e:
        st.sidebar.error(str(e))


def line_plot(data: pd.DataFrame, ycols: list[str], ytitle: str):
    """Grafico interattivo: clic sulla legenda per accendere/spegnere le serie."""
    d = data.melt(id_vars="week", value_vars=ycols, var_name="serie", value_name="v")
    fig = px.line(d, x="week", y="v", color="serie",
                  color_discrete_map=COLOR, template="plotly_dark")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis_title=ytitle, xaxis_title="",
                      legend=dict(orientation="h", y=1.08, title=""))
    st.plotly_chart(fig, use_container_width=True)


tab_dati, tab_modello, tab_alloc = st.tabs(["1 · Dati", "2 · Modello", "3 · Budget"])

# ---------------------------------------------------------------- tab Dati
with tab_dati:
    c1, c2, c3 = st.columns(3)
    c1.metric("Settimane di storico", len(df))
    c2.metric("Spesa media settimanale", f"{sum(df[f'spend_{ch}'].mean() for ch in CH):,.0f} €")
    c3.metric("Candidature medie/settimana", f"{df['applications'].mean():,.0f}")

    st.subheader("Spesa per canale")
    f1, f2 = st.columns([3, 1])
    sel = f1.multiselect("Canali da mostrare", [LABEL[c] for c in CH],
                         default=[LABEL[c] for c in CH])
    liscia = f2.select_slider("Vista", options=["settimanale", "mensile", "trimestrale"],
                              value="mensile",
                              help="La vista aggregata è più leggibile; quella settimanale mostra anche le pause campagna")
    rule = {"settimanale": None, "mensile": "ME", "trimestrale": "QE"}[liscia]

    plot = df[["week"] + [f"spend_{c}" for c in CH]].copy()
    plot.columns = ["week"] + [LABEL[c] for c in CH]
    if rule:
        plot = plot.set_index("week").resample(rule).mean().reset_index()
    line_plot(plot, [c for c in [LABEL[x] for x in CH] if c in sel], "€/settimana (media)")
    st.caption("Suggerimento: clicca le voci della legenda per accendere/spegnere i canali. "
               "Nella vista settimanale i 'buchi' sono pause campagna (utili al modello).")

    st.subheader("Candidature e domanda esterna")
    cols = ["applications"] + [c for c in df.columns if c in config.CONTROLS or c.startswith("ctrl_")]
    nice = {"applications": "Candidature", "richieste_clienti": "Richieste clienti",
            "ricerche_lavoratori": "Ricerche lavoratori"}
    plot2 = df[["week"] + cols].rename(columns=lambda c: nice.get(c, c.replace("ctrl_", "")))
    if rule:
        plot2 = plot2.set_index("week").resample(rule).mean().reset_index()
    line_plot(plot2, [c for c in plot2.columns if c != "week"], "valore (media)")

# ------------------------------------------------------------- tab Modello
with tab_modello:
    st.subheader("Il modello impara le curve di rendimento dei canali")
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
                  help="Quanta parte dell'andamento il modello spiega. Sopra 0,9 è ottimo.")
        c2.metric("Errore medio", f"{d['mape']:.1%}")

        rows = []
        for ch in CH:
            p = fit_res["channels"][ch]
            m = df[f"spend_{ch}"].mean()
            rows.append({"Canale": LABEL[ch],
                         "Tetto massimo (cand./sett.)": round(p["beta"]),
                         "Spesa per metà tetto": f"{p['K']*(1-p['lam']):,.0f} €",
                         "Effetto nel tempo": ("immediato" if p["lam"] < 0.25 else
                                               "qualche settimana" if p["lam"] < 0.55 else
                                               "lungo (brand)"),
                         "Margine alla spesa attuale": (
                             "sì, c'è spazio" if steady_state_response(m, **p) < 0.6 * p["beta"]
                             else "poco: vicino alla saturazione")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown("**Curve di rendimento** — dove la curva si piega, il canale è saturo")
        grid = np.linspace(0, 2.5 * max(df[f"spend_{ch}"].mean() for ch in CH), 80)
        fig = go.Figure()
        for ch in CH:
            fig.add_trace(go.Scatter(
                x=grid, y=[steady_state_response(x, **fit_res["channels"][ch]) for x in grid],
                name=LABEL[ch], line=dict(color=COLOR[LABEL[ch]], width=3)))
            m = df[f"spend_{ch}"].mean()
            fig.add_trace(go.Scatter(
                x=[m], y=[steady_state_response(m, **fit_res["channels"][ch])],
                mode="markers", marker=dict(color=COLOR[LABEL[ch]], size=12, symbol="x"),
                name=f"{LABEL[ch]} oggi", showlegend=False))
        fig.update_layout(template="plotly_dark", height=420,
                          xaxis_title="spesa settimanale (€)",
                          yaxis_title="candidature/settimana",
                          legend=dict(orientation="h", y=1.08),
                          margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("La ✕ indica dove sei oggi su ogni curva.")

        bpath = os.path.join(HERE, "output", "bayes_curves.json")
        if os.path.exists(bpath):
            with st.expander("Quanto sono sicure queste curve? (analisi bayesiana)"):
                with open(bpath) as f:
                    bc = json.load(f)
                ch_sel = st.selectbox("Canale", CH, format_func=lambda c: LABEL[c])
                b = bc[ch_sel]
                fig = go.Figure([
                    go.Scatter(x=b["spend"], y=b["p95"], line=dict(width=0), showlegend=False),
                    go.Scatter(x=b["spend"], y=b["p05"], fill="tonexty",
                               fillcolor="rgba(100,150,255,0.25)", line=dict(width=0),
                               name="banda 90%"),
                    go.Scatter(x=b["spend"], y=b["p50"], name="stima centrale",
                               line=dict(color="#4285F4", width=3))])
                fig.update_layout(template="plotly_dark", height=350,
                                  xaxis_title="spesa (€)", yaxis_title="candidature/sett.",
                                  margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
                apath = os.path.join(HERE, "output", "bayes_alloc.json")
                if os.path.exists(apath):
                    ba = json.load(open(apath))
                    st.info(f"Tenendo conto dell'incertezza, la riallocazione spinta ha "
                            f"probabilità {ba['prob_gain_positivo']:.0%} di migliorare: "
                            f"meglio riallocare con prudenza (vincolo di variazione).")

# ------------------------------------------------------------ tab Budget
with tab_alloc:
    fit_res = st.session_state.get("fit")
    if not fit_res:
        st.warning("Prima stima il modello nella scheda **2 · Modello**.")
        st.stop()

    cur = {ch: float(df[f"spend_{ch}"].mean()) for ch in CH}
    share = {ch: cur[ch] / sum(cur.values()) for ch in CH}

    st.subheader("Imposta il piano")
    c1, c2, c3 = st.columns(3)
    budget_annuale = c1.number_input("Budget annuale (€)", min_value=50_000.0,
                                     value=float(sum(cur.values()) * 52),
                                     step=50_000.0, format="%.0f")
    gran = c2.radio("Gestione", ["anno", "quarter", "mese"], horizontal=True, index=1)
    max_change = c3.slider("Variazione massima per canale", 0.0, 1.0, 0.5, 0.05,
                           help="0,3 = ogni canale può cambiare al massimo del ±30% rispetto a oggi")

    n_per = allocator.PERIODS[gran]["n"]
    labels = allocator.PERIODS[gran]["label"]
    if n_per > 1:
        usa_sug = st.toggle("Suggerisci i pesi dei periodi dai dati", value=True,
                            help="Più budget nei periodi in cui lo storico mostra picchi di domanda")
        pesi_default = (allocator.suggest_period_weights(df, gran)
                        if usa_sug else np.ones(n_per))
        wdf = st.data_editor(pd.DataFrame({"periodo": labels, "peso": pesi_default}),
                             hide_index=True, disabled=["periodo"],
                             key=f"pesi_{gran}_{usa_sug}", use_container_width=True)
        pesi = wdf["peso"].to_numpy(float)
        if usa_sug:
            st.caption(f"Periodo più forte nei dati: **{labels[int(np.argmax(pesi_default))]}**. "
                       "Puoi correggere i pesi: conosci cose che i dati non vedono.")
    else:
        pesi = None

    with st.expander("Limiti per canale (contratti, presidi di brand…)"):
        vdf = st.data_editor(
            pd.DataFrame({"canale": [LABEL[c] for c in CH],
                          "spesa attuale (€/sett.)": [round(cur[c]) for c in CH],
                          "minimo": [0.0] * len(CH), "massimo": [0.0] * len(CH)}),
            hide_index=True, disabled=["canale", "spesa attuale (€/sett.)"],
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

        # --- PRIMA vs DOPO -------------------------------------------------
        # PRIMA = stesso budget per periodo, distribuito col mix attuale
        wk = allocator.PERIODS[gran]["weeks"]
        w = (np.asarray(pesi, float) / np.sum(pesi)) if pesi is not None else np.array([1.0])
        prima_rows = []
        for i, per in enumerate(labels):
            weekly_budget = budget_annuale * w[i] / wk
            for ch in CH:
                x = weekly_budget * share[ch]
                prima_rows.append({"periodo": per, "canale": ch, "spesa_sett": x,
                                   "cand_sett": steady_state_response(x, **fit_res["channels"][ch])})
        prima = pd.DataFrame(prima_rows)

        cand_prima = float((prima["cand_sett"] * wk).sum())
        cand_dopo = float(plan["candidature_periodo"].sum())
        delta = cand_dopo - cand_prima

        st.markdown("## Prima vs Dopo")
        st.caption("**Prima** = stesso budget, distribuito come oggi. "
                   "**Dopo** = il piano ottimizzato dal modello.")
        m1, m2, m3 = st.columns(3)
        m1.metric("Candidature col mix attuale", f"{cand_prima:,.0f}")
        m2.metric("Candidature col piano nuovo", f"{cand_dopo:,.0f}")
        m3.metric("Differenza", f"{delta:+,.0f}", f"{delta/cand_prima:+.1%}")

        # confronto per canale (totali sul piano)
        conf_rows = []
        for ch in CH:
            sp_p = float((prima[prima.canale == ch]["spesa_sett"] * wk).sum())
            sp_d = float(plan[plan.canale == ch]["budget_periodo"].sum())
            ca_p = float((prima[prima.canale == ch]["cand_sett"] * wk).sum())
            ca_d = float(plan[plan.canale == ch]["candidature_periodo"].sum())
            conf_rows.append({
                "Canale": LABEL[ch],
                "Spesa prima (€)": round(sp_p), "Spesa dopo (€)": round(sp_d),
                "Δ spesa": f"{(sp_d-sp_p)/sp_p:+.0%}" if sp_p else "—",
                "Candidature prima": round(ca_p), "Candidature dopo": round(ca_d),
                "Δ candidature": f"{ca_d-ca_p:+,.0f} ({(ca_d-ca_p)/ca_p:+.1%})" if ca_p else "—",
            })
        st.dataframe(pd.DataFrame(conf_rows), use_container_width=True, hide_index=True)

        cmp = pd.DataFrame({
            "canale": [LABEL[c] for c in CH] * 2,
            "scenario": ["Prima"] * len(CH) + ["Dopo"] * len(CH),
            "candidature": [float((prima[prima.canale == c]["cand_sett"] * wk).sum()) for c in CH]
                          + [float(plan[plan.canale == c]["candidature_periodo"].sum()) for c in CH]})
        fig = px.bar(cmp, x="canale", y="candidature", color="scenario", barmode="group",
                     color_discrete_map={"Prima": "#8899AA", "Dopo": "#4285F4"},
                     template="plotly_dark")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                          yaxis_title="candidature sul piano", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

        su = [LABEL[c] for c in CH
              if plan[plan.canale == c]["budget_periodo"].sum()
              > (prima[prima.canale == c]["spesa_sett"] * wk).sum() * 1.03]
        giu = [LABEL[c] for c in CH
               if plan[plan.canale == c]["budget_periodo"].sum()
               < (prima[prima.canale == c]["spesa_sett"] * wk).sum() * 0.97]
        frase = "In sintesi: "
        if su: frase += "**più budget a " + ", ".join(su) + "**"
        if su and giu: frase += ", "
        if giu: frase += "**meno a " + ", ".join(giu) + "**"
        st.markdown(frase + f" → **{delta:+,.0f} candidature attese** "
                    f"({delta/cand_prima:+.1%}) a parità di spesa totale. "
                    "Valuta contratti e obiettivi di brand prima di attuare: la scelta è tua.")

        with st.expander("Dettaglio del piano per periodo e canale"):
            pivot = plan.pivot(index="periodo", columns="canale",
                               values="budget_periodo").loc[labels][CH]
            pivot.columns = [LABEL[c] for c in CH]
            st.dataframe(pivot.round(0), use_container_width=True)
            det = plan.copy(); det["canale"] = det["canale"].map(LABEL)
            st.dataframe(det.round(1), use_container_width=True, hide_index=True)
        st.download_button("Scarica il piano (CSV)", plan.to_csv(index=False).encode(),
                           file_name="piano_budget.csv", mime="text/csv")
