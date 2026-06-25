# MASWE Pattern Library — Indice di avanzamento

Obiettivo: per ciascuna delle 8 categorie MASVS, documentare le debolezze
rilevabili tramite analisi STATICA (Joern/Semgrep/manifest check), con
pattern di codice concreto e mapping verso lo strumento giusto.

Le debolezze che richiedono SOLO test dinamico/runtime sono annotate ma
NON implementate nella pipeline statica attuale.

## Stato di avanzamento

- [x] MASVS-PLATFORM — completato 22/06/2026 (sessione 1)
- [x] MASVS-STORAGE — completato 23/06/2026 (sessione 2)
- [x] MASVS-CRYPTO — completato 23/06/2026 (sessione 2)
- [x] MASVS-AUTH — completato 23/06/2026 (sessione 2)
- [x] MASVS-NETWORK — completato 23/06/2026 (sessione 2)
- [x] MASVS-CODE — completato 23/06/2026 (sessione 2)
- [x] MASVS-RESILIENCE — completato 23/06/2026 (sessione 2)
- [x] MASVS-PRIVACY — completato 23/06/2026 (sessione 2)

## Convenzione di ciascun file categoria

Ogni file `0X_MASVS-NOME.md` contiene una tabella con colonne:
| MASWE ID (se noto) | Debolezza | Rilevabile staticamente? | Pattern di codice | Tool | Stato implementazione |
