# Dati, modelli e decisioni: Marketing Mix Modeling a supporto del budget digitale nel recruiting — il caso Randstad Italia

*Nota redazionale: il presente file segue la struttura IULM per le tesi di laurea magistrale (Frontespizio a cura del Centro Stampa → Indice → Introduzione → Capitoli → Conclusioni → Riferimenti bibliografici). In fase di export in Word applicare: margini 2,5 cm sup/inf e 3 cm dx/sx, testo giustificato, rientro prima riga 0,5 cm, interlinea 1,5, font serif unico 11-12 pt, sezioni che iniziano su pagina dispari, numerazione dall'Introduzione. Citazioni nel testo in stile APA autore-anno.*

## Indice

**Introduzione**

**PARTE I — IL PROBLEMA**

1. **Stato dell'arte** — 1.1 La crisi dell'attribuzione deterministica · 1.2 Il Marketing Mix Modeling: genesi e rinascita · 1.3 Il panorama dei framework open-source · 1.4 Frequentismo e bayesianesimo nel MMM · 1.5 Finalità dell'indagine · 1.6 Le lacune bibliografiche · 1.7 Sintesi
2. **Il contesto** — 2.1 Le specificità del marketing nel settore HR · 2.2 Il mercato del lavoro italiano e la somministrazione · 2.3 Il caso Randstad Italia e l'architettura media · 2.4 Le criticità operative: il limite del last-click

**PARTE II — LA SOLUZIONE**

3. **I pilastri teorici del Marketing Mix Modeling** — 3.1 L'equazione generale · 3.2 La trasformazione adstock · 3.3 La funzione di saturazione · 3.4 La decomposizione dei contributi · 3.5 L'ottimizzatore di budget · 3.6 Il paradigma human-in-the-middle · 3.7 Sintesi
4. **Design del sistema** — 4.1 L'architettura della pipeline · 4.2 Il dataset sintetico · 4.3 Le variabili di controllo · 4.4 L'ingestione automatica di serie esterne · 4.5 La specificazione e la stima · 4.6 Identificabilità e bound informativi · 4.7 Sintesi
5. **Implementazione e risultati** — 5.1 L'esecuzione della pipeline · 5.2 Metriche di accuratezza e recupero dei parametri · 5.3 L'output dell'ottimizzatore · 5.4 La pianificazione multi-periodo · 5.5 L'interfaccia operativa · 5.6 Sintesi

**PARTE III — LA VALUTAZIONE**

6. **Discussione** — 6.1 Dalla curva alla decisione · 6.2 L'analisi di scenario · 6.3 Il confronto con la letteratura · 6.4 I limiti metodologici · 6.5 Sintesi
7. **Conclusioni e sviluppi futuri** — 7.1 Il contributo originale · 7.2 L'evoluzione del paradigma human-in-the-middle · 7.3 La roadmap

**Riferimenti bibliografici**

---

## Introduzione

Ogni anno le imprese europee investono miliardi di euro in pubblicità digitale per presidiare mercati sempre più frammentati. Secondo i dati dell'Interactive Advertising Bureau (IAB Europe, 2024), la spesa in digital advertising nell'area UE ha superato i 96 miliardi di euro nel 2023, confermando un tasso di crescita annuo composto prossimo all'11% nell'ultimo quinquennio. In parallelo, il settore delle agenzie per il lavoro destina al canale digitale una quota crescente del proprio budget promozionale, nella convinzione — spesso non suffragata da evidenze — che la visibilità online si traduca linearmente in candidature qualificate e, in ultima analisi, in ricavi.

Eppure, nonostante l'entità degli investimenti, la domanda fondamentale rimane largamente inevasa: quale euro produce valore, e quale viene dissipato?

La questione non è nuova. Già John Wanamaker — con la celebre sentenza attribuita anche a Lord Leverhulme — lamentava che «metà del denaro speso in pubblicità è sprecato; il problema è che non so quale metà». A distanza di oltre un secolo, l'ipertrofia dei canali digitali ha moltiplicato, anziché ridurre, la complessità del problema: i decision-maker operano oggi in un ecosistema caratterizzato da molteplicità di touchpoint, latenza variabile degli effetti pubblicitari, interazioni non lineari tra canali e asimmetrie informative strutturali tra piattaforme e inserzionisti.

Il presente lavoro si colloca esattamente in questo snodo critico. L'obiettivo è duplice: da un lato, progettare e implementare una pipeline di Marketing Mix Modeling (MMM) calibrata sulle specificità del settore delle agenzie per il lavoro — un dominio finora trascurato dalla letteratura accademica — utilizzando il caso Randstad Italia come banco di prova; dall'altro, esplorare un paradigma decisionale che la tesi definisce *human-in-the-middle*, nel quale l'output algoritmico non sostituisce la discrezionalità del marketing manager, ma la informa, la struttura e, auspicabilmente, la migliora.

La scelta del MMM come strumento analitico non è casuale. Nell'era della progressiva erosione dei meccanismi di tracciamento deterministico — dal declino dei cookie di terze parti all'introduzione dell'App Tracking Transparency di Apple — il Marketing Mix Modeling sta conoscendo una seconda giovinezza, candidandosi a divenire il perno di un nuovo paradigma di misurazione privacy-first (Chan & Perry, 2017; Jin et al., 2017). A differenza dei modelli di attribuzione multi-touch, che dipendono dal tracciamento a livello di utente, il MMM opera su dati aggregati — spesa pubblicitaria, impression, variabili contestuali — e non necessita di identificatori individuali, risultando così strutturalmente compatibile con i vincoli regolatori contemporanei.

Il settore delle agenzie per il lavoro, e in particolare il caso Randstad Italia, offre un terreno di indagine particolarmente stimolante. La variabile obiettivo è multilivello — dall'impressione pubblicitaria alla candidatura, dal colloquio all'inserimento lavorativo — e il ciclo di conversione è lungo, variabile e soggetto a una ciclicità macroeconomica pronunciata. I canali di recruiting digitale — Indeed, LinkedIn, Google, Meta — operano con logiche di pricing, targeting e misurazione radicalmente diverse, rendendo la comparazione e l'ottimizzazione cross-canale una sfida tanto analitica quanto manageriale.

La tesi propone infine un modello decisionale — il paradigma *human-in-the-middle* — nel quale il decisore non è relegato al ruolo di validatore passivo dell'output algoritmico, né a quello di utilizzatore discrezionale libero di ignorarne le raccomandazioni. Egli opera, piuttosto, come un nodo attivo all'interno di un sistema di retroazione nel quale la sua conoscenza contestuale e il suo giudizio qualitativo informano, e sono a loro volta informati da, le evidenze quantitative del modello.

### Struttura del lavoro

L'indagine si articola in tre parti.

La **Parte I — Il Problema** (Capitoli 1–2) delimita il perimetro della ricerca. Il Capitolo 1 ricostruisce lo stato dell'arte del Marketing Mix Modeling, ne esamina l'evoluzione metodologica — dal declino dell'attribuzione deterministica all'ascesa dei framework open-source — e identifica le lacune bibliografiche che motivano l'indagine: l'assenza di applicazioni documentate nel settore HR e la limitata analisi dell'integrazione tra output algoritmico e discrezionalità del decisore. Il Capitolo 2 contestualizza il caso Randstad Italia, esaminando le dinamiche del mercato del lavoro italiano, i canali strategici del recruiting digitale e le criticità operative affrontate dai manager.

La **Parte II — La Soluzione** (Capitoli 3–5) sviluppa l'architettura analitica. Il Capitolo 3 espone i pilastri teorici del MMM — adstock, saturazione, decomposizione, ottimizzazione — e giustifica l'adozione della metodologia alla luce delle sfide delineate. Il Capitolo 4 illustra il design del sistema: la pipeline analitica, le specifiche del dataset sintetico e i criteri di validazione. Il Capitolo 5 documenta l'implementazione e le evidenze modellistiche emerse, restituendone l'output tecnico.

La **Parte III — La Valutazione** (Capitoli 6–7) interpreta i risultati e ne proietta le implicazioni oltre i confini della ricerca. Il Capitolo 6 traduce le curve di risposta in raccomandazioni di riallocazione, conduce l'analisi di scenario e confronta i risultati con le aspettative della letteratura, discutendo le implicazioni del passaggio da decisioni intuitive a decisioni data-driven. Il Capitolo 7 sintetizza il contributo originale, riprende il paradigma human-in-the-middle per esaminarne le prospettive evolutive e delinea la roadmap futura, focalizzata sulla validazione tramite dati reali, sul potenziamento dell'automazione e sullo sviluppo di una dashboard operativa.

**Nota sui dati.** I dati utilizzati nella presente indagine sono sintetici, calibrati sulle distribuzioni reali di Randstad Italia. La scelta è motivata dai vincoli di compliance aziendale vigenti al momento della stesura. L'integrazione di dati reali aggregati sarà valutata in fase successiva, compatibilmente con le autorizzazioni necessarie.

---

# PARTE I — IL PROBLEMA

## Capitolo 1 — Stato dell'arte

### 1.1 La crisi dell'attribuzione deterministica

#### 1.1.1 L'edificio fragile del tracciamento individuale

Per oltre un ventennio, il digital advertising ha fondato la propria promessa di misurabilità su un'architettura tecnica che appariva — e si è rivelata, col senno di poi — strutturalmente fragile: il cookie di terze parti. Introdotto nel 1994 da Lou Montulli come meccanismo di gestione dello stato nelle sessioni HTTP, il cookie ha progressivamente assunto un ruolo che trascendeva la sua funzione originaria, divenendo il fondamento dell'intero ecosistema di ad tracking, retargeting e attribuzione deterministica (Mayer & Mitchell, 2012).

Il modello funzionava, con approssimazione accettabile, in un contesto nel quale l'utente navigava prevalentemente da desktop, i walled garden delle piattaforme erano ancora permeabili e il consenso informato al tracciamento era un concetto giuridico più che un vincolo operativo. Questo contesto, tuttavia, ha cominciato a disgregarsi ben prima del colpo di grazia inferto dalla regolamentazione europea.

#### 1.1.2 Il trittico normativo-tecnologico

La transizione verso un ecosistema privacy-first è il risultato della convergenza di tre forze distinte ma sinergiche.

**La pressione regolamentare.** L'entrata in vigore del Regolamento Generale sulla Protezione dei Dati (GDPR, Regolamento UE 2016/679) il 25 maggio 2018 ha imposto il principio del consenso esplicito per il trattamento dei dati personali, compreso l'uso di cookie e identificatori a fini pubblicitari. In Italia, il Garante per la Protezione dei Dati Personali ha ulteriormente rafforzato il quadro con le Linee guida cookie e altri strumenti di tracciamento del giugno 2021. A livello globale, il California Consumer Privacy Act (CCPA, 2020) e il Digital Markets Act (DMA, Regolamento UE 2022/1925) hanno consolidato la tendenza verso una limitazione strutturale della raccolta dati a livello individuale. L'effetto aggregato è stato una riduzione significativa dei tassi di opt-in: secondo i dati di Usercentrics (2023), in Europa il tasso medio di consenso al tracciamento si attesta intorno al 45%, con punte inferiori al 30% in mercati come la Germania.

**Le restrizioni delle piattaforme.** Apple ha introdotto l'Intelligent Tracking Prevention (ITP) su Safari nel giugno 2017, limitando progressivamente la persistenza dei cookie di terze parti fino a eliminarli del tutto nel marzo 2020. Firefox ha attivato l'Enhanced Tracking Protection (ETP) come impostazione predefinita nel settembre 2019 (Firefox 69), consolidando il blocco dei cookie di tracciamento sul terzo browser per quota di mercato globale. La mossa più dirompente è stata tuttavia l'App Tracking Transparency (ATT), lanciata da Apple con iOS 14.5 nell'aprile 2021, che ha imposto un opt-in esplicito per il tracciamento cross-app sull'intero ecosistema mobile Apple. I tassi di opt-in si sono attestati intorno al 25% a livello globale (Flurry Analytics, 2022), con conseguenze rilevanti sulla capacità delle piattaforme pubblicitarie — Meta in primis, che ha stimato un impatto di circa 10 miliardi di dollari sui ricavi del 2022 — di attribuire conversioni con precisione deterministica.

Il percorso di Google è stato più tortuoso. Nel gennaio 2020, l'azienda ha annunciato l'intenzione di deprecare i cookie di terze parti su Chrome entro due anni. Nel gennaio 2024, ha avviato un test limitato all'1% degli utenti nell'ambito del framework Privacy Sandbox. Nel luglio 2024, tuttavia, Google ha annunciato un cambio di strategia, rinunciando alla deprecazione completa e mantenendo le impostazioni privacy esistenti — una decisione confermata nell'aprile 2025 con l'abbandono del prompt di scelta per l'utente. Nonostante questo ripensamento, il trend strutturale è irreversibile: Safari e Firefox, che rappresentano complessivamente oltre il 30% della quota di mercato browser globale, bloccano già i cookie di terze parti per impostazione predefinita, e il quadro normativo GDPR/CCPA rimane pienamente in vigore.

