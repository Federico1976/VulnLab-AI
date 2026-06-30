from __future__ import annotations

import json
import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{h}"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def infer_apk_name(report_path: Path) -> str:
    try:
        return report_path.parts[-3]
    except Exception:
        return report_path.stem


def build_episode(report_path: Path) -> Dict[str, Any]:
    report = load_json(report_path)
    apk = infer_apk_name(report_path)

    summary = report.get("summary", {})
    graph = summary.get("graph", {})
    quality = summary.get("quality", {})
    stories = summary.get("evidence_stories", {})
    plans = summary.get("dynamic_validation_plans", {})

    episode_id = stable_id(
        "EP1",
        apk,
        graph.get("research_objects"),
        graph.get("entities"),
        graph.get("relations"),
    )

    return {
        "episode_id": episode_id,
        "apk": apk,
        "candidate_only": True,
        "finding_allowed": False,
        "episode_type": "static_to_validation_planning_run",
        "inputs": {
            "phase_b_report": str(report_path),
        },
        "observed_architecture": {
            "research_objects": graph.get("research_objects", 0),
            "entities": graph.get("entities", 0),
            "relations": graph.get("relations", 0),
            "entities_per_ro": graph.get("entities_per_research_object", 0),
            "relations_per_ro": graph.get("relations_per_research_object", 0),
            "by_type": graph.get("by_type", {}),
            "by_runtime": graph.get("by_runtime", {}),
            "by_relation": graph.get("by_relation", {}),
        },
        "reasoning_outputs": {
            "quality": quality,
            "stories": stories,
            "plans": plans,
        },
        "experience_summary": {
            "dominant_runtime": dominant_key(graph.get("by_runtime", {})),
            "dominant_entity_type": dominant_key(graph.get("by_type", {})),
            "dominant_relation_type": dominant_key(graph.get("by_relation", {})),
            "semantic_focus": semantic_focus(graph.get("by_type", {}), graph.get("by_relation", {})),
            "story_uncertainty": stories.get("by_uncertainty", {}),
            "main_experiment": dominant_key(plans.get("by_experiment_type", {})),
        },
        "learning_status": {
            "dynamic_validation_performed": False,
            "proof_evaluation_performed": False,
            "outcome_known": False,
            "usable_for_strategy_training": True,
            "usable_for_failure_training": False,
            "usable_for_counterevidence_training": False,
        },
    }


def semantic_focus(by_type: Dict[str, Any], by_relation: Dict[str, Any]) -> str:
    bridge = by_type.get("BridgeEntity", 0)
    sink = by_type.get("SinkEntity", 0)
    asset = by_type.get("AssetEntity", 0)
    entry = by_type.get("EntrypointEntity", 0)

    may_reach = by_relation.get("may_reach", 0)
    touches_asset = by_relation.get("touches_asset", 0)

    if bridge and sink and may_reach:
        return "bridge_to_sink_focus"

    if entry and asset and touches_asset:
        return "entrypoint_asset_boundary_focus"

    if sink:
        return "sink_reachability_focus"

    if asset:
        return "asset_boundary_focus"

    return "generic_runtime_focus"


def dominant_key(d: Dict[str, Any]) -> str:
    if not d:
        return "unknown"
    return max(d.items(), key=lambda x: x[1])[0]


def build_memory(report_paths: List[Path]) -> Dict[str, Any]:
    episodes = [build_episode(p) for p in report_paths]

    by_runtime: Dict[str, int] = {}
    by_experiment: Dict[str, int] = {}
    by_quality: Dict[str, int] = {}

    for e in episodes:
        rt = e["experience_summary"]["dominant_runtime"]
        ex = e["experience_summary"]["main_experiment"]
        q = e["reasoning_outputs"]["quality"].get("quality", "unknown")

        by_runtime[rt] = by_runtime.get(rt, 0) + 1
        by_experiment[ex] = by_experiment.get(ex, 0) + 1
        by_quality[q] = by_quality.get(q, 0) + 1

    return {
        "schema": "investigation_experience_memory_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "episodic memory of APK investigations for continuous learning",
        "summary": {
            "episodes": len(episodes),
            "by_dominant_runtime": by_runtime,
            "by_main_experiment": by_experiment,
            "by_quality": by_quality,
        },
        "episodes": episodes,
    }


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python3 -m memory.investigation_experience_memory_v1 <experience_memory.json> <phase_b_cognitive_v4_report.json> [...]")
        sys.exit(1)

    out = Path(sys.argv[1])
    reports = [Path(x) for x in sys.argv[2:]]

    memory = build_memory(reports)
    save_json(out, memory)

    print(json.dumps(memory["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
