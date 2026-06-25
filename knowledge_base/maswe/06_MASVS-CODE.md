# MASVS-CODE — Qualita del codice e configurazione build

Fonte: OWASP MASTG 0x05i-Testing-Code-Quality-and-Build-Settings,
MASTG-TEST-0039, MASTG-TEST-0042
Verificato: 23/06/2026 (sessione 2)

## Pattern rilevabili staticamente

### 1. App debuggable in produzione (MSTG-CODE-2)
- **Rilevabile staticamente**: SI - GIA' IMPLEMENTATO nella nostra
  pipeline da sessione 0 (manifest_misconfig.py, check "debuggable_true",
  classificato CRITICAL)
- **Pattern**: `android:debuggable="true"` nel manifest
- **Tool**: manifest_misconfig.py
- **Stato implementazione**: GIA' IMPLEMENTATO

### 2. App firmata con certificato debug/non valido (MSTG-CODE-1)
- **Rilevabile staticamente**: SI (parziale - richiede ispezione del
  certificato di firma dell'APK, non solo del manifest)
- **Pattern**: certificato di firma con CN tipico di debug
  ("Android Debug", "CN=Android Debug,O=Android,C=US") oppure
  certificato auto-firmato con validita anomala
- **Tool**: `apksigner verify --print-certs` o equivalente - NUOVO
  strumento da integrare, non ancora presente nella nostra pipeline
- **Stato implementazione**: NON implementato - richiede aggiunta di
  un controllo nuovo (lettura certificato APK, non solo manifest/codice)

### 3. Debugging symbols presenti in binari nativi (MSTG-CODE-3)
- **Rilevabile staticamente**: SI (per librerie .so incluse nell'APK)
- **Pattern**: presenza di simboli di debug non strippati in file `.so`
  dentro `lib/` - verificabile con `file` o `nm` sui binari nativi
- **Tool**: NUOVO modulo da aggiungere - analisi statica dei binari
  nativi (.so), oggi la pipeline si concentra solo su Java/Kotlin/JS,
  questo e un gap reale per app con componenti NDK/C++
- **Stato implementazione**: NON implementato, priorita bassa (la
  maggior parte delle app bounty non ha logica di sicurezza critica
  in codice nativo, ma va segnalato come gap noto)

### 4. Logging verboso/debug code lasciato in produzione (MSTG-CODE-4)
- **Rilevabile staticamente**: SI - pattern ad alto valore, spesso
  fonte di leak di dati sensibili in log accessibili (logcat)
- **Pattern**: `Log.d()`, `Log.v()`, `System.out.println()` con
  argomenti che sembrano sensibili (token, password, dati utente, URL
  con parametri di autenticazione) - oppure presenza di blocchi di
  codice "mock"/"test" raggiungibili in build di release
- **Tool**: Semgrep (pattern su chiamate Log.* con argomenti sospetti
  per nome variabile) - qui possiamo riusare la stessa euristica sui
  nomi di chiave/variabile che abbiamo gia scritto per
  MASVS-STORAGE #2 (SharedPreferences sensibili)
- **Stato implementazione**: NON implementato - PRIORITARIO, riusa
  euristiche gia progettate, alto valore (log accessibili via adb
  logcat anche senza root su molte versioni Android)

### 5. Librerie terze con CVE note (MSTG-CODE-5)
- **Rilevabile staticamente**: SI - questo e esattamente il problema
  che avevamo intuito dovesse esistere ma non avevamo ancora
  formalizzato: serve un controllo delle DIPENDENZE, non solo del
  codice proprietario
- **Pattern**: identificazione di librerie/SDK terzi presenti nell'APK
  (tramite package name nel CPG/decompilato, es. `com.squareup.okhttp3`,
  `com.google.firebase`) + versione (se determinabile da metadata/risorse)
  + lookup contro database CVE note
- **Tool**: GAP IMPORTANTE - oggi la nostra pipeline FILTRA ESPLICITAMENTE
  le librerie terze (es. il filtro proprietario com/tesla* di sessione 1)
  per motivi di performance Joern. Questo significa che oggi NON
  controlliamo affatto questa categoria. Servirebbe un modulo SEPARATO
  e leggero (no Joern, solo identificazione package + versione + lookup
  OWASP Dependency-Check o NVD) che scansiona ANCHE le librerie che
  scartiamo dal CPG principale
- **Stato implementazione**: NON implementato - GAP STRUTTURALE
  identificato oggi, da pianificare come modulo a se stante

### 6. Gestione eccezioni che esponde informazioni sensibili (MSTG-CODE-6/7)
- **Rilevabile staticamente**: SI (parziale)
- **Pattern**: `catch (Exception e) { ... e.getMessage() mostrato a UI/log ... }`
  oppure stack trace completo esposto all'utente; controlli di
  sicurezza (es. validazione permessi) che in caso di eccezione
  ALLOW invece di DENY by default
- **Tool**: Semgrep per il pattern di esposizione messaggio; Joern per
  il pattern piu sofisticato "fail open" nei controlli di sicurezza
  (richiede identificare manualmente quali metodi sono "controlli di
  sicurezza" - difficile generalizzare, alto tasso di giudizio umano richiesto)
- **Stato implementazione**: NON implementato, priorita media (la parte
  "exception message esposto" e facile, la parte "fail open" e costosa
  da generalizzare)

### 7. Build senza minification/obfuscation (ProGuard/R8 disabilitato)
- **Rilevabile staticamente**: SI - utile come SEGNALE DI CONTESTO,
  non come vulnerabilita diretta
- **Pattern**: codice decompilato con nomi di classe/metodo leggibili
  in chiaro (es. `LoginActivity`, `validatePassword`) invece di nomi
  offuscati a 1-2 caratteri - la PRESENZA di nomi leggibili indica
  `minifyEnabled false` nel build
- **Nota IMPORTANTE**: questo NON e di per se un bug di sicurezza (e
  "free security feature" come dice OWASP, ma la sua assenza non e
  exploitable direttamente) - e utile soprattutto come segnale che
  rende PIU FACILE per noi stessi (e per un attaccante) leggere la
  logica dell'app. Lo registriamo come metadato osservativo, non come
  finding da riportare in un bounty
- **Tool**: osservazione automatica durante l'estrazione (% di classi
  con nomi leggibili vs offuscati) - utile per dare priorita ai target,
  non per generare un finding
- **Stato implementazione**: NON implementato, priorita bassa (utile
  come metadato, non come vulnerabilita)

## Debolezze NON rilevabili staticamente (richiedono test dinamico)
- Verifica reale che logging verboso scriva effettivamente dati sensibili durante l'uso reale dell'app (il pattern di codice e rilevabile, il contenuto effettivo runtime richiede interazione reale + logcat)
- Memory corruption bugs in codice nativo NDK (MSTG-CODE-8) - richiede fuzzing/analisi dinamica specializzata, completamente fuori scope per la pipeline statica attuale
