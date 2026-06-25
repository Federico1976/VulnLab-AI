#!/usr/bin/env python3
import json, sys
from pathlib import Path

TARGETS = [
    "output/base_449df7fd46",
    "output/vienna_lab",
    "output/seek_lab",
    "output/linktree_lab",
    "output/mashop_lab",
]

def load_json(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def quality(row):
    stories = row["evidence_v2_stories"]
    high = row["evidence_v2_high"]
    medium = row["evidence_v2_medium"]
    semantic_objects = row["semantic_objects"]
    avg_conf = row["avg_node_confidence"]

    if high >= 5 and semantic_objects >= 5:
        return "causal_evidence_stories_ready_for_reachability"

    if stories > 0 and (high > 0 or medium > 0):
        return "strong_semantic_objects"

    if semantic_objects > 0 or avg_conf >= 0.25:
        return "weak_capabilities"

    return "raw_signals_only"

def next_action(q):
    if q == "causal_evidence_stories_ready_for_reachability":
        return "run entrypoint/reachability correlation against top stories"
    if q == "strong_semantic_objects":
        return "improve native provider/method correlation"
    if q == "weak_capabilities":
        return "promote raw capability signals into semantic objects"
    return "improve artifact extraction and classification"

def row_for(target):
    t = Path(target)

    artifacts = load_json(t / "universal_runtime_artifacts.json")
    cls = load_json(t / "runtime_artifact_classification.json")
    kg = load_json(t / "semantic_runtime_kg.json")
    conf = load_json(t / "semantic_runtime_kg_confidence.json")
    ev2 = load_json(t / "semantic_evidence_graph_v2.json")

    cls_summary = cls.get("summary", {})
    kg_summary = kg.get("summary", {})
    conf_summary = conf.get("confidence_summary", {})
    ev2_summary = ev2.get("summary", {})

    semantic_objects = (
        cls_summary.get("builtin_channels", 0)
        + cls_summary.get("plugin_channels", 0)
        + cls_summary.get("pigeon_rpc", 0)
        + cls_summary.get("plugin_registrations", 0)
    )

    story_conf = ev2_summary.get("stories_by_confidence", {})

    row = {
        "target": str(t),
        "artifacts_total": artifacts.get("total_artifacts", 0),
        "builtin_channels": cls_summary.get("builtin_channels", 0),
        "pigeon_rpc": cls_summary.get("pigeon_rpc", 0),
        "plugin_registrations": cls_summary.get("plugin_registrations", 0),
        "native_capabilities": cls_summary.get("native_capabilities", 0),
        "semantic_objects": semantic_objects,
        "kg_nodes": kg_summary.get("nodes", 0),
        "kg_edges": kg_summary.get("edges", 0),
        "avg_node_confidence": conf_summary.get("average_node_confidence", 0),
        "avg_edge_confidence": conf_summary.get("average_edge_confidence", 0),
        "evidence_v2_stories": ev2_summary.get("stories", 0),
        "evidence_v2_high": story_conf.get("high", 0),
        "evidence_v2_medium": story_conf.get("medium", 0),
        "evidence_v2_low": story_conf.get("low", 0),
        "capability_families": ev2_summary.get("capability_families", []),
        "source_kinds": ev2_summary.get("source_kinds", []),
    }

    row["semantic_story_quality"] = quality(row)
    row["next_required_action"] = next_action(row["semantic_story_quality"])

    return row

def build(targets):
    rows = [row_for(t) for t in targets if Path(t).exists()]

    summary = {
        "targets": len(rows),
        "quality_distribution": {
            q: sum(1 for r in rows if r["semantic_story_quality"] == q)
            for q in [
                "raw_signals_only",
                "weak_capabilities",
                "strong_semantic_objects",
                "causal_evidence_stories_ready_for_reachability",
            ]
        },
        "ready_for_reachability": [
            r["target"] for r in rows
            if r["semantic_story_quality"] == "causal_evidence_stories_ready_for_reachability"
        ],
    }

    out = {
        "model": "universal_coverage_matrix_v1",
        "summary": summary,
        "rows": rows,
    }

    out_path = Path("output/universal_coverage_matrix.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"[+] wrote {out_path}")

if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else TARGETS
    build(targets)
