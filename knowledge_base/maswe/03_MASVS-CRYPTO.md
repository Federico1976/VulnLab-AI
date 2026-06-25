# MASVS-CRYPTO — Crittografia

Fonte: OWASP MASTG 0x04g-Testing-Cryptography, 0x05e-Testing-Cryptography,
MASTG-TEST-0016 (Random Number Generation), MASTG-KNOW-0012 (Key Generation)
Verificato: 23/06/2026 (sessione 2)

## Pattern rilevabili staticamente

### 1. Hash algoritmi deboli (MD4, MD5, SHA1, DES)
- **Rilevabile staticamente**: SI — GIA' VALIDATO in sessione 1 (Semgrep,
  caso Tesla BLEService.java)
- **Pattern**: `MessageDigest.getInstance("MD5")`, `getInstance("SHA-1")`,
  `Cipher.getInstance("DES")`
- **Nota IMPORTANTE da sessione 1**: questo pattern produce MOLTI falsi
  positivi quando l'hash debole e usato per scopi non crittografici
  (ID derivati, checksum non adversariali, cache key). Il filtro
  `semgrep_filter.py` gia costruito controlla il contesto circostante
  per la frase "VIN identifier" / "checksum" / "cache key" - va estesa
  l'euristica per altri contesti non-crypto comuni
- **Tool**: Semgrep (regola community `use-of-sha1`/`use-of-md5` GIA'
  disponibile e testata) + filtro contesto custom (GIA' implementato,
  da rifinire)
- **Stato implementazione**: IMPLEMENTATO (sessione 1) - da rifinire

### 2. Modalita ECB (Electronic Codebook)
- **Rilevabile staticamente**: SI (pattern sintattico semplice)
- **Pattern**: `Cipher.getInstance("AES/ECB/...")` o equivalente con
  modalita ECB esplicita o implicita (default Java per "AES" senza
  specificare modalita e spesso ECB su alcune implementazioni - da
  verificare caso per caso)
- **Impatto**: blocchi identici di plaintext producono blocchi identici
  di ciphertext - pattern nei dati riconoscibili, possibile replay
- **Tool**: Semgrep (pattern diretto sulla stringa "ECB" nell'algoritmo)
- **Stato implementazione**: NON implementato (ma banale da aggiungere,
  stessa famiglia delle regole SHA1 gia in uso)

### 3. java.util.Random per scopi crittografici
- **Rilevabile staticamente**: SI
- **Pattern**: uso di `new Random()` (invece di `SecureRandom`) per
  generare: token di sessione, chiavi, salt, nonce, ID di reset password
- **Impatto**: PRNG predicibile - un attaccante puo indovinare il
  prossimo valore generato e impersonare un altro utente o accedere a
  dati sensibili (testuale dalla fonte OWASP)
- **Tool**: Semgrep (cerca `new Random()` + verifica se il risultato
  alimenta un contesto sensibile come token/key/password-reset, tramite
  Joern per il data-flow se serve maggiore precisione)
- **Stato implementazione**: NON implementato - PRIORITARIO, pattern
  preciso e a basso rischio di falsi positivi (a differenza di SHA1)

### 4. Chiavi di cifratura hardcoded
- **Rilevabile staticamente**: SI - gia documentato anche in
  MASVS-STORAGE #3 (sovrapposizione intenzionale tra categorie)
- **Pattern**: stringa literal passata direttamente come chiave/password
  a `Cipher.init()`, `SecretKeySpec(byte[], ...)`, `getWritableDatabase(String)`
- **Tool**: Semgrep + grep su pattern `SecretKeySpec\(.*"` con stringa literal
- **Stato implementazione**: NON implementato

### 5. IV (Initialization Vector) statico o riutilizzato
- **Rilevabile staticamente**: SI (parziale - serve distinguere IV
  costante/hardcoded da IV generato correttamente ma riutilizzato a
  runtime, quest'ultimo richiede data-flow piu complesso)
- **Pattern**: `IvParameterSpec` costruito da un array di byte costante/
  hardcoded nel codice (es. tutti zero, o stringa fissa), invece di
  generato con `SecureRandom` ogni volta
- **Tool**: Semgrep per il caso hardcoded semplice; Joern per il caso
  "stesso IV variable riusato in chiamate multiple" (piu complesso, da
  valutare se vale il costo di implementazione)
- **Stato implementazione**: NON implementato (priorita media - il caso
  hardcoded semplice e facile, il caso riuso runtime e costoso)

### 6. Padding oracle (messaggi di errore differenziati)
- **Rilevabile staticamente**: PARZIALE - il pattern di codice e
  rilevabile (cattura distinta di `BadPaddingException` vs altre
  eccezioni con messaggi diversi all'utente/log), ma la verifica reale
  dell'exploitability richiede test attivo (mandare ciphertext malformati
  e osservare differenze di risposta/timing)
- **Pattern**: `catch (BadPaddingException e) { ... messaggio diverso ... }`
  vs `catch (Exception e) { ... messaggio generico ... }` nello stesso
  metodo di decifratura
- **Tool**: Semgrep per individuare il pattern di gestione eccezioni
  differenziata; verifica reale fuori scope statico
- **Stato implementazione**: NON implementato, priorita bassa

### 7. Algoritmi a chiave debole (RSA <2048bit, DH debole)
- **Rilevabile staticamente**: SI
- **Pattern**: `KeyPairGenerator.getInstance("RSA")` + `initialize(N)`
  dove N < 2048 (storicamente 768/1024 rotti o a rischio)
- **Tool**: Semgrep (pattern su valore numerico letterale passato a
  `initialize()`)
- **Stato implementazione**: NON implementato

### 8. Chiavi non protette da Android Keystore (estrazione possibile)
- **Rilevabile staticamente**: PARZIALE - rilevabile "l'app non usa
  AndroidKeyStore" per pattern di assenza, ma la prova "la chiave e
  davvero estraibile da memoria/dump" richiede strumenti dinamici
  (Frida, radare2, citati esplicitamente dalla fonte OWASP)
- **Pattern**: generazione/uso di `SecretKeySpec`/`KeyPairGenerator` SENZA
  passare per `AndroidKeyStore` come provider
- **Tool**: Semgrep (verifica assenza del provider "AndroidKeyStore" nelle
  chiamate crypto del file)
- **Stato implementazione**: NON implementato, priorita media

## Debolezze NON rilevabili staticamente (richiedono test dinamico)
- Estrazione reale di chiavi da memoria/dump (richiede Frida/radare2 e accesso root, esplicitamente citato dalla fonte OWASP come unico modo affidabile)
- Verifica reale di padding oracle exploitability (richiede invio attivo di payload malformati e osservazione risposta/timing)
- Verifica runtime della reale qualita entropica del PRNG in produzione (oltre al pattern di codice, la qualita effettiva del seed richiede osservazione runtime)
