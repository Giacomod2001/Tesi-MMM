> **NOTA (12/06/2026): documento superato.** Questo materiale descriveva l'evoluzione intermedia del sistema (dashboard Dash, fit PyMC Empirical Bayes, livello tattico MTA a catene di Markov). La tesi ha adottato il pivot completo all'architettura Meridian geo-gerarchica con stage 2 a ROAS riscalati (vedi `tesi.md`, Capitoli 3-4, e `pipeline/`). Conservato come documentazione storica del prototipo (`mmm/`, `core/`, `app/`).

# Aggiornamento tesi — evoluzione enterprise del sistema

*Materiale teorico per l'integrazione dei capitoli. Tre temi: la migrazione dell'interfaccia a un paradigma asincrono (Dash), la rappresentazione dell'incertezza bayesiana come requisito decisionale, e l'architettura ibrida MMM + MTA a due livelli. Chiude una nota metodologica sull'Empirical Bayes e sull'agnosticismo dei dati.*

---

## 1. Dalla pagina reattiva alla dashboard asincrona: perché Dash

### 1.1 Il limite architetturale del prototipo

Il prototipo dell'interfaccia operativa era stato realizzato in Streamlit, framework che adotta un modello di esecuzione *script-rerun*: a ogni interazione dell'utente l'intero script viene rieseguito dall'alto verso il basso. Questo paradigma è ideale per la prototipazione — il codice coincide con il flusso della pagina — ma presenta due limiti strutturali quando il sistema deve evolvere verso l'uso aziendale.

Il primo è il blocco sincrono. In Streamlit ogni computazione vive dentro il ciclo di rendering: se l'utente lancia un'operazione lunga, la pagina resta bloccata fino al completamento. Per il fit frequentista (decine di secondi) il problema è gestibile con un indicatore di attesa; per il fit bayesiano (decine di minuti di campionamento MCMC) diventa proibitivo: nessun utente aziendale accetta un'applicazione congelata per venti minuti, e i timeout delle piattaforme di hosting interrompono comunque l'esecuzione. La conseguenza pratica, documentata nel Capitolo 5, era che il fit bayesiano poteva girare solo *offline*, fuori dall'interfaccia — una frattura nel ciclo decisionale che il paradigma human-in-the-middle vorrebbe invece continuo.

Il secondo è la granularità della reattività. Il rerun integrale rende costoso costruire dashboard multi-vista con stato condiviso e aggiornamenti selettivi: ogni interazione paga il costo dell'intera pagina, e la separazione tra le fasi del ragionamento analitico va simulata anziché essere una proprietà dell'architettura.

### 1.2 Il modello a callback e i background callback

Plotly Dash adotta il modello opposto: l'interfaccia è un grafo dichiarativo di componenti, e la logica vive in *callback* — funzioni che reagiscono a specifici input e aggiornano specifici output. Solo ciò che dipende dall'interazione viene ricalcolato. Su questa base, i *background callback* (con coda su Diskcache nella configurazione corrente, scalabile a Celery/Redis in produzione) disaccoppiano l'esecuzione dalla richiesta HTTP: il fit bayesiano parte in un processo separato, l'utente continua a navigare le altre viste, e al completamento i grafici si aggiornano con le bande di incertezza.

La portata concettuale della scelta supera l'ergonomia. Il passaggio al paradigma asincrono allinea l'architettura tecnica al modello decisionale della tesi: il decisore non deve scegliere tra "risposta immediata ma povera" (stime puntuali) e "risposta ricca ma bloccante" (posterior bayesiana); ottiene subito la prima e riceve la seconda quando pronta, dentro la stessa interfaccia e senza interruzione del flusso di lavoro. L'asincronia è la condizione tecnica perché l'incertezza — computazionalmente costosa — possa entrare nella pratica quotidiana anziché restare un esercizio da notebook.

### 1.3 La struttura in tre fasi: descrittiva, predittiva, prescrittiva

La nuova interfaccia organizza la navigazione secondo la tassonomia classica della business analytics. La vista **descrittiva** risponde a «cosa è successo»: KPI aggregati, serie storiche delle leve (la spesa per canale), del risultato e dei fattori esterni, mix di spesa. La vista **predittiva** risponde a «cosa succederebbe»: curve di risposta stimate, livello di saturazione di ciascun canale alla spesa corrente, confronto tra risultati previsti e reali come validazione visiva del modello. La vista **prescrittiva** risponde a «cosa conviene fare»: l'ottimizzatore vincolato che produce la raccomandazione di allocazione. A queste si aggiunge la vista tattica MTA (Sezione 3). La sequenza non è solo informativa ma pedagogica: costringe il percorso decisionale a passare dalla comprensione dei dati alla comprensione del modello prima di arrivare alla raccomandazione — l'ordine inverso dell'uso ingenuo degli strumenti analitici, dove si salta alla risposta senza aver guardato né i dati né le assunzioni.

---

## 2. Mostrare l'incertezza: dalla linea alla banda