**L'obsolescenza tecnologica.** Indipendentemente dalle scelte dei singoli attori, il modello stesso del tracciamento cross-site attraverso identificatori persistenti si è rivelato inadeguato all'evoluzione del panorama digitale. La frammentazione dei dispositivi (cross-device), la migrazione delle interazioni verso ambienti chiusi (in-app browsing, walled garden) e la crescente sofisticazione degli strumenti di ad blocking — utilizzati da circa il 32% degli utenti desktop in Europa secondo PageFair (2023) — hanno eroso progressivamente la copertura e l'affidabilità del tracciamento deterministico anche laddove il consenso era stato ottenuto.

#### 1.1.3 Le conseguenze per la misurazione

L'effetto congiunto di queste tre forze ha prodotto un esito paradossale: proprio mentre gli investimenti in digital advertising raggiungevano il massimo storico, la capacità di misurarne l'efficacia si è deteriorata in misura significativa. I modelli di attribuzione multi-touch (MTA) — che ricostruiscono il percorso di conversione assegnando un credito frazionario a ciascun touchpoint — soffrono di una dipendenza strutturale dal tracciamento a livello individuale e dalla capacità di collegare eventi cross-canale e cross-dispositivo (Li & Kannan, 2014; Berman, 2018).

Come osservano Sapp e Galbrecht (2023), i modelli MTA presentano limitazioni che ne compromettono l'affidabilità anche in assenza dei vincoli privacy descritti: la distorsione sistematica verso i canali posizionati a valle del funnel (il cosiddetto last-touch bias), l'incapacità di catturare effetti cross-canale e l'impossibilità di valutare l'impatto incrementale della spesa — vale a dire la distinzione tra conversioni che si sarebbero verificate comunque (baseline) e quelle effettivamente generate dall'investimento pubblicitario.

Il risultato è un vuoto metodologico che il mercato sta colmando con un ritorno — più maturo, più sofisticato, più computazionalmente intensivo — al Marketing Mix Modeling.

### 1.2 Il Marketing Mix Modeling: genesi e rinascita

#### 1.2.1 Radici storiche

Il Marketing Mix Modeling affonda le proprie radici nella tradizione econometrica degli anni Sessanta e Settanta. I lavori seminali di Bass (1969) sulla diffusione dei prodotti e di Little (1975) sui modelli di risposta pubblicitaria hanno posto le basi concettuali per la modellazione della relazione tra investimenti di marketing e risultati di business. L'intuizione fondamentale era semplice ma potente: se la spesa pubblicitaria varia nel tempo e nello spazio, è possibile — sotto determinate assunzioni — isolare statisticamente il suo effetto incrementale sulla variabile obiettivo (vendite, quote di mercato, conversioni), controllando per i fattori confondenti.

Il concetto di adstock — il termine che descrive l'effetto persistente della pubblicità oltre il periodo di esposizione — è stato formalizzato da Broadbent (1979), divenendo uno dei pilastri concettuali della disciplina. Negli anni Ottanta e Novanta, il MMM è diventato una pratica consolidata nelle grandi aziende di beni di largo consumo (CPG/FMCG), supportato dai dati scanner dei punti vendita e dall'expertise di società specializzate come Nielsen, IRI e Marketing Management Analytics (Tellis, 2006). La metodologia dominante era la regressione lineare multipla, arricchita da trasformazioni non lineari per catturare gli effetti di carry-over temporale e di saturazione.

#### 1.2.2 L'eclissi e la resurrezione

L'avvento del digital advertising alla fine degli anni Novanta e l'affermazione dei modelli di attribuzione multi-touch negli anni Duemila hanno relegato il MMM a un ruolo ancillare. La promessa dell'attribuzione deterministica — poter tracciare ogni clic, ogni impression, ogni conversione fino al singolo utente — appariva superiore all'approccio aggregato e retrospettivo del MMM, percepito come un residuo dell'era analogica.

La rivalutazione del MMM, avviata intorno al 2017–2018 con i contributi fondamentali di Jin et al. (2017) e Chan e Perry (2017) presso Google, e accelerata dalla crisi dell'attribuzione descritta nella sezione precedente, non è tuttavia un mero ritorno al passato. La nuova generazione di modelli si distingue dalla tradizione per almeno quattro dimensioni.

**Sofisticazione metodologica.** L'adozione di framework bayesiani consente di incorporare conoscenza pregressa (prior), quantificare l'incertezza nelle stime e produrre distribuzioni a posteriori anziché stime puntuali — un vantaggio decisivo in contesti decisionali dove la quantificazione del rischio è almeno altrettanto importante della stima del valore atteso (Chan & Perry, 2017).

**Democratizzazione tecnologica.** Il rilascio di framework open-source da parte dei principali attori della big tech — Meta (Robyn, 2021), Google (LightweightMMM, 2022; Meridian, 2025) — e della comunità scientifica (PyMC-Marketing, 2023) ha abbattuto le barriere all'adozione, rendendo il MMM accessibile anche a organizzazioni prive delle risorse per commissionare modelli proprietari a società di consulenza.

**Granularità e frequenza.** I nuovi framework operano nativamente su dati settimanali o giornalieri, anziché sulle aggregazioni trimestrali tipiche del MMM tradizionale, consentendo una maggiore reattività decisionale.

**Integrazione con l'ottimizzazione.** I modelli contemporanei non si limitano a stimare i coefficienti di risposta, ma incorporano moduli di ottimizzazione del budget che traducono le stime in raccomandazioni azionabili, soggette a vincoli operativi definiti dall'utente.

### 1.3 Il panorama dei framework open-source

La democratizzazione del MMM attraverso librerie open-source rappresenta uno dei fenomeni più significativi nell'evoluzione recente della disciplina. Questa sezione esamina i principali framework disponibili, analizzandone le caratteristiche metodologiche, i punti di forza e i limiti.

#### 1.3.1 Robyn (Meta)

Robyn è un framework open-source sviluppato dal team Marketing Science di Meta (ex Facebook) e rilasciato pubblicamente nel novembre 2021 su GitHub sotto licenza MIT (Runge et al., 2024). Scritto in R, Robyn adotta un approccio frequentista basato sulla regressione ridge, con l'aggiunta di un ottimizzatore multiobiettivo (Nevergrad, sviluppato da Facebook AI Research) per la selezione dei modelli e l'allocazione del budget.

Le caratteristiche distintive di Robyn includono la regressione ridge con regolarizzazione L2, che mitiga il rischio di overfitting in presenza di multicollinearità tra le variabili media — un problema endemico nel MMM, dove i canali tendono a covariare temporalmente; l'ottimizzazione multiobiettivo tramite Nevergrad, che esplora lo spazio dei parametri minimizzando simultaneamente l'errore di previsione (NRMSE) e l'errore di decomposizione (DECOMP.RSSD), producendo una frontiera di Pareto di modelli candidati; le trasformazioni di adstock geometriche e di Weibull, che offrono flessibilità nella modellazione del decadimento temporale; la calibrazione opzionale con risultati di esperimenti incrementali (ad esempio, lift test o conversion lift study), che consente di ancorare le stime a evidenze causali; il budget optimizer integrato e la scomposizione delle serie temporali attraverso la libreria Prophet, per il trattamento di trend, stagionalità e festività.

Robyn ha guadagnato una trazione significativa nella comunità dei professionisti del marketing, posizionandosi come lo strumento open-source più adottato per il MMM, particolarmente tra le aziende digital-native. L'approccio frequentista presenta tuttavia limitazioni intrinseche: l'incertezza è quantificabile solo tramite bootstrap, le stime sono puntuali anziché distribuzionali, la selezione tra i modelli della frontiera di Pareto richiede un intervento manuale e la conoscenza di dominio non può essere incorporata formalmente nel modello.

#### 1.3.2 Meridian (Google)

Meridian è il framework open-source di nuova generazione sviluppato da Google, rilasciato il 29 gennaio 2025 dopo una fase di preview avviata nel marzo 2024 e un periodo di test con centinaia di brand (Google, 2025). Meridian succede a LightweightMMM (LMMM), anch'esso sviluppato da Google e rilasciato nel febbraio 2022, oggi deprecato. Adotta un approccio bayesiano implementato in Python, con TensorFlow Probability come backend predefinito e un backend opzionale basato su JAX per prestazioni elevate.

Le caratteristiche metodologiche di Meridian comprendono un modello gerarchico bayesiano, che consente la modellazione simultanea di dati a livello nazionale e subnazionale (geo-level), sfruttando la struttura gerarchica per migliorare la stabilità delle stime attraverso lo shrinkage bayesiano (partial pooling); prior informativi calibrati sulla conoscenza di dominio e, opzionalmente, su risultati sperimentali (ROI priors); la quantificazione nativa dell'incertezza, con intervalli credibili bayesiani per tutti i parametri stimati; l'inferenza tramite MCMC (Markov Chain Monte Carlo), specificamente il campionatore NUTS (No-U-Turn Sampler; Hoffman & Gelman, 2014); il reach & frequency modeling, che consente la modellazione dell'impatto pubblicitario in termini di copertura e frequenza di esposizione anziché della sola spesa — un'innovazione rilevante per catturare i rendimenti decrescenti a livello di audience; e l'integrazione con dati Google (Query Volume, YouTube).

Meridian rappresenta lo stato dell'arte nella modellazione bayesiana del marketing mix ed è il naturale proseguimento del lavoro seminale di Jin et al. (2017), che ha formalizzato l'approccio bayesiano al MMM in ambito Google.

#### 1.3.3 PyMC-Marketing

PyMC-Marketing è una libreria open-source sviluppata dalla comunità PyMC e da PyMC Labs, rilasciata nell'aprile 2023 (PyMC Labs, 2023). A differenza di Robyn e Meridian, non è il prodotto di una singola big tech, ma di un ecosistema collaborativo di ricercatori e professionisti della modellazione bayesiana.

Le caratteristiche principali comprendono un framework pienamente bayesiano, costruito sopra la libreria probabilistica PyMC (Salvatier et al., 2016), che offre un'interfaccia flessibile per la definizione di modelli personalizzati; una modularità che consente all'utente di specificare la struttura del modello — scelta della funzione di adstock, della curva di saturazione, delle distribuzioni a priori — con un grado di libertà superiore rispetto ai framework più vincolati come Robyn e Meridian; l'integrazione con l'ecosistema PyMC, che include strumenti avanzati di diagnostica MCMC (ArviZ; Kumar et al., 2019), selezione dei modelli (LOO-CV, WAIC) e visualizzazione; il supporto per modelli di Customer Lifetime Value (CLV), sia contrattuali sia non contrattuali; e un approccio code-first trasparente, con controllo granulare su ogni componente del modello, incluse le verifiche predittive a priori e a posteriori.

La flessibilità di PyMC-Marketing è al contempo il suo principale punto di forza e il suo limite: la maggiore libertà di modellazione richiede competenze tecniche più elevate e un investimento di tempo superiore nella specificazione e nella validazione del modello.

#### 1.3.4 Quadro sinottico

| Caratteristica | Robyn (Meta) | Meridian (Google) | PyMC-Marketing |
|---|---|---|---|
| Anno di rilascio | 2021 | 2025 (preview 2024) | 2023 |
| Linguaggio | R | Python (TF Probability / JAX) | Python (PyMC / PyTensor) |
| Paradigma | Frequentista | Bayesiano | Bayesiano |
| Modello base | Ridge regression | Gerarchico bayesiano | Bayesiano personalizzabile |
| Ottimizzazione parametri | Nevergrad (multiobiettivo) | MCMC (NUTS) | MCMC (NUTS) |
| Quantificazione incertezza | Bootstrap | Nativa (intervalli credibili) | Nativa (intervalli credibili) |
| Budget optimizer | Sì | Sì | Sì |
| Calibrazione sperimentale | Sì (lift test) | Sì (ROI priors) | Sì (prior informativi) |
| Geo-level modeling | Limitato | Nativo (gerarchico) | Possibile (custom) |
| Caratteristica distintiva | Frontiera di Pareto, automazione | Reach & frequency, dati Google | Modulo CLV, flessibilità |
| Curva di apprendimento | Moderata | Moderata-alta | Alta |

*Tabella 1.1 — Confronto sinottico dei principali framework open-source per il Marketing Mix Modeling.*

### 1.4 Frequentismo e bayesianesimo nel MMM: un confronto metodologico

La scelta tra approccio frequentista e bayesiano non è meramente tecnica: incide sulla natura stessa delle risposte che il modello è in grado di fornire e, di conseguenza, sul tipo di supporto decisionale offerto al manager.

#### 1.4.1 L'approccio frequentista

