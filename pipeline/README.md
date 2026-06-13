# Pipeline MMM & Budget Allocator — caso Randstad Italia

Implementazione del documento di progetto: MMM bayesiano geo-gerarchico
(Google Meridian) su panel **regione × settimana**, con budget allocator
trimestrale a due stadi e validazione quantitativa su dataset sintetico
con ground truth nota.

```
generator/   dati sintetici + ground_truth.json     (solo fase tesi)
ingestion/   parser → mappatura CONFERMATA → validazione → GDPR → panel
model/       Meridian: calibrazione ROAS, stagionalità esogena, geo-gerarchia
allocator/   stage 1 canali (13 settimane, vincoli EUR) → spaccato
             mese/settimana → stage 2 campagne (ROAS riscalati)
validation/  parameter recovery + stress test       (solo fase tesi)
```

## Esecuzione (fase tesi, dati sintetici)

```bash
pip install -r pipeline/requirements.txt

# 1. genera il mondo sintetico (export sporchi + ground truth)
python -m pipeline.generator.run

# 2. ingestion con conferma umana della mappatura (interattiva)
python -m pipeline.ingestion.run
#    rilanci successivi, mappatura già confermata:
python -m pipeline.ingestion.run --plan pipeline/data/canonical/mapping_confirmed.json

# 3. fit Meridian — CONSIGLIATO SU GPU (Colab Pro) o lasciar girare su CPU
python -m pipeline.model.run                  # completo, ~20-40 min su GPU
python -m pipeline.model.run --smoke          # verifica meccanica, stime inutilizzabili

# 4. parameter recovery (stime vs ground truth)
python -m pipeline.validation.recovery
python -m pipeline.validation.stress          # genera gli scenari di stress

# 5. allocazione trimestrale (esempio)
python -m pipeline.allocator.run --budget 450000 \
    --min linkedin=50000 --max meta=250000 --quarter-start 2026-01-05

# test
python -m pytest pipeline/tests -q
```

## App web di ingestion (consigliata per l'operatore)

Per chi non usa il terminale c'è un'interfaccia drag-and-drop che avvolge
lo stesso motore (`build.propose_plan` / `build.ingest`):

```bash
streamlit run app_ingestion.py
```

Flusso: **carica i file → controlla la mappatura proposta in tabella →
conferma → l'ingestion gira e produce i fatti canonici** (con download
CSV). La conferma human-in-the-middle è la stessa della CLI, solo a video.

## Consegna a Randstad (dati reali)

La pipeline è identica: cambiano solo i file in ingresso.

1. Depositare gli export reali in `pipeline/data/raw/` (CSV/XLSX/PDF:
   Meta, Google Ads + report Geografia, LinkedIn, Indeed, estrazione CRM
   delle candidature, serie di domanda, indici stagionali).
2. `python -m pipeline.ingestion.run` (oppure l'**app web** qui sopra) → il
   sistema propone la mappatura colonne→schema canonico; **l'operatore
   conferma o corregge** (il punto human-in-the-middle non è aggirabile).
   La mappatura confermata viene salvata e riusata.
3. I dati individuali vengono **pseudonimizzati** (SHA-256 con sale) e
   aggregati a regione × settimana prima di qualsiasi analisi (GDPR).
4. Fit (`model.run`) e allocazione (`allocator.run`) come sopra. I moduli
   `generator/` e `validation/` non servono in produzione e si possono
   rimuovere senza toccare il resto.

### Ripartizione geografica della spesa (gerarchia di qualità)
1. campagne geo-targettizzate → spesa regionale reale;
2. campagne nazionali → split sulle impression regionali (report
   "Geografia" di Google Ads, breakdown per regione di Meta);
3. nessun breakdown → quota di popolazione (fallback, il log lo segnala).

### Note modellistiche
- Stima a livello **canale**; le campagne vivono nello stage 2
  dell'allocator (ROAS di piattaforma riscalati sul ROI MMM).
- Prior ROI = LogNormale centrata sul ROAS di piattaforma (sigma 0.7).
- Stagionalità esogena come control variable + knot temporali interni
  ridotti a 1/trimestre (anti doppio-conteggio).
- `validation/recovery.py` confronta ROI e adstock con la verità e le
  curve di risposta nel range osservato (la metrica che conta per
  l'allocator).

## Moduli legacy (prototipo tesi, capitoli 4-5)

`mmm/` (fit frequentista + PyMC nazionale, app Streamlit), `core/` e
`app/` (dashboard Dash, MTA Markov) restano nel repo come materiale dei
capitoli precedenti: documentano l'evoluzione del sistema, ma la
pipeline di consegna è questa.
