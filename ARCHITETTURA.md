# Architettura del sistema MMM — documento descrittivo

Documento in prosa pensato per la stesura della tesi: descrive *come è fatto*
il sistema (file, componenti, workflow, scelte modellistiche), non i risultati
numerici. Per le istruzioni operative vedi [`README.md`](README.md) e
[`pipeline/README.md`](pipeline/README.md).

---

## 1. Obiettivo

Il sistema realizza un **Marketing Mix Modeling (MMM)** per ottimizzare la
spesa pubblicitaria di Randstad Italia su quattro canali — Google Ads, Meta,
LinkedIn, Indeed — finalizzata all'acquisizione di candidati. Stima quanto
ogni canale contribuisce alle candidature (il ritorno, ROI/ROAS), tenendo
conto di effetti non lineari (saturazione) e ritardati (adstock), e propone
la **ripartizione ottimale del budget** su base trimestrale.

L'approccio è un **MMM bayesiano geo-gerarchico** basato su Google Meridian,
stimato su un panel **regione × settimana** (20 regioni italiane, frequenza
settimanale con settimana che inizia il lunedì).

---

## 2. Il modello dei dati (schema canonico)

Tutta la pipeline ragiona su quattro "fatti" canonici, ciascuno con
granularità regione × settimana, valuta EUR, date ISO 8601:

- **media** — la spesa pubblicitaria: `week, region, channel, campaign,
  spend, impressions, clicks, platform_conversions`.
- **outcome** — il risultato di business: `week, region, conversions,
  revenue` (candidature e ricavo/fatturato).
- **demand** — fattori di domanda esterni: `week, region, client_requests,
  candidate_searches`.
- **seasonality** — l'indice di stagionalità: `week, region, seasonal_index`
  (la regione può essere `*` = nazionale).

La scelta di un livello canonico unico è centrale: qualunque sia il formato
degli export reali, vengono ricondotti a queste quattro tabelle, ed è solo su
queste che lavorano modello e allocatore. Le campagne vivono come dettaglio
del fatto media e vengono riaggregate al livello canale per la stima.

---

## 3. I componenti della pipeline

Il codice del sistema sta in `pipeline/`, organizzato in cinque moduli che
corrispondono alle fasi logiche.

### 3.1 `generator/` — mondo sintetico (solo per la dimostrazione)
Genera un dataset finto realistico (con `numpy`) che imita gli export sporchi
delle piattaforme, e soprattutto produce `ground_truth.json`: i **veri**
parametri nascosti (ROI, adstock, ecc.) da cui i dati sono stati generati.
Questa "verità nota" è ciò che permette in seguito di verificare se il modello
stima correttamente. In produzione questo modulo non si usa: i dati sono reali.

### 3.2 `ingestion/` — dai file grezzi al panel canonico
È il modulo che trasforma gli export reali (eterogenei, sporchi) nei quattro
fatti canonici. Si articola in:

- **parser robusti** (`parsers.py`): leggono CSV/TSV, Excel multi-foglio e
  tabelle dentro i PDF, gestendo righe di intestazione e di totale,
  separatori variabili, BOM, compressione gzip. Restituiscono tabelle grezze
  senza interpretazione semantica.
- **mappatura semi-automatica con conferma umana** (`mapping.py`): riconosce a
  quale campo canonico corrisponde ogni colonna, tramite un vocabolario di
  alias multilingua (italiano/inglese) ed euristiche, e assegna una
  confidenza. Il sistema **propone**, l'operatore **conferma o corregge**:
  è il punto *human-in-the-middle* del progetto, non aggirabile, e tracciato
  in un file di mappatura confermata (audit trail).
- **pseudonimizzazione GDPR** (`privacy.py`): i dati individuali del CRM
  (nome, cognome, codice fiscale, ID) vengono sostituiti da uno pseudonimo
  (SHA-256 con sale non salvato), l'età diventa fascia quinquennale, e tutto
  viene **aggregato a regione × settimana** prima di qualsiasi analisi. Nel
  modello non entra mai un dato personale.
- **ripartizione geografica** (`geo_split.py`): quando la spesa non è già
  regionale, viene ripartita con una gerarchia di qualità: (1) campagne
  geo-targettizzate → spesa regionale reale; (2) campagne nazionali → split
  sulle impression regionali (report "Geografia" di Google, breakdown di
  Meta); (3) in assenza di breakdown → quota di popolazione residente
  (fallback, segnalato nel log).