### 2.1 Perché una stima puntuale è un'informazione incompleta

Il Capitolo 5 ha documentato il fenomeno: la riallocazione che il modello a stime puntuali presentava come guadagno certo (+1,7%) risultava avere, sotto la distribuzione a posteriori delle curve, soltanto il 13% di probabilità di produrre un miglioramento. La radice del problema è generale e nota in letteratura (l'analogo finanziario è la "massimizzazione dell'errore" nell'ottimizzazione di portafoglio): un ottimizzatore spinge l'allocazione esattamente dove le stime sono più favorevoli, che è anche dove l'errore di stima si concentra. Una linea sola sul grafico comunica una certezza che il modello non possiede; la decisione presa su quella linea eredita silenziosamente tutto il rischio non mostrato.

### 2.2 La banda HDI come oggetto decisionale

Nella nuova interfaccia ogni curva di risposta è accompagnata, quando la posterior è disponibile, dalla banda HDI al 90% (Highest Density Interval): la regione in cui la curva vera si trova con probabilità 0,9 dato il modello e i dati. La banda non è un ornamento statistico ma cambia le domande che l'utente può porre. Dove la banda è stretta (tipicamente nel range di spesa storicamente esplorato), la raccomandazione è affidabile; dove si allarga (in extrapolazione, oltre le spese mai provate), il grafico stesso avverte che il modello sta indovinando. Il confronto tra canali diventa un confronto tra distribuzioni: un canale con mediana più alta ma banda larghissima può essere una scommessa peggiore di un canale con mediana inferiore ma stimato con precisione. E la sovrapposizione tra le bande di due canali dice al manager se la differenza tra i loro rendimenti è reale o compatibile con il rumore.

In termini di human-in-the-middle, la banda è il canale di comunicazione attraverso cui il modello dichiara i propri limiti al decisore — il complemento simmetrico dei prior, con cui il decisore dichiara la propria conoscenza al modello.

### 2.3 Nota metodologica: prior Empirical Bayes

La versione enterprise del fit bayesiano adotta una disciplina rigorosa sui prior, imposta dalla regola di agnosticismo dei dati: nessun parametro di prior può essere un "numero magico" legato alle unità di misura. I centri dei prior sono derivati dinamicamente: quando è disponibile il fit frequentista, le sue stime puntuali ancorano i prior bayesiani (approccio Empirical Bayes: β → Normale troncata centrata sulla stima frequentista, K → LogNormale centrata sul K frequentista, λ e s → Beta e Gamma con media pari alle stime); in assenza, centri e scale derivano dalle statistiche del dataset (spesa media del canale, deviazione standard del target). Le uniche costanti fisse sono rapporti adimensionali (dispersioni relative, concentrazioni), invarianti per costruzione al cambio di unità: il sistema produce stime coerenti sia che la spesa sia espressa in centinaia di euro sia in milioni, requisito verificato con test esplicito. Il costo metodologico dell'Empirical Bayes — l'uso "doppio" dei dati, prima per ancorare i prior poi per l'aggiornamento — è noto in letteratura e va dichiarato: l'incertezza risultante è lievemente sottostimata rispetto a prior elicitati in modo indipendente, ed è il prezzo accettato per l'automazione completa su dataset arbitrari.

---

## 3. L'architettura ibrida MMM + MTA: due livelli decisionali

### 3.1 Il limite dell'analisi a livello canale

Il MMM, per costruzione, opera su dati aggregati settimanali e produce raccomandazioni a livello di **canale**: quanto a Google, quanto a Meta. Ma il decisore operativo lavora un livello sotto: dentro Meta convivono campagne con logiche radicalmente diverse — le dynamic ads ad ampia copertura, il retargeting, i moduli di lead generation, i job alert — e la domanda quotidiana non è solo «quanto a Meta» ma «come divido il budget di Meta tra queste campagne». Il MMM non può rispondere: con quattro canali e 156 settimane il modello satura già la capacità informativa dei dati aggregati; portarlo a livello campagna moltiplicherebbe i parametri oltre ogni possibilità di stima. Simmetricamente, i modelli di attribuzione multi-touch operano sul dato granulare dei percorsi utente, ma — come argomentato nel Capitolo 1 — soffrono di distorsioni strutturali quando usati per decidere la spesa *tra* canali: non vedono gli effetti di lungo periodo, non misurano l'incrementalità rispetto alla baseline, e la loro copertura si erode con il tracciamento.

La soluzione non è scegliere tra i due strumenti ma assegnarli a livelli decisionali diversi, dove ciascuno è forte e l'altro è cieco.

### 3.2 Livello strategico e livello tattico

L'architettura implementata è a due livelli. Il **livello strategico** (MMM) decide l'allocazione inter-canale: opera su dati aggregati, immune ai problemi di tracciamento, capace di misurare incrementalità, saturazione ed effetti ritardati; il suo output è il budget per canale. Il **livello tattico** (MTA) decide l'allocazione intra-canale: prende il budget di canale dal livello strategico e lo ripartisce tra le campagne in proporzione al loro contributo nei percorsi utente. Il punto architetturale cruciale è che l'MTA non decide mai *quanto* spendere su un canale — decisione per cui è strutturalmente inadatto — ma solo *come* distribuire una somma già fissata: le sue distorsioni inter-canale diventano irrilevanti, mentre la sua granularità, irraggiungibile per il MMM, viene messa a frutto dove serve.

### 3.3 Il metodo: catene di Markov e removal effect

Per il livello tattico è stato adottato il modello di attribuzione a catene di Markov (Anderl et al., 2016), che supera le euristiche posizionali (first touch, last touch, lineare) con una logica controfattuale. Il percorso dell'utente è modellato come catena di Markov assorbente: gli stati sono i touchpoint osservati più i tre stati speciali di inizio, conversione e abbandono; le probabilità di transizione sono stimate dalle frequenze empiriche sugli 800.000 percorsi. Il contributo di un touchpoint è il suo *removal effect*: di quanto cala la probabilità complessiva di conversione del grafo se quel touchpoint viene rimosso e i suoi ingressi dirottati verso l'abbandono. Un touchpoint che compare spesso ma è facilmente sostituibile ottiene poco credito; un passaggio obbligato ne ottiene molto, anche se raramente è l'ultimo clic. L'attribution risultante è la normalizzazione dei removal effect, moltiplicata per il totale da attribuire.

Una scelta di design distingue l'implementazione: la metrica da attribuire è un parametro. Con la metrica **volume** si attribuiscono le conversioni (candidature complete), e il riparto tattico massimizza il numero di candidati; con la metrica **utility** si attribuisce il fatturato atteso associato alle conversioni, e il riparto privilegia le campagne che portano candidature di maggior valore economico (nel dataset sintetico, l'utility varia per categoria professionale: una candidatura ICT vale circa il triplo di una nella GDO). La distinzione operazionalizza, a livello tattico, la questione sollevata nella discussione del MMM: le candidature non sono unità omogenee, e il sistema permette di scegliere esplicitamente quale definizione di valore ottimizzare — scelta che spetta al management, non all'algoritmo.

