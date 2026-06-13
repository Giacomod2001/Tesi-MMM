# Marketing Mix Modeling (MMM) — Tesi Magistrale

Repository per la tesi magistrale di Giacomo.
Il progetto affronta il Marketing Mix Modeling (MMM) su due livelli:

- **A) Modello matematico (demo).** Una pipeline compatta e veloce su dati
  sintetici: stima frequentista, inferenza Bayesiana (PyMC) e ottimizzazione
  del budget (`scipy.optimize`). Serve a mostrare la logica MMM end-to-end.
- **B) Pipeline completa Meridian (caso Randstad Italia).** MMM bayesiano
  geo-gerarchico (Google Meridian) su panel regione × settimana, con budget
  allocator trimestrale a due stadi e validazione su ground truth.
  Documentazione dedicata in [`pipeline/README.md`](pipeline/README.md).

---

## Requisiti

- Python 3.11+ (sviluppato e testato su 3.13)
- Per il fit Meridian (workflow B) è consigliata una GPU → usare **Colab**.

---

## A) Modello matematico — `main.py`

Demo rapida (~30 sec) della logica MMM su dati sintetici.

```bash
pip install -r requirements.txt
python main.py
```

Cosa fa, in ordine:
1. **Genera** un dataset settimanale sintetico con Adstock e saturazione.
2. **Fit frequentista** delle curve di risposta (β, λ, K).
3. **Inferenza Bayesiana (MCMC)** con PyMC → medie e intervalli HDI 90%.
4. **Ottimizza il budget** (ROAS marginale con vincoli) e scrive il foglio
   *Ottimizzazione* in `pipeline/data/output/risultati.xlsx`.

### Struttura del codice (workflow A)
- `mmm/data_generator.py` — simula il dataset (Adstock + saturazione).
- `mmm/model.py` — risolutore frequentista (β, λ, K che minimizzano l'MSE).
- `core/mmm_bayes.py` — motore Bayesiano (MCMC) con HDI 90%.
- `mmm/allocator.py` — ottimizzatore non lineare del budget (ROAS, vincoli).
- `results_xlsx.py` — esporta i risultati su Excel.

> Nota: richiede `arviz>=1.0` (API `ci_prob`/`DataTree`), già fissato in
> `requirements.txt`.

---

## B) Pipeline completa Meridian — `pipeline/`

La pipeline "vera" della tesi (caso Randstad), su dati sintetici con ground
truth nota. Si lancia a step:

```bash
pip install -r pipeline/requirements.txt

python -m pipeline.generator.run        # 1. mondo sintetico + ground_truth.json
python -m pipeline.ingestion.run        # 2. ingestion + conferma mappatura (interattivo)
python -m pipeline.model.run            # 3. fit Meridian (~20-40 min, meglio su GPU)
#   python -m pipeline.model.run --smoke #    verifica meccanica veloce (stime inutilizzabili)
python -m pipeline.validation.recovery  # 4. parameter recovery (stime vs ground truth)
python -m pipeline.allocator.run --budget 450000 \
    --min linkedin=50000 --max meta=250000 --quarter-start 2026-01-05   # 5. allocazione

python -m pytest pipeline/tests -q      # test
```

### Caricamento dati senza terminale (app web)
Per l'operatore Randstad c'è un'interfaccia drag-and-drop sopra lo stesso
motore di ingestion:
```bash
streamlit run app_ingestion.py
```
Carichi i file, controlli la mappatura proposta in tabella, confermi: l'app
salva i 4 CSV canonici (media, demand, seasonality, outcome) in una cartella
sul Desktop, pronti per il fit.

### I due workflow: DIMOSTRAZIONE e PRODUZIONE
Lo stesso identico modello serve a due scopi, con nomi distinti per non
confonderli:
- **DIMOSTRAZIONE** (per la tesi): dati finti + verifica che il modello
  funzioni davvero.
- **PRODUZIONE** (per Randstad): dati reali, output = budget consigliato.

| | DIMOSTRAZIONE (tesi) | PRODUZIONE (Randstad) |
|---|---|---|
| 1. Dati | `generator.run`: dati sintetici **+ ground_truth.json** (la verità nota) | export reali di Randstad (niente generazione) |
| 2. Ingestion | `app_ingestion.py` (o `ingestion.run`) | identica |
| 3. Colab | [`colab_dimostrazione.ipynb`](colab_dimostrazione.ipynb): fit **+ parameter recovery** | [`colab_produzione.ipynb`](colab_produzione.ipynb): fit **+ allocazione budget** |
| Risultato | il modello ritrova la verità → il metodo funziona | raccomandazione di budget |

Il fit Meridian richiede una GPU, quindi gira su Colab in entrambi i casi.
La differenza è solo il passo di verifica: nella demo c'è (si confronta con
la verità nota), in produzione no (sui dati reali la verità non esiste — è
proprio ciò che il modello stima).

### Come dimostriamo che il modello funziona (parameter recovery)
La validazione segue tre azioni distinte:
1. **Creare** dati finti di cui si conosce la "verità" (ROI, adstock reali) —
   `pipeline/generator/` con `numpy`.
2. **Stimare** il modello da quei dati — il fit Meridian (`pipeline/model/`).
3. **Verificare** se le stime coincidono con la verità — `validation/recovery`,
   che riporta ROI stimato vs vero, copertura al 90% e errore sulle curve.

Il passo 3 è possibile **solo** con dati finti, perché solo lì la risposta
giusta è nota in anticipo. È questo che dimostra empiricamente la bontà del
modello prima di applicarlo ai dati reali.

> Nota: PyMC e Meridian sono motori di **stima** (azione 2), non generano
> dati; la generazione (azione 1) usa `numpy`. Il prototipo A usa PyMC, la
> pipeline B usa Meridian.

> In alternativa, [`colab_pipeline_mmm.ipynb`](colab_pipeline_mmm.ipynb) fa
> l'intera dimostrazione tutta-in-uno su Colab (genera i dati lì, senza
> passare dall'app).

Per i dettagli (schema canonico, GDPR, consegna su dati reali Randstad) vedi
[`pipeline/README.md`](pipeline/README.md).