Nell'approccio frequentista, i parametri del modello sono trattati come quantità fisse (ma ignote) e le stime sono ottenute massimizzando la verosimiglianza dei dati osservati (o, nel caso della regressione ridge utilizzata da Robyn, minimizzando una funzione di costo penalizzata). L'incertezza è espressa attraverso intervalli di confidenza, che ammettono un'interpretazione rigorosamente procedurale: un intervallo di confidenza al 95% significa che, se l'esperimento fosse ripetuto un numero infinito di volte, il 95% degli intervalli costruiti con la stessa procedura conterrebbe il valore vero del parametro. Questa interpretazione, corretta ma controintuitiva, genera frequentemente fraintendimenti nella comunicazione ai decisori non tecnici (Morey et al., 2016).

I principali vantaggi dell'approccio frequentista nel contesto del MMM sono la velocità computazionale, che consente di esplorare migliaia di configurazioni in tempi contenuti; la semplicità interpretativa delle stime puntuali; la minore dipendenza da assunzioni soggettive; e la minore barriera all'ingresso in termini di competenze statistiche. I limiti includono l'impossibilità di incorporare formalmente la conoscenza pregressa, la sensibilità alla specificazione del modello e l'assenza di una quantificazione probabilistica nativa dell'incertezza parametrica.

#### 1.4.2 L'approccio bayesiano

Nell'approccio bayesiano, i parametri sono trattati come variabili aleatorie dotate di una distribuzione di probabilità. L'inferenza procede aggiornando una distribuzione a priori (prior) — che codifica la conoscenza pregressa — alla luce dei dati osservati, per ottenere una distribuzione a posteriori (posterior) attraverso il teorema di Bayes:

> P(θ | D) = P(D | θ) · P(θ) / P(D)

dove θ indica il vettore dei parametri del modello, D l'insieme dei dati osservati, P(θ) la distribuzione a priori, P(D | θ) la funzione di verosimiglianza, P(D) la probabilità marginale dei dati (costante di normalizzazione) e P(θ | D) la distribuzione a posteriori risultante.

Nel contesto del MMM, l'approccio bayesiano offre vantaggi significativi.

**Incorporazione della conoscenza di dominio.** Le distribuzioni a priori consentono di vincolare i parametri a regioni dello spazio parametrico coerenti con la conoscenza di dominio. È ragionevole, ad esempio, imporre che i coefficienti media siano non negativi — la spesa pubblicitaria non dovrebbe, in condizioni normali, produrre un effetto negativo sulle conversioni — o che il tasso di decadimento dell'adstock sia compreso in un intervallo plausibile per il canale considerato. Come osservano Chan e Perry (2017), l'uso di prior informativi è particolarmente prezioso nei dataset tipici del MMM, che contano di norma 100–200 osservazioni settimanali — un volume insufficiente per stimare con precisione un modello con decine di parametri in assenza di regolarizzazione.

**Quantificazione probabilistica dell'incertezza.** Gli intervalli credibili bayesiani ammettono un'interpretazione diretta e intuitiva: un intervallo credibile al 95% significa che, dato il modello e i dati osservati, il parametro ha una probabilità del 95% di trovarsi nell'intervallo specificato. Questa interpretazione è immediatamente comprensibile per i decisori e consente una valutazione esplicita del rischio associato alle raccomandazioni di budget.

**Regolarizzazione implicita.** Le distribuzioni a priori agiscono come un meccanismo di regolarizzazione naturale, mitigando l'overfitting senza richiedere la selezione di iperparametri di penalizzazione.

**Propagazione dell'incertezza.** L'incertezza parametrica si propaga automaticamente a tutte le quantità derivate — contributo dei media, curve di risposta, allocazione ottimale del budget — consentendo di esprimere le raccomandazioni come intervalli anziché come valori puntuali.

**Robustezza con dati limitati.** In settori con serie storiche brevi o con elevata multicollinearità tra predittori — condizioni tipiche del MMM — i prior stabilizzano le stime e ne migliorano l'affidabilità attraverso il pooling gerarchico e la regolarizzazione implicita.

I limiti dell'approccio bayesiano includono il costo computazionale dell'inferenza MCMC — mitigato dai progressi hardware e algoritmici degli ultimi anni —, la necessità di competenze specialistiche nella specificazione delle distribuzioni a priori e nella diagnostica delle catene, e la potenziale soggettività nell'elicitazione dei prior, sebbene quest'ultima possa essere disciplinata attraverso analisi di sensibilità e verifiche predittive a priori.

#### 1.4.3 Implicazioni per la pratica

La scelta tra i due approcci non è dicotomica. Robyn stesso incorpora elementi di regolarizzazione — la penalizzazione L2 della regressione ridge — che possono essere interpretati come un prior gaussiano implicito sui coefficienti. Simmetricamente, un modello bayesiano con prior non informativi (flat priors) converge, al limite, verso le stime di massima verosimiglianza.

Nella pratica, la tendenza del mercato e della ricerca è orientata con decisione verso l'approccio bayesiano. Il rilascio di Meridian da parte di Google — successore di LightweightMMM, anch'esso bayesiano — e lo sviluppo di PyMC-Marketing testimoniano un consenso crescente sull'adeguatezza dell'inferenza bayesiana per il MMM. Come argomentano Jin et al. (2017), i vantaggi dell'approccio bayesiano sono particolarmente marcati quando i dataset sono di dimensione limitata, la multicollinearità tra predittori è elevata e la comunicazione dell'incertezza ai decisori è un requisito operativo — condizioni che descrivono con precisione il contesto tipico del MMM nel marketing digitale.

Numerosi professionisti raccomandano un percorso progressivo: partire con Robyn per ottenere indicazioni rapide, per poi migrare verso approcci bayesiani per le decisioni strategiche di medio-lungo termine.

### 1.5 Finalità dell'indagine

Il presente lavoro si propone di perseguire tre obiettivi interconnessi.

**Obiettivo 1 — Dimostrare l'applicabilità del MMM al settore delle agenzie per il lavoro.** La letteratura sul Marketing Mix Modeling è largamente concentrata su settori a elevata intensità pubblicitaria — beni di largo consumo, retail, e-commerce, servizi finanziari — dove la variabile obiettivo (vendite, ricavi) è univoca e la relazione con gli investimenti media è consolidata. Il settore delle agenzie per il lavoro presenta peculiarità che rendono l'applicazione del MMM non banale: la variabile obiettivo è multilivello (impression → clic → candidatura → colloquio → inserimento), il ciclo di conversione è lungo e variabile, la domanda è soggetta a una ciclicità macroeconomica pronunciata e i canali di recruiting (Indeed, LinkedIn, Google, Meta) presentano dinamiche di risposta eterogenee. La tesi intende verificare se, e in quale misura, il framework del MMM sia in grado di catturare queste specificità.

**Obiettivo 2 — Progettare e implementare una pipeline analitica end-to-end.** L'indagine non si limita all'applicazione di un framework esistente, ma sviluppa un'architettura completa che include la preparazione dei dati, la modellazione, la validazione, la decomposizione dei contributi media e l'ottimizzazione del budget. La pipeline è progettata per essere riproducibile e trasferibile, con l'ambizione di costituire un riferimento metodologico per applicazioni future nel medesimo settore.

**Obiettivo 3 — Esplorare il paradigma human-in-the-middle.** La tesi propone e analizza un modello decisionale nel quale l'output algoritmico del MMM è integrato con — ma non sostituisce — la discrezionalità del marketing manager. L'ipotesi è che la massimizzazione del valore dell'investimento pubblicitario richieda un'interazione strutturata tra la raccomandazione quantitativa del modello e la conoscenza contestuale, tacita e strategica del decisore umano: vincoli contrattuali con le piattaforme, obiettivi qualitativi non catturati dal modello, considerazioni di posizionamento competitivo, sensibilità politiche interne. Il paradigma human-in-the-middle postula che il valore del sistema risieda non nell'automazione della decisione, ma nella qualità dell'interfaccia tra dato e giudizio.

### 1.6 Le lacune bibliografiche

La revisione della letteratura ha evidenziato due lacune significative che il presente lavoro intende contribuire a colmare.

#### 1.6.1 L'assenza del settore HR

Una ricerca sistematica condotta sulle principali basi dati accademiche — Scopus, Web of Science, Google Scholar — e sulle librerie digitali IEEE Xplore e ACM Digital Library, utilizzando combinazioni dei termini "marketing mix model" OR "media mix model" AND "recruitment" OR "staffing" OR "human resources" OR "job advertising" OR "talent acquisition", non ha restituito risultati pertinenti. Le applicazioni documentate del MMM si concentrano su settori nei quali la relazione tra investimento media e variabile obiettivo (vendite, sottoscrizioni, download di app) è relativamente diretta e il ciclo di conversione è misurabile in giorni o settimane.

Esiste una letteratura adiacente sul cosiddetto Employment Marketing Mix (EMM), che adatta il framework concettuale delle 4P/7P del marketing all'ambito della talent acquisition — dove il prodotto diventa l'esperienza lavorativa, il prezzo la remunerazione, la distribuzione i canali di reclutamento e la promozione l'employer branding. Questa letteratura, tuttavia, opera su un piano puramente concettuale e non propone modellazioni econometriche formali con meccanismi di adstock, saturazione e ottimizzazione del budget.

Il settore delle agenzie per il lavoro presenta caratteristiche che lo rendono un candidato particolarmente interessante — e sfidante — per il MMM.

Il funnel di conversione è lungo e a stadi multipli. La distanza tra l'impressione pubblicitaria e l'output economicamente rilevante (l'inserimento lavorativo del candidato presso l'azienda cliente) è mediata da una catena di conversioni intermedie, ciascuna con tassi di transizione variabili e latenza specifica.

La domanda è soggetta a una marcata ciclicità macroeconomica. La domanda di lavoro interinale è fortemente correlata al ciclo economico, con componenti stagionali (picchi estivi nel manifatturiero e nella logistica) e strutturali (trend occupazionali di lungo periodo) che il modello deve separare dall'effetto della spesa media.

I canali sono strutturalmente eterogenei. I canali di recruiting digitale (job board come Indeed, piattaforme professionali come LinkedIn, motori di ricerca come Google, social network come Meta) operano con logiche di pricing, targeting e misurazione radicalmente diverse, rendendo la comparazione e l'ottimizzazione cross-canale particolarmente complessa.

L'audience è duale. A differenza del marketing di prodotto, dove l'audience è unidimensionale (il consumatore), il marketing nel recruiting si rivolge simultaneamente a candidati e aziende clienti, con obiettivi, canali e metriche distinti.

L'assenza di letteratura su questo dominio non implica che il MMM sia inapplicabile, ma segnala che la sua applicabilità non è stata verificata empiricamente. La presente tesi contribuisce a colmare questa lacuna.

#### 1.6.2 L'interfaccia uomo-modello

Una seconda lacuna riguarda l'analisi dell'interazione tra l'output algoritmico del MMM e il processo decisionale del marketing manager. La letteratura tecnica sul MMM si concentra prevalentemente sulla qualità del modello — accuratezza predittiva, stabilità dei coefficienti, capacità di decomposizione — trattando la traduzione delle stime in decisioni operative come un passaggio implicito e non problematico. Simmetricamente, la letteratura sul decision support e sulla human-AI interaction (Lai et al., 2021; Bansal et al., 2021) ha esplorato le dinamiche di fiducia, calibrazione e complementarità tra decisore umano e sistema algoritmico in numerosi contesti (medico, giuridico, finanziario), ma non ha indagato specificamente il caso del MMM.

Va osservato che il paradigma bayesiano è, per sua natura, intrinsecamente human-in-the-loop: l'elicitazione dei prior costituisce una forma strutturata di incorporazione della conoscenza esperta nel modello. Il ciclo prevede l'estrazione della conoscenza del decisore (ad esempio: «Qual è il range di ROI atteso per LinkedIn?»), la sua traduzione in distribuzioni di probabilità, la verifica predittiva a priori, l'aggiornamento bayesiano alla luce dei dati, l'analisi di sensibilità e il raffinamento iterativo. Questa integrazione è tuttavia limitata alla fase di specificazione del modello e non si estende alla traduzione dei risultati in decisioni operative.

Il presente lavoro contribuisce a colmare questa lacuna proponendo il concetto di human-in-the-middle — un modello nel quale il decisore opera come nodo attivo all'interno di un sistema di retroazione in cui la sua conoscenza contestuale e il suo giudizio qualitativo informano, e sono a loro volta informati da, le evidenze quantitative del modello. A differenza del paradigma human-in-the-loop tradizionale — nel quale l'intervento umano è circoscritto a checkpoint di validazione sincroni — e del paradigma human-on-the-loop — nel quale il decisore supervisiona il sistema in modalità asincrona, intervenendo solo in caso di anomalie — il human-in-the-middle postula una co-determinazione continua nella quale la raccomandazione algoritmica e il giudizio manageriale si informano reciprocamente.

### 1.7 Sintesi del capitolo

