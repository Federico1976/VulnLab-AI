#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_existing(base: Path, candidates: List[str]) -> Path | None:
    for c in candidates:
        p = base / c
        if p.exists():
            return p

    root = base.parent if base.name == "phase_b" else base

    semantic_patterns = [
        "*semantic_entity_graph_v4.json",
        "*semantic_entity_graph*.json",
        "*semantic*graph*.json",
    ]

    research_patterns = [
        "*merged_research_objects.json",
        "*fallback_research_objects.json",
        "*fileprovider_research_objects.json",
        "*research*object*.json",
    ]

    patterns = semantic_patterns if any("semantic" in c for c in candidates) else research_patterns

    matches = []
    for pat in patterns:
        matches.extend(root.rglob(pat))

    matches = [m for m in matches if m.is_file()]
    if not matches:
        return None

    def score(path: Path) -> int:
        name = path.name
        val = 0
        if "semantic_entity_graph_v4" in name:
            val += 100
        if "merged_research_objects" in name:
            val += 100
        if "phase_b" in str(path):
            val += 20
        return val

    return sorted(matches, key=score, reverse=True)[0]


def run_one_apk(apk_output_dir: Path, cognitive_graph: Path) -> Dict[str, Any]:
    gen = apk_output_dir / "generalization"
    phase_b = apk_output_dir / "phase_b"
    gen.mkdir(parents=True, exist_ok=True)

    semantic_graph = find_existing(phase_b, [
        "semantic_entity_graph_v4.json",
        "semantic_entity_graph.json",
    ])

    research_objects = find_existing(phase_b, [
        "merged_research_objects.json",
        "fallback_research_objects.json",
        "fileprovider_research_objects.json",
    ])

    if not semantic_graph and research_objects:
        target_semantic_graph = phase_b / "semantic_entity_graph_v4.json"

        subprocess.run([
            sys.executable, "-m", "phase_b.semantic_entities.entity_builder_v3",
            str(research_objects),
            str(target_semantic_graph),
        ], check=False)

        semantic_graph = find_existing(phase_b, [
            "semantic_entity_graph_v4.json",
            "semantic_entity_graph.json",
            "semantic_entities.json",
            "semantic_graph_quality_v4.json",
        ])

    if not semantic_graph:
        return {
            "apk_output_dir": str(apk_output_dir),
            "status": "skipped",
            "reason": "missing_semantic_graph",
            "research_objects": str(research_objects) if research_objects else None,
        }

    shape_matches = gen / "semantic_shape_matches_v1.json"
    shape_context = gen / "reasoning_shape_context_v1.json"
    reasoning_session = gen / "reasoning_session_v2.json"
    memory_guard = gen / "incremental_memory_regression_guard_v1.json"

    cmd = [
        sys.executable, "-m", "generalization.semantic_shape_matcher",
        str(semantic_graph),
        "--out", str(shape_matches),
    ]

    if research_objects:
        cmd.extend(["--research-objects", str(research_objects)])

    subprocess.run(cmd, check=True)

    subprocess.run([
        sys.executable, "-m", "generalization.shape_reasoning_bridge",
        str(shape_matches),
        "--out", str(shape_context),
    ], check=True)

    subprocess.run([
        sys.executable, "-m", "memory.reasoning_executor_v2",
        str(semantic_graph),
        str(cognitive_graph),
        str(reasoning_session),
        str(shape_context),
    ], check=True)

    subprocess.run([
        sys.executable, "-m", "generalization.incremental_memory_updater",
        str(reasoning_session),
        "--memory", "output/generalization/incremental_memory_snapshot_v1.json",
        "--out", "output/generalization/incremental_memory_snapshot_v1.json",
        "--guard-out", str(memory_guard),
    ], check=True)

    sm = load_json(shape_matches)
    rs = load_json(reasoning_session)
    guard = load_json(memory_guard)

    summary = sm.get("summary", {})
    rsum = rs.get("summary", {})

    primary_shape = rsum.get("primary_shape_id")
    top_conf = rsum.get("top_shape_adjusted_confidence")

    precision_proxy = 0.0
    if primary_shape and guard.get("passed"):
        precision_proxy = min(max((top_conf or 0.0), 0.0), 1.0)

    counter_count = 0
    for d in rs.get("decisions", []):
        counter_count += len(d.get("counterevidence_selection", []))

    return {
        "apk_output_dir": str(apk_output_dir),
        "status": "completed",
        "semantic_graph": str(semantic_graph),
        "research_objects": str(research_objects) if research_objects else None,
        "shape_matches": str(shape_matches),
        "reasoning_session": str(reasoning_session),
        "primary_shape_id": primary_shape,
        "top_shape_adjusted_confidence": top_conf,
        "shape_matches_count": summary.get("matches", 0),
        "strong_shape_matches": summary.get("strong_matches", 0),
        "reasoning_decisions": rsum.get("decisions", 0),
        "counterevidence_items": counter_count,
        "memory_guard_passed": guard.get("passed", False),
        "precision_proxy": precision_proxy,
        "candidate_only": True,
        "finding_allowed": False,
    }


def build_campaign_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    completed = [r for r in results if r.get("status") == "completed"]
    skipped = [r for r in results if r.get("status") != "completed"]

    primary_shapes = {}
    for r in completed:
        s = r.get("primary_shape_id") or "none"
        primary_shapes[s] = primary_shapes.get(s, 0) + 1

    avg_precision_proxy = (
        sum(r.get("precision_proxy", 0.0) for r in completed) / len(completed)
        if completed else 0.0
    )

    avg_confidence = (
        sum(r.get("top_shape_adjusted_confidence") or 0.0 for r in completed) / len(completed)
        if completed else 0.0
    )

    return {
        "schema_version": "campaign_training_report.v1",
        "created_at": int(time.time()),
        "summary": {
            "total": len(results),
            "completed": len(completed),
            "skipped": len(skipped),
            "avg_precision_proxy": round(avg_precision_proxy, 3),
            "avg_shape_adjusted_confidence": round(avg_confidence, 3),
            "distinct_primary_shapes": len(primary_shapes),
            "primary_shape_distribution": primary_shapes,
            "all_candidate_only": all(r.get("candidate_only") is True for r in completed),
            "no_findings_allowed": all(r.get("finding_allowed") is False for r in completed),
            "all_memory_guards_passed": all(r.get("memory_guard_passed") is True for r in completed),
        },
        "results": results,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Campaign Training Runner v1")
    parser.add_argument("--apk-output-dirs", nargs="+", required=True)
    parser.add_argument("--cognitive-graph", required=True)
    parser.add_argument("--out", required=True)

    args = parser.parse_args()

    cognitive_graph = Path(args.cognitive_graph)
    results = []

    for item in args.apk_output_dirs:
        results.append(run_one_apk(Path(item), cognitive_graph))

    report = build_campaign_report(results)
    save_json(args.out, report)

    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
