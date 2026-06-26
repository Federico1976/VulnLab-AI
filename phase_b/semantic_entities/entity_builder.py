#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from .extractors.bridge import BridgeEntityExtractor
from .extractors.entrypoint import EntrypointEntityExtractor
from .extractors.source import SourceEntityExtractor
from .extractors.sink import SinkEntityExtractor
from .extractors.propagation import PropagationEntityExtractor
from .extractors.trust_boundary import TrustBoundaryEntityExtractor
from .extractors.asset import AssetEntityExtractor
from .extractors.sanitizer import SanitizerEntityExtractor
from .extractors.validation import ValidationEvidenceExtractor
from .extractors.counter_evidence import CounterEvidenceExtractor


EXTRACTORS = [
    BridgeEntityExtractor(),
    EntrypointEntityExtractor(),
    SourceEntityExtractor(),
    SinkEntityExtractor(),
    PropagationEntityExtractor(),
    TrustBoundaryEntityExtractor(),
    AssetEntityExtractor(),
    SanitizerEntityExtractor(),
    ValidationEvidenceExtractor(),
    CounterEvidenceExtractor(),
]


def load_research_objects(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text())

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["research_objects", "objects", "items", "cases"]:
            if isinstance(data.get(key), list):
                return data[key]

    raise ValueError("Cannot find research objects list in input JSON")


def dedupe_entities(entities):
    seen = set()
    out = []

    for e in entities:
        d = e.to_dict() if hasattr(e, "to_dict") else e
        if d["id"] in seen:
            continue
        seen.add(d["id"])
        out.append(d)

    return out


def build_edges(entities):
    edges = []

    by_candidate = {}
    by_ro = {}

    for e in entities:
        by_ro.setdefault(e["research_object_id"], []).append(e)
        if e.get("candidate_id"):
            by_candidate.setdefault(e["candidate_id"], []).append(e)

    def add(src, dst, edge_type):
        if src["id"] == dst["id"]:
            return
        edges.append({
            "from": src["id"],
            "to": dst["id"],
            "type": edge_type,
            "research_object_id": src["research_object_id"],
            "candidate_id": src.get("candidate_id") or dst.get("candidate_id"),
        })

    def of_type(group, t):
        return [e for e in group if e["type"] == t]

    for cid, group in by_candidate.items():
        bridges = of_type(group, "BridgeMethodEntity")
        entrypoints = of_type(group, "EntrypointEntity")
        sources = of_type(group, "SourceEntity")
        propagations = of_type(group, "PropagationEntity")
        sinks = of_type(group, "SinkEntity")
        boundaries = of_type(group, "TrustBoundaryEntity")
        sanitizers = of_type(group, "SanitizerEntity")
        validations = of_type(group, "ValidationEvidenceEntity")
        counters = of_type(group, "CounterEvidenceEntity")
        assets = of_type(group, "AssetEntity")

        for ep in entrypoints:
            for br in bridges:
                add(ep, br, "entrypoint_to_bridge")

        for tb in boundaries:
            for br in bridges:
                add(tb, br, "trust_boundary_to_bridge")

        for br in bridges:
            for src in sources:
                add(br, src, "bridge_to_source")

        for src in sources:
            for prop in propagations:
                add(src, prop, "source_to_propagation")

        for prop in propagations:
            for sink in sinks:
                add(prop, sink, "propagation_to_sink")

        for san in sanitizers:
            for prop in propagations:
                add(san, prop, "sanitizer_to_propagation")

        for val in validations:
            for prop in propagations:
                add(val, prop, "validation_to_propagation")
            for sink in sinks:
                add(val, sink, "validation_to_sink")

        for counter in counters:
            for prop in propagations:
                add(counter, prop, "counter_evidence_to_propagation")

        for sink in sinks:
            for asset in assets:
                add(sink, asset, "sink_to_asset")

    return edges

def build_cognitive_graph(research_objects):
    entities = []

    for ro in research_objects:
        for extractor in EXTRACTORS:
            entities.extend(extractor.extract_from_research_object(ro))

        for candidate in ro.get("normalized_candidates") or []:
            for extractor in EXTRACTORS:
                entities.extend(extractor.extract_from_candidate(ro, candidate))

    entities = dedupe_entities(entities)
    edges = build_edges(entities)

    counts_by_type = {}
    for e in entities:
        counts_by_type[e["type"]] = counts_by_type.get(e["type"], 0) + 1

    return {
        "schema": "vulnlab.semantic_entities.v1_1",
        "builder": "extractor_based_candidate_evidence_semantic_entity_builder",
        "research_object_count": len(research_objects),
        "entity_count": len(entities),
        "edge_count": len(edges),
        "counts_by_type": counts_by_type,
        "entities": entities,
        "edges": edges,
        "quality_gates": {
            "candidate_evidence_only": True,
            "declares_vulnerability": False,
            "requires_causal_reachability": True,
            "requires_dynamic_validation": True,
            "runtime_specific_logic_isolated_to_extractors": True,
            "hypothesis_ready": False,
        },
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.semantic_entities.entity_builder <research_objects.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    research_objects = load_research_objects(in_path)
    graph = build_cognitive_graph(research_objects)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "schema": graph["schema"],
        "research_objects": graph["research_object_count"],
        "entities": graph["entity_count"],
        "edges": graph["edge_count"],
        "counts_by_type": graph["counts_by_type"],
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