Il presente capitolo ha delineato il contesto nel quale si inscrive l'indagine. La crisi dell'attribuzione deterministica — prodotta dalla convergenza di pressione regolamentare, restrizioni delle piattaforme e obsolescenza tecnologica — ha creato un vuoto metodologico che il Marketing Mix Modeling, nella sua incarnazione contemporanea, si candida a colmare. L'emergere di framework open-source (Robyn, Meridian, PyMC-Marketing) ha democratizzato l'accesso alla metodologia, mentre il dibattito tra approccio frequentista e bayesiano si sta risolvendo a favore di quest'ultimo, grazie alla sua capacità di incorporare la conoscenza di dominio, quantificare l'incertezza e comunicare i risultati in termini probabilistici.

L'indagine si colloca all'intersezione di due lacune bibliografiche: l'assenza di applicazioni documentate del MMM nel settore delle agenzie per il lavoro e la limitata analisi dell'integrazione tra output algoritmico e discrezionalità del decisore. Il capitolo successivo contestualizzerà il caso Randstad Italia, esaminando le dinamiche del mercato del lavoro italiano e le specificità operative dei canali di recruiting digitale.

## Capitolo 2 — Il contesto

### 2.1 Le specificità del marketing nel settore HR

L'applicazione del Marketing Mix Modeling al settore delle agenzie per il lavoro richiede una comprensione preliminare delle dinamiche strutturali che governano il mercato del recruiting. A differenza del commercio al dettaglio o dei servizi digitali — settori in cui l'obiettivo primario del marketing è stimolare l'acquisto di un bene o servizio — il marketing delle risorse umane opera in un ecosistema intrinsecamente duale e bidirezionale.

La prima specificità è la dualità dell'audience. Un'agenzia per il lavoro come Randstad opera simultaneamente su due mercati contigui ma distinti: il mercato B2B (Business-to-Business), finalizzato all'acquisizione di aziende clienti con esigenze di flessibilità del personale, e il mercato B2C (Business-to-Consumer), orientato all'attrazione, selezione e fidelizzazione dei candidati. Le campagne di digital advertising dirette ai candidati (talent acquisition) costituiscono il fulcro dell'investimento media e l'oggetto primario di questa indagine, in quanto rappresentano la voce di spesa più variabile e complessa da ottimizzare.

La seconda specificità riguarda la natura del prodotto scambiato. Non si tratta di un bene inerte, ma dell'impiego stesso — un'entità che coinvolge profondamente la sfera personale e professionale dell'individuo. Questo determina un funnel di conversione lungo e a stadi multipli. Mentre nell'e-commerce il percorso tra l'impressione pubblicitaria e l'acquisto può consumarsi in una singola sessione di navigazione, nel recruiting il funnel si articola in fasi sequenziali: visualizzazione dell'annuncio, clic, atterraggio sulla career page, compilazione del form di candidatura, pre-screening, colloquio conoscitivo, presentazione all'azienda cliente e, infine, assunzione. Ciascun passaggio presenta tassi di abbandono e latenze temporali che complicano enormemente il tracciamento deterministico.

La terza specificità è la ciclicità macroeconomica. L'investimento pubblicitario per la ricerca di candidati è strettamente correlato ai picchi di produzione delle aziende clienti — si pensi alla logistica durante il periodo natalizio o all'agricoltura e al turismo nei mesi estivi. Il modello econometrico deve pertanto essere in grado di depurare l'effetto incrementale della pubblicità dalle variazioni di baseline generate dal ciclo economico.

### 2.2 Il mercato del lavoro italiano e la somministrazione

Per comprendere la domanda che il marketing del recruiting è chiamato a intercettare, è necessario inquadrare brevemente il mercato nel quale le agenzie per il lavoro operano. In Italia, la somministrazione di lavoro è disciplinata dal D.Lgs. 276/2003 (la cosiddetta riforma Biagi), che ha istituito l'albo informatico delle agenzie per il lavoro presso il Ministero del Lavoro e ha definito i requisiti giuridici e finanziari per l'esercizio dell'attività. Il quadro è stato successivamente rimodellato dal D.Lgs. 81/2015 nell'ambito del Jobs Act e, in senso restrittivo, dal cosiddetto Decreto Dignità (D.L. 87/2018, convertito in L. 96/2018), che ha reintrodotto le causali per i contratti a termine di durata superiore ai dodici mesi e ne ha ridotto la durata massima — un intervento normativo con effetti diretti sui volumi e sulla composizione della domanda di lavoro somministrato.

Tre caratteristiche strutturali di questo mercato sono rilevanti per la modellazione econometrica sviluppata nei capitoli successivi.

La prima è la pro-ciclicità amplificata. Il lavoro somministrato funge da ammortizzatore di flessibilità per le imprese: nelle fasi espansive la domanda di somministrazione cresce più che proporzionalmente rispetto all'occupazione complessiva, poiché le aziende preferiscono forme flessibili in attesa di consolidare le aspettative; nelle fasi recessive si contrae con altrettanta rapidità, essendo la prima voce di costo del lavoro ad essere ridotta. Ne consegue che la serie storica delle candidature e degli avviamenti è strutturalmente più volatile del ciclo economico sottostante — una caratteristica che rafforza la necessità, argomentata nel Capitolo 3, di variabili di controllo macroeconomiche nel modello.

La seconda è la stagionalità settoriale composita. La domanda di lavoro flessibile aggrega cicli stagionali eterogenei: il turismo e l'agroalimentare nei mesi estivi, la logistica e la grande distribuzione nel quarto trimestre (con il picco del periodo natalizio e degli eventi promozionali), il manifatturiero in corrispondenza dei cicli produttivi. La sovrapposizione di questi cicli produce un profilo stagionale complesso, che il modello cattura attraverso la combinazione di armoniche di Fourier multiple e della serie esplicita delle richieste dei clienti.

La terza è l'asimmetria informativa tra i due lati del mercato. Nei periodi di espansione, la criticità per l'agenzia è la scarsità di candidati (talent shortage): la spesa pubblicitaria si concentra sull'attrazione di candidature, e il suo rendimento marginale è elevato. Nei periodi di contrazione, la criticità si sposta sul lato della domanda aziendale, e la stessa spesa pubblicitaria rivolta ai candidati produce candidature che l'agenzia fatica a collocare. Il valore economico di una candidatura incrementale non è dunque costante nel tempo — una considerazione che il modello, avendo come variabile obiettivo le candidature, non incorpora direttamente, ma che il decisore deve tenere presente in fase di interpretazione (un ulteriore argomento a favore del paradigma human-in-the-middle).

### 2.3 Il caso Randstad Italia e l'architettura media

Randstad Italia fa parte del gruppo multinazionale olandese Randstad N.V., leader mondiale nei servizi per le risorse umane. Sul territorio italiano, l'azienda si posiziona ai vertici del mercato per fatturato e capillarità della rete di filiali, offrendo servizi di somministrazione, ricerca e selezione, outplacement e formazione.

L'architettura del digital marketing di un player enterprise come Randstad si inserisce in un media mix diversificato, progettato per intercettare target differenti attraverso piattaforme eterogenee. Per ragioni di riservatezza aziendale, non verranno qui divulgati i set-up tecnologici proprietari né i pesi specifici del budget allocato. È tuttavia essenziale mappare il portafoglio delle opzioni — standard e avanzate — a disposizione di un'agenzia per il lavoro contemporanea. L'analisi preliminare di questo ecosistema — dalle librerie inserzioni pubbliche (Meta Ad Library, Google Ads Transparency Center) fino allo studio delle architetture tipiche del settore — è il prerequisito metodologico per istruire qualsiasi modello MMM.

L'arsenale pubblicitario a disposizione di un inserzionista HR si articola sulle seguenti tipologie di campagne.

**A) Google Ads (Ecosistema Search e Network).** Il motore di ricerca presidia la domanda esplicita. Le opzioni includono campagne Search e Dynamic Search Ads (DSA), per intercettare keyword transazionali (es. "offerte lavoro logistica"). Nei set-up avanzati, il keyword targeting manuale è sostituito da automazioni basate su piattaforme di Feed Management (come Channable), capaci di generare annunci dinamici agganciati al database delle posizioni aperte. A queste si affiancano le campagne Performance Max (PMax) e Display, funzionali al retargeting e all'espansione della reach visiva.

**B) Meta Ads (Facebook e Instagram).** Ecosistema primario per stimolare la domanda latente e gestire volumi elevati, specialmente per i profili blue-collar. Le opzioni spaziano dalle campagne statiche (Lead Generation e Traffico), ben visibili nelle Ad Library pubbliche, che sfruttano moduli nativi in-app per abbattere il costo per acquisizione (CPA), alle Dynamic Ads (DPA e DABA), metodologie avanzate non visibili nelle librerie pubbliche. Le agenzie possono trattare il proprio database di annunci lavorativi come un catalogo prodotti, lasciando che gli algoritmi DPA (retargeting) o DABA (broad audiences) costruiscano l'inserzione in tempo reale, sulla base di prossimità geografica e probabilità di conversione.

**C) LinkedIn Ads.** Canale dal duplice ruolo (B2B e B2C), focalizzato su profili specialized e direttivi. Le opzioni includono Sponsored Content (immagine, video, documento) per l'employer branding; Message Ads (ex Sponsored InMail) per il contatto diretto con i passive candidates; e Lead Gen Forms, ideali sia per candidature qualificate sia per l'acquisizione di lead B2B.

**D) Job Board e aggregatori (Indeed, Jooble, Subito Lavoro, AlmaLaurea).** Costituiscono il canale verticale, spesso operante in logica walled garden. L'investimento si concretizza in annunci sponsorizzati (PPC o Pay-Per-Application), per emergere nei risultati di ricerca organici del portale, e in Display Advertising e DEM, con l'acquisto di spazi premium o l'utilizzo dei database proprietari delle piattaforme per promuovere servizi e iniziative B2B.

### 2.4 Le criticità operative: il limite del last-click

La gestione quotidiana di questo media mix frammentato pone il marketing manager di fronte a criticità operative severe, che rendono indispensabile il passaggio a un approccio di Marketing Mix Modeling.

La prima criticità è la frammentazione del tracciamento. Un candidato potrebbe visualizzare un'inserzione su Facebook (generando una view-through conversion non tracciata), cercare successivamente il brand su Google e infine candidarsi cliccando su un annuncio sponsorizzato su Indeed. I tradizionali modelli di attribuzione web-analytics tendono ad assegnare il cento per cento del merito all'ultimo clic — in questo caso Indeed —, ignorando l'effetto di innesco e generazione della domanda svolto da Meta e Google. Questa cecità algoritmica conduce a un sistematico sotto-finanziamento dei canali upper-funnel (social media, display) a favore dei canali lower-funnel (motori di ricerca, aggregatori), compromettendo nel medio-lungo termine la capacità di generare nuova audience.

La seconda criticità riguarda l'incomparabilità delle metriche. Come può un marketing manager confrontare il costo per candidatura generato da una campagna Lead su Facebook con il costo per clic di un annuncio su LinkedIn o con l'abbonamento premium a una job board? I dati restituiti in silos dalle singole piattaforme tendono a sovrastimare il proprio contributo, generando una somma delle conversioni attribuite spesso superiore al numero reale di candidature registrate nei database aziendali.

L'adozione di un modello MMM, calato sulla realtà di Randstad Italia, mira esattamente a risolvere questa impasse. Spostando il focus dal tracciamento del singolo utente all'analisi statistica dei dati aggregati, il modello consente di stimare l'impatto incrementale reale di ciascun euro speso nei diversi canali, fornendo al decisore una mappa navigabile per l'ottimizzazione del budget. Questo passaggio metodologico — dalle euristiche basate sull'ultimo clic alla modellazione probabilistica degli effetti media — costituisce l'oggetto del capitolo successivo.

---

# PARTE II — LA SOLUZIONE

## Capitolo 3 — I pilastri teorici del Marketing Mix Modeling

### 3.1 L'equazione generale del modello

Il Capitolo 1 ha delineato il contesto metodologico nel quale il Marketing Mix Modeling si colloca: la crisi dell'attribuzione deterministica, l'emergere dei framework open-source e il dibattito tra approccio frequentista e bayesiano. Questa sezione traduce quei principi in un'architettura formale, esplicitando la struttura matematica che sottende ogni implementazione moderna del MMM.

L'obiettivo di un modello di Marketing Mix è stimare la relazione causale tra gli investimenti media e una variabile obiettivo di business — nel caso di un'agenzia per il lavoro, tipicamente il numero di candidature settimanali ricevute. Il modello scompone la variabile obiettivo in una somma di componenti, ciascuna con un'interpretazione economica precisa.

La formulazione generale è la seguente:

> y(t) = α + Σₖ βₖ · f(Adstock(xₖ,ₜ)) + Σⱼ γⱼ · zⱼ,ₜ + εₜ

