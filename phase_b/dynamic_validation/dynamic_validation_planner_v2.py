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


def get_evals(payload):
    return payload.get("proof_evaluations") or payload.get("evaluations") or payload.get("items") or []


def get_models(payload):
    return payload.get("evidence_models") or payload.get("models") or payload.get("items") or []


def extract_seeds(model):
    req = model.get("v2_semantic_requirements", {}) if isinstance(model, dict) else {}
    seeds = []

    for u in req.get("unknowns", []):
        seeds.append({
            "type": "unknown_resolution_runtime_check",
            "description": str(u),
        })

    seeds.extend([
        {
            "type": "runtime_trace",
            "description": "Run APK in instrumented environment and capture logcat/runtime traces.",
        },
        {
            "type": "source_controllability",
            "description": "Trigger candidate entrypoint and verify whether attacker/user-controlled input reaches the candidate path.",
        },
        {
            "type": "sink_reachability",
            "description": "Verify whether the suspected sink executes under controlled test conditions.",
        },
        {
            "type": "guard_validation",
            "description": "Check whether authorization, validation, canonicalization, or sanitizer logic blocks the path.",
        },
    ])

    return seeds


def main():
    if len(sys.argv) != 5:
        print("Usage: python3 -m phase_b.dynamic_validation.dynamic_validation_planner_v2 <proof_evaluations.json> <evidence_models.json> <existing_dynamic_plans.json> <output.json>")
        sys.exit(1)

    evals_payload = load(sys.argv[1])
    evidence_payload = load(sys.argv[2])
    existing_payload = load(sys.argv[3])

    evals = get_evals(evals_payload)
    models = get_models(evidence_payload)

    existing = existing_payload.get("plans") or existing_payload.get("dynamic_validation_plans") or []
    plans = list(existing) if isinstance(existing, list) else []

    added = 0

    for idx, e in enumerate(evals):
        if not isinstance(e, dict):
            continue

        allowed = (
            e.get("dynamic_validation_allowed_v3") is True
            or e.get("decision_v3") == "causal_static_evidence_ready_for_dynamic_validation"
        )

        if not allowed:
            continue

        model = models[idx] if idx < len(models) and isinstance(models[idx], dict) else {}
        rid = model.get("research_object_id") or e.get("causal_reachability_v3", {}).get("research_object_id")

        plan = {
            "dynamic_validation_plan_id": sid("DVPV2", rid, idx),
            "research_object_id": rid,
            "source": "dynamic_validation_planner_v2",
            "status": "candidate_validation_plan",
            "may_declare_vulnerability": False,
            "requires_human_or_llm_test_design": True,
            "goal": "Confirm or disprove causal reachability under runtime conditions before any disclosure claim.",
            "preconditions": [
                "authorized target or local/open-source test scope",
                "instrumented Android device or emulator",
                "controlled APK install",
                "logcat/runtime tracing available",
            ],
            "validation_steps": extract_seeds(model),
            "success_criteria": [
                "source controllability demonstrated",
                "sink execution demonstrated",
                "causal path observed or strongly correlated",
                "guards/sanitizers evaluated",
                "candidate either confirmed for disclosure workflow or disproven",
            ],
            "guardrails": {
                "candidate_only": True,
                "no_exploitation_beyond_validation": True,
                "no_real_user_data": True,
                "no_vulnerability_claim_without_reproduction": True,
            },
        }

        plans.append(plan)
        added += 1

    out = {
        "schema": "vulnlab.dynamic_validation_plans.v2",
        "plans": plans,
        "summary": {
            "existing_plans": len(existing) if isinstance(existing, list) else 0,
            "added_v2_plans": added,
            "total_plans": len(plans),
        },
    }

    save(sys.argv[4], out)

    print(json.dumps({
        "status": "ok",
        "added_v2_plans": added,
        "total_plans": len(plans),
        "output": sys.argv[4],
    }, indent=2))


if __name__ == "__main__":
    main()
