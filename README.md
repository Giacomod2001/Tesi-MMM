# Marketing Mix Modeling (MMM) - Modello Matematico

Repository per la tesi magistrale di Giacomo.
Il progetto implementa un modello matematico puro per il Marketing Mix Modeling (MMM), con stima frequentista, inferenza Bayesiana tramite PyMC e ottimizzazione del budget tramite `scipy.optimize`.

## Come utilizzare il modello

Questo progetto è progettato per essere eseguito da riga di comando, puro backend.

### 1. Installazione
Assicurati di avere Python installato. Clona la repository e installa le dipendenze:
```bash
pip install -r requirements.txt
```

### 2. Esecuzione
Per avviare l'intera pipeline logica (generazione dati, fit frequentista, fit Bayesiano e ottimizzazione budget), esegui:
```bash
python main.py
```
Lo script stamperà a schermo le curve di efficienza, l'incertezza Bayesiana calcolata e la ripartizione ottimale del budget.

## Struttura del Codice Logico
- `mmm/data_generator.py`: Simula un dataset aziendale con logiche di Adstock e Saturazione.
- `core/model.py`: Risolutore Frequentista per trovare i parametri $\beta$, $\lambda$, e $K$ che minimizzano l'errore quadratico medio.
- `core/mmm_bayes.py`: Motore di Inferenza Bayesiana (Markov Chain Monte Carlo) per calcolare gli intervalli di confidenza HDI al 90%.
- `mmm/allocator.py`: Ottimizzatore non lineare per la massimizzazione del ROI marginale (ROAS) con vincoli di budget.
