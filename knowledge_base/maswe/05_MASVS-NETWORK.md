# MASVS-NETWORK — Comunicazioni di rete

Fonte: OWASP MASTG 0x05g-Testing-Network-Communication, MASTG-TEST-0019,
MASTG-TEST-0022, MASTG-TEST-0244, MASTG-KNOW-0015
Verificato: 23/06/2026 (sessione 2)

## Pattern rilevabili staticamente

### 1. TrustManager permissivo ("accetta tutti i certificati")
- **Rilevabile staticamente**: SI - il pattern di vulnerabilita mobile
  piu documentato e ricercato al mondo, presente in praticamente ogni
  scanner Android esistente
- **Pattern**: implementazione custom di `X509TrustManager` dove
  `checkClientTrusted`, `checkServerTrusted` hanno corpo vuoto (no-op,
  nessuna eccezione lanciata) e `getAcceptedIssuers()` ritorna array vuoto
- **Codice vulnerabile di riferimento** (OWASP, pattern noto come
  "TrustManager permissivo" - usato spesso "solo in development" ma
  rimasto in produzione):
```java
  TrustManager[] trustAllCerts = new TrustManager[] {
      new X509TrustManager() {
          public void checkClientTrusted(X509Certificate[] chain, String authType) {}
          public void checkServerTrusted(X509Certificate[] chain, String authType) {}
          public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[]{}; }
      }
  };
```
- **Tool**: Semgrep - questo e un pattern GIA' coperto da molte regole
  community esistenti (`trust-manager-accepts-any-certificate` o simile)
  - verificare disponibilita nelle regole `p/java` gia testate
- **Stato implementazione**: NON implementato (ma probabilmente GIA'
  disponibile come regola Semgrep community pronta all'uso - verificare
  prima di scriverne una custom)

### 2. HostnameVerifier permissivo
- **Rilevabile staticamente**: SI
- **Pattern**: implementazione custom di `HostnameVerifier` con
  `verify()` che ritorna sempre `true`, o uso di
  `ALLOW_ALL_HOSTNAME_VERIFIER` (deprecato ma ancora presente in codice
  legacy)
- **Tool**: Semgrep
- **Stato implementazione**: NON implementato

### 3. Cleartext HTTP traffic abilitato esplicitamente
- **Rilevabile staticamente**: SI (banale, manifest/XML check)
- **Pattern**: `android:usesCleartextTraffic="true"` nel manifest, OPPURE
  `<domain-config cleartextTrafficPermitted="true">` nel file
  `network_security_config.xml`
- **Nota**: da Android 9 (API 28) il default e bloccare cleartext, quindi
  la PRESENZA esplicita di questo flag e un segnale forte di
  intenzionalita (qualcuno l'ha abilitato deliberatamente)
- **Tool**: manifest_misconfig.py - nuovo check XML diretto, banale da
  aggiungere; serve anche leggere il file XML referenziato da
  `android:networkSecurityConfig` se presente
- **Stato implementazione**: NON implementato (ma e il piu facile e
  rapido da aggiungere di tutta questa categoria - priorita immediata)

### 4. Uso di HTTP invece di HTTPS negli URL hardcoded
- **Rilevabile staticamente**: SI - GIA' VALIDATO concettualmente in
  sessione 1 (avevamo cercato URL hardcoded nel bundle JS di Tesla)
- **Pattern**: stringhe literal `"http://..."` (non `https://`) usate
  come endpoint di rete reali (non placeholder/commenti/namespace XML)
- **Tool**: grep/Semgrep su pattern URL, con filtro per escludere falsi
  positivi comuni (namespace XML `http://schemas.android.com/...`,
  `http://www.w3.org/...` - questi NON sono endpoint di rete)
- **Stato implementazione**: PARZIALE (avevamo fatto grep manuale ieri,
  manca la generalizzazione + filtro namespace nella pipeline)

### 5. Certificate pinning assente o con pin scaduti
- **Rilevabile staticamente**: SI (parziale)
- **Pattern**: assenza di `<pin-set>` nel Network Security Config per
  domini che gestiscono dati sensibili, OPPURE presenza di `<pin-set>`
  con attributo `expiration` nel passato
- **Tool**: parsing del file `network_security_config.xml` (se presente)
  - controllo data di scadenza diretto
- **Stato implementazione**: NON implementato, priorita media (utile ma
  meno critico del TrustManager permissivo, che e un bypass totale
  mentre questo e "solo" assenza di una difesa aggiuntiva)

### 6. SSLSocket senza verifica hostname esplicita
- **Rilevabile staticamente**: SI
- **Pattern**: uso di `SSLSocket` a basso livello SENZA chiamata
  successiva a verifica hostname (`getDefaultHostnameVerifier().verify()`)
  - la fonte OWASP nota esplicitamente che `SSLSocket` NON verifica
  l'hostname di default, a differenza di `HttpsURLConnection`
- **Tool**: Semgrep (pattern: uso `SSLSocket` senza verifica hostname nel
  medesimo metodo/classe)
- **Stato implementazione**: NON implementato, priorita media

### 7. targetSdkVersion < 24 (Network Security Config non enforced)
- **Rilevabile staticamente**: SI (banale, manifest check, GIA' presente
  in parte nella nostra pipeline)
- **Pattern**: `targetSdkVersion < 24` - versioni precedenti permettono
  installazione di CA custom dall'utente che vengono automaticamente
  fidate, aumentando il rischio di MITM tramite CA malevola installata
  dall'utente/attaccante con accesso fisico
- **Tool**: manifest check (il campo esiste gia nel nostro
  `metadata.json`, va solo aggiunta la soglia di valutazione)
- **Stato implementazione**: PARZIALE (il dato e gia estratto, manca la
  valutazione di rischio esplicita)

## Debolezze NON rilevabili staticamente (richiedono test dinamico)
- Verifica reale che il certificate pinning funzioni a runtime contro un attacco MITM attivo (la fonte OWASP stessa, MASTG-TEST-0244, dice esplicitamente che questo richiede intercettazione di rete attiva - l'analisi statica puo solo essere fuorviata da implementazioni offuscate/dynamic loading)
- Verifica se, nonostante configurazione corretta nel manifest/NSC, l'app stia effettivamente usando API a basso livello che bypassano la configurazione (richiede traffic capture reale)
