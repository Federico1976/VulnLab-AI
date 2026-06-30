from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

from core.semantic_entity_graph_extractor_v4 import build_graph
from core.semantic_graph_quality_gate_v4 import score_graph
from core.evidence_story_builder_v4 import build_evidence_stories
from core.dynamic_validation_planner_v4 import build_plans


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_phase_b_cognitive_v4(phase_b_dir: Path) -> Dict[str, Any]:
    ro_path = phase_b_dir / "merged_research_objects.json"

    if not ro_path.exists():
        raise FileNotFoundError(f"missing {ro_path}")

    graph_path = phase_b_dir / "semantic_entity_graph_v4.json"
    quality_path = phase_b_dir / "semantic_graph_quality_v4.json"
    stories_path = phase_b_dir / "evidence_stories_v4.json"
    plans_path = phase_b_dir / "dynamic_validation_plans_v4.json"

    graph = build_graph(ro_path)
    save_json(graph_path, graph)

    quality = score_graph(graph)
    save_json(quality_path, quality)

    stories = build_evidence_stories(graph)
    save_json(stories_path, stories)

    plans = build_plans(stories)
    save_json(plans_path, plans)

    return {
        "phase_b_dir": str(phase_b_dir),
        "candidate_only": True,
        "finding_allowed": False,
        "outputs": {
            "semantic_entity_graph_v4": str(graph_path),
            "semantic_graph_quality_v4": str(quality_path),
            "evidence_stories_v4": str(stories_path),
            "dynamic_validation_plans_v4": str(plans_path),
        },
        "summary": {
            "graph": graph.get("summary", {}),
            "quality": {
                "quality": quality.get("quality"),
                "score": quality.get("score"),
                "warnings": quality.get("warnings"),
            },
            "evidence_stories": stories.get("summary", {}),
            "dynamic_validation_plans": plans.get("summary", {}),
        },
    }


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 -m core.phase_b_cognitive_v4_runner <output/<app>/phase_b>")
        sys.exit(1)

    phase_b_dir = Path(sys.argv[1])
    result = run_phase_b_cognitive_v4(phase_b_dir)

    report_path = phase_b_dir / "phase_b_cognitive_v4_report.json"
    save_json(report_path, result)

    print(json.dumps({
        "report": str(report_path),
        "candidate_only": result["candidate_only"],
        "finding_allowed": result["finding_allowed"],
        "summary": result["summary"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