dove y(t) rappresenta il valore della variabile obiettivo al tempo t (ad esempio, il numero di candidature nella settimana t); α è l'intercetta, ossia la baseline organica — il livello di candidature che l'azienda riceverebbe anche in assenza di qualsiasi investimento pubblicitario, per effetto della notorietà del brand, del traffico diretto e del passaparola; xₖ,ₜ indica la spesa (o le impression) del canale media k al tempo t; la funzione Adstock(·) modella il carry-over temporale dell'effetto pubblicitario (Sezione 3.2); la funzione f(·) applica la trasformazione di saturazione che cattura i rendimenti decrescenti (Sezione 3.3); βₖ è il coefficiente che misura l'effetto incrementale del canale k dopo le trasformazioni; zⱼ,ₜ rappresenta le variabili di controllo — stagionalità, trend, festività, indicatori macroeconomici come il tasso di disoccupazione o l'indice della produzione industriale — che influenzano la variabile obiettivo indipendentemente dalla spesa media; γⱼ è il coefficiente associato a ciascuna variabile di controllo; εₜ è il termine di errore.

L'ordine delle trasformazioni è cruciale e non intercambiabile: la spesa grezza viene prima trasformata in adstock (per tenere conto dell'effetto memoria), poi sottoposta alla funzione di saturazione (per modellare i rendimenti decrescenti). Solo a questo punto il valore trasformato viene moltiplicato per il coefficiente β, che ne misura l'impatto sulla variabile obiettivo.

È importante sottolineare che l'intercetta α riveste un ruolo analitico fondamentale nel contesto del settore HR. A differenza di un e-commerce puro, dove la baseline organica può essere trascurabile, un'agenzia per il lavoro come Randstad genera un flusso costante di candidature spontanee — candidati che conoscono il brand, che cercano direttamente il sito, che vengono segnalati dal passaparola o che si recano fisicamente in filiale. La corretta stima di questa baseline è il prerequisito per isolare l'effetto incrementale della pubblicità: una sovrastima di α conduce a una sottostima del contributo media, e viceversa.

### 3.2 La trasformazione adstock: modelli di decadimento e carry-over

Il concetto di adstock, formalizzato da Broadbent (1979) e introdotto nel Capitolo 1, si fonda su un'osservazione empirica fondamentale: l'effetto di un'esposizione pubblicitaria non si esaurisce nell'istante in cui avviene, ma persiste nel tempo con intensità decrescente. Un candidato che vede un'inserzione di lavoro su Facebook il lunedì non necessariamente si candida lo stesso giorno: potrebbe rifletterci, parlarne con un familiare, cercare informazioni sull'azienda e candidarsi il venerdì successivo. L'adstock è la funzione matematica che traduce questo comportamento in una variabile utilizzabile dal modello.

#### 3.2.1 Il decadimento geometrico

La forma più semplice di adstock è il decadimento geometrico, nel quale l'effetto della spesa decresce esponenzialmente nel tempo secondo un tasso costante:

> A(t) = x(t) + λ · A(t−1)

dove A(t) è il valore di adstock al tempo t, x(t) è la spesa nel periodo corrente e λ ∈ [0,1] è il tasso di ritenzione. Un λ prossimo a 1 indica un effetto persistente (il ricordo della pubblicità decade lentamente); un λ prossimo a 0 indica un effetto effimero (la pubblicità agisce quasi esclusivamente nel periodo di erogazione).

