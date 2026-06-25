#!/usr/bin/env python3
"""
batch_analyze_manifest.py
===========================
Estensione del Reasoning Agent: analizza TUTTI i componenti di un
manifest.json prodotto dall'Extractor, integrando TRE fonti di contesto:
  1. Manifest (dati strutturali del componente)
  2. Knowledge Base (pattern simili recuperati da Qdrant)
  3. Joern CPG (metodi reali + sink pericolosi verificati nel grafo)

Uso:
    python3 batch_analyze_manifest.py --manifest-file manifest.json --cpg-path cpg.bin --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reasoning_agent import (
    build_query_from_component,
    retrieve_relevant_patterns,
    call_claude_api,
)
from joern_bridge import query_joern, format_joern_context


def select_components_to_analyze(manifest_data: dict) -> list:
    selected = []
    components = manifest_data.get("components", {})
    for comp_type, comp_list in components.items():
        for comp in comp_list:
            exported = comp.get("exported")
            has_intent_filters = len(comp.get("intent_filters", [])) > 0
            if exported is True:
                selected.append((comp_type, comp, "exported"))
            elif exported is None and has_intent_filters:
                selected.append((comp_type, comp, "implicit_exported"))
            elif exported is None and not has_intent_filters:
                selected.append((comp_type, comp, "undetermined"))
    return selected


def summarize_skipped(manifest_data: dict, selected: list) -> dict:
    components = manifest_data.get("components", {})
    total = sum(len(v) for v in components.values())
    return {
        "total_components": total,
        "selected_for_analysis": len(selected),
        "skipped_as_internal": total - len(selected),
    }


def extract_simple_name(component_full_name: str) -> str:
    """com.example.app.SharedThemeReceiver -> SharedThemeReceiver"""
    return component_full_name.rsplit(".", 1)[-1]


def build_full_prompt(component: dict, query: str, retrieved_patterns: list, joern_context: str) -> dict:
    """Prompt che integra le TRE fonti: manifest + KB + Joern."""
    patterns_text = "\n\n".join(
        f"[Pattern {i+1}] (score={p['score']}, source={p['source']}, category={p['category']})\n{p['text']}"
        for i, p in enumerate(retrieved_patterns)
    )

    system_prompt = """Sei un analista di sicurezza esperto in Android application security. \
Ricevi tre fonti di contesto su un componente Android:
1. I dati strutturali del componente (dal manifest)
2. Pattern di vulnerabilità noti, recuperati da una knowledge base di disclosure reali
3. Dati VERIFICATI dal Code Property Graph (CPG) reale del codice tramite Joern: quanti metodi \
ha il componente e se esistono chiamate a sink Android pericolosi raggiungibili da esso

Il tuo compito:
1. Integra le tre fonti: il CPG è la fonte più autorevole sul comportamento REALE del codice, \
più affidabile dei pattern testuali della KB, che sono solo indicativi
2. Se il CPG mostra zero sink pericolosi, questo è un segnale forte di basso rischio per questo \
specifico componente, anche se i pattern recuperati dalla KB sembrano allarmanti
3. Se il CPG mostra sink pericolosi, valuta se il pattern recuperato dalla KB corrisponde \
concettualmente a quel sink specifico
4. Sii esplicito sul livello di confidenza (alto/medio/basso) e sul perché
5. Distingui sempre un'ipotesi da una conferma: serve comunque un data flow path completo \
source->sink per una conferma piena, non solo la presenza di un sink nel metodo
6. Se i dati sono insufficienti per una valutazione, dillo esplicitamente
"""

    user_message = f"""## Componente Android analizzato

```json
{json.dumps(component, indent=2)}
```

## Fonte 1 — Query di retrieval usata

{query}

## Fonte 2 — Pattern recuperati dalla Knowledge Base (i {len(retrieved_patterns)} più simili)

{patterns_text}

## Fonte 3 — Dati verificati dal Code Property Graph (Joern)

{joern_context}

## Richiesta

