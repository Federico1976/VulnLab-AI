# MASVS-RESILIENCE — Resilienza al reverse engineering e anti-tampering

Fonte: OWASP MASTG 0x05j-Testing-Resiliency-Against-Reverse-Engineering,
MASTG-KNOW-0027 (Root Detection), MASTG-TEST-0045
Verificato: 23/06/2026 (sessione 2)

## NOTA FONDAMENTALE PRIMA DI TUTTO IL RESTO

A differenza delle 7 categorie precedenti, RESILIENCE non protegge da una
vulnerabilita exploitable in senso classico - rende PIU DIFFICILE il
reverse engineering. La fonte OWASP stessa lo dice esplicitamente: "root
detection non e molto efficace di per se" ed e una categoria SEPARATA
dai livelli L1/L2, applicabile solo ad app dove il binario stesso e il
target (DRM, pagamenti, algoritmi proprietari, app dove un bypass
client-side causa danno finanziario diretto).

**Implicazione pratica per i nostri report di bug bounty**: l'ASSENZA di
root detection/anti-tampering NON E QUASI MAI un finding riportabile da
solo. E rilevante principalmente in due casi:
1. Come CONTESTO che spiega perche siamo riusciti ad analizzare l'app
   cosi facilmente (utile per noi, non per il report)
2. Come parte di una catena di vulnerabilita piu ampia, dove l'assenza
   di anti-tampering rende PIU FACILE sfruttare un'altra vulnerabilita
   reale gia trovata in altre categorie

## Pattern rilevabili staticamente (principalmente come CONTESTO, non come finding diretto)

### 1. Assenza di root detection
- **Rilevabile staticamente**: SI (rilevare l'assenza e facile - basta
  NON trovare i pattern tipici sotto)
- **Pattern tipici di root detection presente** (se troviamo questi,
  vuol dire che l'app HA protezioni - utile come dato di contesto):
  - check su file noti: `/system/bin/su`, `/system/xbin/su`, `Superuser.apk`
  - check su package noti: `com.noshufou.android.su`, `eu.chainfire.supersu`
  - check su proprieta build: `ro.build.tags` contenente "test-keys"
  - uso di librerie dedicate: `RootBeer`, SDK RASP commerciali
  - SafetyNet/Play Integrity API: controllo `basicIntegrity`/`ctsProfileMatch`
- **Tool**: Semgrep/grep per rilevare la PRESENZA (non l'assenza, che e
  il default quando non troviamo nulla)
- **Stato implementazione**: NON implementato, priorita bassa (utile
  come metadato di contesto per il report finale, non come vulnerabilita)

### 2. Assenza di anti-debugging
- **Rilevabile staticamente**: SI (stesso principio del #1)
- **Pattern tipici se presenti**: check su `Debug.isDebuggerConnected()`,
  `ApplicationInfo.FLAG_DEBUGGABLE`, timing checks anti-ptrace
- **Tool**: Semgrep
- **Stato implementazione**: NON implementato, priorita bassa

### 3. Detection di ambiente emulato/virtuale
- **Rilevabile staticamente**: SI
- **Pattern tipici se presenti**: controlli su `Build.FINGERPRINT`
  contenente "generic"/"unknown", `Build.MODEL` contenente "sdk"/
  "Emulator"/"Android SDK built for x86", sensori mancanti tipici di
  emulatori
- **Nota pratica per NOI**: se un APK ha questi controlli ATTIVI,
  significa che le nostre future fasi di analisi dinamica
  (sull'emulatore che abbiamo gia configurato sul NUC) potrebbero
  essere bloccate o vedere comportamento alterato dell'app - utile
  saperlo PRIMA di investire tempo nel test dinamico
- **Tool**: Semgrep - questo specifico controllo ha VALORE OPERATIVO
  diretto per noi (decidere se l'emulatore funzionera per quel target),
  non solo per il report
- **Stato implementazione**: NON implementato, ma e l'UNICO controllo
  di questa intera categoria con beneficio operativo diretto per il
  nostro workflow, non solo per il bounty report - priorita media-alta
  per questo motivo specifico

### 4. Mancanza di obfuscation (ProGuard/R8)
- **Rilevabile staticamente**: SI - GIA' DOCUMENTATO in MASVS-CODE #7
  (sovrapposizione intenzionale, la fonte OWASP classifica questo sia
  in CODE che in RESILIENCE secondo la versione del documento)
- **Stato implementazione**: vedi MASVS-CODE #7

### 5. Assenza di anti-tampering/integrity check sul codice stesso
- **Rilevabile staticamente**: PARZIALE - rilevare l'assenza e facile,
  ma verificare se i check PRESENTI sono effettivamente efficaci
  richiede analisi dinamica (provare a bypassarli)
- **Pattern tipici se presenti**: verifica del proprio checksum/firma a
  runtime, confronto hash del proprio APK con valore noto
- **Tool**: Semgrep
- **Stato implementazione**: NON implementato, priorita bassa

## Debolezze NON rilevabili staticamente (richiedono test dinamico)
- Efficacia reale dei controlli trovati (la fonte OWASP stessa nota che bypassare root detection e spesso banale - es. semplice rinomina del binario `su` - quindi anche TROVANDO il controllo staticamente, non sappiamo se e efficace senza testarlo attivamente)
- Rilevamento di hooking/instrumentation Frida a runtime
- Verifica reale se Play Integrity API/SafetyNet sono configurati correttamente lato server (il client puo chiamare l'API correttamente ma il server potrebbe non validare la risposta)
