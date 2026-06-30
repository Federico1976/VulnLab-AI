from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def score_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    summary = graph.get("summary", {})
    by_type = summary.get("by_type", {})
    by_relation = summary.get("by_relation", {})

    ros = max(summary.get("research_objects", 0), 1)
    entities = summary.get("entities", 0)
    relations = summary.get("relations", 0)

    entities_per_ro = entities / ros
    relations_per_ro = relations / ros

    required_types = [
        "RuntimeArtifactEntity",
        "CapabilityEntity",
        "TrustBoundaryEntity",
        "SinkEntity",
        "PropagationEntity",
    ]

    missing_types = [t for t in required_types if by_type.get(t, 0) == 0]

    causal_relations = (
        by_relation.get("enables_candidate_capability", 0)
        + by_relation.get("may_drive_sink", 0)
        + by_relation.get("may_reach", 0)
        + by_relation.get("suggests_propagation", 0)
    )

    structural_relations = (
        by_relation.get("declares", 0)
        + by_relation.get("contains_sink", 0)
        + by_relation.get("has_capability", 0)
        + by_relation.get("crosses_boundary", 0)
        + by_relation.get("touches_asset", 0)
    )

    causal_ratio = causal_relations / max(relations, 1)
    density_ratio = relations / max(entities, 1)

    warnings: List[str] = []

    if missing_types:
        warnings.append("missing_core_entity_types")

    if entities_per_ro < 5:
        warnings.append("under_extracted_graph")

    if entities_per_ro > 30:
        warnings.append("possible_entity_over_extraction")

    if relations_per_ro > 45:
        warnings.append("possible_relation_explosion")

    if density_ratio > 3.0:
        warnings.append("high_relation_density")

    if causal_ratio < 0.25:
        warnings.append("low_causal_relation_ratio")

    if by_relation.get("enables_candidate_capability", 0) > ros * 15:
        warnings.append("boundary_capability_overlinking")

    score = 1.0

    score -= 0.12 * len(missing_types)

    if "under_extracted_graph" in warnings:
        score -= 0.20
    if "possible_entity_over_extraction" in warnings:
        score -= 0.10
    if "possible_relation_explosion" in warnings:
        score -= 0.15
    if "high_relation_density" in warnings:
        score -= 0.10
    if "low_causal_relation_ratio" in warnings:
        score -= 0.15
    if "boundary_capability_overlinking" in warnings:
        score -= 0.10

    score = max(round(score, 2), 0.0)

    if score >= 0.85:
        quality = "excellent"
    elif score >= 0.70:
        quality = "good"
    elif score >= 0.50:
        quality = "needs_review"
    else:
        quality = "poor"

    return {
        "schema": "semantic_graph_quality_gate_v4",
        "candidate_only": True,
        "finding_allowed": False,
        "input_schema": graph.get("schema"),
        "quality": quality,
        "score": score,
        "warnings": warnings,
        "metrics": {
            "research_objects": ros,
            "entities": entities,
            "relations": relations,
            "entities_per_ro": round(entities_per_ro, 2),
            "relations_per_ro": round(relations_per_ro, 2),
            "density_ratio": round(density_ratio, 2),
            "causal_ratio": round(causal_ratio, 2),
            "causal_relations": causal_relations,
            "structural_relations": structural_relations,
            "missing_core_entity_types": missing_types,
        },
        "by_type": by_type,
        "by_relation": by_relation,
        "recommendation": recommendation(warnings, quality),
    }


def recommendation(warnings: List[str], quality: str) -> str:
    if quality in ("excellent", "good") and not warnings:
        return "Graph is suitable for Evidence Story Builder v4."

    if "boundary_capability_overlinking" in warnings:
        return "Reduce boundary-to-capability relations using stricter causal rules before evidence story generation."

    if "possible_relation_explosion" in warnings or "high_relation_density" in warnings:
        return "Graph is usable but should be compressed before causal evidence modeling."

    if "under_extracted_graph" in warnings:
        return "Extractor is missing semantic concepts; improve entity extraction rules."

    if "missing_core_entity_types" in warnings:
        return "Core causal entity types are missing; do not use for strong story generation yet."

    return "Graph can be used for candidate-only evidence stories with uncertainty preserved."


def main() -> None:
    if len(sys.argv) not in (2, 3):
        print("Usage: python3 -m core.semantic_graph_quality_gate_v4 <semantic_entity_graph_v4.json> [quality_report.json]")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) == 3 else inp.with_name("semantic_graph_quality_v4.json")

    graph = load_json(inp)
    report = score_graph(graph)
    save_json(out, report)

    print(json.dumps({
        "input": str(inp),
        "output": str(out),
        "quality": report["quality"],
        "score": report["score"],
        "warnings": report["warnings"],
        "metrics": report["metrics"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
