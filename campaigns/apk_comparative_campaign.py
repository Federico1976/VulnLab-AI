#!/usr/bin/env python3
import json, sys
from pathlib import Path

DEFAULT_TARGETS = [
    "output/base_449df7fd46",
    "output/vienna_lab",
    "output/seek_lab",
    "output/linktree_lab",
    "output/mashop_lab",
]

def load(p):
    p = Path(p)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def row(t):
    target = Path(t)

    matrix = load("output/universal_coverage_matrix.json")
    ev2 = load(target / "semantic_evidence_graph_v2.json")
    reach = load(target / "universal_reachability_v2.json")
    validation = load(target / "dynamic_validation_plans.json")
    disclosure = load(target / "responsible_disclosure_candidates.json")
    reasoning = load(target / "reasoning_context.json")
    bridges = load(target / "universal_semantic_bridges.json")

    coverage_row = {}
    for r in matrix.get("rows", []):
        if r.get("target") == str(target) or Path(r.get("target", "")).name == target.name:
            coverage_row = r
            break

    evs = ev2.get("summary", {})
    rs = reach.get("summary", {})
    vs = validation.get("summary", {})
    ds = disclosure.get("summary", {})
    bs = bridges.get("summary", {})

    return {
        "target": str(target),
        "semantic_story_quality": coverage_row.get("semantic_story_quality"),
        "bridge_objects": bs.get("bridge_objects", 0),
        "bridge_types": bs.get("bridges", []),
        "stories": evs.get("stories", 0),
        "stories_high": evs.get("stories_by_confidence", {}).get("high", 0),
        "stories_medium": evs.get("stories_by_confidence", {}).get("medium", 0),
        "stories_low": evs.get("stories_by_confidence", {}).get("low", 0),
        "reachability_paths": rs.get("paths", 0),
        "reachability_status": rs.get("by_status", {}),
        "validation_plans": vs.get("plans", 0),
        "disclosure_ready": ds.get("disclosure_ready", 0),
        "reasoning_stories_exported": len(reasoning.get("top_evidence_stories", [])),
        "known_limitations": [
            "reachability_predictive_not_proven",
            "confidence_still_flat_for_non_flutter",
            "fixed_story_pruning_can_make_outputs_uniform"
        ],
    }

def grade(r):
    if r["stories_high"] >= 10:
        return "A_ready_for_reachability_focus"
    if r["stories_medium"] >= 25:
        return "B_strong_semantic_candidate"
    if r["stories"] > 0:
        return "C_semantic_candidate_needs_calibration"
    return "D_raw_or_missing"

def build(targets):
    rows = [row(t) for t in targets if Path(t).exists()]
    for r in rows:
        r["comparative_grade"] = grade(r)

    out = {
        "model": "apk_comparative_campaign_v1",
        "principle": "compare APKs by semantic evidence quality, not raw finding count",
        "rows": rows,
        "summary": {
            "targets": len(rows),
            "grades": {
                g: sum(1 for r in rows if r["comparative_grade"] == g)
                for g in sorted(set(r["comparative_grade"] for r in rows))
            },
            "total_stories": sum(r["stories"] for r in rows),
            "total_high_stories": sum(r["stories_high"] for r in rows),
            "total_validation_plans": sum(r["validation_plans"] for r in rows),
            "disclosure_ready": sum(r["disclosure_ready"] for r in rows),
        }
    }

    p = Path("output/apk_comparative_campaign.json")
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {p}")

if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TARGETS
    build(targets)
