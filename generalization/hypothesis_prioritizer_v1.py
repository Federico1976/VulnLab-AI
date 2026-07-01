#!/usr/bin/env python3
"""
Hypothesis Prioritizer v1.

Input:
- semantic_story_v1.json
- strategy_memory_v2.json

Output:
- hypothesis_priorities_v1.json

Purpose:
- Rank abstract investigation hypotheses by expected information gain.
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


def estimate_experiment_cost(strategy_family: str) -> float:
    costs = {
        "counter_evidence_first": 0.25,
        "proof_gap_closure": 0.45,
        "eig_driven_experiment_selection": 0.35,
        "proof_mode_guided_validation": 0.50,
        "strategy_validation_pair_reuse": 0.35,
        "source_sink_strengthening": 0.60,
        "causal_state_disambiguation": 0.55,
        "general_investigation_strategy": 0.70,
    }
    return costs.get(strategy_family, 0.70)


def compatibility_score(strategy: Dict[str, Any], contract: Dict[str, Any]) -> float:
    score = 0.0

    if strategy.get("abstract_shape") == contract.get("semantic_shape"):
        score += 0.35

    if strategy.get("framework") == contract.get("framework_family"):
        score += 0.20

    if strategy.get("proof_mode") == contract.get("proof_mode"):
        score += 0.20

    if strategy.get("validation_family") == contract.get("validation_family"):
        score += 0.15

    if strategy.get("abstract_shape") == "unknown":
        score -= 0.10

    return max(0.0, min(score, 1.0))


def hypothesis_name(strategy_family: str) -> str:
    names = {
        "counter_evidence_first": "Prioritize blocker and counter-evidence resolution",
        "proof_gap_closure": "Close recurring proof gap before confidence escalation",
        "eig_driven_experiment_selection": "Select next experiment by expected information gain",
        "proof_mode_guided_validation": "Choose validation path from current proof mode",
        "strategy_validation_pair_reuse": "Reuse historically useful strategy/validation pair",
        "source_sink_strengthening": "Strengthen ordered source-to-sink evidence",
        "causal_state_disambiguation": "Disambiguate causal state with decisive evidence",
        "general_investigation_strategy": "Weak general investigation guidance",
    }
    return names.get(strategy_family, names["general_investigation_strategy"])



def required_evidence_for_family(strategy_family: str, proof_mode: str) -> List[str]:
    base = {
        "counter_evidence_first": [
            "blocker resolution evidence",
            "negative runtime propagation evidence",
            "counter-example trace",
        ],
        "proof_gap_closure": [
            "runtime marker propagation",
            "ordered method-level call chain",
            "sanitizer decision",
            "impact proof",
        ],
        "eig_driven_experiment_selection": [
            "experiment outcome",
            "information gain measurement",
            "proof gap delta",
        ],
        "proof_mode_guided_validation": [
            "static trace confirmation",
            "runtime probe confirmation",
            "causal graph consistency check",
        ],
        "strategy_validation_pair_reuse": [
            "strategy applicability evidence",
            "validation family compatibility",
            "historical pattern support",
        ],
        "source_sink_strengthening": [
            "source confirmation",
            "sink confirmation",
            "ordered call chain",
            "taint or propagation evidence",
        ],
        "causal_state_disambiguation": [
            "causal edge confirmation",
            "alternative path elimination",
            "counter-evidence collection",
        ],
    }

    evidence = list(base.get(strategy_family, ["triage evidence"]))

    if "runtime" in proof_mode and "runtime probe confirmation" not in evidence:
        evidence.append("runtime probe confirmation")

    if "static" in proof_mode and "static trace confirmation" not in evidence:
        evidence.append("static trace confirmation")

    return sorted(set(evidence))


def recommended_experiments_for_family(strategy_family: str) -> List[Dict[str, Any]]:
    experiments = {
        "counter_evidence_first": [
            ("collect_counter_evidence", "Collect decisive counter-evidence before confidence escalation.", 0.25),
            ("resolve_known_blockers", "Resolve recurring blockers from strategy memory.", 0.30),
        ],
        "proof_gap_closure": [
            ("runtime_marker_probe", "Check whether marker propagation is observable at runtime.", 0.45),
            ("ordered_call_chain_reconstruction", "Reconstruct ordered source-to-sink call chain.", 0.55),
            ("sanitizer_decision_check", "Verify whether sanitizer or validation blocks propagation.", 0.40),
        ],
        "eig_driven_experiment_selection": [
            ("rank_candidate_experiments", "Rank available experiments by expected information gain.", 0.35),
            ("measure_proof_gap_delta", "Measure which proof gap each experiment can close.", 0.30),
        ],
        "proof_mode_guided_validation": [
            ("static_trace_review", "Review static trace for ordered source-to-sink consistency.", 0.45),
            ("runtime_probe_review", "Review runtime probe state and marker propagation.", 0.45),
            ("causal_consistency_review", "Check causal graph consistency against static/runtime evidence.", 0.35),
        ],
        "strategy_validation_pair_reuse": [
            ("reuse_validation_family", "Reuse historically useful validation family for this semantic shape.", 0.35),
            ("validate_strategy_fit", "Check whether selected strategy matches current semantic contract.", 0.25),
        ],
        "source_sink_strengthening": [
            ("source_confirmation", "Confirm source is attacker/user/input controlled.", 0.35),
            ("sink_confirmation", "Confirm sink semantics and sensitivity.", 0.35),
            ("ordered_chain_confirmation", "Confirm ordered method-level propagation.", 0.55),
        ],
        "causal_state_disambiguation": [
            ("causal_edge_validation", "Validate uncertain causal graph edges.", 0.45),
            ("alternative_path_elimination", "Eliminate false-positive causal paths.", 0.50),
        ],
    }

    return [
        {
            "experiment_id": eid,
            "description": desc,
            "estimated_cost": cost,
            "candidate_only": True,
            "finding_allowed": False,
        }
        for eid, desc, cost in experiments.get(strategy_family, [
            ("generic_triage", "Perform generic evidence triage.", 0.70),
        ])
    ]


def historical_rates(strategy: Dict[str, Any]) -> Dict[str, float]:
    support = num(strategy.get("support_count"))
    diversity = num(strategy.get("apk_diversity"))
    reliability = num(strategy.get("strategy_reliability_score"))

    success = min(1.0, reliability * 0.70 + min(diversity, 10.0) / 10.0 * 0.20)
    failure = max(0.0, 1.0 - success - min(support, 20.0) / 20.0 * 0.10)

    return {
        "historical_success": round(success, 4),
        "historical_failure": round(failure, 4),
    }


def blocking_conditions_from_strategy(strategy: Dict[str, Any], semantic_story: Dict[str, Any]) -> List[str]:
    learning = semantic_story.get("learning_fields", {}) or {}
    blockers = []

    for item in strategy.get("common_counter_evidence", []) or []:
        value = item.get("value") if isinstance(item, dict) else item
        if value:
            blockers.append(norm(value))

    missing = learning.get("missing_proof")
    if missing and missing != "unknown":
        blockers.append("missing_proof:" + norm(missing))

    return sorted(set(blockers))


def build_hypothesis(strategy: Dict[str, Any], semantic_story: Dict[str, Any]) -> Dict[str, Any]:
    contract = semantic_story.get("semantic_contract", {}) or {}
    learning = semantic_story.get("learning_fields", {}) or {}

    family = strategy.get("strategy_family", "general_investigation_strategy")
    reliability = num(strategy.get("strategy_reliability_score"))
    eig = num(strategy.get("avg_expected_information_gain"), num(contract.get("expected_information_gain"), 0.3))
    compat = compatibility_score(strategy, contract)
    cost = estimate_experiment_cost(family)

    required_evidence = required_evidence_for_family(family, strategy.get("proof_mode", "unknown"))
    recommended_next_experiments = recommended_experiments_for_family(family)
    rates = historical_rates(strategy)
    blocking_conditions = blocking_conditions_from_strategy(strategy, semantic_story)

    blocker_pressure = 0.0
    if strategy.get("common_counter_evidence"):
        blocker_pressure += 0.20
    if strategy.get("common_missing_proofs"):
        blocker_pressure += 0.20
    if learning.get("missing_proof") not in [None, "unknown", []]:
        blocker_pressure += 0.10

    priority = (
        reliability * 0.35
        + eig * 0.25
        + compat * 0.25
        + blocker_pressure * 0.10
        - cost * 0.05
    )
    priority = round(max(0.0, min(priority, 1.0)), 4)

    return {
        "hypothesis_id": "hyp_" + stable_id(
            strategy.get("strategy_id"),
            semantic_story.get("apk_name"),
            contract.get("semantic_shape"),
            contract.get("proof_mode"),
        ),
        "hypothesis_name": hypothesis_name(family),
        "hypothesis_object": {
            "hypothesis_family": family,
            "required_evidence": required_evidence,
            "expected_information_gain": eig,
            "estimated_cost": cost,
            "historical_success": rates["historical_success"],
            "historical_failure": rates["historical_failure"],
            "blocking_conditions": blocking_conditions,
            "recommended_next_experiments": recommended_next_experiments,
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
        },
        "source_strategy_id": strategy.get("strategy_id"),
        "strategy_family": family,
        "abstract_shape": strategy.get("abstract_shape"),
        "framework": strategy.get("framework"),
        "proof_mode": strategy.get("proof_mode"),
        "validation_family": strategy.get("validation_family"),
        "priority_score": priority,
        "score_factors": {
            "strategy_reliability": reliability,
            "expected_information_gain": eig,
            "semantic_compatibility": round(compat, 4),
            "blocker_pressure": round(blocker_pressure, 4),
            "estimated_experiment_cost": cost,
            "historical_success": rates["historical_success"],
            "historical_failure": rates["historical_failure"],
        },
        "common_missing_proofs": strategy.get("common_missing_proofs", []),
        "common_counter_evidence": strategy.get("common_counter_evidence", []),
        "recommended_action": strategy.get("recommended_action"),
        "required_evidence": required_evidence,
        "blocking_conditions": blocking_conditions,
        "recommended_next_experiments": recommended_next_experiments,
        "guardrail_rule": "Hypothesis priority is triage only. It cannot declare vulnerabilities or findings.",
    }


def prioritize(semantic_story: Dict[str, Any], strategy_memory: Dict[str, Any]) -> Dict[str, Any]:
    strategies = strategy_memory.get("strategies", []) or []
    hypotheses = [build_hypothesis(s, semantic_story) for s in strategies]

    hypotheses = sorted(
        hypotheses,
        key=lambda h: (
            -float(h.get("priority_score") or 0),
            h.get("hypothesis_id"),
        ),
    )

    return {
        "schema": "hypothesis_priorities_v1",
        "generated_at": now_iso(),
        "apk_name": semantic_story.get("apk_name"),
        "source_semantic_story": semantic_story.get("source_evidence_story"),
        "source_strategy_memory_schema": strategy_memory.get("schema"),
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
            "target_specific_detectors_allowed": False,
            "learns_findings": False,
            "learns_cves": False,
        },
        "stats": {
            "strategy_count": len(strategies),
            "hypothesis_count": len(hypotheses),
        },
        "semantic_contract": semantic_story.get("semantic_contract"),
        "ranked_hypotheses": hypotheses,
    }


def run(semantic_story_path: Path, strategy_memory_path: Path, out: Path) -> Dict[str, Any]:
    semantic_story = load_json(semantic_story_path)
    strategy_memory = load_json(strategy_memory_path)
    result = prioritize(semantic_story, strategy_memory)
    save_json(out, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--semantic-story", required=True)
    parser.add_argument("--strategy-memory", default="output/strategy_memory_v2.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = run(
        semantic_story_path=Path(args.semantic_story),
        strategy_memory_path=Path(args.strategy_memory),
        out=Path(args.out),
    )

    print(json.dumps({
        "ok": True,
        "out": args.out,
        "stats": result.get("stats"),
        "top_hypothesis": result.get("ranked_hypotheses", [{}])[0],
        "guardrails": result.get("guardrails"),
    }, indent=2))


if __name__ == "__main__":
    main()
