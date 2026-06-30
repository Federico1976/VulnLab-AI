from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from memory.universal_cognitive_graph_v2 import build_v2
from memory.reasoning_executor_v1 import build_reasoning_session
from memory.continuous_learning_engine_v1 import build_learning_update
from memory.knowledge_merge_engine_v1 import merge_external
from memory.meta_strategy_memory_v1 import build_meta


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main() -> None:
    if len(sys.argv) not in (6, 7):
        print(
            "Usage: python3 -m memory.cognitive_brain_runner_v1 "
            "<phase_b_dir> <universal_cognitive_graph_v1.json> "
            "<external_knowledge.json> <validation_results.json|none> <output_dir> [prefix]"
        )
        sys.exit(1)

    phase_b_dir = Path(sys.argv[1])
    graph_v1_path = Path(sys.argv[2])
    external_path = Path(sys.argv[3])
    validation_arg = sys.argv[4]
    output_dir = Path(sys.argv[5])
    prefix = sys.argv[6] if len(sys.argv) == 7 else phase_b_dir.parent.name

    semantic_graph_path = phase_b_dir / "semantic_entity_graph_v4.json"

    semantic_graph = load_json(semantic_graph_path)
    graph_v1 = load_json(graph_v1_path)
    external = load_json(external_path)
    validation = None if validation_arg == "none" else load_json(Path(validation_arg))

    graph_v2 = build_v2(graph_v1)
    reasoning = build_reasoning_session(semantic_graph, graph_v1)
    learning = build_learning_update(reasoning, validation, graph_v2)
    merge = merge_external(external, graph_v2)
    meta = build_meta(graph_v2, learning, merge)

    output_dir.mkdir(parents=True, exist_ok=True)

    graph_v2_path = output_dir / f"{prefix}_universal_cognitive_graph_v2.json"
    reasoning_path = output_dir / f"{prefix}_reasoning_session_v1.json"
    learning_path = output_dir / f"{prefix}_continuous_learning_update_v1.json"
    merge_path = output_dir / f"{prefix}_knowledge_merge_v1.json"
    meta_path = output_dir / f"{prefix}_meta_strategy_memory_v1.json"
    report_path = output_dir / f"{prefix}_cognitive_brain_report_v1.json"

    save_json(graph_v2_path, graph_v2)
    save_json(reasoning_path, reasoning)
    save_json(learning_path, learning)
    save_json(merge_path, merge)
    save_json(meta_path, meta)

    report = {
        "schema": "cognitive_brain_runner_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "phase_b_dir": str(phase_b_dir),
        "outputs": {
            "universal_cognitive_graph_v2": str(graph_v2_path),
            "reasoning_session_v1": str(reasoning_path),
            "continuous_learning_update_v1": str(learning_path),
            "knowledge_merge_v1": str(merge_path),
            "meta_strategy_memory_v1": str(meta_path),
        },
        "summary": {
            "graph_v2": graph_v2.get("summary", {}),
            "reasoning": reasoning.get("summary", {}),
            "learning": learning.get("summary", {}),
            "knowledge_merge": merge.get("summary", {}),
            "meta_strategy": meta.get("summary", {}),
        },
    }

    save_json(report_path, report)
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
