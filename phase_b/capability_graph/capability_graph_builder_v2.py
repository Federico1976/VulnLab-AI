#!/usr/bin/env python3
import json
import sys
import hashlib
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sid(prefix, *parts):
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}-{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


def get_caps(payload):
    return payload.get("capabilities") or []


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.capability_graph.capability_graph_builder_v2 <semantic_capabilities.json> <existing_graphs.json> <output.json>")
        sys.exit(1)

    caps_payload = load(sys.argv[1])
    existing_payload = load(sys.argv[2])

    caps = get_caps(caps_payload)

    graphs = []
    nodes = []
    edges = []

    for cap in caps:
        if not isinstance(cap, dict):
            continue

        cap_id = cap.get("capability_id") or cap.get("id") or sid("CAP", json.dumps(cap, sort_keys=True))
        rid = cap.get("research_object_id")
        cap_type = cap.get("type")
        name = cap.get("name") or cap.get("capability") or cap_type or cap_id

        graph_id = sid("CGV2", rid, cap_id)

        cap_node = {
            "node_id": cap_id,
            "type": "CapabilityNode",
            "name": name,
            "research_object_id": rid,
            "capability_type": cap_type,
            "candidate_only": True,
            "verification_state": cap.get("verification_state", "unverified"),
            "source": "capability_graph_builder_v2",
        }

        proof_node = {
            "node_id": sid("PROOFREQ", rid, cap_id),
            "type": "ProofRequirementNode",
            "name": "proof_requirements_required",
            "research_object_id": rid,
        }

        validation_node = {
            "node_id": sid("DYNREQ", rid, cap_id),
            "type": "DynamicValidationRequirementNode",
            "name": "dynamic_validation_required",
            "research_object_id": rid,
        }

        policy_node = {
            "node_id": sid("POLICY", rid, cap_id),
            "type": "FindingPolicyGuardrailNode",
            "name": "candidate_only_no_finding_without_validation",
            "research_object_id": rid,
        }

        local_nodes = [cap_node, proof_node, validation_node, policy_node]
        local_edges = [
            {
                "edge_id": sid("EDGE", cap_node["node_id"], proof_node["node_id"]),
                "type": "REQUIRES_PROOF",
                "source": cap_node["node_id"],
                "target": proof_node["node_id"],
                "research_object_id": rid,
            },
            {
                "edge_id": sid("EDGE", cap_node["node_id"], validation_node["node_id"]),
                "type": "REQUIRES_DYNAMIC_VALIDATION",
                "source": cap_node["node_id"],
                "target": validation_node["node_id"],
                "research_object_id": rid,
            },
            {
                "edge_id": sid("EDGE", cap_node["node_id"], policy_node["node_id"]),
                "type": "GOVERNED_BY_CANDIDATE_ONLY_POLICY",
                "source": cap_node["node_id"],
                "target": policy_node["node_id"],
                "research_object_id": rid,
            },
        ]

        graphs.append({
            "graph_id": graph_id,
            "type": "CapabilityGraphV2",
            "research_object_id": rid,
            "capability_id": cap_id,
            "nodes": local_nodes,
            "edges": local_edges,
            "candidate_only": True,
            "source": "capability_graph_builder_v2",
        })

        nodes.extend(local_nodes)
        edges.extend(local_edges)

    out = {
        "schema": "vulnlab.capability_graphs.v2",
        "graphs": graphs,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "graphs": len(graphs),
            "nodes": len(nodes),
            "edges": len(edges),
            "capabilities_consumed": len(caps),
            "previous_schema": existing_payload.get("schema") if isinstance(existing_payload, dict) else None,
        },
    }

    save(sys.argv[3], out)

    print(json.dumps({
        "status": "ok",
        "graphs": len(graphs),
        "nodes": len(nodes),
        "edges": len(edges),
        "output": sys.argv[3],
    }, indent=2))


if __name__ == "__main__":
    main()
