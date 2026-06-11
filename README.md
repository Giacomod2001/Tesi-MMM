# MMM + MTA Decision Suite

Sistema di supporto decisionale per il budget del recruiting digitale:
**MMM** (livello strategico, allocazione inter-canale) + **MTA** con catene
di Markov (livello tattico, riparto intra-canale per campagna).
Dati sintetici — caso di studio, tesi magistrale IULM.

## Avvio rapido

```bash
pip install -r requirements.txt
python -m app.main          # dashboard Dash (tema scuro) su http://127.0.0.1:8050
```

Fit bayesiano: si lancia dall'interfaccia (pagina Predittiva, background
callback) oppure offline. Richiede `pip install -r requirements-bayes.txt`.

## Architettura

- `app/` — dashboard Dash multi-pagina: Descrittiva / Predittiva /
  Prescrittiva / MTA. Background callback (diskcache) per il fit bayesiano.
- `core/` — logica agnostica (zero nomi hardcodati):
  - `schema.py` — auto-detect di date, spese, KPI e controlli in CSV arbitrari;
    vincoli ottimizzatore derivati dallo storico
  - `mmm_bayes.py` — fit bayesiano PyMC con prior **Empirical Bayes**
    (ancorati al fit frequentista o alle scale del dataset; invariante alle
    unita' di misura)
  - `mta_markov.py` — attribution Markov (removal effect), metriche volume /
    utility, riparto tattico del budget di canale tra le campagne
  - `datagen_mta.py` — generatore di ~800k percorsi utente sintetici
    (funnel a 3 stadi, demografia, utility per categoria)
- `mmm/` — pipeline MMM originale (fit frequentista scipy, allocator
  multi-periodo, ingestione Excel/CSV/PDF, app Streamlit legacy, test)
- `data/` — percorsi MTA (campione + aggregati di transizione + completo
  compresso), posterior bayesiane pre-calcolate

## Test e riproducibilita'

```bash
cd mmm && python run_pipeline.py && python test_locale.py
python core/datagen_mta.py     # rigenera gli 800k percorsi (seed fisso)
```
