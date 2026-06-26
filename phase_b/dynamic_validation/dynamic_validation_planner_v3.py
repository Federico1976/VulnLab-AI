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
    return payload.get("proof_evaluations") or payload.get("evaluations") or []


def get_models(payload):
    return payload.get("evidence_models") or payload.get("models") or payload.get("items") or []


def get_existing_plans(payload):
    return payload.get("plans") or payload.get("dynamic_validation_plans") or []


def make_steps(model, evaluation):
    rid = model.get("research_object_id") or evaluation.get("research_object_id")
    req = model.get("v2_semantic_requirements", {})
    unknowns = req.get("unknowns", [])
    proof_requirements = req.get("proof_requirements", [])

    steps = [
        {
            "step": "scope_guard",
            "instruction": "Confirm the APK is open-source, local, or authorized for testing before runtime validation.",
            "success_signal": "authorized_scope_confirmed"
        },
        {
            "step": "install_and_launch",
            "instruction": "Install the APK on an instrumented emulator/device and launch the relevant entrypoint.",
            "success_signal": "app_launch_and_runtime_trace_available"
        },
        {
            "step": "trigger_candidate_surface",
            "instruction": "Trigger the Research Object candidate surface using safe inputs only.",
            "success_signal": "candidate_surface_triggered"
        },
        {
            "step": "observe_source_controllability",
            "instruction": "Verify whether controlled input reaches the candidate runtime path.",
            "success_signal": "source_controllability_observed_or_disproved"
        },
        {
            "step": "observe_sink_reachability",
            "instruction": "Verify whether the suspected sink or security effect is reached.",
            "success_signal": "sink_reachability_observed_or_disproved"
        },
        {
            "step": "guard_and_sanitizer_check",
            "instruction": "Observe whether permissions, validation, canonicalization, sanitizers, or authorization checks block the path.",
            "success_signal": "guard_behavior_observed"
        },
        {
            "step": "decision_update",
            "instruction": "Update evidence state as confirmed, disproven, or still unknown. Do not declare vulnerability without reproduction.",
            "success_signal": "evidence_model_updated"
        }
    ]

    for u in unknowns[:8]:
        steps.append({
            "step": "resolve_unknown",
            "instruction": str(u),
            "success_signal": "unknown_resolved_or_marked_unresolved"
        })

    for p in proof_requirements[:8]:
        steps.append({
            "step": "satisfy_proof_requirement",
            "instruction": str(p),
            "success_signal": "proof_requirement_satisfied_or_disproved"
        })

    return steps


def main():
    if len(sys.argv) != 5:
        print("Usage: python3 -m phase_b.dynamic_validation.dynamic_validation_planner_v3 <proof_evaluations.json> <evidence_models.json> <existing_dynamic_plans.json> <output.json>")
        sys.exit(1)

    evals_payload = load(sys.argv[1])
    evidence_payload = load(sys.argv[2])
    existing_payload = load(sys.argv[3])

    evals = get_evals(evals_payload)
    models = get_models(evidence_payload)
    existing = get_existing_plans(existing_payload)

    plans = list(existing) if isinstance(existing, list) else []
    existing_ids = set(p.get("dynamic_validation_plan_id") for p in plans if isinstance(p, dict))

    added = 0

    for idx, e in enumerate(evals):
        if not isinstance(e, dict):
            continue

        allowed = (
            e.get("dynamic_validation_allowed_v3") is True
            or e.get("decision_v3") == "causal_static_evidence_ready_for_dynamic_validation"
            or e.get("decision_v4") in (
                "static_evidence_ready_for_causal_assessment",
                "causal_static_evidence_ready_for_dynamic_validation",
            )
        )

        if not allowed:
            continue

        model = models[idx] if idx < len(models) and isinstance(models[idx], dict) else {}
        rid = model.get("research_object_id") or e.get("research_object_id")
        plan_id = sid("DVPV3", rid, idx)

        if plan_id in existing_ids:
            continue

        plan = {
            "dynamic_validation_plan_id": plan_id,
            "schema": "vulnlab.dynamic_validation_plan.v3",
            "research_object_id": rid,
            "proof_evaluation_id": e.get("proof_evaluation_id"),
            "source": "dynamic_validation_planner_v3",
            "status": "candidate_validation_plan",
            "priority": "medium",
            "requires_human_or_llm_test_design": True,
            "may_declare_vulnerability": False,
            "candidate_only": True,
            "goal": "Move candidate from static/causal evidence to runtime-confirmed or disproven state.",
            "validation_steps": make_steps(model, e),
            "success_criteria": [
                "authorized runtime validation completed",
                "source controllability confirmed or disproven",
                "sink reachability confirmed or disproven",
                "guard/sanitizer behavior observed",
                "no vulnerability claim without reproducible dynamic evidence"
            ],
            "guardrails": {
                "no_real_user_data": True,
                "no_destructive_actions": True,
                "no_persistence_or_stealth": True,
                "candidate_only_until_confirmed": True,
                "responsible_disclosure_only": True
            },
        }

        plans.append(plan)
        existing_ids.add(plan_id)
        added += 1

    out = {
        "schema": "vulnlab.dynamic_validation_plans.v3",
        "plans": plans,
        "summary": {
            "existing_plans": len(existing) if isinstance(existing, list) else 0,
            "added_v3_plans": added,
            "total_plans": len(plans),
        },
    }

    save(sys.argv[4], out)

    print(json.dumps({
        "status": "ok",
        "added_v3_plans": added,
        "total_plans": len(plans),
        "output": sys.argv[4],
    }, indent=2))


if __name__ == "__main__":
    main()
