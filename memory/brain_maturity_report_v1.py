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


def score(state: Dict[str, Any], graph_v2: Dict[str, Any], confidence: Dict[str, Any], strategy_v3: Dict[str, Any]) -> Dict[str, Any]:
    counters = state.get("counters", {})
    graph_summary = graph_v2.get("summary", {})
    conf_summary = confidence.get("summary", {})
    strat_summary = strategy_v3.get("summary", {})

    checks = {
        "has_episodes": counters.get("episodes", 0) >= 10,
        "has_reasoning_routes": graph_summary.get("reasoning_routes", 0) >= 3,
        "has_strategy_profiles": strat_summary.get("strategies", 0) >= 3,
        "has_confidence_priorities": len(conf_summary.get("by_priority", {})) >= 2,
        "has_learning_history": state.get("version", 0) >= 1,
    }

    passed = sum(1 for v in checks.values() if v)
    maturity_score = round(passed / max(len(checks), 1), 2)

    if maturity_score >= 0.95:
        maturity = "excellent_architectural_readiness"
    elif maturity_score >= 0.80:
        maturity = "strong_readiness"
    elif maturity_score >= 0.60:
        maturity = "needs_training"
    else:
        maturity = "immature"

    return {
        "schema": "brain_maturity_report_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "maturity": maturity,
        "maturity_score": maturity_score,
        "checks": checks,
        "metrics": {
            "episodes": counters.get("episodes", 0),
            "reasoning_routes": graph_summary.get("reasoning_routes", 0),
            "strategy_profiles": strat_summary.get("strategies", 0),
            "confidence_priorities": conf_summary.get("by_priority", {}),
            "brain_version": state.get("version", 0),
        },
        "remaining_work": [
            "run_training_campaign_on_30_plus_apks",
            "ingest_real_validation_results",
            "measure_precision_false_positive_false_negative",
            "expand_external_knowledge_distillation",
            "freeze_before_first_new_bounty_apk",
        ],
    }


def main() -> None:
    if len(sys.argv) != 6:
        print("Usage: python3 -m memory.brain_maturity_report_v1 <brain_state.json> <universal_cognitive_graph_v2.json> <confidence.json> <strategy_v3.json> <out.json>")
        sys.exit(1)

    state = load_json(Path(sys.argv[1]))
    graph = load_json(Path(sys.argv[2]))
    confidence = load_json(Path(sys.argv[3]))
    strategy = load_json(Path(sys.argv[4]))
    out = Path(sys.argv[5])

    report = score(state, graph, confidence, strategy)
    save_json(out, report)

    print(json.dumps({
        "maturity": report["maturity"],
        "maturity_score": report["maturity_score"],
        "metrics": report["metrics"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
