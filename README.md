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

Per i dettagli (schema canonico, GDPR, consegna su dati reali Randstad) vedi
[`pipeline/README.md`](pipeline/README.md).

Il notebook [`colab_pipeline_mmm.ipynb`](colab_pipeline_mmm.ipynb) replica il
fit su Colab (GPU) quando il modello Meridian è troppo lento in locale.
