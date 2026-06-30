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


def build_meta(strategy_graph_v2: Dict[str, Any], learning_update: Dict[str, Any], knowledge_merge: Dict[str, Any]) -> Dict[str, Any]:
    routes = strategy_graph_v2.get("reasoning_routes", [])
    updates = learning_update.get("updates", [])
    external_links = knowledge_merge.get("links", [])

    meta = [
        {
            "meta_strategy_id": "META-STOP-BEFORE-PROOF",
            "name": "stop_before_proof",
            "candidate_only": True,
            "finding_allowed": False,
            "principle": "Never promote a candidate story to a finding before dynamic validation and proof evaluation.",
            "applies_when": ["any_candidate_story", "any_strategy_shape"],
            "action": "keep_finding_allowed_false",
        },
        {
            "meta_strategy_id": "META-SEEK-COUNTEREVIDENCE-FIRST",
            "name": "seek_counterevidence_first",
            "candidate_only": True,
            "finding_allowed": False,
            "principle": "Before increasing confidence, actively seek reachability, control and flow counterevidence.",
            "applies_when": ["strategy_has_failure_or_counterevidence_history"],
            "action": "prioritize_counterevidence_checks",
        },
        {
            "meta_strategy_id": "META-REASON-LEARN-REASON",
            "name": "reason_learn_reason_loop",
            "candidate_only": True,
            "finding_allowed": False,
            "principle": "After each run or validation result, update memory and rerun reasoning with calibrated confidence.",
            "applies_when": ["new_episode", "new_validation_result", "new_external_knowledge"],
            "action": "trigger_continuous_learning_update",
        }
    ]

    return {
        "schema": "meta_strategy_memory_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "general reasoning principles controlling strategy selection, stopping, learning and escalation",
        "summary": {
            "meta_strategies": len(meta),
            "reasoning_routes_seen": len(routes),
            "learning_updates_seen": len(updates),
            "external_links_seen": len(external_links),
        },
        "meta_strategies": meta,
    }


def main() -> None:
    if len(sys.argv) != 5:
        print("Usage: python3 -m memory.meta_strategy_memory_v1 <universal_cognitive_graph_v2.json> <continuous_learning_update_v1.json> <knowledge_merge_v1.json> <meta_strategy_memory_v1.json>")
        sys.exit(1)

    graph = load_json(Path(sys.argv[1]))
    learning = load_json(Path(sys.argv[2]))
    merge = load_json(Path(sys.argv[3]))
    out = Path(sys.argv[4])

    meta = build_meta(graph, learning, merge)
    save_json(out, meta)

    print(json.dumps(meta["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
