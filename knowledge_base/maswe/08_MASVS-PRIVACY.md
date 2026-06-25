# MASVS-PRIVACY — Privacy dell'utente

Fonte: OWASP MASVS-PRIVACY (12-MASVS-PRIVACY), NowSecure blog su MASVS
Privacy 2024, MASTG-TEST-0001 (sezione permessi file)
Verificato: 23/06/2026 (sessione 2) - ULTIMA categoria della mappa

## NOTA FONDAMENTALE PRIMA DI TUTTO IL RESTO

La fonte OWASP stessa dice chiaramente: "alcuni test associati possono
essere automatizzati, altri richiedono intervento manuale per la natura
sfumata della privacy. Per esempio, se un'app raccoglie dati che non ha
menzionato nello store o nella privacy policy, serve un controllo manuale
attento per individuarlo."

**Implicazione pratica**: questa e la categoria PIU DEBOLE delle 8 per
l'automazione statica pura sul solo codice APK, perche il problema
centrale (raccolta dati non dichiarata) richiede un CONFRONTO con un
documento esterno (privacy policy/store listing) che il codice da solo
non contiene. Quello che POSSIAMO fare staticamente e identificare COSA
viene raccolto/inviato, non se e dichiarato correttamente altrove -
quella correlazione resta un controllo manuale.

## Pattern rilevabili staticamente

### 1. Richiesta permessi eccessivi rispetto alla funzione dichiarata
- **Rilevabile staticamente**: SI (il pattern di permessi e gia visibile
  nel nostro `manifest_misconfig.py`, manca la VALUTAZIONE di
  proporzionalita)
- **Pattern**: presenza di permessi sensibili (`ACCESS_FINE_LOCATION`,
  `READ_CONTACTS`, `RECORD_AUDIO`, `CAMERA`) la cui necessita non e
  evidente dalla categoria dichiarata dell'app - esempio dalla fonte
  OWASP: form che richiede SSN quando il campo era opzionale, mai
  comunicato come tale all'utente
- **Tool**: oggi abbiamo SOLO l'elenco permessi (gia in `metadata.json`),
  NON abbiamo un modo automatico di giudicare "proporzionalita" - questo
  richiede correlazione con la categoria/descrizione dell'app, che e
  FUORI dal codice APK stesso (serve leggere la store listing)
- **Stato implementazione**: PARZIALE (dati gia estratti, manca
  qualsiasi logica di valutazione - e l'unico controllo di questa
  categoria che richiederebbe dati ESTERNI all'APK, es. scraping della
  pagina Play Store, per essere completo)

### 2. Identificatori di tracking persistenti raccolti senza disclosure
- **Rilevabile staticamente**: SI (identificare l'USO e facile, la
  DISCLOSURE richiede il confronto manuale di cui sopra)
- **Pattern**: uso di `Settings.Secure.ANDROID_ID`,
  `TelephonyManager.getDeviceId()` (IMEI, deprecato/restrittivo dalle
  API moderne ma ancora presente in codice legacy),
  `AdvertisingIdClient` per Advertising ID, raccolti e inviati a
  endpoint di rete/analytics/SDK terzi
- **Tool**: Semgrep per identificare le chiamate; Joern per il data-flow
  (identificatore raccolto -> endpoint di rete) - questo e ESATTAMENTE
  il pattern generale che abbiamo gia in mente da MASVS-STORAGE #6
  (data-flow da fonte sensibile a sink esterno), applicato qui a
  identificatori di tracking invece che a password/token
- **Stato implementazione**: NON implementato, ma riusa direttamente
  l'infrastruttura di data-flow gia pianificata altrove - buon
  candidato per implementazione congiunta con MASVS-STORAGE #6

