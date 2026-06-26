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


CORE = {
    "SourceEntity",
    "PropagationEntity",
    "SinkEntity",
}


def compact_entity(e):
    ev = e.get("evidence")

    return {
        "id": e.get("id"),
        "type": e.get("type"),
        "role": e.get("role"),
        "candidate_id": e.get("candidate_id"),
        "source_field": e.get("source_field"),
        "confidence": e.get("confidence"),
        "evidence": ev,
    }


def summarize_types(entities):
    out = defaultdict(int)
    for e in entities:
        out[e["type"]] += 1
    return dict(out)


def build_story(ro_id, candidate_id, candidate_entities, ro_context_entities):
    by_type = defaultdict(list)

    for e in candidate_entities:
        by_type[e["type"]].append(compact_entity(e))

    missing = [t for t in CORE if not by_type.get(t)]

    has_validation = bool(by_type.get("ValidationEvidenceEntity"))
    has_counter = bool(by_type.get("CounterEvidenceEntity"))

    if missing:
        readiness = "incomplete"
    elif has_validation and not has_counter:
        readiness = "proof_planner_ready"
    elif has_validation and has_counter:
        readiness = "proof_planner_ready_with_constraints"
    else:
        readiness = "hypothesis_ready"

    story = {
        "story_id": f"CS-{ro_id}-{candidate_id}",
        "research_object_id": ro_id,
        "candidate_id": candidate_id,
        "readiness": readiness,
        "missing_core_entities": missing,
        "candidate_entity_count": len(candidate_entities),
        "research_object_context_entity_count": len(ro_context_entities),
        "candidate_counts_by_type": summarize_types(candidate_entities),
        "research_object_context_counts_by_type": summarize_types(ro_context_entities),
        "summary": {
            "has_entrypoint": bool(by_type.get("EntrypointEntity")),
            "has_bridge": bool(by_type.get("BridgeMethodEntity")),
            "has_trust_boundary": bool(by_type.get("TrustBoundaryEntity")),
            "has_source": bool(by_type.get("SourceEntity")),
            "has_propagation": bool(by_type.get("PropagationEntity")),
            "has_sink": bool(by_type.get("SinkEntity")),
            "has_asset": bool(by_type.get("AssetEntity")),
            "has_sanitizer": bool(by_type.get("SanitizerEntity")),
            "has_validation": has_validation,
            "has_counter_evidence": has_counter,
        },
        "causal_sequence": {},
        "research_object_context": [compact_entity(e) for e in ro_context_entities],
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "requires_dynamic_validation_before_disclosure": True,
        }
    }

    for t in ORDER:
        if by_type.get(t):
            story["causal_sequence"][t] = by_type[t]

    return story


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.semantic_entities.causal_story_builder_v1_1 <semantic_graph.json> <out.json>")
        sys.exit(1)

    graph_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    graph = json.loads(graph_path.read_text())
    entities = graph.get("entities", [])

    ro_context = defaultdict(list)
    by_ro_candidate = defaultdict(list)

    for e in entities:
        ro_id = e.get("research_object_id")
        cid = e.get("candidate_id")

        if not ro_id:
            continue

        if cid:
            by_ro_candidate[(ro_id, cid)].append(e)
        else:
            ro_context[ro_id].append(e)

    stories = []

    for (ro_id, cid), ents in by_ro_candidate.items():
        story = build_story(ro_id, cid, ents, ro_context.get(ro_id, []))

        # Regola chiave: il Proof Planner non deve ricevere storie senza core chain.
        if story["readiness"] != "incomplete":
            stories.append(story)

    stories.sort(key=lambda s: (
        s["readiness"] != "proof_planner_ready",
        s["readiness"] != "proof_planner_ready_with_constraints",
        s["readiness"] != "hypothesis_ready",
        s["research_object_id"],
        s["candidate_id"],
    ))

    output = {
        "schema": "vulnlab.causal_stories.v1_1",
        "input_schema": graph.get("schema"),
        "story_count": len(stories),
        "summary": {
            "proof_planner_ready": sum(1 for s in stories if s["readiness"] == "proof_planner_ready"),
            "proof_planner_ready_with_constraints": sum(1 for s in stories if s["readiness"] == "proof_planner_ready_with_constraints"),
            "hypothesis_ready": sum(1 for s in stories if s["readiness"] == "hypothesis_ready"),
            "incomplete_filtered_out": len(by_ro_candidate) - len(stories),
            "research_object_context_groups": len(ro_context),
        },
        "stories": stories,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "only_candidate_level_causal_stories": True,
            "research_object_level_entities_attached_as_context": True,
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
