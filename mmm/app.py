"""
MMM Budget Allocator — interfaccia Streamlit (human-in-the-middle).
Avvio:  streamlit run app.py

I tre tab ricalcano i tre tipi di modello decisionale (cap. 1):
descrittivo (Analisi), predittivo (Stima & Risposta), prescrittivo (Ottimizzazione).
"""
import io
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
COLOR = {"Google": "#4285F4", "Meta": "#E4405F", "LinkedIn": "#0A66C2", "Indeed": "#7A36C2",
         "Candidature": "#2EC4B6", "Richieste clienti": "#FFB703",
         "Ricerche lavoratori": "#8ECAE6"}
HERE = os.path.dirname(os.path.abspath(__file__))

# Soglie del semaforo di saturazione: quota dell'effetto massimo (beta)
# raggiunta alla spesa media corrente.
SAT_VERDE, SAT_GIALLO = 0.70, 0.90

st.title("Budget Allocator — Marketing Mix Modeling")
st.markdown(
    "Analizza lo storico di **spesa e candidature** e trova **come distribuire il budget** "
    "tra i canali per massimizzare le candidature. *Dati sintetici dimostrativi.*")

with st.expander("Come si usa (3 passi)"):
    st.markdown("""
1. **Analisi** — Esplora le tue *leve* (spesa per canale), il *KPI* (candidature) e i *fattori esterni* (domanda di mercato). Puoi caricare i tuoi dati dalla barra a sinistra.
2. **Stima** — Il modello stima le *curve di risposta* di ogni canale: quanto rende ogni euro investito e quando si raggiunge la saturazione.
3. **Ottimizzazione** — Imposta budget e vincoli: il modello trova l'allocazione che massimizza le candidature. La raccomandazione è tua da valutare e decidere.
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
    st.plotly_chart(fig)


def predict_applications(fit_res: dict, data: pd.DataFrame):
    """Candidature previste dal modello sullo storico.

    Replica la specificazione stimata da model.fit():
    baseline (trend + stagionalità) + controlli centrati + risposta dei canali.
    Restituisce None se ai dati mancano colonne usate nella stima
    (es. dataset cambiato dopo il fit).
    """
    t = np.arange(len(data), dtype=float)
    w = 2 * np.pi * (t % 52) / 52
    base = fit_res["baseline"]
    a1, b1, a2, b2 = base["fourier"]
    y = (base["alpha"] + base["trend_per_week"] * t
         + a1 * np.sin(w) + b1 * np.cos(w)
         + a2 * np.sin(2 * w) + b2 * np.cos(2 * w))
    for c, g in fit_res["controls"].items():
        col = c if c in data.columns else f"ctrl_{c}"
        if col not in data.columns:
            return None
        v = data[col].to_numpy(float)
        y = y + g * (v - np.nanmean(v))
    for ch, p in fit_res["channels"].items():
        col = f"spend_{ch}"
        if col not in data.columns:
            return None
        y = y + channel_response(data[col].to_numpy(float), **p)
    return y


def saturazione(p: dict, spesa_media: float) -> tuple[float, str, str]:
    """Quota dell'effetto massimo (beta) raggiunta alla spesa media corrente."""
    quota = steady_state_response(spesa_media, **p) / p["beta"] if p["beta"] else 0.0
    if quota < SAT_VERDE:
        return quota, "🟢", "Margine di crescita"
    if quota < SAT_GIALLO:
        return quota, "🟡", "Si sta saturando"
    return quota, "🔴", "Saturato"


tab_dati, tab_modello, tab_alloc = st.tabs(
    ["1 · Analisi Descrittiva", "2 · Stima & Risposta", "3 · Ottimizzazione"])

# ------------------------------------------------- tab Analisi Descrittiva
with tab_dati:
    c1, c2, c3 = st.columns(3)
    c1.metric("Settimane di storico", len(df))
    c2.metric("Spesa media settimanale", f"{sum(df[f'spend_{ch}'].mean() for ch in CH):,.0f} €")
    c3.metric("Candidature medie/settimana", f"{df['applications'].mean():,.0f}")

    vista, _ = st.columns([1, 2])
    liscia = vista.select_slider("Vista", options=["settimanale", "mensile", "trimestrale"],
                                 value="mensile",
                                 help="La vista aggregata è più leggibile; quella settimanale mostra anche le pause campagna")
    rule = {"settimanale": None, "mensile": "ME", "trimestrale": "QE"}[liscia]

    def aggrega(d: pd.DataFrame) -> pd.DataFrame:
        return d.set_index("week").resample(rule).mean().reset_index() if rule else d

    # --- Le Leve: ciò che controlli ----------------------------------------
    with st.container(border=True):
        st.subheader("🎛️ Le tue Leve (spesa per canale)")
        sel = st.multiselect("Canali da mostrare", [LABEL[c] for c in CH],
                             default=[LABEL[c] for c in CH])
        plot = df[["week"] + [f"spend_{c}" for c in CH]].copy()
        plot.columns = ["week"] + [LABEL[c] for c in CH]
        line_plot(aggrega(plot), [c for c in [LABEL[x] for x in CH] if c in sel],
                  "€/settimana (media)")
        st.caption("Suggerimento: clicca le voci della legenda per accendere/spegnere i canali. "
                   "Nella vista settimanale i 'buchi' sono pause campagna (utili al modello).")

    # --- Il KPI: ciò che vuoi massimizzare ----------------------------------
    with st.container(border=True):
        st.subheader("🎯 Il tuo KPI (candidature)")
        kpi = df[["week", "applications"]].rename(columns={"applications": "Candidature"})
        line_plot(aggrega(kpi), ["Candidature"], "candidature/settimana (media)")

    # --- I Fattori Esterni: ciò che subisci ---------------------------------
    with st.container(border=True):
        st.subheader("🌍 Fattori Esterni (non controllabili)")
        nice = {"richieste_clienti": "Richieste clienti",
                "ricerche_lavoratori": "Ricerche lavoratori"}
        ext_cols = [c for c in df.columns if c in config.CONTROLS or c.startswith("ctrl_")]
        if ext_cols:
            est = df[["week"] + ext_cols].rename(
                columns=lambda c: nice.get(c, c.replace("ctrl_", "").replace("_", " ")))
            line_plot(aggrega(est), [c for c in est.columns if c != "week"], "valore (media)")
        else:
            st.info("Nessuna variabile esterna nel dataset: puoi caricarla dalla barra a sinistra.")
        st.caption("Queste variabili influenzano le candidature ma non dipendono dal tuo "
                   "budget marketing.")

# ------------------------------------------------- tab Stima & Risposta
with tab_modello:
    st.subheader("Il modello stima le curve di risposta dei canali")
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

        # --- Previsto vs osservato: controllo visivo del fit ----------------
        y_hat = predict_applications(fit_res, df)
        if y_hat is None:
            st.info("I dati sono cambiati dopo la stima: premi di nuovo **Stima il modello** "
                    "per aggiornare il confronto fra previsto e osservato.")
        else:
            st.markdown("**Candidature previste vs osservate**")
            fig = go.Figure([
                go.Scatter(x=df["week"], y=df["applications"],
                           name="Candidature osservate",
                           line=dict(color="#8899AA", width=2)),
                go.Scatter(x=df["week"], y=y_hat,
                           name="Candidature previste dal modello",
                           line=dict(color="#4285F4", width=2.5)),
            ])
            fig.update_layout(template="plotly_dark", height=380,
                              margin=dict(l=10, r=10, t=10, b=10),
                              yaxis_title="candidature/settimana", xaxis_title="",
                              legend=dict(orientation="h", y=1.08, title=""))
            st.plotly_chart(fig)
            st.caption("Dove le due linee divergono, un fattore esterno non catturato "
                       "dal modello sta influenzando i risultati.")

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
        st.dataframe(pd.DataFrame(rows), hide_index=True)

        st.markdown("**Curve di risposta** — dove la curva si piega, il canale è saturo")
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
        st.plotly_chart(fig)
        st.caption("La ✕ indica dove sei oggi su ogni curva.")

        # --- Semaforo di saturazione ----------------------------------------
        st.markdown("**Semaforo di saturazione** — quanto ogni canale è vicino al suo tetto")
        for col, ch in zip(st.columns(len(CH)), CH):
            quota, icona, stato = saturazione(fit_res["channels"][ch], df[f"spend_{ch}"].mean())
            col.markdown(f"**{LABEL[ch]}**")
            col.progress(min(quota, 1.0), text=f"{icona} {stato} — {quota:.0%}")
        st.caption("Il valore indica quanto il canale si avvicina al suo effetto massimo. "
                   "Più è alto, meno rende spendere di più.")

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
                st.plotly_chart(fig)
                apath = os.path.join(HERE, "output", "bayes_alloc.json")
                if os.path.exists(apath):
                    ba = json.load(open(apath))
                    st.info(f"Tenendo conto dell'incertezza, la riallocazione spinta ha "
                            f"probabilità {ba['prob_gain_positivo']:.0%} di migliorare: "
                            f"meglio riallocare con prudenza (vincolo di variazione).")

# ------------------------------------------------- tab Ottimizzazione
with tab_alloc:
    fit_res = st.session_state.get("fit")
    if not fit_res:
        st.warning("Prima stima il modello nella scheda **2 · Stima & Risposta**.")
        st.stop()

    cur = {ch: float(df[f"spend_{ch}"].mean()) for ch in CH}
    share = {ch: cur[ch] / sum(cur.values()) for ch in CH}

    st.subheader("Imposta il piano")
    st.caption("I valori sono pre-compilati dal tuo storico. "
               "Modificali secondo i tuoi vincoli operativi.")
    # default: spesa media settimanale dello storico, arrotondata a 1.000 €
    budget_default = max(round(sum(cur.values()) / 1000), 1) * 1000 * 52
    c1, c2, c3 = st.columns(3)
    budget_annuale = c1.number_input("Budget annuale (€)", min_value=50_000.0,
                                     value=float(budget_default),
                                     step=50_000.0, format="%.0f",
                                     help="Pre-compilato: spesa media settimanale dello storico "
                                          "(arrotondata a 1.000 €) × 52 settimane")
    gran = c2.radio("Gestione", ["anno", "quarter", "mese"], horizontal=True, index=1)
    max_change = c3.slider("Variazione massima per canale", 0.0, 1.0, 0.3, 0.05,
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
                             key=f"pesi_{gran}_{usa_sug}")
        pesi = wdf["peso"].to_numpy(float)
        if usa_sug:
            st.caption(f"Periodo più forte nei dati: **{labels[int(np.argmax(pesi_default))]}**. "
                       "Puoi correggere i pesi: conosci cose che i dati non vedono.")
    else:
        pesi = None

    with st.expander("Limiti per canale (contratti, presidi di brand…)"):
        st.caption("Pre-compilati: minimo = 50% e massimo = 200% della spesa media storica. "
                   "Imposta 0 per togliere un limite.")
        vdf = st.data_editor(
            pd.DataFrame({"canale": [LABEL[c] for c in CH],
                          "spesa attuale (€/sett.)": [round(cur[c]) for c in CH],
                          "minimo": [float(round(cur[c] * 0.5)) for c in CH],
                          "massimo": [float(round(cur[c] * 2.0)) for c in CH]}),
            hide_index=True, disabled=["canale", "spesa attuale (€/sett.)"],
            key="vincoli")
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

        # confronto per canale (totali sul piano): alimenta tabella,
        # spiegazione della raccomandazione ed export
        ricap = pd.DataFrame([{
            "canale": ch,
            "sp_prima": float((prima[prima.canale == ch]["spesa_sett"] * wk).sum()),
            "sp_dopo": float(plan[plan.canale == ch]["budget_periodo"].sum()),
            "ca_prima": float((prima[prima.canale == ch]["cand_sett"] * wk).sum()),
            "ca_dopo": float(plan[plan.canale == ch]["candidature_periodo"].sum()),
        } for ch in CH])

        conf_rows = []
        for r in ricap.itertuples():
            conf_rows.append({
                "Canale": LABEL[r.canale],
                "Spesa prima (€)": round(r.sp_prima), "Spesa dopo (€)": round(r.sp_dopo),
                "Δ spesa": f"{(r.sp_dopo - r.sp_prima) / r.sp_prima:+.0%}" if r.sp_prima else "—",
                "Candidature prima": round(r.ca_prima), "Candidature dopo": round(r.ca_dopo),
                "Δ candidature": (f"{r.ca_dopo - r.ca_prima:+,.0f} "
                                  f"({(r.ca_dopo - r.ca_prima) / r.ca_prima:+.1%})"
                                  if r.ca_prima else "—"),
            })
        st.dataframe(pd.DataFrame(conf_rows), hide_index=True)

        # --- Spiegazione della raccomandazione ------------------------------
        delta_sp = dict(zip(ricap["canale"], ricap["sp_dopo"] - ricap["sp_prima"]))
        ch_giu = min(delta_sp, key=delta_sp.get)
        ch_su = max(delta_sp, key=delta_sp.get)
        soglia = 0.01 * budget_annuale  # spostamenti sotto l'1% non si commentano
        if delta_sp[ch_su] > soglia and delta_sp[ch_giu] < -soglia:
            q_giu, ic_giu, lab_giu = saturazione(fit_res["channels"][ch_giu], cur[ch_giu])
            q_su, ic_su, lab_su = saturazione(fit_res["channels"][ch_su], cur[ch_su])
            st.info(
                f"**Perché questa raccomandazione?** Il modello suggerisce di spostare budget "
                f"da **{LABEL[ch_giu]}** verso **{LABEL[ch_su]}**: alla spesa attuale "
                f"{LABEL[ch_giu]} è al **{q_giu:.0%}** del suo effetto massimo "
                f"({ic_giu} {lab_giu.lower()}), mentre {LABEL[ch_su]} è al **{q_su:.0%}** "
                f"({ic_su} {lab_su.lower()}): lì ogni euro in più rende ancora.\n\n"
                f"⚠️ Questa è una **RACCOMANDAZIONE** basata sul modello. "
                f"La decisione finale resta tua.")
        else:
            st.info("Il piano resta vicino al mix attuale: secondo il modello l'allocazione "
                    "di oggi è già quasi ottimale rispetto ai vincoli impostati.\n\n"
                    "⚠️ Questa è una **RACCOMANDAZIONE** basata sul modello. "
                    "La decisione finale resta tua.")

        # --- Export del piano ------------------------------------------------
        esporta = pd.DataFrame({
            "Canale": [LABEL[c] for c in ricap["canale"]],
            "Spesa prima (EUR)": ricap["sp_prima"].round(0),
            "Spesa dopo (EUR)": ricap["sp_dopo"].round(0),
            "Variazione spesa (EUR)": (ricap["sp_dopo"] - ricap["sp_prima"]).round(0),
            "Candidature prima": ricap["ca_prima"].round(0),
            "Candidature dopo": ricap["ca_dopo"].round(0),
            "Variazione candidature": (ricap["ca_dopo"] - ricap["ca_prima"]).round(0),
        })
        dl1, dl2 = st.columns(2)
        dl1.download_button("📥 Scarica piano di riallocazione (CSV)",
                            esporta.to_csv(index=False).encode("utf-8-sig"),
                            file_name="piano_riallocazione.csv", mime="text/csv",
                            on_click="ignore", width="stretch")
        try:
            xbuf = io.BytesIO()
            dettaglio = plan.copy()
            dettaglio["canale"] = dettaglio["canale"].map(LABEL)
            with pd.ExcelWriter(xbuf) as xw:
                esporta.to_excel(xw, sheet_name="Riallocazione", index=False)
                dettaglio.round(1).to_excel(xw, sheet_name="Piano per periodo", index=False)
            dl2.download_button("📥 Scarica piano di riallocazione (Excel)", xbuf.getvalue(),
                                file_name="piano_riallocazione.xlsx",
                                mime="application/vnd.openxmlformats-officedocument."
                                     "spreadsheetml.sheet",
                                on_click="ignore", width="stretch")
        except ImportError:
            dl2.caption("Per l'export Excel serve il pacchetto `openpyxl`.")

        cmp = pd.DataFrame({
            "canale": [LABEL[c] for c in ricap["canale"]] * 2,
            "scenario": ["Prima"] * len(CH) + ["Dopo"] * len(CH),
            "candidature": list(ricap["ca_prima"]) + list(ricap["ca_dopo"])})
        fig = px.bar(cmp, x="canale", y="candidature", color="scenario", barmode="group",
                     color_discrete_map={"Prima": "#8899AA", "Dopo": "#4285F4"},
                     template="plotly_dark")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                          yaxis_title="candidature sul piano", xaxis_title="")
        st.plotly_chart(fig)

        su = [LABEL[r.canale] for r in ricap.itertuples() if r.sp_dopo > r.sp_prima * 1.03]
        giu = [LABEL[r.canale] for r in ricap.itertuples() if r.sp_dopo < r.sp_prima * 0.97]
        frase = "In sintesi: "
        if su: frase += "**più budget a " + ", ".join(su) + "**"
        if su and giu: frase += ", "
        if giu: frase += "**meno a " + ", ".join(giu) + "**"
        st.markdown(frase + f" → **{delta:+,.0f} candidature attese** "
                    f"({delta/cand_prima:+.1%}) a parità di spesa totale.")

        with st.expander("Dettaglio del piano per periodo e canale"):
            pivot = plan.pivot(index="periodo", columns="canale",
                               values="budget_periodo").loc[labels][CH]
            pivot.columns = [LABEL[c] for c in CH]
            st.dataframe(pivot.round(0))
            det = plan.copy(); det["canale"] = det["canale"].map(LABEL)
            st.dataframe(det.round(1), hide_index=True)
        st.download_button("Scarica il dettaglio per periodo (CSV)",
                           plan.to_csv(index=False).encode("utf-8-sig"),
                           file_name="piano_budget.csv", mime="text/csv",
                           on_click="ignore")
