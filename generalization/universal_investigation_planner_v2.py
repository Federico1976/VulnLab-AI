#!/usr/bin/env python3
"""
Universal Investigation Planner v2.

Input:
- hypothesis_priorities_v1.json

Output:
- universal_investigation_plan_v2.json

Purpose:
- Convert ranked hypothesis objects into an ordered uncertainty-reduction plan.
- No findings.
- No CVE-specific logic.
- No target-specific detectors.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def experiment_role(experiment_id: str) -> str:
    roles = {
        "runtime_probe_review": "runtime_probe",
        "runtime_marker_probe": "runtime_probe",
        "static_trace_review": "ordered_call_chain",
        "ordered_call_chain_reconstruction": "ordered_call_chain",
        "ordered_chain_confirmation": "ordered_call_chain",
        "source_confirmation": "source_validation",
        "sink_confirmation": "sink_validation",
        "sanitizer_decision_check": "sanitizer_validation",
        "causal_consistency_review": "causal_consistency",
        "causal_edge_validation": "causal_consistency",
        "collect_counter_evidence": "counter_evidence_collection",
        "resolve_known_blockers": "blocker_resolution",
        "alternative_path_elimination": "counter_evidence_collection",
        "measure_proof_gap_delta": "information_gain_measurement",
        "rank_candidate_experiments": "experiment_ranking",
        "reuse_validation_family": "strategy_reuse_validation",
        "validate_strategy_fit": "strategy_fit_check",
    }
    return roles.get(experiment_id, "generic_validation")


def build_plan_step(hypothesis: Dict[str, Any], experiment: Dict[str, Any], index: int) -> Dict[str, Any]:
    obj = hypothesis.get("hypothesis_object", {}) or {}
    eig = num(obj.get("expected_information_gain"))
    cost = num(experiment.get("estimated_cost"), num(obj.get("estimated_cost"), 0.7))
    priority = num(hypothesis.get("priority_score"))

    uncertainty_reduction = round(max(0.0, min(1.0, (eig * 0.55 + priority * 0.35 - cost * 0.10))), 4)

    return {
        "step_id": "plan_step_" + stable_id(
            hypothesis.get("hypothesis_id"),
            experiment.get("experiment_id"),
            index,
        ),
        "order": index,
        "experiment_id": experiment.get("experiment_id"),
        "experiment_role": experiment_role(experiment.get("experiment_id", "")),
        "description": experiment.get("description"),
        "source_hypothesis_id": hypothesis.get("hypothesis_id"),
        "hypothesis_family": obj.get("hypothesis_family"),
        "required_evidence": obj.get("required_evidence", []),
        "blocking_conditions": obj.get("blocking_conditions", []),
        "expected_information_gain": eig,
        "estimated_cost": cost,
        "uncertainty_reduction_score": uncertainty_reduction,
        "success_condition": "Required evidence collected or proof gap reduced.",
        "failure_condition": "Counter-evidence confirms blocker or proof gap remains open.",
        "output_expected": {
            "evidence_delta": True,
            "proof_gap_delta": True,
            "counter_evidence_delta": True,
            "finding_allowed": False,
        },
        "candidate_only": True,
        "finding_allowed": False,
        "report_allowed": False,
    }


def build_plan(hypothesis_priorities: Dict[str, Any], max_steps: int = 8) -> Dict[str, Any]:
    hypotheses = hypothesis_priorities.get("ranked_hypotheses", []) or []

    raw_steps: List[Dict[str, Any]] = []
    for h in hypotheses:
        obj = h.get("hypothesis_object", {}) or {}
        for exp in obj.get("recommended_next_experiments", []) or []:
            raw_steps.append(build_plan_step(h, exp, len(raw_steps) + 1))

    raw_steps = sorted(
        raw_steps,
        key=lambda s: (
            -float(s.get("uncertainty_reduction_score") or 0),
            float(s.get("estimated_cost") or 1),
            s.get("experiment_id") or "",
        ),
    )

    deduped = []
    seen_roles = set()

    for step in raw_steps:
        role = step.get("experiment_role")
        key = (role, step.get("experiment_id"))

        if key in seen_roles:
            continue

        seen_roles.add(key)
        deduped.append(step)

        if len(deduped) >= max_steps:
            break

    for idx, step in enumerate(deduped, 1):
        step["order"] = idx

    return {
        "schema": "universal_investigation_plan_v2",
        "generated_at": now_iso(),
        "apk_name": hypothesis_priorities.get("apk_name"),
        "source_schema": hypothesis_priorities.get("schema"),
        "semantic_contract": hypothesis_priorities.get("semantic_contract"),
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
            "target_specific_detectors_allowed": False,
            "learns_findings": False,
            "learns_cves": False,
        },
        "planning_policy": {
            "objective": "maximize_uncertainty_reduction_without_declaring_findings",
            "ordering_basis": [
                "expected_information_gain",
                "semantic_compatibility",
                "historical_success",
                "blocking_conditions",
                "estimated_cost",
            ],
            "output_type": "investigation_plan_only",
        },
        "stats": {
            "input_hypothesis_count": len(hypotheses),
            "plan_step_count": len(deduped),
        },
        "ordered_plan": deduped,
    }


def run(hypothesis_priorities_path: Path, out: Path, max_steps: int = 8) -> Dict[str, Any]:
    hypotheses = load_json(hypothesis_priorities_path)
    plan = build_plan(hypotheses, max_steps=max_steps)
    save_json(out, plan)
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hypotheses", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-steps", type=int, default=8)
    args = parser.parse_args()

    result = run(
        hypothesis_priorities_path=Path(args.hypotheses),
        out=Path(args.out),
        max_steps=args.max_steps,
    )

    print(json.dumps({
        "ok": True,
        "out": args.out,
        "stats": result.get("stats"),
        "top_step": result.get("ordered_plan", [{}])[0],
        "guardrails": result.get("guardrails"),
    }, indent=2))


if __name__ == "__main__":
    main()
