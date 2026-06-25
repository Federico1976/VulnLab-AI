#!/usr/bin/env python3
"""
reasoning_agent.py
===================
Layer C - Reasoning Agent

Collega Extractor + Knowledge Base + Claude API nel ciclo completo.

Flusso:
  1. Prende i dati di un componente Android (da manifest.json/components/*.json)
  2. Costruisce una query testuale a partire dai suoi attributi
  3. Interroga la Knowledge Base (Qdrant) per pattern simili
  4. Costruisce un prompt strutturato per Claude
  5. (solo se --dry-run NON è passato) Chiama l'API Claude e mostra la risposta

Uso:
    # Modalità test, senza API key, mostra solo il prompt costruito
    python3 reasoning_agent.py --component-file esempio_componente.json --dry-run

    # Modalità reale (richiede ANTHROPIC_API_KEY impostata)
    python3 reasoning_agent.py --component-file esempio_componente.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "knowledge_base"))
from knowledge_base import search  # riusa la KB già costruita


# ---------------------------------------------------------------------------
# Step 1: costruzione della query a partire dal componente
# ---------------------------------------------------------------------------

def build_query_from_component(component: dict) -> str:
    """Trasforma i dati strutturati di un componente Android in una
    descrizione testuale, pensata per il retrieval semantico nella KB.
    Questa è la parte più delicata: la qualità della query determina
    la qualità dei pattern recuperati (principio dei paper: il retriever
    conta più del modello)."""

    parts = []
    name = component.get("name", "unknown")
    exported = component.get("exported")
    permission = component.get("permission")
    intent_filters = component.get("intent_filters", [])
    raw = component.get("raw_attribs", {})

    parts.append(f"Android component {name}")

    if exported is True:
        parts.append("exported component, reachable by other apps on the device")
    elif exported is False:
        parts.append("internal component, explicitly not exported (android:exported=false declared)")
    else:
        parts.append("UNDETERMINED export status: no android:exported attribute declared and no "
                      "intent-filter present; whether this component is reachable from other apps "
                      "depends on the app's target SDK version (implicit-export rules changed across "
                      "Android API levels) and cannot be decided from the manifest alone")

    if permission:
        parts.append(f"protected by permission {permission}")
    else:
        parts.append("no permission check declared")

    if raw.get("grant_uri_permissions") == "true":
        parts.append("grants URI permissions to callers, potential path traversal surface")

    if raw.get("authorities"):
        parts.append(f"content provider with authorities {raw['authorities']}")

    for intent_filter in intent_filters:
        actions = intent_filter.get("actions", [])
        categories = intent_filter.get("categories", [])
        data = intent_filter.get("data", [])
        if "android.intent.category.BROWSABLE" in categories:
            parts.append("browsable deep link handler, accepts external URIs")
        if data:
            schemes = [d.get("scheme") for d in data if d.get("scheme")]
            if schemes:
                parts.append(f"custom URI scheme(s): {', '.join(schemes)}")
        if actions:
            parts.append(f"responds to actions: {', '.join(actions)}")

    return ". ".join(parts) + "."


# ---------------------------------------------------------------------------
# Step 2: retrieval dalla Knowledge Base
# ---------------------------------------------------------------------------

def retrieve_relevant_patterns(query: str, top_k: int = 6) -> list[dict]:
    """Interroga la KB. Per ora un singolo retrieval; in futuro possiamo
    diversificare le query (principio 'la diversità conta' dal paper
    VulScribeR) per recuperare pattern da angolazioni diverse invece di
    N varianti dello stesso pattern."""
    return search(query, top_k=top_k)


# ---------------------------------------------------------------------------
# Step 3: costruzione del prompt per Claude
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Sei un analista di sicurezza esperto in Android application security, \
specializzato nell'identificare vulnerability pattern (non singole funzioni o righe di codice) \
in componenti APK. Ricevi un componente Android e una lista di pattern di vulnerabilità noti, \
recuperati da una knowledge base di disclosure reali e bug bounty report.

Il tuo compito:
1. Valuta se il componente analizzato corrisponde a uno o più dei pattern recuperati
2. Sii esplicito sul livello di confidenza (alto/medio/basso) e sul perché
3. Se nessun pattern recuperato è rilevante, dillo chiaramente — non forzare una corrispondenza
4. Distingui sempre un'ipotesi da una conferma: questa è analisi statica preliminare, non una \
prova di exploitability
5. Se i dati del componente sono insufficienti per una valutazione, dillo esplicitamente e \
indica quali informazioni aggiuntive servirebbero (es. codice decompilato del metodo chiamato)
6. ATTENZIONE AI FATTORI MITIGANTI: i pattern recuperati dalla knowledge base descrivono rischi \
generici per categoria di componente, ma il retrieval semantico NON valuta da solo se il \
componente specifico ha protezioni che neutralizzano il rischio. Devi farlo tu, leggendo i dati \
del componente:
   - Se exported=false e non ci sono intent-filter, il componente non è raggiungibile da altre \
app: la superficie d'attacco esterna è verosimilmente assente, anche se i pattern recuperati \
parlano di componenti exported in generale
   - Se è presente una permission esplicita (specialmente system-level o signature-level), il \
rischio di accesso da app malevole è fortemente ridotto rispetto a un componente identico ma \
senza permission
   - Non trattare "score di similarità alto" come "rischio alto": un pattern può essere recuperato \
perché topicamente simile (es. parla di componenti Android in generale) senza che il componente \
specifico condivida la condizione di rischio reale (es. assenza di permission)
"""


