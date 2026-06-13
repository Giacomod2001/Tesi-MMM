"""
App web di data ingestion — caso Randstad.

Interfaccia drag-and-drop sopra il motore esistente
(`pipeline.ingestion.build`): l'utente carica i file, il sistema PROPONE
la mappatura, l'utente CONFERMA/corregge a tabella, poi l'ingestion gira
e produce i fatti canonici. Nessun terminale.

Avvio:
    streamlit run app_ingestion.py
"""
from __future__ import annotations

import os
import sys

# rende importabile il pacchetto `pipeline` qualunque sia la CWD
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd
import streamlit as st

from pipeline import config
from pipeline.ingestion import build, mapping

# --------------------------------------------------------------- costanti UI
IGNORA = "— ignora colonna —"
CAMPI_CANONICI = list(mapping.FIELD_ALIASES.keys())
OPZIONI_CAMPO = [IGNORA] + CAMPI_CANONICI
OPZIONI_KIND = ["media", "demand", "seasonality", "individual"]
OPZIONI_CANALE = ["—", "google", "meta", "linkedin", "indeed"]

KIND_LABEL = {
    "media": "Spesa media (Google/Meta/LinkedIn/Indeed)",
    "demand": "Domanda / serie esterna",
    "seasonality": "Stagionalità",
    "individual": "Candidature individuali (CRM, dati personali)",
}

st.set_page_config(page_title="Ingestion MMM — Randstad", layout="wide")


# --------------------------------------------------------------- helper
def salva_upload(files, svuota: bool) -> int:
    """Scrive i file caricati nella cartella raw della pipeline."""
    os.makedirs(config.RAW_DIR, exist_ok=True)
    if svuota:
        for f in os.listdir(config.RAW_DIR):
            p = os.path.join(config.RAW_DIR, f)
            if os.path.isfile(p):
                os.remove(p)
    n = 0
    for uf in files:
        with open(os.path.join(config.RAW_DIR, uf.name), "wb") as out:
            out.write(uf.getbuffer())
        n += 1
    return n


def df_da_plan(sm: mapping.SourceMap) -> pd.DataFrame:
    """Tabella editabile colonna-export -> campo-canonico per un file."""
    righe = [{"colonna nel file": c.source,
              "campo canonico": c.field,
              "confidenza": round(c.confidence, 2)} for c in sm.columns]
    return pd.DataFrame(righe, columns=["colonna nel file",
                                        "campo canonico", "confidenza"])


def desktop_dir() -> str:
    """Trova il Desktop in modo robusto (anche se redirezionato su OneDrive)."""
    home = os.path.expanduser("~")
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                    r"\Shell Folders") as k:
                p = os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0])
                if os.path.isdir(p):
                    return p
        except OSError:
            pass
    cand = os.path.join(home, "Desktop")
    return cand if os.path.isdir(cand) else home


def salva_csv(facts: dict, folder: str) -> list[str]:
    """Scrive i fatti canonici come CSV nella cartella indicata."""
    os.makedirs(folder, exist_ok=True)
    scritti = []
    for name, df in facts.items():
        p = os.path.join(folder, f"{name}.csv")
        df.to_csv(p, index=False)
        scritti.append(p)
    return scritti


# --------------------------------------------------------------- intestazione
st.title("Caricamento dati — Marketing Mix Modeling")
st.caption("Carica gli export di Google Ads, Meta, LinkedIn, Indeed e CRM. "
           "Il sistema propone come leggere le colonne: tu controlli e confermi.")

with st.sidebar:
    st.subheader("Dove salvare i risultati")
    st.text_input("Cartella di output (sul Desktop)",
                  value=os.path.join(desktop_dir(), "MMM_dati_puliti"),
                  key="out_dir")
    st.caption("Dopo l'ingestion i 4 CSV puliti finiscono qui.")

# =============================================================== STEP 1 — upload
st.header("1 · Carica i file")
col_u, col_o = st.columns([3, 1])
with col_u:
    files = st.file_uploader(
        "Trascina qui i file (CSV, Excel, PDF) oppure clicca per sceglierli",
        type=["csv", "tsv", "txt", "xlsx", "xls", "xlsm", "pdf", "json", "gz"],
        accept_multiple_files=True)
with col_o:
    svuota = st.checkbox("Sostituisci i file precedenti", value=True,
                         help="Svuota la cartella prima di caricare i nuovi file.")
    st.caption("Metti il canale nel nome del file "
               "(es. `google_ads.csv`) per il riconoscimento automatico.")

if st.button("Analizza i file", type="primary", disabled=not files):
    n = salva_upload(files, svuota)
    plans, tables = build.propose_plan(config.RAW_DIR)
    st.session_state.plans = plans
    st.session_state.tables = tables
    st.session_state.result = None
    st.success(f"{n} file caricati, {len(plans)} riconosciuti. "
               "Controlla la mappatura qui sotto.")

