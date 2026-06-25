#!/usr/bin/env python3
import json, sys
from pathlib import Path

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def build(target_dir):
    t = Path(target_dir).resolve()

    coverage = load("output/universal_coverage_matrix.json")
    ev2 = load(t / "semantic_evidence_graph_v2.json")
    conf = load(t / "semantic_runtime_kg_confidence.json")

    row = None
    for r in coverage.get("rows", []):
        if Path(r["target"]).name == t.name or r["target"] == str(t):
            row = r
            break

    stories = ev2.get("stories", [])
    top = [
        s for s in stories
        if s.get("confidence_label") in ("very_high", "high", "medium")
    ][:25]

    ctx = {
        "target": str(t),
        "purpose": "LLM reasoning context for defensive APK hunting / responsible disclosure",
        "rules": [
            "candidate evidence only",
            "do not claim vulnerability without reachability proof",
            "do not claim vulnerability without dynamic validation",
            "reason from evidence graph, not raw strings"
        ],
        "coverage_row": row,
        "confidence_summary": conf.get("confidence_summary", {}),
        "top_evidence_stories": top,
        "questions_for_llm": [
            "Which stories are ready for entrypoint correlation?",
            "Which require native implementation confirmation first?",
            "Which dynamic validation plan is safest and most useful?",
            "What evidence is still missing before responsible disclosure?"
        ]
    }

    out = t / "reasoning_context.json"
    out.write_text(json.dumps(ctx, indent=2), encoding="utf-8")

    print(json.dumps({
        "target": str(t),
        "stories_exported": len(top),
        "semantic_story_quality": row.get("semantic_story_quality") if row else None
    }, indent=2))
    print(f"[+] wrote {out}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m reasoning_api.export_reasoning_context output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
