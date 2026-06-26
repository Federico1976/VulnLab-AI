#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import defaultdict


CHAIN_EDGES = {
    "entrypoint_to_bridge",
    "trust_boundary_to_bridge",
    "bridge_to_source",
    "source_to_propagation",
    "propagation_to_sink",
    "sink_to_asset",
    "validation_to_propagation",
    "validation_to_sink",
    "sanitizer_to_propagation",
    "counter_evidence_to_propagation",
}


def count_types(entities):
    counts = defaultdict(int)
    for e in entities:
        counts[e["type"]] += 1
    return counts


def edge_types(edges):
    out = defaultdict(int)
    for e in edges:
        out[e["type"]] += 1
    return out


def score_ro(entities, edges):
    counts = count_types(entities)
    ecounts = edge_types(edges)

    score = 0
    reasons = []
    blockers = []

    has_bridge = counts["BridgeMethodEntity"] > 0
    has_entrypoint = counts["EntrypointEntity"] > 0
    has_source = counts["SourceEntity"] > 0
    has_propagation = counts["PropagationEntity"] > 0
    has_sink = counts["SinkEntity"] > 0
    has_validation = counts["ValidationEvidenceEntity"] > 0
    has_counter = counts["CounterEvidenceEntity"] > 0

    if has_bridge:
        score += 10
        reasons.append("has_bridge")

    if has_entrypoint:
        score += 10
        reasons.append("has_entrypoint")

    if has_source:
        score += 15
        reasons.append("has_source")

    if has_propagation:
        score += 20
        reasons.append("has_propagation")

    if has_sink:
        score += 20
        reasons.append("has_sink")

    if ecounts["bridge_to_source"]:
        score += 10
        reasons.append("has_bridge_to_source_edge")

    if ecounts["source_to_propagation"]:
        score += 15
        reasons.append("has_source_to_propagation_edge")

    if ecounts["propagation_to_sink"]:
        score += 20
        reasons.append("has_propagation_to_sink_edge")

    if has_validation:
        score += 10
        reasons.append("has_validation_evidence")

    if has_counter:
        score -= 10
        reasons.append("has_counter_evidence_or_constraints")

    if not has_source:
        blockers.append("missing_source")
    if not has_propagation:
        blockers.append("missing_propagation")
    if not has_sink:
        blockers.append("missing_sink")
    if not ecounts["source_to_propagation"]:
        blockers.append("missing_source_to_propagation_edge")
    if not ecounts["propagation_to_sink"]:
        blockers.append("missing_propagation_to_sink_edge")

    score = max(0, min(score, 100))

    causal_chain_ready = (
        has_source
        and has_propagation
        and has_sink
        and ecounts["source_to_propagation"] > 0
        and ecounts["propagation_to_sink"] > 0
    )

    if score >= 85 and causal_chain_ready:
        readiness = "proof_planner_ready"
    elif score >= 65:
        readiness = "hypothesis_ready"
    elif score >= 45:
        readiness = "question_generator_ready"
    else:
        readiness = "needs_more_evidence"

    return {
        "score": score,
        "readiness": readiness,
        "causal_chain_ready": causal_chain_ready,
        "counts_by_type": dict(counts),
        "edge_counts_by_type": dict(ecounts),
        "blockers": blockers,
        "reasons": reasons,
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.semantic_entities.quality_scorer_v1_1 <semantic_graph.json> <out.json>")
        sys.exit(1)

    graph_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    graph = json.loads(graph_path.read_text())
    entities = graph.get("entities", [])
    edges = graph.get("edges", [])

    entities_by_ro = defaultdict(list)
    edges_by_ro = defaultdict(list)

    for e in entities:
        entities_by_ro[e["research_object_id"]].append(e)

    for edge in edges:
        rid = edge.get("research_object_id")
        if rid:
            edges_by_ro[rid].append(edge)

    results = []
    for rid, ents in entities_by_ro.items():
        q = score_ro(ents, edges_by_ro.get(rid, []))
        q["research_object_id"] = rid
        q["entity_count"] = len(ents)
        q["edge_count"] = len(edges_by_ro.get(rid, []))
        results.append(q)

    results.sort(key=lambda x: x["score"], reverse=True)

    output = {
        "schema": "vulnlab.semantic_entity_quality.v1_1",
        "input_schema": graph.get("schema"),
        "summary": {
            "proof_planner_ready": sum(1 for r in results if r["readiness"] == "proof_planner_ready"),
            "hypothesis_ready": sum(1 for r in results if r["readiness"] == "hypothesis_ready"),
            "question_generator_ready": sum(1 for r in results if r["readiness"] == "question_generator_ready"),
            "needs_more_evidence": sum(1 for r in results if r["readiness"] == "needs_more_evidence"),
            "causal_chain_ready": sum(1 for r in results if r["causal_chain_ready"]),
        },
        "research_objects": results,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "requires_chain_edges": True,
            "used_for_prioritization_only": True,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "summary": output["summary"],
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
