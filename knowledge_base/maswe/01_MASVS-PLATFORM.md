# MASVS-PLATFORM — Interazione con la piattaforma Android

Fonte: OWASP MASTG 0x05h-Testing-Platform-Interaction, 0x05a-Platform-Overview
Verificato: 22/06/2026

## Pattern rilevabili staticamente

### 1. WebView + addJavascriptInterface non sicuro
- **Rilevabile staticamente**: SI
- **Pattern**: `webView.addJavascriptInterface(obj, name)` dove la classe di `obj`
  ha metodi pubblici senza annotazione `@JavascriptInterface` (vulnerabile su
  targetSdk < 17, RCE via riflessione)
- **Codice vulnerabile di riferimento**:
```java
  webView.addJavascriptInterface(new JSInterface(), "Android");
  // class JSInterface { public String getSecret() { ... } } // manca @JavascriptInterface
```
- **Tool**: Semgrep (regola custom da scrivere) + verifica manuale targetSdk nel manifest
- **Stato implementazione**: NON implementato

### 2. WebView con resource access pericoloso
- **Rilevabile staticamente**: SI
- **Pattern**: `setAllowFileAccess(true)`, `setAllowContentAccess(true)`,
  `loadUrl("file://" + variabile_dinamica)`
- **Tool**: Semgrep
- **Stato implementazione**: NON implementato

### 3. Content Provider con SQL injection
- **Rilevabile staticamente**: SI (parziale — serve correlare manifest + codice)
- **Pattern**: `<provider exported="true">` nel manifest, query nel provider
  costruite con concatenazione di stringhe passate a `rawQuery`/`execSQL`
  invece di parametri bind (`?`)
- **Codice vulnerabile di riferimento** (da OWASP):
```xml
  <provider android:name=".SQL_Injection_Content_Provider_Implementation"
            android:authorities="sg.vp.owasp_mobile.provider.College"
            android:exported="true" />
```
- **Tool**: manifest_misconfig.py (già abbiamo l'exported check) + Joern
  per il data-flow URI→rawQuery dentro il Provider
- **Stato implementazione**: PARZIALE (solo controllo exported, manca data-flow SQL)

### 4. Fragment Injection (CVE storica, targetSdk < 19)
- **Rilevabile staticamente**: SI
- **Pattern**: Activity che estende `PreferenceActivity` o pattern simile
  senza override di `isValidFragment()`, combinato con
  `targetSdkVersion < 19` nel manifest
- **Tool**: manifest check (targetSdk) + Semgrep (ricerca classe/metodo)
- **Stato implementazione**: NON implementato (nota: rilevanza bassa oggi,
  targetSdk < 19 è raro su app moderne, ma va comunque controllato)

### 5. Intent/Deep link non validato prima di azione sensibile
- **Rilevabile staticamente**: SI (già validato in sessione 1 su Tesla)
- **Pattern**: `getIntent().getData()` / `getIntent().getStringExtra()` il cui
  valore raggiunge un sink sensibile (avvio Activity, comando WebView,
  azione su account/pagamento) senza controllo di host/scheme/whitelist
- **Tool**: Joern (data-flow source→sink, già implementato come funzione generale,
  manca l'estensione "azione sensibile" come categoria di sink dedicata)
- **Stato implementazione**: PARZIALE (data-flow generico c'è, manca
  classificazione "sink sensibile per deep link" specifica)

### 6. Broadcast non protetto con dati sensibili
- **Rilevabile staticamente**: SI
- **Pattern**: `sendBroadcast(intent)` senza `android:permission` dichiarato
  E l'intent contiene `putExtra` con dati che sembrano sensibili (token,
  password, dati personali — riconoscibili da nome variabile/chiave)
- **Tool**: Joern (abbiamo già `sendBroadcast` come sink — manca l'euristica
  sul contenuto sensibile degli extra)
- **Stato implementazione**: PARZIALE (sink rilevato, manca classificazione contenuto)

## Debolezze NON rilevabili staticamente (richiedono test dinamico, fuori scope pipeline attuale)
- Local File Inclusion via WebView con parametro dinamico realmente exploitabile (serve runtime per confermare il path traversal reale)
- Universal/App Links non verificati (richiede verifica server-side del file assetlinks.json, non solo codice client)
