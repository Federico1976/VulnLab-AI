# MASVS-AUTH — Autenticazione e autorizzazione

Fonte: OWASP MASTG 0x05f-Testing-Local-Authentication, MASTG-KNOW-0001
(Biometric Authentication)
Verificato: 23/06/2026 (sessione 2)

## Pattern rilevabili staticamente

### 1. Autenticazione biometrica "boolean-only" (bypassabile)
- **Rilevabile staticamente**: SI - pattern centrale di questa categoria,
  citato esplicitamente dalla fonte OWASP come la debolezza piu comune
- **Pattern**: uso di `BiometricPrompt`/`FingerprintManager` dove il
  risultato dell'autenticazione e usato SOLO come booleano per decidere
  un ramo `if/else` (es. "sblocca schermata"), SENZA che la riuscita
  dell'autenticazione sia legata alla decifratura di una chiave reale
  nell'AndroidKeyStore (pattern CryptoObject)
- **Codice vulnerabile (pattern concettuale dalla fonte OWASP)**:
```java
  // VULNERABILE: solo boolean, nessun dato ritornato
  biometricPrompt.authenticate(promptInfo);
  // onAuthenticationSucceeded() richiamato -> if (success) sblocca_funzione()
  // Un attaccante con accesso al binario/hook puo forzare il branch
  // "success" senza presentare alcuna biometria reale
```
- **Codice corretto (pattern dalla fonte OWASP)**:
```java
  // SICURO: la chiave reale e protetta da AndroidKeyStore, si sblocca
  // SOLO se la biometria e valida, perche il CryptoObject e legato
  // a una chiave con setUserAuthenticationRequired(true)
  biometricPrompt.authenticate(promptInfo, cryptoObject);
```
- **Tool**: Semgrep - pattern: classe usa `BiometricPrompt.authenticate()`
  CON un solo argomento (PromptInfo) invece di due argomenti
  (PromptInfo + CryptoObject) -> segnala come probabile bypass-bile
- **Stato implementazione**: NON implementato - PRIORITARIO, pattern
  preciso, alto valore (bypass completo di un controllo di sicurezza),
  basso rischio di falsi positivi (la firma del metodo e inequivocabile)

### 2. FingerprintManager deprecato ancora in uso
- **Rilevabile staticamente**: SI (banale)
- **Pattern**: import/uso di `android.hardware.fingerprint.FingerprintManager`
  (deprecato da API 28) invece di `BiometricPrompt`/`BiometricManager`
- **Nota**: non e una vulnerabilita di per se, ma un segnale di codice
  legacy che spesso accompagna pattern #1 (boolean-only) perche le API
  piu vecchie incoraggiavano quel design
- **Tool**: Semgrep (import check semplice)
- **Stato implementazione**: NON implementato, priorita bassa (segnale
  di contesto, non vulnerabilita diretta)

### 3. Confirm Credentials usato per dati ad alta sensibilita (L2)
- **Rilevabile staticamente**: SI (parziale - serve correlare con
  classificazione del dato protetto, che e contestuale)
- **Pattern**: uso del flow "Confirm Credentials" (basato sul lock screen
  dell'utente, es. `KeyguardManager.createConfirmDeviceCredentialIntent`)
  per proteggere funzionalita che richiederebbero L2 (es. pagamenti,
  dati finanziari) - la fonte OWASP dice esplicitamente "non
  raccomandato per controlli di sicurezza L2" perche la sicurezza e
  forte solo quanto il lock screen (spesso pattern banali)
- **Tool**: Semgrep per il pattern di chiamata + revisione manuale del
  contesto (cosa viene protetto) - qui l'automazione puo solo segnalare
  "presente", la gravita reale richiede giudizio umano sul contesto
- **Stato implementazione**: NON implementato, priorita media

### 4. setUserAuthenticationValidityDurationSeconds troppo permissivo
- **Rilevabile staticamente**: SI
- **Pattern**: chiave KeyStore con `setUserAuthenticationValidityDurationSeconds(N)`
  con N grande (es. minuti/ore) invece di `-1` (richiede biometria ad
  ogni operazione) per dati sensibili - finestra temporale ampia in cui
  un dispositivo sbloccato permette operazioni sensibili senza nuova
  autenticazione
- **Tool**: Semgrep (pattern sul valore numerico passato)
- **Stato implementazione**: NON implementato, priorita media

### 5. setInvalidatedByBiometricEnrollment non impostato
- **Rilevabile staticamente**: SI
- **Pattern**: chiave KeyStore creata senza
  `setInvalidatedByBiometricEnrollment(true)` - se un attaccante con
  accesso fisico al device aggiunge una propria impronta digitale al
  device (su device non protetti adeguatamente), la chiave resta valida
  anche per la nuova impronta non autorizzata dall'utente originale
- **Tool**: Semgrep
- **Stato implementazione**: NON implementato, priorita media

## Debolezze NON rilevabili staticamente (richiedono test dinamico)
- Verifica reale che il bypass del pattern #1 funzioni effettivamente (richiede hook runtime con Frida per forzare il branch "success")
- Robustezza reale del lock screen dell'utente nel pattern #3 (dipende dalla configurazione del device specifico, non dal codice app)
- Test di sessione: scadenza token, revoca su logout, gestione multi-dispositivo - questi pattern riguardano tipicamente l'AUTH lato server/API, fuori scope per analisi statica del solo client APK
