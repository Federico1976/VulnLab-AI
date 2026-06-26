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


def get_models(payload):
    return payload.get("evidence_models") or payload.get("models") or payload.get("items") or []


def get_joern(payload):
    if isinstance(payload, dict):
        return payload.get("results") or payload.get("items") or []
    if isinstance(payload, list):
        return payload
    return []


def get_effects(model):
    return model.get("security_effects") or model.get("effects") or []


def evaluate_model(model, idx, joern_results):
    rid = model.get("research_object_id")
    effects = get_effects(model)

    req = model.get("v2_semantic_requirements", {})
    proof_requirements = req.get("proof_requirements", []) or model.get("evidence_requirements", [])
    unknowns = req.get("unknowns", [])

    joern_count = len(joern_results)
    has_effects = len(effects) > 0
    has_requirements = len(proof_requirements) > 0
    has_static_context = joern_count > 0

    if has_effects and has_requirements and has_static_context:
        decision = "static_evidence_ready_for_causal_assessment"
    elif has_effects and has_requirements:
        decision = "needs_static_execution_evidence"
    elif has_effects:
        decision = "needs_semantic_requirements"
    else:
        decision = "needs_security_effects"

    return {
        "proof_evaluation_id": sid("PEV4", rid, idx),
        "schema": "vulnlab.proof_evaluation.v4",
        "research_object_id": rid,
        "evidence_model_id": model.get("evidence_model_id"),
        "status": "candidate_evidence_only",
        "decision": decision,
        "decision_v4": decision,
        "candidate_only": True,
        "finding_allowed": False,
        "finding_allowed_v4": False,
        "dynamic_validation_allowed": False,
        "dynamic_validation_allowed_v4": False,
        "requires_causal_reachability": True,
        "requires_dynamic_validation": True,
        "security_effect_count": len(effects),
        "proof_requirement_count": len(proof_requirements),
        "unknown_count": len(unknowns),
        "joern_normalized_results": joern_count,
        "static_context_available": has_static_context,
        "evidence_model_summary": {
            "research_object_id": rid,
            "effect_types": sorted(set(str(e.get("type")) for e in effects if isinstance(e, dict))),
            "proof_requirements": proof_requirements,
            "unknowns": unknowns,
        },
        "blockers": [
            "causal_reachability_required",
            "dynamic_validation_required_before_any_finding",
        ],
        "guardrails": {
            "candidate_only": True,
            "no_vulnerability_claim": True,
            "responsible_disclosure_requires_reproduction": True,
        },
    }


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.proof_evaluator.proof_evaluator_v4 <evidence_models.json> <normalized_joern_results.json> <output.json>")
        sys.exit(1)

    evidence = load(sys.argv[1])
    joern = load(sys.argv[2])

    models = get_models(evidence)
    joern_results = get_joern(joern)

    evaluations = [
        evaluate_model(m, i, joern_results)
        for i, m in enumerate(models)
        if isinstance(m, dict)
    ]

    summary = {}
    for e in evaluations:
        d = e.get("decision_v4")
        summary[d] = summary.get(d, 0) + 1

    out = {
        "schema": "vulnlab.proof_evaluations.v4",
        "proof_evaluations": evaluations,
        "evaluations": evaluations,
        "summary": summary,
        "v4_summary": {
            "evaluations": len(evaluations),
            "joern_normalized_results": len(joern_results),
            "finding_policy": "no vulnerability declaration without causal reachability and dynamic validation",
        },
    }

    save(sys.argv[3], out)

    print(json.dumps({
        "status": "ok",
        "evaluations": len(evaluations),
        "summary": summary,
        "joern_normalized_results": len(joern_results),
        "output": sys.argv[3],
    }, indent=2))


if __name__ == "__main__":
    main()