Il modello geometrico ha il pregio della semplicità — un singolo parametro da stimare — ma presenta un limite strutturale: assume che il picco dell'effetto coincida sempre con il periodo di erogazione della spesa. L'assunzione è ragionevole per i canali a risposta diretta (come Google Search, dove l'utente clicca e si candida quasi immediatamente), ma risulta inadeguata per i canali upper-funnel (come i social media o il display advertising), dove l'effetto massimo può manifestarsi con un ritardo di giorni o settimane rispetto all'esposizione.

#### 3.2.2 Il decadimento ritardato (delayed adstock)

Per superare questa limitazione, i framework moderni — in particolare Meridian e PyMC-Marketing — implementano funzioni di adstock a due parametri che consentono di modellare sia la persistenza sia il ritardo dell'effetto. La distribuzione di Weibull, nella sua forma CDF (Cumulative Distribution Function) o PDF (Probability Density Function), è la scelta più comune.

Nella parametrizzazione Weibull-PDF, l'effetto non raggiunge il picco al tempo zero, ma dopo un ritardo θ (il parametro di scala), e poi decade con una velocità controllata dal parametro di forma k. Questo consente di catturare dinamiche come la seguente: una campagna display su Meta genera awareness nella prima settimana, raggiunge il picco di effetto sulle candidature nella seconda settimana — quando il ricordo si traduce in azione — e decade progressivamente nelle settimane successive.

La scelta tra decadimento geometrico e Weibull non è arbitraria, ma deve riflettere la conoscenza del comportamento del canale. Nel settore del recruiting, dove il ciclo decisionale del candidato è mediamente più lungo rispetto a un acquisto d'impulso, il delayed adstock è particolarmente appropriato per i canali di awareness (Meta, LinkedIn, Display), mentre il decadimento geometrico semplice può essere sufficiente per i canali a risposta diretta (Google Search, job board sponsorizzate).

### 3.3 La funzione di saturazione: rendimenti decrescenti e funzione di Hill

La seconda trasformazione fondamentale applicata alla spesa media è la funzione di saturazione, che modella un principio economico intuitivo: i rendimenti marginali della pubblicità sono decrescenti. I primi euro investiti su un canale generano un effetto proporzionalmente elevato, ma al crescere della spesa ogni euro aggiuntivo produce un incremento minore. Esiste un punto oltre il quale un aumento della spesa non produce alcun beneficio incrementale apprezzabile: il canale è «saturo».

#### 3.3.1 La funzione di Hill

La funzione di Hill, originariamente sviluppata in biochimica per modellare la relazione dose-risposta tra la concentrazione di un ligando e la risposta biologica, è diventata lo standard nella modellazione della saturazione nel MMM contemporaneo. La sua forma è la seguente:

> f(x) = xˢ / (Kˢ + xˢ)

dove x è il valore di adstock (la spesa trasformata), K è il parametro di half-saturation (il livello di spesa al quale si raggiunge il 50% dell'effetto massimo) e s è il parametro di slope (che controlla la ripidità della curva di saturazione).

L'interpretazione dei parametri è diretta e operativamente rilevante. Il parametro K risponde alla domanda: «A quale livello di spesa settimanale questo canale raggiunge metà del suo potenziale massimo?». Un K basso indica un canale che satura rapidamente (pochi euro bastano per estrarre gran parte del valore); un K alto indica un canale con ampio margine di crescita. Il parametro s controlla la forma della curva: valori bassi producono una curva graduale (la saturazione avviene progressivamente); valori alti producono una curva ripida (il canale passa bruscamente da «sottosfruttato» a «saturo»).

#### 3.3.2 Implicazioni per il settore HR

Nel contesto del recruiting digitale, la funzione di saturazione ha implicazioni strategiche di primo piano. Canali diversi presentano curve di saturazione radicalmente diverse. Le job board (come Indeed), che operano su un bacino di utenti attivi nella ricerca di lavoro (audience finita), tendono a saturare rapidamente: oltre una certa soglia di sponsorizzazione, il numero di candidati raggiungibili è esaurito. I social media (Meta, LinkedIn), che operano su un bacino potenziale molto più ampio (audience latente), presentano tipicamente curve di saturazione più graduali, con margini di crescita superiori ma anche con una quota maggiore di impression «a vuoto» — utenti non interessati a cambiare lavoro.

La stima accurata di queste curve — e delle differenze tra canali — è precisamente ciò che consente al modello MMM di formulare raccomandazioni di riallocazione del budget: spostare euro da un canale saturo (dove il rendimento marginale è prossimo allo zero) verso un canale sottosfruttato (dove il rendimento marginale è ancora elevato).

### 3.4 La decomposizione dei contributi media

Una volta stimati i parametri del modello — i coefficienti β, i parametri di adstock e quelli di saturazione per ciascun canale — è possibile procedere alla decomposizione (media decomposition), ovvero alla scomposizione della variabile obiettivo nei contributi attribuibili a ciascuna fonte.

Operativamente, la decomposizione calcola, per ogni periodo t, la quota di candidature attribuibile a ciascun canale media, alla baseline organica e alle variabili di controllo. Il contributo del canale k al tempo t è dato dal prodotto del coefficiente βₖ per il valore trasformato (adstock + saturazione) della spesa del canale k in quel periodo.

Dalla decomposizione si derivano le metriche di performance fondamentali per il decisore.

Il contributo incrementale totale di ciascun canale, ottenuto sommando i contributi settimanali sull'intero periodo di osservazione. Questa metrica risponde alla domanda: «Quante candidature in più ha generato questo canale rispetto allo scenario di spesa nulla?».

Il ROI incrementale (Return on Investment), calcolato come rapporto tra il contributo incrementale e la spesa totale sostenuta sul canale. Un ROI di 15 significa che ogni euro investito ha generato 15 candidature incrementali. Il confronto tra i ROI dei diversi canali rivela le inefficienze allocative: se Google ha un ROI di 20 e LinkedIn di 8, il modello suggerisce che un trasferimento marginale di budget da LinkedIn a Google genererebbe un incremento netto di candidature.

Il ROAS marginale (Return on Ad Spend marginale), che a differenza del ROI medio misura il rendimento dell'ultimo euro speso su ciascun canale. Questo è il dato operativamente più rilevante per l'ottimizzazione, poiché cattura la condizione attuale della curva di saturazione: un canale può avere un ROI medio elevato (perché storicamente ha funzionato bene) ma un ROAS marginale basso (perché è ormai saturo al livello di spesa corrente).

È cruciale sottolineare che, in un framework bayesiano, queste metriche non sono stime puntuali ma distribuzioni di probabilità. Il ROI di Google non è «20», ma una distribuzione con mediana 20 e intervallo credibile al 90% compreso, ad esempio, tra 14 e 27. Questa quantificazione dell'incertezza è fondamentale per il processo decisionale: consente al marketing manager di valutare non solo il rendimento atteso, ma anche il rischio associato a ogni ipotesi di riallocazione.

### 3.5 L'ottimizzatore di budget

Il passaggio dalla decomposizione alla raccomandazione operativa avviene attraverso il modulo di ottimizzazione del budget, presente in tutti i principali framework (Robyn, Meridian, PyMC-Marketing). L'ottimizzatore risponde alla domanda più urgente per il marketing manager: «Dato il mio budget totale, come dovrei distribuirlo tra i canali per massimizzare il numero di candidature?».

#### 3.5.1 Formulazione del problema

Il problema è formulato come un'ottimizzazione vincolata. La funzione obiettivo è la massimizzazione delle candidature totali previste dal modello (o, equivalentemente, la massimizzazione del ROI complessivo del portafoglio media). I vincoli tipici includono il vincolo di budget totale (la somma della spesa allocata ai canali non può superare il budget disponibile), i vincoli di spesa minima e massima per canale (che riflettono impegni contrattuali o scelte strategiche — ad esempio, il mantenimento di una presenza minima su LinkedIn per ragioni di employer branding, anche qualora il ROI non lo giustifichi in termini puramente quantitativi) e i vincoli di variazione rispetto allo status quo (per evitare riallocazioni traumatiche, è possibile imporre che la variazione di budget per ciascun canale non superi una soglia percentuale rispetto all'allocazione corrente).

#### 3.5.2 Il meccanismo operativo

L'ottimizzatore utilizza le curve di risposta stimate dal modello — composizione di adstock e saturazione — per simulare l'effetto di molteplici combinazioni di allocazione del budget, identificando quella che massimizza la funzione obiettivo sotto i vincoli specificati. In pratica, l'algoritmo opera lungo le curve di saturazione di ciascun canale, sottraendo euro dai canali dove il rendimento marginale è basso (zona piatta della curva) e aggiungendoli a quelli dove il rendimento marginale è ancora elevato (zona ripida della curva).

L'output dell'ottimizzatore è una tabella di riallocazione che specifica, per ciascun canale, la spesa corrente, la spesa ottimale suggerita, la variazione assoluta e percentuale, e l'incremento atteso di candidature. Include inoltre la stima dell'incremento totale ottenibile a parità di budget complessivo — il cosiddetto budget efficiency gain.

È essenziale comprendere che l'ottimizzatore produce una raccomandazione, non una decisione. La traduzione della raccomandazione in azione operativa spetta al marketing manager, che deve valutare fattori non catturati dal modello: vincoli contrattuali in corso con le piattaforme, obiettivi qualitativi (come la diversificazione del profilo dei candidati), considerazioni di posizionamento competitivo e dinamiche di medio-lungo termine non riflesse nella serie storica.

### 3.6 Il paradigma human-in-the-middle e gli strumenti di supporto alla ricerca

#### 3.6.1 Il decisore come nodo attivo

Il Capitolo 1 ha introdotto il paradigma human-in-the-middle come un modello decisionale nel quale il manager non è né il validatore passivo di un output algoritmico, né il decisore autonomo che ignora le evidenze quantitative, ma il nodo attivo di un sistema di retroazione bidirezionale. Le sezioni precedenti di questo capitolo hanno reso tangibile il concetto: il decisore interviene nel ciclo del modello in almeno tre momenti distinti.

In fase di specificazione, il marketing manager inietta la propria conoscenza di dominio nei prior bayesiani — ad esempio, dichiarando che il ROI atteso di Google Search è probabilmente compreso tra 10 e 25, sulla base dell'esperienza operativa accumulata. Questa informazione guida il modello verso stime coerenti con la realtà del settore, ed è particolarmente preziosa quando i dati sono limitati o rumorosi.

In fase di vincolo dell'ottimizzazione, il decisore traduce la conoscenza contestuale e strategica in parametri operativi — imponendo, ad esempio, un livello minimo di spesa su LinkedIn perché l'employer branding verso i profili white-collar è un obiettivo aziendale non negoziabile, anche qualora il ROI puro non lo giustifichi.

In fase di interpretazione e attuazione, il manager valuta criticamente la raccomandazione algoritmica alla luce di fattori che il modello non può catturare: un contratto quadro con Indeed in scadenza, una nuova campagna di brand awareness pianificata dal team comunicazione, una variazione imminente del mercato del lavoro in un settore specifico.

Il paradigma human-in-the-middle postula che la qualità della decisione finale non sia funzione della sola accuratezza del modello, né della sola esperienza del decisore, ma della qualità dell'interfaccia tra i due. Un modello accurato con un decisore che ne ignora i risultati, o un decisore esperto privo di supporto quantitativo, producono entrambi esiti subottimali. Il valore del sistema risiede nella co-determinazione.

#### 3.6.2 Gli strumenti di intelligenza artificiale a supporto del processo di ricerca

Il paradigma human-in-the-middle non si applica esclusivamente alla fase di ottimizzazione del budget pubblicitario, ma permea l'intero processo di indagine documentato in questo elaborato. È opportuno, per ragioni di trasparenza metodologica e di coerenza intellettuale con la tesi sostenuta, dichiarare che la presente ricerca si è avvalsa di strumenti di intelligenza artificiale generativa come copiloti analitici durante l'arco della stesura.

In particolare, l'autore ha utilizzato Antigravity (Google DeepMind), un assistente di intelligenza artificiale agentico, come strumento di supporto nelle seguenti attività: l'esplorazione sistematica delle librerie inserzioni pubbliche (Meta Ad Library, Google Ads Transparency Center, LinkedIn Ad Library) per la mappatura dell'ecosistema pubblicitario descritta nel Capitolo 2; la ricerca e il reperimento delle fonti bibliografiche; la strutturazione e la revisione formale dei contenuti; l'analisi critica delle architetture tecniche dei framework open-source (Robyn, Meridian, PyMC-Marketing).

È fondamentale precisare la natura di questo utilizzo. Lo strumento ha operato come un amplificatore delle capacità analitiche dell'autore — accelerando la ricerca, sistematizzando le informazioni, suggerendo connessioni — ma non ha in alcun momento sostituito il giudizio critico, la responsabilità intellettuale e la direzione scientifica del lavoro, che restano integralmente in capo all'autore. Ogni affermazione, ogni interpretazione e ogni argomentazione presente in questo elaborato è stata valutata, validata e, ove necessario, corretta o riformulata dall'autore sulla base della propria conoscenza del dominio e della propria esperienza professionale nel settore.

Questa dichiarazione non è un mero adempimento formale, ma un esempio concreto del paradigma che la tesi stessa teorizza. Così come il marketing manager utilizza l'output del MMM come input qualificato per una decisione che resta umana, l'autore ha utilizzato l'output dell'intelligenza artificiale generativa come input qualificato per un processo di ricerca e scrittura che resta, nella sua essenza e nella sua responsabilità, un atto intellettuale umano. In entrambi i casi, il valore non risiede nell'automazione, ma nella qualità del dialogo tra la capacità computazionale della macchina e il giudizio critico della persona.

### 3.7 Sintesi del capitolo

Il presente capitolo ha formalizzato i pilastri teorici del Marketing Mix Modeling, traducendo i principi metodologici introdotti nel Capitolo 1 in un'architettura operativa. L'equazione generale del modello scompone la variabile obiettivo in baseline organica, contributi media trasformati e variabili di controllo. Le trasformazioni di adstock (decadimento geometrico o ritardato) e di saturazione (funzione di Hill) catturano rispettivamente la persistenza temporale e i rendimenti decrescenti dell'effetto pubblicitario. La decomposizione dei contributi e il calcolo del ROI incrementale forniscono la base analitica per l'ottimizzazione del budget, che produce raccomandazioni di riallocazione vincolate alle esigenze operative.

Il capitolo si è chiuso con una riflessione sul paradigma human-in-the-middle, dimostrando che il decisore interviene attivamente in ogni fase del ciclo — dalla specificazione dei prior all'interpretazione dei risultati — e con una dichiarazione trasparente sull'utilizzo di strumenti di intelligenza artificiale generativa a supporto della ricerca, coerente con il medesimo paradigma.

Il capitolo successivo tradurrà questi principi in un design operativo: la scelta del framework, la specifica del dataset e i criteri di validazione del modello.

## Capitolo 4 — Design del sistema

### 4.1 L'architettura della pipeline

I principi teorici esposti nel Capitolo 3 sono stati tradotti in una pipeline analitica end-to-end, implementata in Python e organizzata in moduli a responsabilità singola, raccolti nella directory `mmm/` del repository di ricerca. La scelta di un'implementazione custom — in luogo dell'adozione diretta di un framework esistente — risponde a una precisa esigenza metodologica: rendere ogni passaggio della catena analitica ispezionabile, documentabile e difendibile in sede di discussione, evitando l'effetto «scatola nera» che l'uso di librerie monolitiche comporterebbe. L'architettura è al contempo progettata per la migrazione: la struttura del modello è identica a quella dei framework bayesiani contemporanei, cosicché il fit frequentista qui documentato potrà essere sostituito, in una fase successiva della roadmap, dalle distribuzioni a posteriori di PyMC-Marketing senza modificare il resto della pipeline.

La pipeline si articola in sette moduli. Il modulo `config.py` centralizza la configurazione: i canali modellati (Google, Meta, LinkedIn, Indeed), i livelli medi di spesa settimanale, i parametri «veri» del processo generativo sintetico e le variabili di controllo. Il modulo `transforms.py` implementa le due trasformazioni fondamentali — adstock geometrico e funzione di Hill — insieme alle funzioni derivate per il calcolo della risposta a regime e del ROAS marginale. Il modulo `data_generator.py` produce il dataset sintetico settimanale. Il modulo `ingestion.py` gestisce l'importazione automatica di serie storiche esterne in formato arbitrario. Il modulo `model.py` esegue la stima dei parametri. Il modulo `allocator.py` implementa l'ottimizzazione vincolata del budget e la pianificazione multi-periodo. Infine, `app.py` espone l'intera pipeline attraverso un'interfaccia web interattiva (Streamlit), mentre `run_pipeline.py` consente l'esecuzione riproducibile dell'intero flusso da riga di comando, dalla generazione dei dati alla raccomandazione di allocazione.

### 4.2 Il dataset sintetico

In ottemperanza ai vincoli di compliance dichiarati nell'Introduzione, l'indagine opera su un dataset sintetico di 156 osservazioni settimanali (tre anni), calibrato qualitativamente sulle dinamiche del settore. Il processo generativo riproduce le specificità descritte nel Capitolo 2.

La spesa settimanale per canale è generata attorno a livelli medi differenziati (12.000 EUR per Google, 9.000 per Meta, 8.000 per Indeed, 5.000 per LinkedIn), modulata da una componente stagionale sinusoidale, da rumore moltiplicativo e da pause campagna casuali di due-quattro settimane. Queste ultime non sono un dettaglio ornamentale: le interruzioni di erogazione introducono la variabilità indipendente tra i canali che rende statisticamente identificabili i parametri di risposta — un principio noto in letteratura, dove la varianza della spesa è riconosciuta come prerequisito informativo del MMM.

I parametri veri del processo generativo codificano la conoscenza di dominio discussa nella Sezione 3.3.2: Indeed, operando su un'audience finita di candidati attivi, satura rapidamente (K = 7.000 EUR, slope ripida s = 1,8) e ha memoria pubblicitaria breve (λ = 0,20); Meta, che stimola domanda latente, presenta saturazione graduale (K = 30.000) e persistenza media (λ = 0,45); LinkedIn ha l'effetto massimo più contenuto (β = 90 candidature/settimana) ma la coda temporale più lunga (λ = 0,55); Google Search combina risposta quasi immediata (λ = 0,15) ed elevata efficacia.

La variabile obiettivo — le candidature settimanali — è costruita come somma di quattro componenti: una baseline organica (α = 850 candidature/settimana, con trend lieve e doppia armonica stagionale), l'effetto delle variabili di controllo, i contributi dei quattro canali trasformati secondo la catena adstock-saturazione, e un rumore gaussiano osservazionale. Poiché il processo generativo è noto, il dataset funge da banco di prova controllato: ogni stima del modello può essere confrontata con il valore vero che l'ha generata — il cosiddetto *parameter recovery test*, criterio di validazione principale di questo capitolo.

### 4.3 Le variabili di controllo: domanda dei clienti e dei candidati

Il modello incorpora due variabili di controllo specifiche del settore, corrispondenti ai due lati del mercato duale descritto nella Sezione 2.1. La prima, `richieste_clienti`, rappresenta la serie storica delle richieste di fulfillment provenienti dalle aziende clienti — la domanda B2B di personale, con trend crescente e picchi pre-estivi e di quarto trimestre legati a logistica e manifattura. La seconda, `ricerche_lavoratori`, misura l'intensità della ricerca di lavoro lato candidati, con i picchi di gennaio e settembre tipici dei cicli di ricollocazione.

L'inclusione di queste serie risponde all'esigenza, argomentata nel Capitolo 3, di depurare l'effetto incrementale della pubblicità dalle variazioni di domanda che si sarebbero verificate comunque: una settimana con molte candidature potrebbe riflettere non l'efficacia delle campagne, ma semplicemente un picco stagionale di persone in cerca di occupazione. Nel processo generativo sintetico, i coefficienti veri sono fissati a γ = 0,15 per le richieste clienti e γ = 0,08 per le ricerche dei lavoratori (entrambe le serie sono centrate sulla media, cosicché l'intercetta conserva l'interpretazione di baseline al livello medio di domanda).

### 4.4 L'ingestione automatica di serie esterne

Nella prospettiva operativa — e nella roadmap di adozione con dati reali — le serie di domanda non saranno generate sinteticamente, ma fornite dalle funzioni aziendali in formati eterogenei e non standardizzati: estrazioni Excel del CRM commerciale, report PDF della direzione, esportazioni CSV dei sistemi di analytics. Il modulo `ingestion.py` affronta questo problema con una strategia di riconoscimento automatico in quattro stadi.

Il primo stadio è l'estrazione grezza delle tabelle, differenziata per formato: per i file Excel vengono letti tutti i fogli di lavoro; per i PDF vengono estratte le tabelle di tutte le pagine tramite la libreria pdfplumber, con un meccanismo di fallback testuale per i documenti privi di griglia esplicita; per i CSV il separatore viene inferito automaticamente. Il secondo stadio è il rilevamento della colonna temporale: ogni colonna viene sottoposta a un parser che riconosce date in formato standard, mesi italiani e inglesi in forma estesa o abbreviata («Gennaio 2024», «set 2023»), e notazioni anno-mese («2024-01», «01/2024»); la colonna con il maggior tasso di riconoscimento viene eletta a indice temporale. Il terzo stadio è la coercizione numerica robusta, che gestisce le convenzioni tipografiche italiane — il punto come separatore delle migliaia («2.150»), la virgola decimale («1.234,56») — e scarta le colonne non numeriche. Il quarto stadio è il riallineamento temporale: le serie mensili o irregolari vengono interpolate linearmente nel tempo sulla griglia settimanale del dataset MMM, e le serie risultanti vengono aggiunte al modello come variabili di controllo aggiuntive con prefisso `ctrl_`.

A scopo dimostrativo e di test, il repository include nella directory `mmm/data/esempi/` tre file campione che riproducono i casi d'uso attesi: un file Excel (`richieste_clienti.xlsx`) con dodici osservazioni mensili, mesi italiani in forma estesa e valori con separatore delle migliaia all'italiana; un file CSV (`ricerche.csv`) con venti osservazioni settimanali, date in formato europeo giorno/mese/anno, separatore punto e virgola e virgola decimale; e un file PDF (`fulfillment.pdf`) contenente una tabella mensile in notazione anno-mese. Lo script di test locale (`test_locale.py`) verifica che tutti e tre i formati vengano riconosciuti, convertiti e fusi correttamente nel dataset settimanale — una forma di test di integrazione che documenta, al contempo, il contratto informale che i file di input devono rispettare: una colonna interpretabile come periodo temporale e almeno una colonna numerica.

### 4.5 La specificazione e la stima del modello

Il modello stimato segue fedelmente l'equazione generale della Sezione 3.1. La baseline è parametrizzata come somma di intercetta, trend lineare e due armoniche di Fourier annuali (seno e coseno per la frequenza fondamentale e per la prima armonica), per un totale di sei parametri. A questi si aggiungono un coefficiente lineare per ciascuna variabile di controllo e quattro parametri per ciascun canale media: l'effetto massimo β, il tasso di ritenzione dell'adstock λ, la half-saturation K e la slope s della funzione di Hill. Con quattro canali e due controlli, il modello conta ventiquattro parametri stimati congiuntamente su 156 osservazioni.

La stima è condotta per minimi quadrati non lineari con bound sui parametri (algoritmo Trust Region Reflective, implementazione `scipy.optimize.least_squares`). La scelta dell'approccio frequentista, motivata nella Sezione 4.1, ha richiesto tuttavia un accorgimento che costituisce uno dei risultati metodologici più istruttivi dell'implementazione, documentato nella sezione seguente.

### 4.6 Il problema dell'identificabilità e i bound informativi

Una prima versione del fit, condotta con bound deliberatamente larghi (K libero fino a venti volte la spesa media), ha prodotto un esito apparentemente paradossale: un fit eccellente in termini predittivi (R² = 0,94) accompagnato da stime dei parametri strutturali gravemente distorte — per Google, un β stimato di 1.213 contro un valore vero di 260, e un K di 224.556 contro 18.000.

Il fenomeno ha una spiegazione precisa. Quando la spesa osservata non raggiunge la zona di saturazione della curva di Hill, la curva è approssimativamente lineare nel range dei dati: in tale regime, il rapporto β/K è identificato, ma β e K singolarmente non lo sono — coppie (β, K) molto diverse producono curve quasi indistinguibili dove i dati esistono, divergendo solo nella regione extrapolativa che i dati non coprono. Si tratta della manifestazione concreta, nel nostro banco di prova, del problema di identificabilità debole che la letteratura bayesiana sul MMM indica come motivazione principale per l'uso di prior informativi (Chan & Perry, 2017; Jin et al., 2017).

La soluzione adottata è l'equivalente frequentista di tale prescrizione: bound informativi che vincolano K entro un intervallo plausibile rispetto alla spesa osservata (tra 0,3 e 5 volte la spesa media del canale) e β entro un multiplo ragionevole del livello della variabile obiettivo. Si noti la lettura metodologica: il vincolo non è un artificio numerico, ma una forma strutturata di iniezione di conoscenza di dominio nel modello — il primo dei tre momenti di intervento del decisore previsti dal paradigma human-in-the-middle (Sezione 3.6.1).

Coerentemente con questa diagnosi, la validazione è stata sdoppiata su due livelli. Il primo è il parameter recovery classico, parametro per parametro. Il secondo — decisionalmente più rilevante — è il *curve recovery*: l'errore medio assoluto tra la curva di risposta a regime vera e quella stimata, valutato nel range operativo di spesa (da 0,5 a 1,5 volte la spesa media). È infatti la curva, non il singolo parametro, l'oggetto su cui opera l'ottimizzatore di budget: due parametrizzazioni diverse che producono la stessa curva nel range operativo conducono alle stesse decisioni di allocazione.

### 4.7 Sintesi del capitolo

Il capitolo ha delineato il design del sistema: un'architettura modulare a sette componenti, un dataset sintetico di 156 osservazioni settimanali con processo generativo noto, due variabili di controllo specifiche del mercato duale del recruiting, un modulo di ingestione automatica per serie esterne in formato arbitrario, una specificazione del modello fedele all'equazione generale del Capitolo 3 con bound informativi che incorporano la conoscenza di dominio, e un protocollo di validazione a due livelli — parameter recovery e curve recovery. Il capitolo successivo documenta l'esecuzione della pipeline e ne restituisce l'output tecnico.

## Capitolo 5 — Implementazione e risultati

### 5.1 L'esecuzione della pipeline

L'intera pipeline è eseguibile in modo riproducibile da riga di comando (`python run_pipeline.py`): la sequenza genera il dataset sintetico, stima il modello, produce le tabelle di parameter recovery e curve recovery e calcola l'allocazione ottimale di riferimento. Un secondo script (`python test_locale.py`) costituisce il test di integrazione del sistema: verifica l'ingestione dei tre file di esempio (Excel mensile con mesi italiani, CSV settimanale con date europee, PDF con tabella anno-mese), il loro riallineamento sulla griglia settimanale, il fit del modello con i controlli esterni aggiunti e il rispetto dei vincoli da parte dell'ottimizzatore. Il run di riferimento (seed deterministico, 156 settimane) produce i risultati documentati di seguito.

### 5.2 Metriche di accuratezza e recupero dei parametri

Sul piano predittivo, il modello raggiunge un R² di 0,968, un NRMSE di 0,044 e un MAPE dell'1,9% — valori che collocano il fit nella fascia di qualità che la letteratura applicata considera buona per il MMM (NRMSE inferiore a 0,10).

Sul piano del recupero dei parametri, i coefficienti delle variabili di controllo sono stimati con precisione notevole: 0,161 contro un valore vero di 0,15 per le richieste clienti, 0,069 contro 0,08 per le ricerche dei lavoratori. I parametri di canale mostrano il pattern atteso dalla diagnosi di identificabilità: i tassi di adstock e le slope sono recuperati in modo ragionevole, mentre β e K presentano errori compensativi (per Google, β stimato 367 contro 260 e K stimato 29.652 contro 18.000 — entrambi sovrastimati in proporzione simile, lasciando la curva sostanzialmente corretta).

Il curve recovery conferma questa lettura: l'errore medio sulla curva di risposta nel range operativo è del 6,7% per Indeed, del 17,5% per Meta, del 18,0% per LinkedIn e del 24,8% per Google. Per un modello frequentista a stime puntuali su 156 osservazioni rumorose, si tratta di un livello di accuratezza compatibile con l'uso decisionale, fermo restando che la quantificazione formale dell'incertezza attorno a queste curve — gli intervalli credibili — è demandata alla fase bayesiana della roadmap.

### 5.3 L'output dell'ottimizzatore

Sul piano dell'ottimizzazione, il run di riferimento a parità di budget (31.958 EUR/settimana, pari alla spesa storica media) raccomanda una riallocazione che riduce Google del 24,5% e Indeed del 3,5%, aumenta Meta dell'11,0% e LinkedIn del 43,9%, con un incremento atteso delle candidature dell'1,7% a parità di spesa. La firma dell'ottimo vincolato è verificabile direttamente nell'output: dopo la riallocazione, il ROAS marginale è equalizzato a 7,1 candidature per mille euro su tutti i canali — la condizione di ottimalità per cui nessuno spostamento marginale di budget tra canali può più migliorare il risultato. È la traduzione algoritmica del principio economico esposto nella Sezione 3.5.2: l'ottimizzatore sottrae euro dalle zone piatte delle curve di saturazione e li sposta verso le zone ancora ripide, fino a pareggiare i rendimenti marginali.

### 5.4 La pianificazione multi-periodo e i vincoli manageriali

L'ottimizzatore opera nativamente sulla scala settimanale, ma l'orizzonte decisionale del marketing manager è il piano annuale, articolato per trimestri o mesi. Il modulo di pianificazione multi-periodo colma questa distanza: il decisore specifica il budget complessivo del piano, la granularità di gestione (anno, quarter o mese) e i pesi relativi dei periodi — ad esempio, una maggiore dotazione per il quarto trimestre in previsione dei picchi logistici — e il sistema risolve un problema di ottimizzazione vincolata per ciascun periodo, restituendo il piano completo di allocazione per periodo e canale.

I vincoli disponibili formalizzano i tre momenti di intervento manageriale del paradigma human-in-the-middle: la spesa minima per canale (per presidi strategici come l'employer branding su LinkedIn, indipendentemente dal ROI di breve periodo), la spesa massima (per tetti contrattuali o di rischio) e la variazione massima rispetto allo status quo (per evitare riallocazioni traumatiche che il modello, cieco alle dinamiche organizzative, potrebbe altrimenti suggerire). In un esperimento illustrativo con budget annuale di 1,7 milioni di euro distribuito sui quattro trimestri con pesi 0,8 / 1,0 / 0,9 / 1,3 e presidio minimo su LinkedIn, il sistema produce un piano che rispetta tutti i vincoli e stima circa 18.000 candidature attese sull'anno.

### 5.5 L'interfaccia operativa

L'ultimo anello della catena è l'interfaccia web (Streamlit), che rende la pipeline accessibile al decisore non tecnico e costituisce il prototipo della dashboard operativa prefigurata nella roadmap (Capitolo 7). L'interfaccia si articola in tre viste. La vista *Dati* consente di caricare il dataset principale e di importare le serie esterne — richieste clienti, ricerche dei lavoratori o qualunque altra serie di controllo — in qualsiasi formato supportato, con riscontro immediato delle serie riconosciute. La vista *Modello* esegue la stima, espone le diagnostiche (R², NRMSE, MAPE), i parametri per canale, i coefficienti dei controlli, la decomposizione settimanale dei contributi e le curve di risposta a regime. La vista *Allocator* implementa il ciclo decisionale: il manager imposta il budget annuale, sceglie la granularità di gestione, distribuisce i pesi tra i periodi, dichiara i vincoli per canale e ottiene il piano ottimale con il dettaglio per periodo e canale, esportabile in CSV.

L'interfaccia chiude il cerchio del paradigma teorizzato: il modello calcola, il manager vincola e interpreta, e l'esito — esplicitamente etichettato come raccomandazione, non come decisione — torna nelle mani del decisore per la valutazione finale alla luce dei fattori che il modello non vede.

### 5.6 Sintesi del capitolo

Il capitolo ha restituito l'output tecnico della pipeline: un fit con R² di 0,968 e MAPE dell'1,9%, il recupero accurato dei coefficienti delle variabili di controllo, un curve recovery compreso tra il 6,7% e il 24,8% di errore medio nel range operativo, e una raccomandazione di riallocazione che equalizza i rendimenti marginali su tutti i canali. L'interpretazione di queste evidenze — e dei loro limiti — è oggetto della Parte III.

---

# PARTE III — LA VALUTAZIONE

## Capitolo 6 — Discussione

### 6.1 Dalla curva alla decisione

Il primo livello di lettura dei risultati riguarda la direzione della riallocazione raccomandata. A parità di budget, il modello suggerisce di ridurre Google (−24,5%) e Indeed (−3,5%) per finanziare l'espansione di Meta (+11,0%) e LinkedIn (+43,9%). La logica economica della raccomandazione è leggibile direttamente nei ROAS marginali pre-ottimizzazione: al livello di spesa storico, l'ultimo euro investito rendeva 5,8 candidature per mille euro su Google e 6,6 su Indeed, contro 8,0 su Meta e 10,3 su LinkedIn. I primi due canali operavano nella zona piatta delle rispettive curve di saturazione; gli altri due nella zona ancora ripida. L'ottimizzatore non fa che pareggiare questi rendimenti, portandoli tutti a 7,1.

L'esito merita una lettura alla luce della diagnosi formulata nella Sezione 2.4. I canali che il modello suggerisce di ridurre — il motore di ricerca e la job board — sono esattamente i canali lower-funnel che le euristiche di attribuzione last-click tendono a sovra-finanziare, perché raccolgono il clic finale di percorsi di conversione innescati altrove. I canali da espandere — i social media — sono quelli upper-funnel sistematicamente penalizzati dalla stessa euristica. Il risultato del banco di prova sintetico riproduce dunque, in forma controllata, il fenomeno che la letteratura documenta sui dati reali: il passaggio da una misurazione per ultimo clic a una misurazione incrementale ridistribuisce il merito — e quindi il budget — dai canali di raccolta della domanda ai canali di generazione della domanda.

Va peraltro sottolineato ciò che la raccomandazione non dice. L'incremento atteso a parità di budget è dell'1,7%: un guadagno di efficienza reale ma non drammatico, coerente con uno scenario in cui l'allocazione storica non era gravemente distorta. Il valore del modello, in questo contesto, non risiede nel promettere guadagni eclatanti, ma nel sostituire una giustificazione quantitativa e ispezionabile a un'allocazione fondata su consuetudine e contrattazione interna — e nel rendere visibile il costo opportunità di ogni vincolo che il decisore sceglie di imporre.

### 6.2 L'analisi di scenario

Il secondo livello di lettura emerge dall'analisi di scenario condotta sulle curve stimate, facendo variare il budget complessivo rispetto al livello storico (31.958 EUR/settimana).

Nello scenario di contrazione (−20%, 25.566 EUR/settimana), l'allocazione ottima produce 294 candidature settimanali contro le 288 del mix storico semplicemente scalato: il guadagno dell'ottimizzazione sale al 2,3%. Nello scenario di espansione (+20%, 38.349 EUR/settimana) le candidature attese salgono a 386 (+1,3% sul mix scalato), e nello scenario +50% a 433 (+0,9%). Si osservano due regolarità economicamente significative.

La prima: il guadagno relativo dell'ottimizzazione cresce al ridursi del budget. Quando le risorse sono scarse, allocarle bene conta di più: con un budget ridotto, tutti i canali operano nella zona ripida delle curve, dove le differenze di pendenza tra canali sono massime e l'allocazione intelligente produce il vantaggio maggiore. In espansione, viceversa, i canali migliori si avvicinano progressivamente alla saturazione e le alternative tendono a equivalersi. La conseguenza manageriale è notevole: l'adozione di un sistema di ottimizzazione è tanto più preziosa quanto più il contesto è di austerità — esattamente il contesto in cui, nella prassi, gli strumenti analitici vengono percepiti come un lusso rinviabile.

La seconda: la composizione ottima del portafoglio cambia con la scala. Nello scenario −20% l'allocazione ottima riduce drasticamente Google (5.807 EUR contro gli 11.228 storici) preservando relativamente LinkedIn e Meta; nello scenario +50% Google torna a essere il primo canale (16.689 EUR). I rendimenti marginali decrescenti implicano che non esista un «mix ottimo» universale espresso in percentuali fisse: la quota ottima di ciascun canale è funzione del livello di spesa complessivo. Le regole pratiche diffuse nel settore — allocazioni percentuali fisse per canale — sono dunque strutturalmente subottimali rispetto a una riallocazione adattiva.

Il profilo dei ROAS marginali lungo la curva conferma e quantifica la diagnosi qualitativa formulata nella Sezione 3.3.2: Indeed esibisce il crollo più rapido (da 17,6 candidature per mille euro a metà della spesa storica a 1,2 al doppio della spesa storica), coerente con la natura di canale ad audience finita che satura rapidamente; Meta e Google degradano più dolcemente; LinkedIn mostra un profilo a campana (10,3 al livello storico, 7,9 a metà spesa), riflesso della slope elevata stimata per quel canale.

### 6.3 Il confronto con la letteratura

I risultati del banco di prova si prestano a un confronto con le aspettative formulate dalla letteratura metodologica esaminata nel Capitolo 1.

In primo luogo, l'entità del guadagno di efficienza (1-2% a parità di budget) è coerente con l'ordine di grandezza che gli studi applicativi riportano per riallocazioni vincolate in contesti con allocazioni di partenza ragionevoli; guadagni a doppia cifra emergono in letteratura solo in presenza di distorsioni allocative severe o di vincoli di partenza molto lontani dall'ottimo. In secondo luogo, la gerarchia delle curve di saturazione stimate — job board rapida a saturare, social graduali — riproduce il pattern atteso dalla distinzione tra audience attiva finita e audience latente ampia, fornendo una prima evidenza, sia pure su dati sintetici, che la struttura del modello è in grado di rappresentare le specificità del recruiting. In terzo luogo, l'esperienza dell'identificabilità debole di β e K conferma empiricamente l'argomento centrale di Chan e Perry (2017) e Jin et al. (2017) a favore dei prior informativi: con 100-200 osservazioni settimanali e canali che non esplorano la zona di saturazione, la verosimiglianza da sola non basta a separare i parametri strutturali, e la conoscenza di dominio — sotto forma di prior o, come qui, di bound — è una componente necessaria, non un'opzione.

Quanto al passaggio da decisioni intuitive a decisioni data-driven, l'esperimento suggerisce una conclusione sfumata. Il modello non sostituisce le intuizioni del manager: le disciplina. Le intuizioni corrette (la job board satura presto; i social hanno margine) vengono confermate e quantificate; quelle scorrette (l'allocazione percentuale fissa) vengono falsificate con un controfattuale esplicito. La funzione del sistema è trasformare il disaccordo organizzativo da conflitto di opinioni a confronto su assunzioni ispezionabili — quali prior, quali vincoli, quale orizzonte.

### 6.4 I limiti metodologici

Tre limiti dell'implementazione corrente meritano menzione esplicita, in quanto delimitano la validità delle conclusioni e motivano la roadmap.

Il primo è la natura puntuale delle stime: l'approccio frequentista adottato non produce distribuzioni di probabilità, e l'incertezza sulle curve di risposta — e dunque sulle raccomandazioni di allocazione — non è quantificata formalmente. La migrazione a PyMC-Marketing, resa agevole dall'identità strutturale del modello, è il passo successivo naturale.

Il secondo è l'adstock geometrico: come discusso nella Sezione 3.2.2, i canali upper-funnel del recruiting esibiscono verosimilmente effetti ritardati che la parametrizzazione geometrica non cattura; l'estensione a funzioni di Weibull è prevista nella fase bayesiana.

Il terzo è la natura sintetica dei dati: il banco di prova controllato dimostra che la pipeline funziona — recupera le curve che hanno generato i dati e converge all'allocazione ottima — ma non che il modello descriva correttamente il mercato reale. La validazione su dati aggregati reali, compatibilmente con le autorizzazioni aziendali, resta il banco di prova definitivo.

### 6.5 Sintesi del capitolo

Il capitolo ha interpretato l'output tecnico della pipeline alla luce degli obiettivi dell'indagine. La riallocazione raccomandata riproduce, in forma controllata, la correzione del last-touch bias documentata dalla letteratura: meno risorse ai canali di raccolta della domanda, più risorse ai canali che la generano. L'analisi di scenario ha mostrato che il valore dell'ottimizzazione cresce nei contesti di budget scarso e che il mix ottimo è funzione della scala di spesa — falsificando la prassi delle allocazioni percentuali fisse. Il confronto con la letteratura ha confermato la coerenza dell'ordine di grandezza dei guadagni e la necessità strutturale di conoscenza di dominio nella stima. I limiti dichiarati — stime puntuali, adstock geometrico, dati sintetici — delimitano il perimetro delle conclusioni e definiscono l'agenda del capitolo finale.

## Capitolo 7 — Conclusioni e sviluppi futuri (bozza)

*[Capitolo da sviluppare in fase di chiusura del lavoro. Traccia dei contenuti:]*

### 7.1 Il contributo originale

Bilancio rispetto ai tre obiettivi della Sezione 1.5: l'applicabilità del MMM al settore HR (prima applicazione documentata, verificata su banco di prova sintetico), la pipeline end-to-end riproducibile e trasferibile, e l'operazionalizzazione del paradigma human-in-the-middle nei tre momenti di intervento del decisore (specificazione, vincolo, interpretazione).

### 7.2 L'evoluzione del paradigma human-in-the-middle

Riflessione sulla metamorfosi del ruolo del decisore con la maturazione del sistema — da calibratore del modello, a gestore delle eccezioni, a supervisore di un feedback loop in cui decisioni ed esiti rientrano come dati. Discussione dei confini dell'automazione decisionale nel dominio HR.

### 7.3 La roadmap

Tre direttrici: validazione su dati reali aggregati (e calibrazione con esperimenti incrementali), migrazione bayesiana con PyMC-Marketing (prior elicitabili, intervalli di probabilità sulle raccomandazioni, adstock di Weibull), industrializzazione della dashboard operativa per il team.

---

# Riferimenti bibliografici

BANSAL G., WU T., ZHOU J., FOK R., NUSHI B., KAMAR E., RIBEIRO M.T. e WELD D.S. (2021). Does the whole exceed its parts? The effect of AI explanations on complementary team performance. In: *Proceedings of the 2021 CHI Conference on Human Factors in Computing Systems*, Yokohama, maggio 2021. New York: ACM, pp. 1-16

BASS F.M. (1969). A new product growth for model consumer durables. *Management Science*, 15(5), pp. 215-227

BERMAN R. (2018). Beyond the last touch: Attribution in online advertising. *Marketing Science*, 37(5), pp. 771-792

BROADBENT S. (1979). One way TV advertisements work. *Journal of the Market Research Society*, 21(3), pp. 139-166

CHAN D. e PERRY M. (2017). *Challenges and opportunities in media mix modeling* [Online]. Google Research. Disponibile all'indirizzo: <https://research.google/pubs/pub45998/>. (Consultato il 10/06/2026)

GOOGLE (2025). *Meridian: an open-source marketing mix model* [Online]. Disponibile all'indirizzo: <https://developers.google.com/meridian>. (Consultato il 10/06/2026)

HOFFMAN M.D. e GELMAN A. (2014). The No-U-Turn Sampler: Adaptively setting path lengths in Hamiltonian Monte Carlo. *Journal of Machine Learning Research*, 15(1), pp. 1593-1623

IAB EUROPE (2024). *AdEx Benchmark 2023 Report* [Online]. Bruxelles: IAB Europe. Disponibile all'indirizzo: <https://iabeurope.eu>. (Consultato il 10/06/2026)

JIN Y., WANG Y., SUN Y., CHAN D. e KOEHLER J. (2017). *Bayesian methods for media mix modeling with carryover and shape effects* [Online]. Google Research. Disponibile all'indirizzo: <https://research.google/pubs/pub46001/>. (Consultato il 10/06/2026)

KUMAR R., CARROLL C., HARTIKAINEN A. e MARTIN O. (2019). ArviZ: a unified library for exploratory analysis of Bayesian models in Python. *Journal of Open Source Software*, 4(33), 1143

LAI V., CHEN C., LIAO Q.V., SMITH-RENNER A. e TAN C. (2021). *Towards a science of human-AI decision making: A survey of empirical studies* [Online]. arXiv:2112.11471. Disponibile all'indirizzo: <https://arxiv.org/abs/2112.11471>. (Consultato il 10/06/2026)

LI H. e KANNAN P.K. (2014). Attributing conversions in a multichannel online marketing environment: An empirical model and a field experiment. *Journal of Marketing Research*, 51(1), pp. 40-56

LITTLE J.D.C. (1975). BRANDAID: A marketing-mix model, part 1: Structure. *Operations Research*, 23(4), pp. 628-655

MAYER J.R. e MITCHELL J.C. (2012). Third-party web tracking: Policy and technology. In: *Proceedings of the 2012 IEEE Symposium on Security and Privacy*, San Francisco, maggio 2012. IEEE, pp. 413-427

MOREY R.D., HOEKSTRA R., ROUDER J.N., LEE M.D. e WAGENMAKERS E.-J. (2016). The fallacy of placing confidence in confidence intervals. *Psychonomic Bulletin & Review*, 23(1), pp. 103-123

PYMC LABS (2023). *PyMC-Marketing: Bayesian marketing analytics* [Online]. Disponibile all'indirizzo: <https://www.pymc-marketing.io>. (Consultato il 10/06/2026)

RUNGE J., SKOKAN I., ZHOU G. e PAUWELS K. (2024). *Packaging up media mix modeling: An introduction to Robyn's open-source approach* [Online]. Marketing Science Institute Working Paper Series, Report No. 24-147. Disponibile all'indirizzo: <https://arxiv.org/abs/2403.14674>. (Consultato il 10/06/2026)

SALVATIER J., WIECKI T.V. e FONNESBECK C. (2016). Probabilistic programming in Python using PyMC3. *PeerJ Computer Science*, 2, e55

SAPP S. e GALBRECHT A. (2023). *[Riferimento da completare: verificare titolo e sede di pubblicazione del contributo citato nel Capitolo 1]*

TELLIS G.J. (2006). Modeling marketing mix. In: GROVER R. e VRIENS M. (a cura di), *The handbook of marketing research: Uses, misuses, and future advances*. Thousand Oaks: Sage, pp. 506-522

**Fonti normative**

D.Lgs. 10 settembre 2003, n. 276 (riforma Biagi) · D.Lgs. 15 giugno 2015, n. 81 (Jobs Act) · D.L. 12 luglio 2018, n. 87, conv. L. 9 agosto 2018, n. 96 (Decreto Dignità) · Regolamento UE 2016/679 (GDPR) · Regolamento UE 2022/1925 (Digital Markets Act) · California Consumer Privacy Act (2020) · Garante per la Protezione dei Dati Personali, *Linee guida cookie e altri strumenti di tracciamento*, giugno 2021

**Risorse e dataset di settore**

Flurry Analytics (2022), dati di opt-in ATT · Usercentrics (2023), benchmark europei sui tassi di consenso · PageFair (2023), *Adblock Report* · Meta Ad Library, Google Ads Transparency Center, LinkedIn Ad Library (librerie inserzioni pubbliche, consultate nel 2026)
