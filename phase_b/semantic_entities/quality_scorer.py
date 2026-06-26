#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import defaultdict


CORE_TYPES = {
    "BridgeMethodEntity",
    "SourceEntity",
    "SinkEntity",
    "PropagationEntity",
}

SUPPORT_TYPES = {
    "EntrypointEntity",
    "TrustBoundaryEntity",
    "AssetEntity",
    "SanitizerEntity",
    "ValidationEvidenceEntity",
    "CounterEvidenceEntity",
}


def score_research_object(entities):
    counts = defaultdict(int)
    for e in entities:
        counts[e["type"]] += 1

    score = 0
    reasons = []

    if counts["BridgeMethodEntity"]:
        score += 20
        reasons.append("has_bridge_method_entity")

    if counts["SourceEntity"]:
        score += 20
        reasons.append("has_source_entity")

    if counts["SinkEntity"]:
        score += 20
        reasons.append("has_sink_entity")

    if counts["PropagationEntity"]:
        score += 25
        reasons.append("has_propagation_entity")

    if counts["EntrypointEntity"]:
        score += 10
        reasons.append("has_entrypoint_entity")

    if counts["TrustBoundaryEntity"]:
        score += 10
        reasons.append("has_trust_boundary_entity")

    if counts["ValidationEvidenceEntity"]:
        score += 10
        reasons.append("has_validation_evidence")

    if counts["CounterEvidenceEntity"]:
        score -= 10
        reasons.append("has_counter_evidence_or_constraints")

    score = max(0, min(score, 100))

    missing_core = [t for t in CORE_TYPES if counts[t] == 0]

    if score >= 80 and not missing_core:
        readiness = "proof_planner_ready"
    elif score >= 60:
        readiness = "hypothesis_ready"
    elif score >= 40:
        readiness = "question_generator_ready"
    else:
        readiness = "needs_more_evidence"

    return {
        "score": score,
        "readiness": readiness,
        "counts_by_type": dict(counts),
        "missing_core_entities": missing_core,
        "reasons": reasons,
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.semantic_entities.quality_scorer <semantic_entities.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    graph = json.loads(in_path.read_text())
    entities = graph.get("entities", [])

    by_ro = defaultdict(list)
    for e in entities:
        by_ro[e["research_object_id"]].append(e)

    results = []
    for rid, group in by_ro.items():
        q = score_research_object(group)
        q["research_object_id"] = rid
        q["entity_count"] = len(group)
        results.append(q)

    results.sort(key=lambda x: x["score"], reverse=True)

    output = {
        "schema": "vulnlab.semantic_entity_quality.v1",
        "input_schema": graph.get("schema"),
        "research_object_count": len(results),
        "summary": {
            "proof_planner_ready": sum(1 for r in results if r["readiness"] == "proof_planner_ready"),
            "hypothesis_ready": sum(1 for r in results if r["readiness"] == "hypothesis_ready"),
            "question_generator_ready": sum(1 for r in results if r["readiness"] == "question_generator_ready"),
            "needs_more_evidence": sum(1 for r in results if r["readiness"] == "needs_more_evidence"),
        },
        "research_objects": results,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "used_for_prioritization_only": True,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "research_objects": len(results),
        "summary": output["summary"],
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
