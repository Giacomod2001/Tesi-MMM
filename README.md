# Marketing Mix Modeling (MMM) — Tesi Magistrale

MMM bayesiano geo-gerarchico (Google Meridian) per ottimizzare la spesa
pubblicitaria su Google, Meta, LinkedIn e Indeed. Caso applicativo: Randstad
Italia. Il modello stima il ritorno (ROI/ROAS) di ogni canale su un panel
regione × settimana e propone la ripartizione ottimale del budget trimestrale.

> Descrizione discorsiva di architettura, componenti e scelte modellistiche
> (pensata per la stesura della tesi): [`ARCHITETTURA.md`](ARCHITETTURA.md).

---

## Idea in breve

Il flusso è sempre lo stesso, in tre passi:

1. **Ingestion** — dai file grezzi delle piattaforme ai dati puliti (app web).
2. **Fit** — il modello stima ROI, adstock e curve di risposta (su Colab, GPU).
3. **Uso** — allocazione del budget, oppure verifica che il modello funzioni.

Lo stesso identico modello serve a **due scopi**, tenuti separati con nomi
distinti per non confonderli:

- **DIMOSTRAZIONE** (per la tesi): gira su dati **finti** di cui si conosce
  già la "verità", per provare che il modello stima correttamente.
- **PRODUZIONE** (per Randstad): gira su dati **reali**, per decidere davvero
  come ripartire il budget.

L'unica differenza è il passo finale: la dimostrazione confronta le stime con
la verità nota; la produzione no, perché sui dati reali quella verità non
esiste (è proprio ciò che il modello stima).

---

## Passo 1 — Ingestion (in locale, comune ai due workflow)

Interfaccia drag-and-drop: carichi gli export, controlli come vengono lette
le colonne, confermi.

```bash
pip install -r requirements.txt
streamlit run app_ingestion.py
```

L'app legge file grezzi (CSV, Excel, PDF) di Google Ads, Meta, LinkedIn,
Indeed e CRM, propone la mappatura delle colonne (tu confermi o correggi a
tabella), applica la pseudonimizzazione GDPR e l'aggregazione regione ×
settimana, e salva i **4 file canonici** (`media`, `demand`, `seasonality`,
`outcome`) in una cartella sul Desktop.

---

## Passi 2–3 — Fit e uso (su Colab, serve GPU)

Il fit Meridian richiede una GPU, quindi gira su Colab. Si carica lì i 4 CSV
prodotti dall'app. Due notebook, uno per workflow:

| | DIMOSTRAZIONE (tesi) | PRODUZIONE (Randstad) |
|---|---|---|
| Dati | `pipeline.generator.run`: dati sintetici **+ `ground_truth.json`** | export reali di Randstad |
| Ingestion | app (passo 1) | app (passo 1), identica |
| Notebook | [`colab_dimostrazione.ipynb`](colab_dimostrazione.ipynb) | [`colab_produzione.ipynb`](colab_produzione.ipynb) |
| Su Colab | fit **+ parameter recovery** | fit **+ allocazione budget** |
| Risultato | il modello ritrova la verità → il metodo funziona | ripartizione di budget consigliata |

Aprire un notebook su Colab: `File → Apri notebook → GitHub →`
`Giacomod2001/Tesi-MMM`, oppure il link diretto
`https://colab.research.google.com/github/Giacomod2001/Tesi-MMM/blob/main/colab_produzione.ipynb`.
Poi `Runtime → Cambia tipo di runtime → GPU` ed esegui le celle in ordine.

---

## Come dimostriamo che il modello funziona (parameter recovery)

Tre azioni distinte:

1. **Creare** dati finti di cui si conosce la verità (ROI, adstock reali) —
   `pipeline/generator/`, con `numpy`.
2. **Stimare** il modello da quei dati — il fit Meridian (`pipeline/model/`).
3. **Verificare** che le stime coincidano con la verità — `pipeline/validation/`,
   che riporta ROI stimato vs vero, copertura al 90% e errore sulle curve.

Il passo 3 è possibile **solo** con dati finti, perché solo lì la risposta
giusta è nota in anticipo. È questo che dimostra empiricamente la bontà del
modello prima di usarlo sui dati reali.

---

## Tutto da terminale (senza app né Colab)

La pipeline è eseguibile anche interamente da riga di comando (utile per
sviluppo o se si dispone di una GPU locale):

```bash
pip install -r pipeline/requirements.txt

python -m pipeline.generator.run        # dati sintetici + ground_truth.json
python -m pipeline.ingestion.run        # ingestion + conferma mappatura
python -m pipeline.model.run            # fit Meridian (~20-40 min; --smoke per prova veloce)
python -m pipeline.validation.recovery  # solo DIMOSTRAZIONE: stime vs verità
python -m pipeline.allocator.run --budget 450000 \
    --min linkedin=50000 --max meta=250000 --quarter-start 2026-07-06

python -m pytest pipeline/tests -q       # test
```

---

## Struttura del codice

```
app_ingestion.py     app web di ingestion (Streamlit, gira in locale)
results_xlsx.py      esporta i risultati su Excel (usato dalla pipeline)
colab_dimostrazione.ipynb / colab_produzione.ipynb   notebook Colab (fit su GPU)

pipeline/
  generator/    dati sintetici + ground_truth.json        (solo DIMOSTRAZIONE)
  ingestion/    parser robusti -> mappatura confermata -> GDPR -> panel canonico
  model/        Meridian: ROI, adstock, stagionalità, geo-gerarchia
  allocator/    ottimizzazione budget trimestrale a due stadi (canali -> campagne)
  validation/   parameter recovery + stress test          (solo DIMOSTRAZIONE)
```

Dettagli su schema canonico, GDPR e consegna su dati reali Randstad:
[`pipeline/README.md`](pipeline/README.md).

---

## Requisiti

- Python 3.11+
- App di ingestion (locale): `pip install -r requirements.txt`
- Fit Meridian (Colab/GPU): `pip install -r pipeline/requirements.txt`
