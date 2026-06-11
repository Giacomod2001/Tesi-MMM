# MMM + MTA Decision Suite

**Applicazione Live:** [https://tesi-mmm.onrender.com](https://tesi-mmm.onrender.com)

Sistema di supporto decisionale per il budget del recruiting digitale, sviluppato per una tesi magistrale IULM. L'applicazione combina due modelli:
1. **MMM (Marketing Mix Modeling)**: livello strategico per l'allocazione del budget tra i canali (con stima della saturazione e dei ritorni marginali).
2. **MTA (Multi-Touch Attribution) con Catene di Markov**: livello tattico per ripartire il budget di canale sulle singole campagne, basato sull'analisi dei percorsi di conversione (Removal Effect).

*L'app usa dati sintetici dimostrativi a scopo accademico.*

## 🚀 Avvio rapido (Locale)

```bash
# Installa le dipendenze
pip install -r requirements.txt

# Avvia l'applicazione Dash
python -m app.main
```
Apri il browser su `http://127.0.0.1:8050`

*Nota: per l'analisi avanzata dell'incertezza (modello Bayesiano in background) è richiesto `pip install -r requirements-bayes.txt`.*

## 🏗️ Architettura

- `app/` — Dashboard multi-pagina sviluppata in **Dash** (tema scuro). Include 4 sezioni: Analisi Descrittiva, Stima & Risposta, Ottimizzazione (MMM), Riparto Campagne (MTA).
- `core/` — Logica agnostica del motore (zero nomi hardcodati):
  - `schema.py` — Riconoscimento automatico di date, spese, KPI e controlli da un CSV arbitrario; generazione intelligente dei vincoli.
  - `mmm_bayes.py` — Fit bayesiano con **PyMC** (Empirical Bayes invariante alle unità di misura).
  - `mta_markov.py` — Attribution multi-touch tramite catene di Markov e calcolo del Removal Effect.
- `mmm/` — Contiene i modelli frequentisti di MMM (Hill + Adstock) e l'algoritmo di ottimizzazione (SLSQP), oltre al generatore del dataset sintetico.
- `data/` — Dataset sintetici settimanali e percorsi aggregati per MTA pre-calcolati.

## 📝 Struttura dell'Applicazione

L'app è costruita per guidare l'utente passo-passo dal dato grezzo alla decisione di business:
1. **1. Analisi Descrittiva**: Esplorazione dello storico investimenti (leve), risultati (KPI) e trend esterni.
2. **2. Stima & Risposta**: Il modello calcola quanto rende ogni euro speso su un canale e dove inizia a saturare, generando le curve di risposta. Include la fascia di incertezza tramite calcolo bayesiano asincrono.
3. **3. Ottimizzazione**: Un algoritmo di ottimizzazione propone il mix ideale di spesa per massimizzare le conversioni a parità di budget.
4. **4. Riparto Campagne**: Calata la strategia di canale, le catene di Markov dicono all'utente come allocare esattamente quel budget di canale tra le varie campagne attive.
