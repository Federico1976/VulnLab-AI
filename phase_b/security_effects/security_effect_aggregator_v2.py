#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import defaultdict


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.security_effects.security_effect_aggregator_v2 <security_effects.json> <output.json>")
        sys.exit(1)

    payload = load(sys.argv[1])
    effects = payload.get("effects") or []

    grouped = defaultdict(list)
    for e in effects:
        if isinstance(e, dict):
            grouped[e.get("research_object_id")].append(e)

    aggregated = []

    for rid, items in grouped.items():
        aggregated.append({
            "research_object_id": rid,
            "aggregated_effect_id": f"AGG-{rid}",
            "type": "AggregatedSecurityEffectsV2",
            "effects": items,
            "effect_count": len(items),
            "candidate_only": True,
            "may_declare_vulnerability": False,
            "requires_causal_reachability": True,
            "requires_dynamic_validation": True,
            "source": "security_effect_aggregator_v2",
        })

    out = {
        "schema": "vulnlab.security_effects.aggregated.v2",
        "aggregated_effects": aggregated,
        "summary": {
            "hypotheses": len(aggregated),
            "aggregated_effects": len(aggregated),
            "raw_effects": len(effects),
        },
    }

    save(sys.argv[2], out)

    print(json.dumps({
        "status": "ok",
        "aggregated_effects": len(aggregated),
        "raw_effects": len(effects),
        "output": sys.argv[2],
    }, indent=2))


if __name__ == "__main__":
    main()
