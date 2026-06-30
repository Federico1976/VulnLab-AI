from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from memory.cognitive_brain_runner_v1 import load_json, save_json
from memory.reasoning_executor_v1 import build_reasoning_session
from memory.multi_hypothesis_ranker_v1 import build_ranker
from memory.incremental_memory_updater_v1 import apply_update, empty_state


def find_phase_b_dirs(root: Path) -> List[Path]:
    return sorted(
        p for p in root.glob("*/phase_b")
        if (p / "semantic_entity_graph_v4.json").exists()
    )


def run_training(root: Path, cognitive_graph_path: Path, brain_state_path: Path, out_dir: Path) -> Dict[str, Any]:
    cognitive_graph = load_json(cognitive_graph_path)
    phase_dirs = find_phase_b_dirs(root)

    state = load_json(brain_state_path) if brain_state_path.exists() else empty_state()

    runs = []

    for d in phase_dirs:
        app = d.parent.name
        semantic_graph = load_json(d / "semantic_entity_graph_v4.json")

        reasoning = build_reasoning_session(semantic_graph, cognitive_graph)
        ranker = build_ranker(reasoning)

        app_out = out_dir / app
        app_out.mkdir(parents=True, exist_ok=True)

        reasoning_path = app_out / "reasoning_session_v1.json"
        ranker_path = app_out / "multi_hypothesis_ranker_v1.json"

        save_json(reasoning_path, reasoning)
        save_json(ranker_path, ranker)

        runs.append({
            "app": app,
            "phase_b_dir": str(d),
            "reasoning": reasoning.get("summary", {}),
            "ranker": ranker.get("summary", {}),
            "outputs": {
                "reasoning_session_v1": str(reasoning_path),
                "multi_hypothesis_ranker_v1": str(ranker_path),
            }
        })

        apply_update(state, f"campaign_training:{app}", [reasoning_path, ranker_path])

    save_json(brain_state_path, state)

    by_top_shape: Dict[str, int] = {}
    by_top_rank: Dict[str, int] = {}

    for r in runs:
        ts = r["ranker"].get("top_shape", "none")
        tr = r["ranker"].get("top_rank", "none")
        by_top_shape[ts] = by_top_shape.get(ts, 0) + 1
        by_top_rank[tr] = by_top_rank.get(tr, 0) + 1

    report = {
        "schema": "campaign_training_runner_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "summary": {
            "apps": len(runs),
            "by_top_shape": by_top_shape,
            "by_top_rank": by_top_rank,
            "brain_state_version": state.get("version"),
            "brain_counters": state.get("counters"),
        },
        "runs": runs,
    }

    save_json(out_dir / "campaign_training_report_v1.json", report)
    return report


def main() -> None:
    if len(sys.argv) != 5:
        print("Usage: python3 -m memory.campaign_training_runner_v1 <output_root> <universal_cognitive_graph_v1.json> <brain_state.json> <out_dir>")
        sys.exit(1)

    root = Path(sys.argv[1])
    graph = Path(sys.argv[2])
    state = Path(sys.argv[3])
    out_dir = Path(sys.argv[4])

    report = run_training(root, graph, state, out_dir)
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
