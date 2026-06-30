#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sid(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


POLICY_WEIGHTS = {
    "vulnerability_probability": 0.30,
    "false_positive_reduction": 0.25,
    "evidence_gain": 0.20,
    "knowledge_gain": 0.15,
    "cost_efficiency": 0.10,
}


DEFAULT_COSTS = {
    "prove_external_reachability": 0.25,
    "prove_reachability": 0.25,
    "prove_caller_control_and_privilege_gap": 0.45,
    "prove_binder_or_component_reachability": 0.50,
    "prove_privileged_action": 0.55,
    "prove_uri_or_path_control": 0.35,
    "prove_file_boundary_crossing": 0.40,
    "prove_canonicalization_absence_or_bypass": 0.45,
    "prove_external_navigation_control": 0.35,
    "prove_url_load_sink": 0.35,
    "prove_domain_or_scheme_filter_gap": 0.45,
    "resolve_counter_evidence": 0.30,
    "resolve_shape_counter_evidence": 0.30,
    "produce_candidate_only_validation_result": 0.20,
    "inspect_semantic_graph": 0.15,
    "identify_candidate_shape": 0.15,
    "build_candidate_validation_plan": 0.20,
}


def step_cost(step: str) -> float:
    return DEFAULT_COSTS.get(step, 0.35)


def estimate_vulnerability_probability(decision: Dict[str, Any]) -> float:
    conf = decision.get("confidence_calibration", {})
    val = conf.get("shape_adjusted_confidence")
    if isinstance(val, (int, float)):
        return min(max(float(val), 0.0), 1.0)
    val = conf.get("calibrated_confidence")
    if isinstance(val, (int, float)):
        return min(max(float(val), 0.0), 1.0)
    return 0.35


def estimate_false_positive_reduction(decision: Dict[str, Any]) -> float:
    counters = decision.get("counterevidence_selection", [])
    missing = decision.get("evidence_story_update", {}).get("add_missing_evidence", [])
    if not counters and not missing:
        return 0.25
    return min(0.25 + 0.12 * len(counters) + 0.06 * len(missing), 1.0)


def estimate_evidence_gain(decision: Dict[str, Any]) -> float:
    exp = decision.get("experiment_planning", {})
    steps = exp.get("steps", [])
    if not steps:
        return 0.10

    gain = 0.0
    for st in steps:
        s = str(st)
        if "prove" in s:
            gain += 0.18
        elif "resolve" in s:
            gain += 0.15
        elif "validation" in s:
            gain += 0.14
        else:
            gain += 0.06

    return min(gain, 1.0)


def estimate_knowledge_gain(decision: Dict[str, Any], memory: Dict[str, Any], external_knowledge: Dict[str, Any]) -> float:
    shape = decision.get("candidate_shape")
    if not shape:
        return 0.10

    memory_shapes = set((memory.get("indexes", {}).get("by_shape", {}) or {}).keys())
    external_shapes = {
        p.get("pattern_shape")
        for p in external_knowledge.get("patterns", [])
        if p.get("pattern_shape")
    }

    gain = 0.25

    if shape not in memory_shapes:
        gain += 0.35
    else:
        gain += 0.10

    if shape in external_shapes:
        gain += 0.20

    counters = decision.get("counterevidence_selection", [])
    if counters:
        gain += min(0.08 * len(counters), 0.20)

    return min(gain, 1.0)


def estimate_cost_efficiency(decision: Dict[str, Any]) -> float:
    steps = decision.get("experiment_planning", {}).get("steps", [])
    if not steps:
        return 0.30

    total_cost = sum(step_cost(str(s)) for s in steps)
    avg_cost = total_cost / max(len(steps), 1)

    return round(1.0 - min(avg_cost, 1.0), 3)


def score_decision(decision: Dict[str, Any], memory: Dict[str, Any], external_knowledge: Dict[str, Any]) -> Dict[str, Any]:
    vuln_prob = estimate_vulnerability_probability(decision)
    fp_reduction = estimate_false_positive_reduction(decision)
    evidence_gain = estimate_evidence_gain(decision)
    knowledge_gain = estimate_knowledge_gain(decision, memory, external_knowledge)
    cost_eff = estimate_cost_efficiency(decision)

    score = (
        vuln_prob * POLICY_WEIGHTS["vulnerability_probability"]
        + fp_reduction * POLICY_WEIGHTS["false_positive_reduction"]
        + evidence_gain * POLICY_WEIGHTS["evidence_gain"]
        + knowledge_gain * POLICY_WEIGHTS["knowledge_gain"]
        + cost_eff * POLICY_WEIGHTS["cost_efficiency"]
    )

    return {
        "policy_score": round(score, 3),
        "components": {
            "vulnerability_probability": round(vuln_prob, 3),
            "false_positive_reduction": round(fp_reduction, 3),
            "evidence_gain": round(evidence_gain, 3),
            "knowledge_gain": round(knowledge_gain, 3),
            "cost_efficiency": round(cost_eff, 3),
        },
        "weights": POLICY_WEIGHTS,
    }


