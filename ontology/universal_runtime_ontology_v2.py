#!/usr/bin/env python3
import json, sys
from pathlib import Path

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def build(target_dir):
    target = Path(target_dir).resolve()
    fam = load(target / "universal_runtime_families.json")
    providers = load(target / "runtime_capability_providers.json")
    ev3 = load(target / "semantic_evidence_graph_v3.json")

    nodes, edges, seen = [], [], set()

    def node(kind, name, level, extra=None):
        k = (kind, name, level)
        if k in seen: return
        seen.add(k)
        obj = {"kind": kind, "name": name, "ontology_level": level}
        if extra: obj.update(extra)
        nodes.append(obj)

    def edge(a, b, reason):
        edges.append({"from": a, "to": b, "reason": reason})

    for f in fam.get("runtime_families", []):
        node("RuntimeFamily", f["runtime_family"], "RuntimeFamily", f)

    for p in providers.get("providers", []):
        node("RuntimeCapabilityProvider", f"{p['runtime_family']}:{p['capability_provider']}", "CapabilityProvider", p)
        edge(
            {"kind": "RuntimeFamily", "name": p["runtime_family"]},
            {"kind": "RuntimeCapabilityProvider", "name": f"{p['runtime_family']}:{p['capability_provider']}"},
            "runtime family exposes capability provider"
        )

    for s in ev3.get("stories", []):
        src = s["causal_path"][0]
        cap = s["capability_family"]
        sink = s["sink_candidate"]

        node(src["kind"], src["name"], "RuntimeOrBridgeObject", src)
        node("SemanticObject", f"{src['kind']}:{src['name']}:{cap}", "SemanticObject")
        node("NativeAPI", sink, "NativeAPI")
        node("Sink", sink, "Sink")
        node("Reachability", "unknown_or_candidate", "Reachability")
        node("Validation", "pending", "Validation")
        node("Disclosure", "candidate_only", "Disclosure")

        edge(src, {"kind": "SemanticObject", "name": f"{src['kind']}:{src['name']}:{cap}"}, "object contextualized as semantic capability")
        edge({"kind": "SemanticObject", "name": f"{src['kind']}:{src['name']}:{cap}"}, {"kind": "NativeAPI", "name": sink}, "semantic object maps to native API")
        edge({"kind": "NativeAPI", "name": sink}, {"kind": "Sink", "name": sink}, "native API is sink candidate")
        edge({"kind": "Sink", "name": sink}, {"kind": "Reachability", "name": "unknown_or_candidate"}, "sink requires reachability proof")
        edge({"kind": "Reachability", "name": "unknown_or_candidate"}, {"kind": "Validation", "name": "pending"}, "reachability gates validation")
        edge({"kind": "Validation", "name": "pending"}, {"kind": "Disclosure", "name": "candidate_only"}, "validation gates disclosure")

    out = {
        "target": str(target),
        "model": "universal_runtime_ontology_v2",
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "runtime_families": sorted(n["name"] for n in nodes if n["kind"] == "RuntimeFamily"),
            "levels": sorted(set(n["ontology_level"] for n in nodes)),
        }
    }

    path = target / "universal_runtime_ontology_v2.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m ontology.universal_runtime_ontology_v2 output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