### 3.3 `model/` — la stima (Google Meridian)
Stima il MMM bayesiano. Per ogni canale ricava la **curva di risposta**
(quanto rende un euro speso, con saturazione di tipo Hill e memoria di tipo
adstock) e il **ROI** con la relativa incertezza (intervalli di credibilità).
Scelte modellistiche principali:

- prior sul ROI = **LogNormale** centrata sul ROAS di piattaforma (sigma 0.7):
  si parte da ciò che le piattaforme dichiarano, lasciando che i dati
  correggano;
- **stagionalità esogena** introdotta come variabile di controllo, con i nodi
  temporali interni del modello ridotti (≈1 per trimestre) per evitare il
  doppio conteggio dell'effetto stagionale;
- struttura **geo-gerarchica**: le regioni condividono informazione, utile
  dove i dati regionali sono scarsi.

L'output è `model_fit.json` (sintesi a posteriori per canale) e il modello
serializzato.

### 3.4 `allocator/` — ottimizzazione del budget
Dato il ROI stimato e i vincoli (budget totale, minimi/massimi per canale),
calcola la ripartizione ottimale su un trimestre (13 settimane). Lavora a
**due stadi**: prima alloca tra i canali, poi spacca il risultato in
mese/settimana e infine ridistribuisce a livello di campagna (riscalando i
ROAS di piattaforma sul ROI stimato dal modello).

### 3.5 `validation/` — la prova che il modello funziona
- **`recovery.py`** (*parameter recovery*): confronta le stime del modello
  con la verità nota di `ground_truth.json` — ROI stimato vs vero, copertura
  al 90% (quante volte il valore vero cade nell'intervallo del modello), e
  errore percentuale sulle curve di risposta nel range di spesa osservato.
- **`stress.py`**: genera scenari di stress (es. storici più corti) per
  saggiare la robustezza delle stime.

Questi moduli hanno senso solo con dati sintetici, perché solo lì la verità è
nota in anticipo.

---

## 4. I due workflow

Lo stesso modello (Meridian) viene usato in due modi, con nomi distinti:

- **DIMOSTRAZIONE** (tesi): si parte da dati sintetici con verità nota, si fa
  l'ingestion (anche tramite l'app), si stima il modello, e si esegue il
  *parameter recovery*. Scopo: dimostrare empiricamente che il metodo
  ricostruisce parametri noti, prima di applicarlo a dati reali. Notebook:
  `colab_dimostrazione.ipynb`.
- **PRODUZIONE** (Randstad): si parte dagli export reali, stessa ingestion,
  stessa stima, e poi l'ottimizzazione del budget. Non c'è verifica di
  recovery, perché sui dati reali la "verità" del ROI non è nota — è proprio
  ciò che si vuole stimare. Notebook: `colab_produzione.ipynb`.

La pipeline è identica nei due casi: cambia solo l'origine dei dati e la
presenza (demo) o assenza (produzione) del passo di validazione.

---

## 5. L'app di ingestion

`app_ingestion.py` è un'interfaccia web (Streamlit) che avvolge il motore di
ingestion: l'operatore trascina i file, vede la mappatura proposta in una
tabella editabile, conferma, e ottiene i quattro CSV canonici. Serve a rendere
accessibile a un utente non tecnico esattamente la stessa logica della
versione da riga di comando (`ingestion.run`), conferma human-in-the-middle
inclusa.

---

## 6. Dove gira: locale vs Colab

Il fit Meridian è oneroso e trae vantaggio dalla GPU, quindi gira su Google
Colab; le fasi leggere (ingestion, allocazione) girano in locale. I due
notebook caricano su Colab i CSV canonici prodotti localmente dall'app e
lanciano la stima. L'ingestion locale e il fit su GPU sono così separati per
ragioni puramente di calcolo, non di logica.

---

## 7. Privacy e conformità (GDPR)

Il trattamento dei dati individuali (candidature CRM) avviene una sola volta,
in ingestion, con pseudonimizzazione irreversibile e aggregazione immediata a
regione × settimana. Il modello e l'allocatore non vedono mai dati personali,
ma solo aggregati. La mappatura confermata e il log dell'ingestion fungono da
traccia di controllo.