def build_prompt(component: dict, query: str, retrieved_patterns: list[dict]) -> dict:
    patterns_text = "\n\n".join(
        f"[Pattern {i+1}] (score={p['score']}, source={p['source']}, category={p['category']})\n{p['text']}"
        for i, p in enumerate(retrieved_patterns)
    )

    user_message = f"""## Componente Android analizzato

```json
{json.dumps(component, indent=2)}
```

## Query di retrieval usata

{query}

## Pattern recuperati dalla Knowledge Base (i {len(retrieved_patterns)} più simili)

{patterns_text}

## Richiesta

Analizza il componente sopra rispetto ai pattern recuperati. Indica se rappresenta un rischio \
plausibile, quale pattern specifico richiama, il livello di confidenza, e cosa servirebbe per \
validare l'ipotesi (es. tracciare dove vanno gli extra dell'Intent nel codice decompilato).
"""

    return {
        "system": SYSTEM_PROMPT,
        "user_message": user_message,
    }


# ---------------------------------------------------------------------------
# Step 4: chiamata API (solo se non dry-run)
# ---------------------------------------------------------------------------

def call_claude_api(prompt: dict, model: str = "claude-haiku-4-5-20251001") -> str:
    """Chiama l'API Claude. Importa il SDK solo qui, così la modalità
    dry-run funziona anche senza il pacchetto 'anthropic' installato."""
    import anthropic

    client = anthropic.Anthropic()  # legge ANTHROPIC_API_KEY dall'ambiente
    response = client.messages.create(
        model=model,
        max_tokens=1500,
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user_message"]}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Reasoning Agent - Extractor + KB + Claude")
    parser.add_argument("--component-file", required=True, type=Path,
                         help="Path a un file JSON con i dati di un componente Android")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true",
                         help="Costruisce ed esegue tutto tranne la chiamata API: mostra il prompt risultante")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001",
                         help="Modello da usare (default: Haiku 4.5, economico per i test)")
    args = parser.parse_args()

    if not args.component_file.exists():
        print(f"[!] File non trovato: {args.component_file}", file=sys.stderr)
        sys.exit(1)

    component = json.loads(args.component_file.read_text())

    print("=" * 70)
    print("STEP 1 — Query costruita dal componente")
    print("=" * 70)
    query = build_query_from_component(component)
    print(query)

    print("\n" + "=" * 70)
    print(f"STEP 2 — Top {args.top_k} pattern recuperati dalla Knowledge Base")
    print("=" * 70)
    retrieved = retrieve_relevant_patterns(query, top_k=args.top_k)
    if not retrieved:
        print("[!] Nessun pattern recuperato. Verifica che Qdrant sia attivo e popolato.")
        sys.exit(1)
    for i, p in enumerate(retrieved, 1):
        print(f"\n[{i}] score={p['score']}  source={p['source']}  category={p['category']}")
        print(f"    {p['text'][:200]}{'...' if len(p['text']) > 200 else ''}")

    print("\n" + "=" * 70)
    print("STEP 3 — Prompt completo costruito per Claude")
    print("=" * 70)
    prompt = build_prompt(component, query, retrieved)
    print("\n--- SYSTEM PROMPT ---")
    print(prompt["system"])
    print("\n--- USER MESSAGE ---")
    print(prompt["user_message"])

    if args.dry_run:
        print("\n" + "=" * 70)
        print("[DRY-RUN] Nessuna chiamata API eseguita. Il prompt sopra è quello")
        print("che verrebbe effettivamente inviato a Claude in modalità reale.")
        print("=" * 70)
        return

    print("\n" + "=" * 70)
    print(f"STEP 4 — Chiamata API Claude (modello: {args.model})")
    print("=" * 70)
    try:
        result = call_claude_api(prompt, model=args.model)
        print("\n--- RISPOSTA DI CLAUDE ---")
        print(result)
    except ImportError:
        print("[!] Il pacchetto 'anthropic' non è installato. Esegui:")
        print("    pip install anthropic --break-system-packages")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Errore nella chiamata API: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
