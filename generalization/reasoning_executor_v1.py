#!/usr/bin/env python3
"""
Reasoning Executor v1.

Input:
- semantic_story_v1.json
- knowledge_pattern_memory_v1.json
- distilled_pattern_memory_v1.json
- strategy_memory_v2.json
- hypothesis_priorities_v1.json
- universal_investigation_plan_v2.json
- evidence_story_v1.json
- optional Ollama/LLM reasoning artifacts

Output:
- reasoning_executor_decision_v1.json

Purpose:
- Select the current best investigative action.
- No findings.
- No CVE-specific logic.
- No target-specific detectors.
- No report generation.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def norm(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    value = str(value).strip()
    return value if value else "unknown"


def stable_id(*parts: Any) -> str:
    raw = "|".join(norm(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def role_bias(role: str) -> float:
    """
    Bias conservativo: prima ridurre incertezza e proof-gap,
    non cercare impatto/finding prematuri.
    """
    values = {
        "counter_evidence_collection": 0.10,
        "blocker_resolution": 0.09,
        "causal_consistency": 0.08,
        "runtime_probe": 0.07,
        "ordered_call_chain": 0.07,
        "sanitizer_validation": 0.06,
        "source_validation": 0.05,
        "sink_validation": 0.05,
        "strategy_fit_check": 0.04,
        "strategy_reuse_validation": 0.03,
        "information_gain_measurement": 0.03,
        "experiment_ranking": 0.02,
    }
    return values.get(role, 0.01)


def blocker_pressure(step: Dict[str, Any]) -> float:
    blockers = step.get("blocking_conditions") or []
    if not blockers:
        return 0.0
    return min(len(blockers) * 0.05, 0.20)


def score_step(step: Dict[str, Any]) -> Dict[str, Any]:
    eig = num(step.get("expected_information_gain"))
    cost = num(step.get("estimated_cost"), 0.7)
    uncertainty = num(step.get("uncertainty_reduction_score"))
    bias = role_bias(step.get("experiment_role", "unknown"))
    blocker = blocker_pressure(step)

    score = (
        uncertainty * 0.40
        + eig * 0.25
        + bias
        + blocker
        - cost * 0.10
    )

    score = round(max(0.0, min(score, 1.0)), 4)

    return {
        "decision_score": score,
        "uncertainty_reduction_score": uncertainty,
        "expected_information_gain": eig,
        "estimated_cost": cost,
        "role_bias": round(bias, 4),
        "blocker_pressure": round(blocker, 4),
    }


def select_best_step(plan: Dict[str, Any]) -> Dict[str, Any]:
    steps = plan.get("ordered_plan", []) or []
    if not steps:
        return {}

    scored = []
    for step in steps:
        item = dict(step)
        item["decision_score_factors"] = score_step(step)
        item["decision_score"] = item["decision_score_factors"]["decision_score"]
        scored.append(item)

    scored.sort(
        key=lambda s: (
            -float(s.get("decision_score") or 0),
            -float(s.get("uncertainty_reduction_score") or 0),
            float(s.get("estimated_cost") or 1),
            int(s.get("order") or 999),
        )
    )

    return scored[0]


def find_hypothesis(hypotheses: Dict[str, Any], hypothesis_id: str) -> Dict[str, Any]:
    for h in hypotheses.get("ranked_hypotheses", []) or []:
        if h.get("hypothesis_id") == hypothesis_id:
            return h
    return {}


def infer_proof_gap_after_action(step: Dict[str, Any]) -> str:
    role = step.get("experiment_role")

    mapping = {
        "counter_evidence_collection": "proof_gap_may_reduce_by_invalidating_false_positive_paths",
        "blocker_resolution": "proof_gap_may_reduce_by_removing_known_blockers",
        "causal_consistency": "proof_gap_may_reduce_by_confirming_or_rejecting_causal_edges",
        "runtime_probe": "proof_gap_may_reduce_by_confirming_runtime_marker_propagation",
        "ordered_call_chain": "proof_gap_may_reduce_by_confirming_ordered_method_level_flow",
        "sanitizer_validation": "proof_gap_may_reduce_by_confirming_sanitizer_decision",
        "source_validation": "proof_gap_may_reduce_by_confirming_input_control",
        "sink_validation": "proof_gap_may_reduce_by_confirming_sink_sensitivity",
    }

    return mapping.get(role, "proof_gap_delta_unknown_until_experiment_result")


def build_reasoning_trace(
    semantic_story: Dict[str, Any],
    knowledge: Dict[str, Any],
    strategy: Dict[str, Any],
    hypotheses: Dict[str, Any],
    plan: Dict[str, Any],
    selected_step: Dict[str, Any],
    selected_hypothesis: Dict[str, Any],
) -> List[Dict[str, Any]]:
    contract = semantic_story.get("semantic_contract", {}) or {}

    return [
        {
            "stage": "semantic_contract_review",
            "observation": {
                "framework_family": contract.get("framework_family"),
                "semantic_shape": contract.get("semantic_shape"),
                "proof_mode": contract.get("proof_mode"),
                "validation_family": contract.get("validation_family"),
            },
            "reason": "Use normalized semantic contract as source of truth for decision context.",
        },
        {
            "stage": "memory_review",
            "observation": {
                "knowledge_patterns": (knowledge.get("stats") or {}).get("pattern_count"),
                "strategy_count": (strategy.get("stats") or {}).get("strategy_count"),
                "hypothesis_count": (hypotheses.get("stats") or {}).get("hypothesis_count"),
                "plan_steps": (plan.get("stats") or {}).get("plan_step_count"),
            },
            "reason": "Use learned abstract memory only for prioritization, not for finding generation.",
        },
        {
            "stage": "hypothesis_selection",
            "observation": {
                "selected_hypothesis": selected_hypothesis.get("hypothesis_name"),
                "strategy_family": selected_hypothesis.get("strategy_family"),
                "priority_score": selected_hypothesis.get("priority_score"),
            },
            "reason": "Prefer the hypothesis with the best mix of EIG, compatibility, blockers and historical strategy reliability.",
        },
        {
            "stage": "plan_step_selection",
            "observation": {
                "selected_experiment": selected_step.get("experiment_id"),
                "experiment_role": selected_step.get("experiment_role"),
                "decision_score": selected_step.get("decision_score"),
                "score_factors": selected_step.get("decision_score_factors"),
            },
            "reason": "Select the next action that maximizes uncertainty reduction while preserving guardrails.",
        },
    ]


def build_decision(apk_output_dir: Path) -> Dict[str, Any]:
    semantic_story = load_json(apk_output_dir / "semantic_story_v1.json") or {}
    evidence_story = load_json(apk_output_dir / "evidence_story_v1.json") or {}
    hypotheses = load_json(apk_output_dir / "hypothesis_priorities_v1.json") or {}
    plan = load_json(apk_output_dir / "universal_investigation_plan_v2.json") or {}

    knowledge = load_json(Path("output/knowledge_pattern_memory_v1.json")) or {}
    distilled = load_json(Path("output/distilled_pattern_memory_v1.json")) or {}
    strategy = load_json(Path("output/strategy_memory_v2.json")) or {}

    llm_reasoning = (
        load_json(apk_output_dir / "ollama_llm_reasoning_v2.json")
        or load_json(apk_output_dir / "ollama_llm_reasoning_v1.json")
        or load_json(apk_output_dir / "llm_reasoning_output_v1.json")
        or {}
    )

    selected_step = select_best_step(plan)
    selected_hypothesis = find_hypothesis(
        hypotheses,
        selected_step.get("source_hypothesis_id"),
    )

    decision = {
        "schema": "reasoning_executor_decision_v1",
        "generated_at": now_iso(),
        "apk_name": semantic_story.get("apk_name") or evidence_story.get("apk_name") or apk_output_dir.name,
        "output_dir": str(apk_output_dir),
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
            "target_specific_detectors_allowed": False,
            "learns_findings": False,
            "learns_cves": False,
        },
        "inputs": {
            "semantic_story": str(apk_output_dir / "semantic_story_v1.json"),
            "evidence_story": str(apk_output_dir / "evidence_story_v1.json"),
            "knowledge_pattern_memory": "output/knowledge_pattern_memory_v1.json",
            "distilled_pattern_memory": "output/distilled_pattern_memory_v1.json",
            "strategy_memory": "output/strategy_memory_v2.json",
            "hypothesis_priorities": str(apk_output_dir / "hypothesis_priorities_v1.json"),
            "universal_investigation_plan": str(apk_output_dir / "universal_investigation_plan_v2.json"),
            "llm_reasoning_present": bool(llm_reasoning),
        },
        "current_best_action": {
            "experiment_id": selected_step.get("experiment_id"),
            "experiment_role": selected_step.get("experiment_role"),
            "description": selected_step.get("description"),
            "decision_score": selected_step.get("decision_score"),
            "expected_information_gain": selected_step.get("expected_information_gain"),
            "estimated_cost": selected_step.get("estimated_cost"),
            "uncertainty_reduction_score": selected_step.get("uncertainty_reduction_score"),
            "success_condition": selected_step.get("success_condition"),
            "failure_condition": selected_step.get("failure_condition"),
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
        },
        "selected_hypothesis": {
            "hypothesis_id": selected_hypothesis.get("hypothesis_id"),
            "hypothesis_name": selected_hypothesis.get("hypothesis_name"),
            "strategy_family": selected_hypothesis.get("strategy_family"),
            "priority_score": selected_hypothesis.get("priority_score"),
            "hypothesis_object": selected_hypothesis.get("hypothesis_object"),
        },
        "selected_plan_step": selected_step,
        "proof_gap_after_execution_prediction": infer_proof_gap_after_action(selected_step),
        "reasoning_trace": build_reasoning_trace(
            semantic_story,
            knowledge,
            strategy,
            hypotheses,
            plan,
            selected_step,
            selected_hypothesis,
        ),
        "final_decision_policy": {
            "allowed_output": "next_investigation_action_only",
            "forbidden_outputs": [
                "finding",
                "vulnerability_claim",
                "severity",
                "exploit",
                "disclosure_report",
                "target_specific_detector",
            ],
        },
    }

    return decision


def run(apk_output_dir: Path, out: Path) -> Dict[str, Any]:
    decision = build_decision(apk_output_dir)
    save_json(out, decision)
    return decision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk_output_dir")
    parser.add_argument("--out")
    args = parser.parse_args()

    out = Path(args.out) if args.out else Path(args.apk_output_dir) / "reasoning_executor_decision_v1.json"
    result = run(Path(args.apk_output_dir), out)

    print(json.dumps({
        "ok": True,
        "out": str(out),
        "apk_name": result.get("apk_name"),
        "current_best_action": result.get("current_best_action"),
        "guardrails": result.get("guardrails"),
    }, indent=2))


if __name__ == "__main__":
    main()