### 3.4 Il dataset sintetico dei percorsi

Come per il MMM, la validazione del livello tattico richiede un banco di prova controllato. Il generatore produce circa 800.000 percorsi utente con le caratteristiche strutturali del funnel di recruiting: tre stadi di conversione (visualizzazione dell'annuncio, registrazione, candidatura completa), lunghezza dei percorsi variabile con prevalenza di percorsi brevi, tredici touchpoint distribuiti su cinque sorgenti (incluso il traffico organico, che l'attribution deve saper trattare senza che gli venga assegnato budget), dimensioni demografiche (fascia d'età, area geografica, categoria professionale) e utility economica per conversione, variabile per categoria. Il processo generativo distingue per ciascuna campagna una propensione ad *attrarre* (aprire percorsi) e una a *chiudere* (convertirli): è questa asimmetria che rende il dataset un test significativo per l'attribution, perché crea esattamente la situazione — campagne di apertura sottovalutate dal last click — che il removal effect dovrebbe correggere.

### 3.5 L'agnosticismo come requisito architetturale

L'intera pipeline — MMM e MTA — è stata resa indipendente dai nomi: nessun canale, campagna o colonna è cablato nel codice. Il layer di ingestione classifica autonomamente le colonne di un CSV arbitrario (la dimensione temporale, le leve di spesa, il KPI, i fattori esterni, e per i percorsi: la colonna dei touchpoint, quella di conversione, quella di valore), deriva i vincoli di default dell'ottimizzatore dallo storico (minimi e massimi plausibili per canale) e ricava la gerarchia canale→campagna dalla convenzione di denominazione dei touchpoint. I nomi compaiono solo dove devono: nei dati. La motivazione non è solo ingegneristica (riusabilità su clienti e mercati diversi) ma metodologica: un sistema che richiede riconfigurazione manuale a ogni nuovo dataset reintroduce, sotto forma di configurazione, esattamente quegli interventi impliciti e non documentati che la pipeline riproducibile voleva eliminare.

---

## 4. Sintesi per la discussione

Le tre evoluzioni convergono sullo stesso punto teorico. Il paradigma asincrono rende l'incertezza computazionalmente sostenibile dentro l'interfaccia; le bande HDI la rendono visibile e decidibile; l'architettura a due livelli assegna a ciascun modello il perimetro in cui le sue assunzioni reggono. In tutti e tre i casi, il progresso non consiste nel rendere il sistema più autonomo, ma nel rendere più ricco e più onesto il dialogo tra il sistema e il decisore: più informazione dove prima c'era una stima secca, più trasparenza sui limiti dove prima c'era una linea sicura di sé, più granularità dove prima la raccomandazione si fermava un livello sopra le decisioni reali. È la traiettoria che il paradigma human-in-the-middle prescrive alla maturazione di un sistema di supporto decisionale: crescere in capacità senza crescere in opacità.
