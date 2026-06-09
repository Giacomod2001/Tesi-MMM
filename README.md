# Tesi magistrale — MMM Budget Allocator (caso Randstad Italia)

Marketing Mix Modeling per il recruiting digitale: pipeline analitica,
ottimizzatore di budget e interfaccia operativa. Dati sintetici calibrati
(vincoli di compliance — vedi tesi.md, Nota sui dati).

## Struttura del repository

- `tesi.md` — testo della tesi (Introduzione, Parte I-III)
- `deck_mmm.pptx` — mini deck di sintesi del sistema
- `mmm/` — pipeline Python
  - `config.py` — canali, parametri del processo generativo, controlli
  - `transforms.py` — adstock geometrico + saturazione di Hill
  - `data_generator.py` — dataset sintetico settimanale (156 settimane)
  - `ingestion.py` — import automatico di serie esterne (Excel/CSV/PDF/JSON)
  - `model.py` — fit del modello (scipy, bound informativi)
  - `allocator.py` — ottimizzazione vincolata + pianificazione anno/quarter/mese
  - `app.py` — interfaccia Streamlit
  - `run_pipeline.py` — esecuzione end-to-end riproducibile
  - `test_locale.py` — test di integrazione (usa i file in `mmm/data/esempi/`)
  - `data/esempi/` — file campione: Excel mensile (mesi italiani),
    CSV settimanale (date europee), PDF con tabella

## Avvio rapido

```bash
pip install -r mmm/requirements.txt
cd mmm
python run_pipeline.py      # pipeline completa: dati -> fit -> allocazione
python test_locale.py       # test di integrazione con i file di esempio
streamlit run app.py        # interfaccia web
```
