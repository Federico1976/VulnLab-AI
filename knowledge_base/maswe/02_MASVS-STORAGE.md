# MASVS-STORAGE — Storage locale e gestione dati sensibili

Fonte: OWASP MASTG 0x05d-Testing-Data-Storage, MASTG-TEST-0001, MASTG-TEST-0029,
MASTG-Hacking-Playground (InsecureBankv2)
Verificato: 23/06/2026 (sessione 2)

## Pattern rilevabili staticamente

### 1. MODE_WORLD_READABLE / MODE_WORLD_WRITEABLE
- **Rilevabile staticamente**: SI (banale, grep diretto)
- **Pattern**: `getSharedPreferences(name, Context.MODE_WORLD_READABLE)` o
  `MODE_WORLD_WRITEABLE`, anche passati come intero letterale `1`/`2`
  invece della costante (es. `getSharedPreferences("key", 1)`)
- **Nota**: deprecato da API 17, ma il pattern resta rilevante per app con
  minSdk basso o codice legacy non aggiornato
- **Codice vulnerabile di riferimento** (OWASP):
```java
  SharedPreferences sharedPref = getSharedPreferences("key", MODE_WORLD_READABLE);
  SharedPreferences.Editor editor = sharedPref.edit();
  editor.putString("username", "administrator");
  editor.putString("password", "supersecret");
  editor.commit();
```
- **Tool**: Semgrep (pattern semplice) + grep diretto come fallback
- **Stato implementazione**: NON implementato

### 2. SharedPreferences con dati sensibili non incriptati
- **Rilevabile staticamente**: SI (parziale — serve euristica sul nome della chiave)
- **Pattern**: `putString("password", ...)`, `putString("token", ...)`,
  `putString(*"secret"*, ...)`, `putString(*"auth"*, ...)` senza passare
  prima per `EncryptedSharedPreferences`
- **Tool**: Semgrep (regola su nome chiave + verifica import EncryptedSharedPreferences nel file)
- **Stato implementazione**: NON implementato

### 3. Crittografia debole/banale per dati a riposo
- **Rilevabile staticamente**: SI
- **Pattern**: XOR o bit-flipping custom invece di librerie crittografiche
  provate; chiavi di cifratura hardcoded nel codice
  (es. `getWritableDatabase("SuperPassword123")`)
- **Codice vulnerabile di riferimento** (OWASP):
```java
  this.db = localUserSecretStore.getWritableDatabase("SuperPassword123");
```
- **Tool**: Semgrep per il pattern chiave-hardcoded-in-chiamata-DB +
  pattern grep per XOR/bit-shift su array di byte vicino a parole come "encrypt"
- **Stato implementazione**: NON implementato (nota: in parte sovrapposto a
  MASVS-CRYPTO, da categoria 3 — qui ci concentriamo sul *dove* la chiave
  debole tocca lo storage)

### 4. Dati sensibili scritti su External Storage
- **Rilevabile staticamente**: SI
- **Pattern**: `Environment.getExternalStorageDirectory()` o
  `getExternalFilesDir()` usato per scrivere file con nomi/contenuti
  sensibili (es. `password.txt`, file con dati carta di credito)
  combinato con `WRITE_EXTERNAL_STORAGE` nel manifest
- **Codice vulnerabile di riferimento** (OWASP Hacking Playground):
  scrittura di `password.txt` su `/storage/emulated/0/`
- **Tool**: manifest check (permission già presente nel nostro
  `manifest_misconfig.py`) + Joern (data-flow: variabile con nome
  sensibile → `FileOutputStream` su path `getExternalStorageDirectory`)
- **Stato implementazione**: PARZIALE (permission check già presente,
  manca il collegamento data-flow al sink di scrittura file)

### 5. WebView che legge SharedPreferences/file sandbox via file://
- **Rilevabile staticamente**: SI (combinato con pattern #2 della categoria PLATFORM)
- **Pattern**: WebView con `setAllowFileAccessFromFileURLs(true)` (o default
  non disabilitato) + pagina caricata che può fare XHR su
  `file:///data/data/<pkg>/shared_prefs/*.xml`
- **Codice vulnerabile di riferimento** (OWASP, JS lato WebView):
```javascript
  var file = "file:///data/data/sg.vp.owasp_mobile.myfirstbrokenapp/shared_prefs/key.xml";
  var xhr = new XMLHttpRequest();
  xhr.open("GET", file, true);
```
- **Tool**: Semgrep sul lato Java (configurazione WebView) — il lato
  JS/HTML caricato dinamicamente è fuori scope per l'analisi statica
  dell'APK (a meno che l'HTML sia incluso negli assets)
- **Stato implementazione**: NON implementato — dipende da #2 della
  categoria PLATFORM

### 6. Componenti IPC esposti che leakano dati sensibili da SharedPreferences
- **Rilevabile staticamente**: SI — questo è il pattern più ricco trovato,
  combina manifest + data-flow
- **Pattern**: `BroadcastReceiver`/`Service` esportato (manifest) il cui
  `onReceive`/`onHandleIntent` legge da `SharedPreferences` un valore
  sensibile (password, token) e lo invia altrove (SMS, log, broadcast,
  rete) senza controllo del chiamante
- **Caso reale completo** (InsecureBankv2, MASTG-TEST-0029):
  un `BroadcastReceiver` esportato riceve `phonenumber`+`newpass` da
  Intent esterno, legge `superSecurePassword` da SharedPreferences,
  decritta, e invia tutto via SMS in chiaro — chiunque può triggerare
  l'invio della password decrittata di un altro utente
- **Tool**: questo è ESATTAMENTE il pattern generale "deep link/intent →
  sink sensibile" che abbiamo già iniziato a costruire nella categoria
  PLATFORM (#5 e #6) — qui lo specializziamo aggiungendo "SharedPreferences
  read" come ulteriore nodo intermedio nel grafo di data-flow Joern
- **Stato implementazione**: NON implementato, ma è IL CASO PRIORITARIO
  da implementare per primo: unisce manifest_misconfig.py (componente
  esportato) + Joern (data-flow Intent extra → SharedPreferences read →
  sink di invio dati)

### 7. Backup automatico non disabilitato (allowBackup)
- **Rilevabile staticamente**: SI (banale, manifest check)
- **Pattern**: assenza di `android:allowBackup="false"` nel manifest
  (default è `true` da API 23) — permette che fino a 25MB di dati app
  finiscano nel backup cloud Google dell'utente, incluse SharedPreferences
  non escluse esplicitamente
- **Tool**: manifest_misconfig.py — nuovo check da aggiungere, semplicissimo
- **Stato implementazione**: NON implementato (ma è il più facile da
  aggiungere subito: un controllo XML diretto)

### 8. File temporanei/journal SQLite con dati sensibili residui
- **Rilevabile staticamente**: PARZIALE — il pattern di codice è
  rilevabile (uso di SQLite per dati sensibili), ma la verifica reale
  della presenza di file journal/WAL con dati residui richiede ispezione
  runtime del filesystem
- **Tool**: solo segnalazione statica "DB SQLite usato per dati sensibili,
  verificare a runtime se journal mode lascia residui"
- **Stato implementazione**: NON implementato, priorità bassa

## Debolezze NON rilevabili staticamente (richiedono test dinamico)
- Verifica reale che SharedPreferences/DB contengano dati effettivamente sensibili durante l'uso reale dell'app (serve interazione reale + ispezione filesystem)
- Verifica se il backup cloud contiene effettivamente i file sensibili (serve generare un backup reale e ispezionarlo)
- Presenza di file di log con dati sensibili scritti runtime (serve uso reale + logcat)
