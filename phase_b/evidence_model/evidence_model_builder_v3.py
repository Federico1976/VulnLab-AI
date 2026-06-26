#!/usr/bin/env python3
import json
import sys
import hashlib
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sid(prefix, *parts):
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}-{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.evidence_model.evidence_model_builder_v3 <aggregated_effects.json> <existing_evidence_models.json> <output.json>")
        sys.exit(1)

    agg = load(sys.argv[1])
    existing = load(sys.argv[2])

    aggregated = agg.get("aggregated_effects") or []

    models = []

    for a in aggregated:
        if not isinstance(a, dict):
            continue

        rid = a.get("research_object_id")
        effects = a.get("effects") or []

        model = {
            "evidence_model_id": sid("EMV3", rid),
            "type": "EvidenceModelV3",
            "research_object_id": rid,
            "status": "candidate_evidence_only",
            "confidence": "medium" if effects else "low",
            "candidate_only": True,
            "may_declare_vulnerability": False,
            "requires_causal_reachability": True,
            "requires_dynamic_validation": True,
            "source": "evidence_model_builder_v3",
            "security_effects": effects,
            "evidence_requirements": [
                "source_controllability",
                "sink_reachability",
                "causal_path",
                "guard_or_sanitizer_analysis",
                "dynamic_validation",
            ],
            "evidence_state": "ready_for_causal_reachability_assessment",
        }

        models.append(model)

    out = {
        "schema": "vulnlab.evidence_models.v3",
        "evidence_models": models,
        "summary": {
            "evidence_models": len(models),
            "previous_schema": existing.get("schema") if isinstance(existing, dict) else None,
        },
    }

    save(sys.argv[3], out)

    print(json.dumps({
        "status": "ok",
        "evidence_models": len(models),
        "output": sys.argv[3],
    }, indent=2))


if __name__ == "__main__":
    main()
