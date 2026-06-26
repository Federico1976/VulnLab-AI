#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def joern_results(payload):
    if isinstance(payload, dict):
        return payload.get("results") or payload.get("items") or []
    if isinstance(payload, list):
        return payload
    return []


def evidence_models(payload):
    return payload.get("evidence_models") or payload.get("models") or payload.get("items") or []


def evaluations(payload):
    return payload.get("proof_evaluations") or payload.get("evaluations") or payload.get("items") or []


def score_joern(results):
    methods = set()
    files = set()
    sinks = set()
    sources = set()

    for r in results:
        if not isinstance(r, dict):
            continue
        if r.get("method"):
            methods.add(str(r.get("method")))
        if r.get("file"):
            files.add(str(r.get("file")))
        if r.get("sink"):
            sinks.add(str(r.get("sink")))
        if r.get("source"):
            sources.add(str(r.get("source")))

    return {
        "normalized_results": len(results),
        "methods": len(methods),
        "files": len(files),
        "sources": len(sources),
        "sinks": len(sinks),
        "has_static_execution_evidence": len(results) > 0,
    }


def main():
    if len(sys.argv) != 5:
        print("Usage: python3 -m phase_b.proof_evaluator.proof_evaluator_joern_enricher_v2 <proof_evaluations.json> <evidence_models.json> <normalized_joern_results.json> <output.json>")
        sys.exit(1)

    eval_payload = load(sys.argv[1])
    evidence_payload = load(sys.argv[2])
    joern_payload = load(sys.argv[3])

    evs = evaluations(eval_payload)
    models = evidence_models(evidence_payload)
    results = joern_results(joern_payload)
    js = score_joern(results)

    upgraded = 0

    for e in evs:
        if not isinstance(e, dict):
            continue

        e["joern_v2"] = js

        guardrail = False
        proof_requirements = []
        unknowns = []

        for m in models:
            req = m.get("v2_semantic_requirements", {}) if isinstance(m, dict) else {}
            if req.get("candidate_only_guardrail"):
                guardrail = True
            proof_requirements.extend(req.get("proof_requirements", []))
            unknowns.extend(req.get("unknowns", []))

        e["proof_requirements_v2"] = sorted(set(str(x) for x in proof_requirements if x))
        e["unknowns_v2"] = sorted(set(str(x) for x in unknowns if x))
        e["finding_policy_v2"] = {
            "may_declare_vulnerability": False,
            "reason": "candidate evidence only: causal reachability and dynamic validation are mandatory",
            "guardrail_active": True if guardrail or unknowns or proof_requirements else False,
        }

        if js["has_static_execution_evidence"]:
            e["static_evidence_state_v2"] = "joern_results_available_but_not_yet_causal"
        else:
            e["static_evidence_state_v2"] = "no_joern_results"

        e["decision_v2"] = "needs_more_static_evidence"
        e["dynamic_validation_allowed_v2"] = False

        upgraded += 1

    eval_payload["schema"] = "vulnlab.proof_evaluations.v2_joern_aware"
    eval_payload["v2_summary"] = {
        "upgraded_evaluations": upgraded,
        "joern_normalized_results": js["normalized_results"],
        "decision_policy": "never declare vulnerability without causal reachability and dynamic validation",
    }

    save(sys.argv[4], eval_payload)

    print(json.dumps({
        "status": "ok",
        "upgraded_evaluations": upgraded,
        "joern_normalized_results": js["normalized_results"],
        "output": sys.argv[4],
    }, indent=2))


if __name__ == "__main__":
    main()