def allocate_budget(decisions: List[Dict[str, Any]], total_budget_units: float) -> List[Dict[str, Any]]:
    total_score = sum(max(d.get("policy", {}).get("policy_score", 0.0), 0.0) for d in decisions)

    if total_score <= 0:
        share = total_budget_units / max(len(decisions), 1)
        for d in decisions:
            d["budget_allocation"] = {
                "budget_units": round(share, 3),
                "allocation_reason": "equal_split_no_positive_policy_score",
            }
        return decisions

    for d in decisions:
        score = d.get("policy", {}).get("policy_score", 0.0)
        d["budget_allocation"] = {
            "budget_units": round(total_budget_units * score / total_score, 3),
            "allocation_reason": "proportional_to_policy_score",
        }

    return decisions


def select_next_best_experiment(decision: Dict[str, Any]) -> Dict[str, Any]:
    steps = decision.get("experiment_planning", {}).get("steps", [])
    counters = decision.get("counterevidence_selection", [])

    if counters:
        ce = counters[0]
        return {
            "experiment_id": sid("nbe", decision.get("candidate_shape"), ce.get("type")),
            "step": "resolve_counter_evidence",
            "target": ce.get("type"),
            "question": ce.get("question"),
            "why": "Highest immediate false-positive reduction.",
        }

    if steps:
        return {
            "experiment_id": sid("nbe", decision.get("candidate_shape"), steps[0]),
            "step": steps[0],
            "target": decision.get("candidate_shape"),
            "question": f"Execute next proof step '{steps[0]}' for shape '{decision.get('candidate_shape')}'.",
            "why": "Highest ranked available experiment from strategy plan.",
        }

    return {
        "experiment_id": sid("nbe", decision.get("candidate_shape"), "manual_review"),
        "step": "manual_review",
        "target": decision.get("candidate_shape"),
        "question": "No executable step found; inspect reasoning session manually.",
        "why": "Fallback when no strategy is available.",
    }


def run_policy_engine(
    reasoning_session: Dict[str, Any],
    memory: Dict[str, Any],
    external_knowledge: Dict[str, Any],
    total_budget_units: float,
) -> Dict[str, Any]:
    decisions = reasoning_session.get("decisions", [])

    scored = []
    for d in decisions:
        enriched = json.loads(json.dumps(d))
        enriched["policy"] = score_decision(enriched, memory, external_knowledge)
        enriched["next_best_experiment"] = select_next_best_experiment(enriched)
        scored.append(enriched)

    scored.sort(
        key=lambda d: (
            d.get("policy", {}).get("policy_score", 0.0),
            d.get("confidence_calibration", {}).get("shape_adjusted_confidence") or 0.0,
        ),
        reverse=True,
    )

    scored = allocate_budget(scored, total_budget_units)

    return {
        "schema_version": "universal_investigation_policy_engine.v1",
        "created_at": int(time.time()),
        "policy": {
            "purpose": "metacognitive selection of best investigation strategy, not vulnerability confirmation",
            "candidate_only": True,
            "finding_allowed": False,
            "weights": POLICY_WEIGHTS,
            "total_budget_units": total_budget_units,
        },
        "summary": {
            "decisions_seen": len(decisions),
            "ranked_decisions": len(scored),
            "top_candidate_shape": scored[0].get("candidate_shape") if scored else None,
            "top_policy_score": scored[0].get("policy", {}).get("policy_score") if scored else None,
            "next_best_experiment": scored[0].get("next_best_experiment") if scored else None,
            "finding_allowed": False,
        },
        "ranked_decisions": scored,
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Universal Investigation Policy Engine v1")
    ap.add_argument("reasoning_session")
    ap.add_argument("--memory", required=True)
    ap.add_argument("--external-knowledge", required=True)
    ap.add_argument("--budget", type=float, default=10.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    reasoning_session = load_json(args.reasoning_session)
    memory = load_json(args.memory)
    external = load_json(args.external_knowledge)

    result = run_policy_engine(reasoning_session, memory, external, args.budget)
    save_json(args.out, result)

    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
