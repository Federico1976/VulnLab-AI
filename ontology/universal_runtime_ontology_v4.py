#!/usr/bin/env python3
import json, sys
from pathlib import Path

REL = {
    ("RuntimeFamily", "RuntimeArtifact"): "owns",
    ("RuntimeArtifact", "RuntimeCapabilityProvider"): "exposes",
    ("RuntimeCapabilityProvider", "SemanticObject"): "implements",
    ("SemanticObject", "NativeSinkCandidate"): "maps_to",
    ("NativeSinkCandidate", "ReachabilityState"): "requires_reachability",
    ("ReachabilityState", "ValidationState"): "requires_validation",
    ("ValidationState", "Disclosure"): "gates_disclosure",
}

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def build(target_dir):
    target = Path(target_dir).resolve()
    ev = load(target / "semantic_evidence_graph_v5.json")

    nodes, edges = {}, {}

    def add_node(x):
        kind = x.get("kind")
        name = x.get("name")
        key = f"{kind}:{name}"
        if key not in nodes:
            nodes[key] = dict(x)
        return {"kind": kind, "name": name}

    def add_edge(a, b):
        rel = REL.get((a["kind"], b["kind"]), "causal_transition")
        key = f"{a['kind']}:{a['name']}->{b['kind']}:{b['name']}:{rel}"
        edges[key] = {"from": a, "to": b, "relation": rel}

    for s in ev.get("stories", []):
        path = s.get("causal_path", [])
        prev = None
        for x in path:
            cur = add_node(x)
            if prev:
                add_edge(prev, cur)
            prev = cur

        disclosure = add_node({"kind": "Disclosure", "name": "candidate_only_not_ready"})
        if prev:
            add_edge(prev, disclosure)

    out = {
        "target": str(target),
        "model": "universal_runtime_ontology_v4_causal_final",
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "relations": sorted(set(e["relation"] for e in edges.values())),
            "runtime_families": sorted(set(n["name"] for n in nodes.values() if n.get("kind") == "RuntimeFamily")),
        }
    }

    path = target / "universal_runtime_ontology_v4.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m ontology.universal_runtime_ontology_v4 output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
