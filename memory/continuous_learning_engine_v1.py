from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_learning_update(
    reasoning_session: Dict[str, Any],
    validation_results: Dict[str, Any] | None,
    cognitive_graph_v2: Dict[str, Any],
) -> Dict[str, Any]:
    decisions = reasoning_session.get("decisions", [])
    results = validation_results.get("results", []) if validation_results else []

    result_count = len(results)
    confirmed = sum(1 for r in results if str(r.get("outcome", "")).lower() in {"confirmed", "validated"})
    rejected = sum(1 for r in results if str(r.get("outcome", "")).lower() in {"failed", "rejected", "blocked", "not_reachable", "false_positive"})

    updates = []

    for d in decisions:
        shape = d.get("candidate_shape")
        priority = d.get("confidence_calibration", {}).get("priority")

        updates.append({
            "strategy_shape": shape,
            "previous_priority": priority,
            "observed_results": result_count,
            "confirmed_results": confirmed,
            "rejected_results": rejected,
            "recommended_memory_updates": [
                "update_investigation_experience_memory",
                "update_failure_memory_if_rejected",
                "update_counterevidence_memory_if_rejected",
                "recompute_confidence_calibration",
                "rerun_knowledge_distillation",
                "rebuild_universal_cognitive_graph",
            ],
            "finding_allowed": False,
        })

    return {
        "schema": "continuous_learning_update_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "describe incremental memory updates after reasoning and optional validation results",
        "summary": {
            "decisions": len(decisions),
            "validation_results": result_count,
            "confirmed": confirmed,
            "rejected": rejected,
            "cognitive_graph_routes": cognitive_graph_v2.get("summary", {}).get("reasoning_routes"),
        },
        "updates": updates,
        "next_required_actions": [
            "ingest_new_episode",
            "ingest_validation_results_when_available",
            "recompute_strategy_memory",
            "recompute_confidence",
            "recompute_distillation",
            "rebuild_cognitive_graph",
            "rerun_reasoning"
        ],
    }


def main() -> None:
    if len(sys.argv) not in (4, 5):
        print("Usage: python3 -m memory.continuous_learning_engine_v1 <reasoning_session.json> <universal_cognitive_graph_v2.json> <out.json> [validation_results.json]")
        sys.exit(1)

    reasoning = load_json(Path(sys.argv[1]))
    graph_v2 = load_json(Path(sys.argv[2]))
    out = Path(sys.argv[3])
    validation = load_json(Path(sys.argv[4])) if len(sys.argv) == 5 else None

    update = build_learning_update(reasoning, validation, graph_v2)
    save_json(out, update)

    print(json.dumps(update["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