### 3. SDK di terze parti noti per raccolta dati aggressiva
- **Rilevabile staticamente**: SI (parziale - identificare la PRESENZA
  dell'SDK e facile, giudicare se la raccolta e "aggressiva" o
  "dichiarata" richiede conoscenza esterna sull'SDK stesso)
- **Pattern**: identificazione di package noti di SDK
  advertising/analytics/tracking (es. `com.facebook.ads`,
  `com.google.android.gms.ads`, vari SDK di attribution/fingerprinting)
  - stesso meccanismo di identificazione package usato per il gap
  "librerie terze con CVE" di MASVS-CODE #5
- **Tool**: stesso modulo leggero proposto in MASVS-CODE #5
  (identificazione package+versione delle dipendenze), con in aggiunta
  una lista di riferimento di SDK noti per categoria privacy (separata
  dalla lista CVE)
- **Stato implementazione**: NON implementato - STESSO GAP STRUTTURALE
  di MASVS-CODE #5 (libreria terze filtrate dal CPG principale), si
  risolve insieme con lo stesso modulo

### 4. Permessi file con accesso non correttamente isolato (multi-utente)
- **Rilevabile staticamente**: PARZIALE - citato dalla fonte OWASP
  stessa nella sezione storage, ma rilevante anche qui: solo l'utente/
  gruppo dell'app dovrebbe avere permessi rwx sui file in
  `/data/data/<package>`, altri utenti non dovrebbero avere accesso
- **Nota**: questo e principalmente verificabile RUNTIME (ispezione
  permessi filesystem reali su device), non staticamente dal solo APK
- **Tool**: nessuno applicabile staticamente in modo significativo
- **Stato implementazione**: NON implementabile staticamente, fuori
  scope per la pipeline attuale

### 5. Dati condivisi con terze parti senza meccanismo di consenso visibile
- **Rilevabile staticamente**: PARZIALE - possiamo rilevare il
  data-flow tecnico (dato X arriva a endpoint/SDK Y), ma "esiste un
  meccanismo di consenso prima" e una domanda sul FLUSSO UI/UX
  dell'app, difficile da dedurre dal solo grafo di chiamate senza
  comprensione semantica della sequenza di schermate
- **Tool**: Joern puo dirci CHE il dato arriva alla terza parte; non
  puo dirci se prima e stato mostrato un dialog di consenso - quello
  richiederebbe analisi del layout/flow delle Activity, molto piu
  costoso e fuori scope oggi
- **Stato implementazione**: NON implementabile in modo affidabile con
  la pipeline attuale, priorita bassa

## Debolezze NON rilevabili staticamente (richiedono confronto esterno o test dinamico)
- Correlazione tra dati raccolti (rilevabili nel codice) e quanto dichiarato nella privacy policy/store listing - richiede lettura di documenti ESTERNI all'APK, processo fondamentalmente diverso da tutto il resto della pipeline
- Verifica reale a runtime di QUALI dati vengono effettivamente trasmessi durante l'uso reale (il codice mostra cosa l'app PUO fare, non cosa fa sempre)
- Presenza/correttezza di dialog di consenso utente nel flusso UI reale

## NOTA FINALE - riepilogo gap strutturali emersi durante la mappatura (sessione 2)

Durante la costruzione di questa libreria sono emersi 3 gap strutturali
ricorrenti, che vanno affrontati come moduli a se stanti prima di
procedere all'implementazione dei singoli pattern:

1. **Le librerie terze sono oggi invisibili alla pipeline** (filtrate
   per performance Joern) - serve un modulo leggero separato per
   identificazione package+versione, usato sia per CVE (MASVS-CODE #5)
   che per SDK privacy-invasivi (MASVS-PRIVACY #3)

2. **Tutto cio che richiede correlazione con risorse ESTERNE all'APK**
   (privacy policy, store listing, configurazione server-side) e
   strutturalmente fuori scope per un'analisi puramente statica del
   file APK - va sempre segnalato esplicitamente come limite, non
   nascosto o ignorato

3. **Il pattern "data-flow da fonte sensibile a sink esterno"**
   (identificato per la prima volta su SharedPreferences in
   MASVS-STORAGE #6) si ripete identico in MASVS-PRIVACY #2 - vale la
   pena implementare la struttura Joern in modo GENERICO (lista
   configurabile di "fonti sensibili" e "sink esterni"), non come
   funzione singola per ogni categoria
