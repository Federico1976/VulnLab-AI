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


def get_evals(payload):
    return payload.get("proof_evaluations") or payload.get("evaluations") or payload.get("items") or []


def get_causal(payload):
    return payload.get("causal_reachability_objects") or payload.get("objects") or []


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.proof_evaluator.proof_evaluator_v3_causal_enricher <proof_evaluations.json> <causal_reachability.json> <output.json>")
        sys.exit(1)

    evals_payload = load(sys.argv[1])
    causal_payload = load(sys.argv[2])

    evals = get_evals(evals_payload)
    causal = get_causal(causal_payload)

    ready = [
        c for c in causal
        if isinstance(c, dict)
        and c.get("state") == "causal_static_evidence_ready_for_dynamic_validation"
    ]

    upgraded = 0

    for i, e in enumerate(evals):
        if not isinstance(e, dict):
            continue

        c = causal[i] if i < len(causal) else (ready[0] if ready else None)

        if isinstance(c, dict):
            e["causal_reachability_v3"] = c
            e["decision_v3"] = c.get("state")

            if c.get("state") == "causal_static_evidence_ready_for_dynamic_validation":
                e["dynamic_validation_allowed_v3"] = True
                e["finding_allowed_v3"] = False
                e["final_blocker_v3"] = "dynamic_validation_required_before_any_finding"
            else:
                e["dynamic_validation_allowed_v3"] = False
                e["finding_allowed_v3"] = False
                e["final_blocker_v3"] = "more_static_or_causal_evidence_required"

            e["responsible_disclosure_guardrail_v3"] = {
                "candidate_only": True,
                "may_declare_vulnerability": False,
                "requires_causal_reachability": True,
                "requires_dynamic_validation": True,
            }

            upgraded += 1

    evals_payload["schema"] = "vulnlab.proof_evaluations.v3_causal_aware"
    evals_payload["v3_summary"] = {
        "upgraded_evaluations": upgraded,
        "causal_ready_for_dynamic_validation": len(ready),
        "finding_policy": "no vulnerability declaration without dynamic validation",
    }

    save(sys.argv[3], evals_payload)

    print(json.dumps({
        "status": "ok",
        "upgraded_evaluations": upgraded,
        "causal_ready_for_dynamic_validation": len(ready),
        "output": sys.argv[3],
    }, indent=2))


if __name__ == "__main__":
    main()
