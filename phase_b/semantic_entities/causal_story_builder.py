#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import defaultdict


ORDER = [
    "EntrypointEntity",
    "BridgeMethodEntity",
    "TrustBoundaryEntity",
    "SourceEntity",
    "PropagationEntity",
    "SinkEntity",
    "AssetEntity",
    "SanitizerEntity",
    "ValidationEvidenceEntity",
    "CounterEvidenceEntity",
]


def compact_entity(e):
    return {
        "id": e["id"],
        "type": e["type"],
        "role": e.get("role"),
        "candidate_id": e.get("candidate_id"),
        "source_field": e.get("source_field"),
        "confidence": e.get("confidence"),
        "evidence": e.get("evidence"),
    }


def build_story(ro_id, candidate_id, entities):
    by_type = defaultdict(list)
    for e in entities:
        by_type[e["type"]].append(compact_entity(e))

    missing = []
    for required in ["SourceEntity", "PropagationEntity", "SinkEntity"]:
        if not by_type.get(required):
            missing.append(required)

    if missing:
        readiness = "incomplete"
    elif by_type.get("ValidationEvidenceEntity"):
        readiness = "proof_planner_ready"
    else:
        readiness = "hypothesis_ready"

    story = {
        "story_id": f"CS-{ro_id}-{candidate_id or 'ro'}",
        "research_object_id": ro_id,
        "candidate_id": candidate_id,
        "readiness": readiness,
        "missing_core_entities": missing,
        "causal_sequence": {},
        "summary": {
            "has_entrypoint": bool(by_type.get("EntrypointEntity")),
            "has_bridge": bool(by_type.get("BridgeMethodEntity")),
            "has_source": bool(by_type.get("SourceEntity")),
            "has_propagation": bool(by_type.get("PropagationEntity")),
            "has_sink": bool(by_type.get("SinkEntity")),
            "has_asset": bool(by_type.get("AssetEntity")),
            "has_sanitizer": bool(by_type.get("SanitizerEntity")),
            "has_validation": bool(by_type.get("ValidationEvidenceEntity")),
            "has_counter_evidence": bool(by_type.get("CounterEvidenceEntity")),
        },
    }

    for t in ORDER:
        if by_type.get(t):
            story["causal_sequence"][t] = by_type[t]

    return story


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.semantic_entities.causal_story_builder <semantic_graph.json> <out.json>")
        sys.exit(1)

    graph_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    graph = json.loads(graph_path.read_text())
    entities = graph.get("entities", [])

    by_ro_candidate = defaultdict(list)

    for e in entities:
        ro_id = e["research_object_id"]
        candidate_id = e.get("candidate_id") or "__research_object_level__"
        by_ro_candidate[(ro_id, candidate_id)].append(e)

    stories = []
    for (ro_id, candidate_id), ents in by_ro_candidate.items():
        cid = None if candidate_id == "__research_object_level__" else candidate_id
        stories.append(build_story(ro_id, cid, ents))

    stories.sort(key=lambda s: (
        s["readiness"] != "proof_planner_ready",
        s["readiness"] != "hypothesis_ready",
        s["research_object_id"],
        s["candidate_id"] or "",
    ))

    output = {
        "schema": "vulnlab.causal_stories.v1",
        "input_schema": graph.get("schema"),
        "story_count": len(stories),
        "summary": {
            "proof_planner_ready": sum(1 for s in stories if s["readiness"] == "proof_planner_ready"),
            "hypothesis_ready": sum(1 for s in stories if s["readiness"] == "hypothesis_ready"),
            "incomplete": sum(1 for s in stories if s["readiness"] == "incomplete"),
        },
        "stories": stories,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "used_as_compact_reasoning_input": True,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "story_count": output["story_count"],
        "summary": output["summary"],
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