# =============================================================== STEP 2 — conferma
if st.session_state.get("plans"):
    st.header("2 · Controlla e conferma la mappatura")
    st.caption("Per ogni file: verifica tipo, canale e l'abbinamento "
               "colonne -> campi. Correggi col menù a tendina se serve.")

    edited: dict[str, dict] = {}
    for sm in st.session_state.plans:
        f = sm.file
        with st.expander(f"{f}  ·  {KIND_LABEL.get(sm.kind, sm.kind)}"
                         + (f"  ·  canale: {sm.channel}" if sm.channel else ""),
                         expanded=True):
            for nota in sm.notes:
                st.warning(nota)

            c1, c2, c3 = st.columns([2, 2, 1])
            kind = c1.selectbox(
                "Tipo di file", OPZIONI_KIND,
                index=OPZIONI_KIND.index(sm.kind) if sm.kind in OPZIONI_KIND else 0,
                key=f"kind_{f}",
                format_func=lambda k: KIND_LABEL.get(k, k))
            chan_idx = OPZIONI_CANALE.index(sm.channel) if sm.channel in OPZIONI_CANALE else 0
            channel = c2.selectbox("Canale (solo per spesa media)",
                                   OPZIONI_CANALE, index=chan_idx, key=f"chan_{f}")
            confermato = c3.checkbox("Confermo", value=True, key=f"conf_{f}")

            tab = st.data_editor(
                df_da_plan(sm), key=f"editor_{f}", hide_index=True,
                width="stretch", num_rows="fixed",
                column_config={
                    "colonna nel file": st.column_config.TextColumn(disabled=True),
                    "campo canonico": st.column_config.SelectboxColumn(
                        options=OPZIONI_CAMPO, required=True,
                        help="A quale campo del modello corrisponde questa colonna?"),
                    "confidenza": st.column_config.NumberColumn(
                        disabled=True, format="%.0f%%",
                        help="Quanto è sicuro il riconoscimento automatico."),
                })

            with st.popover("Anteprima dati grezzi"):
                st.dataframe(st.session_state.tables[f].head(8),
                             width="stretch")

            edited[f] = {"kind": kind, "channel": channel,
                         "confirmed": confermato, "tab": tab}

    # ----------------------------------------------------------- esecuzione
    st.divider()
    if st.button("Esegui l'ingestion", type="primary"):
        # ricostruisci i SourceMap dalle modifiche dell'utente
        for sm in st.session_state.plans:
            e = edited[sm.file]
            sm.kind = e["kind"]
            sm.channel = None if e["channel"] == "—" else e["channel"]
            sm.confirmed = e["confirmed"]
            sm.columns = [
                mapping.ColumnMap(str(r["colonna nel file"]),
                                  str(r["campo canonico"]),
                                  float(r["confidenza"]))
                for _, r in e["tab"].iterrows()
                if r["campo canonico"] != IGNORA]

        confermati = [p for p in st.session_state.plans if p.confirmed]
        if not confermati:
            st.error("Nessun file confermato: spunta almeno un «Confermo».")
        else:
            try:
                res = build.ingest(raw_dir=config.RAW_DIR,
                                   plan=st.session_state.plans,
                                   interactive=False,
                                   tables=st.session_state.tables)
                try:
                    salva_csv(res["facts"], st.session_state.out_dir)
                    res["out_dir"] = st.session_state.out_dir
                except OSError as e:
                    res["out_dir"] = None
                    st.warning(f"Ingestion ok, ma non ho potuto salvare "
                               f"nella cartella scelta: {e}")
                st.session_state.result = res
            except Exception as exc:  # noqa: BLE001 — mostra l'errore all'utente
                st.session_state.result = None
                st.error(f"Errore durante l'ingestion: {exc}")

# =============================================================== STEP 3 — risultato
res = st.session_state.get("result")
if res:
    st.header("3 · Risultato")
    st.success("Ingestion completata. I fatti canonici sono pronti per il modello.")

    with st.expander("Log e validazione", expanded=False):
        for line in res["log"]:
            st.text(line)

    tabs = st.tabs([f"{k}  ({len(df):,} righe)"
                    for k, df in res["facts"].items()])
    for tab, (name, df) in zip(tabs, res["facts"].items()):
        with tab:
            st.dataframe(df.head(200), width="stretch")
            st.download_button(
                f"Scarica {name}.csv",
                df.to_csv(index=False).encode("utf-8"),
                file_name=f"{name}.csv", mime="text/csv", key=f"dl_{name}")

    if res.get("out_dir"):
        st.success("I 4 CSV puliti sono stati salvati sul tuo Desktop in:\n\n"
                   f"`{res['out_dir']}`")
        if os.name == "nt" and st.button("Apri la cartella"):
            os.startfile(res["out_dir"])  # noqa: S606 — app locale desktop
    st.caption(f"(Copia anche in `{config.CANON_DIR}` per la pipeline.)")
    st.info("Prossimo passo (su Colab, serve GPU): per la PRODUZIONE usa "
            "`colab_produzione.ipynb` (fit + allocazione budget); per la "
            "DIMOSTRAZIONE `colab_dimostrazione.ipynb` (fit + recovery, "
            "serve anche `ground_truth.json`).")
