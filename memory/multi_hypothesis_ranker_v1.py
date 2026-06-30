from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


PRIORITY_WEIGHT = {
    "high": 1.0,
    "medium": 0.75,
    "low": 0.45,
    "deprioritize": 0.1,
    None: 0.3,
}


def rank_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    shape = decision.get("candidate_shape")
    conf = decision.get("confidence_calibration", {})
    strategy = decision.get("strategy_selection", {})
    counter = decision.get("counterevidence_selection", [])
    failures = decision.get("failure_prediction", [])

    calibrated = conf.get("calibrated_confidence") or 0.3
    priority = conf.get("priority")
    priority_score = PRIORITY_WEIGHT.get(priority, 0.3)

    maturity = strategy.get("maturity")
    maturity_bonus = 0.1 if maturity == "mature" else 0.0

    counter_penalty = min(len(counter) * 0.05, 0.20)
    failure_penalty = min(len(failures) * 0.05, 0.20)

    local = decision.get("local_graph_evidence", {})
    by_type = local.get("by_type", {})
    by_relation = local.get("by_relation", {})

    bridge = by_type.get("BridgeEntity", 0)
    entry = by_type.get("EntrypointEntity", 0)
    asset = by_type.get("AssetEntity", 0)
    sink = by_type.get("SinkEntity", 0)

    may_reach = by_relation.get("may_reach", 0)
    touches_asset = by_relation.get("touches_asset", 0)
    contains_sink = by_relation.get("contains_sink", 0)

    info_value = 0.55
    local_fit = 0.0

    if shape == "entrypoint_to_content_uri_asset":
        info_value = 0.85
        local_fit = min((entry * 0.02) + (asset * 0.01) + (touches_asset * 0.01), 0.20)

    elif shape == "bridge_to_webview_sink":
        info_value = 0.90
        local_fit = min((bridge * 0.03) + (sink * 0.01) + (may_reach * 0.02), 0.25)

    elif shape == "bridge_to_file_asset":
        info_value = 0.65
        local_fit = min((bridge * 0.03) + (asset * 0.01) + (contains_sink * 0.005), 0.15)

    final_score = (
        calibrated * 0.40
        + priority_score * 0.20
        + info_value * 0.20
        + local_fit
        + maturity_bonus
        - counter_penalty
        - failure_penalty
    )

    final_score = round(max(0.0, min(final_score, 1.0)), 2)

    if final_score >= 0.80:
        rank = "investigate_first"
    elif final_score >= 0.60:
        rank = "investigate_second"
    elif final_score >= 0.40:
        rank = "keep_as_backup"
    else:
        rank = "deprioritize"

    return {
        "candidate_shape": shape,
        "rank": rank,
        "final_score": final_score,
        "calibrated_confidence": calibrated,
        "priority": priority,
        "maturity": maturity,
        "information_value": info_value,
        "local_fit": round(local_fit, 2),
        "counterevidence_count": len(counter),
        "failure_prediction_count": len(failures),
        "recommended_first_action": first_action(decision),
        "why": {
            "confidence": calibrated,
            "priority_score": priority_score,
            "maturity_bonus": maturity_bonus,
            "counter_penalty": counter_penalty,
            "failure_penalty": failure_penalty,
            "information_value": info_value,
            "local_fit": round(local_fit, 2),
        },
    }


def first_action(decision: Dict[str, Any]) -> str:
    counter = decision.get("counterevidence_selection", [])
    experiment = decision.get("experiment_planning", {})

    if counter:
        return f"seek_counterevidence:{counter[0].get('type')}"

    return f"run_experiment:{experiment.get('experiment_type', 'runtime_reachability_probe')}"


def build_ranker(reasoning_session: Dict[str, Any]) -> Dict[str, Any]:
    ranked = [rank_decision(d) for d in reasoning_session.get("decisions", [])]
    ranked = sorted(ranked, key=lambda x: x["final_score"], reverse=True)

    return {
        "schema": "multi_hypothesis_ranker_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "rank competing candidate hypotheses by confidence, information value, failures and counterevidence",
        "summary": {
            "hypotheses": len(ranked),
            "top_shape": ranked[0]["candidate_shape"] if ranked else "none",
            "top_rank": ranked[0]["rank"] if ranked else "none",
            "top_score": ranked[0]["final_score"] if ranked else 0,
        },
        "ranked_hypotheses": ranked,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 -m memory.multi_hypothesis_ranker_v1 <reasoning_session_v1.json> <multi_hypothesis_ranker_v1.json>")
        sys.exit(1)

    reasoning = load_json(Path(sys.argv[1]))
    out = Path(sys.argv[2])

    report = build_ranker(reasoning)
    save_json(out, report)

    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
