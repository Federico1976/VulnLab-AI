#!/usr/bin/env python3
import json
import sys
import hashlib
from pathlib import Path
from collections import Counter, defaultdict


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sid(prefix, *parts):
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}-{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


def get_evals(payload):
    return payload.get("proof_evaluations") or payload.get("evaluations") or []


def get_tasks(payload):
    return payload.get("tasks") or payload.get("unknown_resolution_tasks") or []


def get_plans(payload):
    return payload.get("plans") or payload.get("dynamic_validation_plans") or []


def eval_decision(e):
    return (
        e.get("decision_v4")
        or e.get("decision_v3")
        or e.get("decision_v2")
        or e.get("decision")
        or e.get("verdict")
        or "unknown_decision"
    )


def eval_rid(e):
    return (
        e.get("research_object_id")
        or e.get("causal_reachability_v3", {}).get("research_object_id")
        or e.get("evidence_model_summary", {}).get("research_object_id")
    )


def main():
    if len(sys.argv) != 5:
        print("Usage: python3 -m phase_b.research_strategy_memory.strategy_memory_builder_v2 <proof_evaluations.json> <unknown_resolution_tasks.json> <dynamic_validation_plans.json> <output.json>")
        sys.exit(1)

    evals_payload = load(sys.argv[1])
    unknowns_payload = load(sys.argv[2])
    dynamic_payload = load(sys.argv[3])

    evals = get_evals(evals_payload)
    unknowns = get_tasks(unknowns_payload)
    plans = get_plans(dynamic_payload)

    decisions = Counter(eval_decision(e) for e in evals if isinstance(e, dict))
    rid_groups = defaultdict(list)

    for e in evals:
        if not isinstance(e, dict):
            continue
        rid_groups[eval_rid(e)].append(e)

    dynamic_by_rid = defaultdict(int)
    for p in plans:
        if isinstance(p, dict):
            dynamic_by_rid[p.get("research_object_id")] += 1

    unknown_by_rid = defaultdict(int)
    for u in unknowns:
        if isinstance(u, dict):
            unknown_by_rid[u.get("research_object_id")] += 1

    strategies = []

    for rid, items in rid_groups.items():
        local_decisions = Counter(eval_decision(e) for e in items)
        any_dynamic = any(
            e.get("dynamic_validation_allowed_v3")
            or e.get("dynamic_validation_allowed_v4")
            for e in items
        )

        strategy = {
            "strategy_id": sid("RSMV2", rid),
            "schema": "vulnlab.research_strategy_memory.v2",
            "research_object_id": rid,
            "source": "strategy_memory_builder_v2",
            "strategy_type": "research_object_followup_strategy",
            "candidate_only": True,
            "finding_allowed": False,
            "decision_distribution": dict(local_decisions),
            "dynamic_validation_plans": dynamic_by_rid.get(rid, 0),
            "unknown_resolution_tasks": unknown_by_rid.get(rid, 0),
            "recommended_next_action": (
                "perform_dynamic_validation"
                if any_dynamic or dynamic_by_rid.get(rid, 0) > 0
                else "collect_more_static_or_causal_evidence"
            ),
            "why": (
                "Static and causal evidence reached dynamic-validation readiness, but finding is still blocked until runtime validation."
                if any_dynamic or dynamic_by_rid.get(rid, 0) > 0
                else "Research object still lacks enough proof evidence for dynamic validation."
            ),
            "guardrails": {
                "candidate_only": True,
                "requires_causal_reachability": True,
                "requires_dynamic_validation_before_finding": True,
                "responsible_disclosure_only": True,
            },
            "campaign_learning_tags": [
                "research_object_based_strategy",
                "proof_v4_compatible",
                "dynamic_validation_first",
            ],
        }

        strategies.append(strategy)

    global_strategy = {
        "strategy_id": sid("RSMV2-GLOBAL", json.dumps(dict(decisions), sort_keys=True), len(plans)),
        "schema": "vulnlab.research_strategy_memory.v2",
        "strategy_type": "global_campaign_strategy",
        "source": "strategy_memory_builder_v2",
        "candidate_only": True,
        "finding_allowed": False,
        "decision_distribution": dict(decisions),
        "total_evaluations": len(evals),
        "total_dynamic_validation_plans": len(plans),
        "total_unknown_resolution_tasks": len(unknowns),
        "recommended_next_action": (
            "run_dynamic_validation_or_continue_multi_apk_campaign"
            if plans
            else "expand_research_object_builders_or_static_correlation"
        ),
        "guardrails": {
            "no_vulnerability_claim_without_dynamic_validation": True,
            "responsible_disclosure_only": True,
        },
    }

    strategies.append(global_strategy)

    out = {
        "schema": "vulnlab.research_strategy_memory.v2",
        "strategies": strategies,
        "summary": {
            "strategies": len(strategies),
            "research_objects_with_strategy": len(rid_groups),
            "evaluations_consumed": len(evals),
            "dynamic_validation_plans_consumed": len(plans),
            "unknown_tasks_consumed": len(unknowns),
            "decision_distribution": dict(decisions),
        },
    }

    save(sys.argv[4], out)

    print(json.dumps({
        "status": "ok",
        "strategies": len(strategies),
        "evaluations_consumed": len(evals),
        "dynamic_validation_plans_consumed": len(plans),
        "output": sys.argv[4],
    }, indent=2))


if __name__ == "__main__":
    main()