Integra le tre fonti sopra e fornisci una valutazione di sicurezza per questo componente. \
Indica il livello di confidenza e cosa servirebbe per una conferma piena se l'ipotesi è solo parziale.
"""

    return {"system": system_prompt, "user_message": user_message}


def analyze_component(comp_type: str, component: dict, reason: str, cpg_path: str,
                       top_k: int, dry_run: bool, model: str) -> dict:
    query = build_query_from_component(component)
    retrieved = retrieve_relevant_patterns(query, top_k=top_k)

    simple_name = extract_simple_name(component.get("name", ""))
    joern_result = query_joern(cpg_path, simple_name)
    joern_context = format_joern_context(joern_result)

    prompt = build_full_prompt(component, query, retrieved, joern_context)

    result = {
        "component_type": comp_type,
        "component_name": component.get("name"),
        "selection_reason": reason,
        "query": query,
        "top_pattern_score": retrieved[0]["score"] if retrieved else None,
        "top_pattern_category": retrieved[0]["category"] if retrieved else None,
        "joern_method_count": joern_result.get("method_count", 0),
        "joern_sink_count": joern_result.get("sink_count", 0),
        "full_prompt": prompt,
        "claude_analysis": None,
    }

    if dry_run:
        result["claude_analysis"] = "[DRY-RUN: nessuna chiamata API eseguita]"
    else:
        try:
            result["claude_analysis"] = call_claude_api(prompt, model=model)
        except Exception as e:
            result["claude_analysis"] = f"[ERRORE: {e}]"

    return result


def main():
    parser = argparse.ArgumentParser(description="Analizza in batch tutti i componenti di un manifest, con Joern")
    parser.add_argument("--manifest-file", required=True, type=Path)
    parser.add_argument("--cpg-path", required=True, help="Path al cpg.bin prodotto da extract_structure + javasrc2cpg")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--show-full-prompt", action="store_true",
                         help="Mostra il prompt completo per ogni componente (utile per copiarlo manualmente in chat)")
    parser.add_argument("--only-component", default=None,
                         help="Filtra l'analisi solo al componente che contiene questa stringa nel nome")
    args = parser.parse_args()

    if not args.manifest_file.exists():
        print(f"[!] File non trovato: {args.manifest_file}", file=sys.stderr)
        sys.exit(1)

    manifest_data = json.loads(args.manifest_file.read_text())
    selected = select_components_to_analyze(manifest_data)
    stats = summarize_skipped(manifest_data, selected)

    print("=" * 70)
    print("SELEZIONE COMPONENTI")
    print("=" * 70)
    print(f"Totale componenti nel manifest: {stats['total_components']}")
    print(f"Selezionati per analisi:        {stats['selected_for_analysis']}")
    print(f"Scartati (interni):             {stats['skipped_as_internal']}")
    print()

    if args.only_component:
        selected = [s for s in selected if args.only_component in s[1].get("name", "")]

    if not selected:
        print("[*] Nessun componente da analizzare (controlla --only-component).")
        return

    results = []
    for i, (comp_type, comp, reason) in enumerate(selected, 1):
        print(f"[{i}/{len(selected)}] Analizzo {comp_type}: {comp.get('name')} (motivo: {reason})")
        result = analyze_component(comp_type, comp, reason, args.cpg_path, args.top_k, args.dry_run, args.model)
        results.append(result)
        print(f"    -> top pattern KB: {result['top_pattern_category']} (score={result['top_pattern_score']})")
        print(f"    -> Joern: {result['joern_method_count']} metodi, {result['joern_sink_count']} sink")

    print("\n" + "=" * 70)
    print("REPORT AGGREGATO")
    print("=" * 70)
    for r in results:
        print(f"\n--- {r['component_type']}: {r['component_name']} ({r['selection_reason']}) ---")
        print(f"KB top pattern: {r['top_pattern_category']} (score={r['top_pattern_score']})")
        print(f"Joern: {r['joern_method_count']} metodi, {r['joern_sink_count']} sink")
        if args.show_full_prompt:
            print(f"\n=== PROMPT COMPLETO PER {r['component_name']} ===")
            print(f"\n--- SYSTEM ---\n{r['full_prompt']['system']}")
            print(f"\n--- USER MESSAGE ---\n{r['full_prompt']['user_message']}")
            print("=" * 70)
        if not args.dry_run:
            print(f"\nAnalisi Claude:\n{r['claude_analysis']}")

    if args.output:
        full_report = {"stats": stats, "results": results}
        args.output.write_text(json.dumps(full_report, indent=2, default=str))
        print(f"\n[✓] Report completo salvato in: {args.output}")


if __name__ == "__main__":
    main()
