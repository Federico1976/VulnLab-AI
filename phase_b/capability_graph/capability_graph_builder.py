#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import defaultdict


RELATION_RULES = [
    ("ExternalInputCapability", "IntentLaunchCapability", "external_input_may_influence_intent_launch"),
    ("ExternalInputCapability", "WebViewNavigationCapability", "external_input_may_influence_webview_navigation"),
    ("ExternalInputCapability", "FileAccessCapability", "external_input_may_influence_file_access"),
    ("ExternalInputCapability", "FileProviderCapability", "external_input_may_influence_file_provider_uri"),
    ("ExternalInputCapability", "NetworkOrUploadCapability", "external_input_may_influence_network_or_upload"),
    ("ExternalInputCapability", "DocumentPickerCapability", "external_input_may_influence_document_provider"),
    ("FileAccessCapability", "NetworkOrUploadCapability", "file_access_may_feed_network_upload"),
    ("FileAccessCapability", "FileProviderCapability", "file_access_may_feed_file_provider"),
    ("SanitizerOrGuardCapability", "IntentLaunchCapability", "guard_may_constrain_intent_launch"),
    ("SanitizerOrGuardCapability", "WebViewNavigationCapability", "guard_may_constrain_webview_navigation"),
    ("SanitizerOrGuardCapability", "FileAccessCapability", "guard_may_constrain_file_access"),
    ("SanitizerOrGuardCapability", "NetworkOrUploadCapability", "guard_may_constrain_network_or_upload"),
    ("CryptoOrHashCapability", "FileAccessCapability", "hashing_may_apply_to_file_content"),
]


def cap_id(obj, cap):
    return f"{obj['capability_object_id']}::{cap['capability_type']}"


def build_graph_for_object(obj):
    nodes = []
    edges = []

    caps = obj.get("capabilities", [])

    for cap in caps:
        nodes.append({
            "id": cap_id(obj, cap),
            "type": cap["capability_type"],
            "category": cap["category"],
            "confidence": cap["confidence"],
            "score": cap["score"],
            "matched_keywords": cap.get("matched_keywords", []),
            "security_questions": cap.get("security_questions", []),
        })

    by_type = defaultdict(list)
    for cap in caps:
        by_type[cap["capability_type"]].append(cap)

    for src_type, dst_type, relation in RELATION_RULES:
        for src in by_type.get(src_type, []):
            for dst in by_type.get(dst_type, []):
                edges.append({
                    "from": cap_id(obj, src),
                    "to": cap_id(obj, dst),
                    "type": relation,
                    "confidence": "candidate",
                })

    return nodes, edges


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.capability_graph.capability_graph_builder <semantic_capabilities.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())
    objects = data.get("capability_objects", [])

    graph_objects = []

    total_nodes = 0
    total_edges = 0

    for obj in objects:
        nodes, edges = build_graph_for_object(obj)
        total_nodes += len(nodes)
        total_edges += len(edges)

        graph_objects.append({
            "capability_graph_id": f"CG-{obj['capability_object_id']}",
            "capability_object_id": obj["capability_object_id"],
            "joern_request_id": obj["joern_request_id"],
            "hypothesis_id": obj["hypothesis_id"],
            "story_id": obj["story_id"],
            "research_object_id": obj["research_object_id"],
            "candidate_id": obj["candidate_id"],
            "task_type": obj["task_type"],
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
            "quality_gates": {
                "declares_vulnerability": False,
                "candidate_evidence_only": True,
                "capability_edges_are_hypotheses": True,
            }
        })

    output = {
        "schema": "vulnlab.capability_graphs.v1",
        "input_schema": data.get("schema"),
        "graph_count": len(graph_objects),
        "node_count": total_nodes,
        "edge_count": total_edges,
        "capability_graphs": graph_objects,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "requires_security_effect_inference": True,
            "requires_proof_evaluator": True,
        }
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "graphs": len(graph_objects),
        "nodes": total_nodes,
        "edges": total_edges,
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
