#!/usr/bin/env python3
import json, sys
from pathlib import Path

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def build(target_dir):
    target = Path(target_dir).resolve()
    ev4 = load(target / "semantic_evidence_graph_v4.json")
    roles = load(target / "runtime_roles.json")

    nodes, edges = {}, {}

    role_by_family = {
        r["runtime_family"]: r["role"]
        for r in roles.get("runtime_roles", [])
    }

    def node(kind, name, level, extra=None):
        key = f"{kind}:{name}:{level}"
        if key not in nodes:
            obj = {"kind": kind, "name": name, "ontology_level": level}
            if extra:
                obj.update(extra)
            nodes[key] = obj

    def edge(a, b, reason):
        key = f"{a['kind']}:{a['name']}->{b['kind']}:{b['name']}:{reason}"
        edges[key] = {"from": a, "to": b, "reason": reason}

    for r in roles.get("runtime_roles", []):
        if r["role"] == "blocked_runtime":
            continue
        node("RuntimeFamily", r["runtime_family"], "RuntimeFamily", {
            "runtime_role": r["role"],
            "confidence_score": r.get("confidence_score"),
            "artifact_kinds": r.get("artifact_kinds", []),
        })

    for s in ev4.get("stories", []):
        path = s["causal_path"]
        prev = None

        for x in path:
            kind = x["kind"]
            name = x["name"]

            if kind == "RuntimeFamily":
                level = "RuntimeFamily"
                x = dict(x)
                x["runtime_role"] = role_by_family.get(name, "unknown_role")
            elif kind == "RuntimeArtifact":
                level = "RuntimeArtifact"
            elif kind == "RuntimeCapabilityProvider":
                level = "CapabilityProvider"
            elif kind == "NativeSinkCandidate":
                level = "Sink"
            elif kind == "ReachabilityState":
                level = "Reachability"
            elif kind == "ValidationState":
                level = "Validation"
            else:
                level = "SemanticObject"

            node(kind, name, level, x)

            if prev:
                edge(
                    {"kind": prev["kind"], "name": prev["name"]},
                    {"kind": kind, "name": name},
                    "causal_runtime_ontology_transition"
                )

            prev = x

        node("Disclosure", "candidate_only", "Disclosure")
        edge(
            {"kind": "ValidationState", "name": "pending"},
            {"kind": "Disclosure", "name": "candidate_only"},
            "validation gates disclosure"
        )

    out = {
        "target": str(target),
        "model": "universal_runtime_ontology_v3_roles_dedup_causal",
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "runtime_families": sorted(set(
                n["name"] for n in nodes.values()
                if n["kind"] == "RuntimeFamily"
            )),
            "runtime_roles": {
                role: sorted(set(
                    n["name"] for n in nodes.values()
                    if n["kind"] == "RuntimeFamily" and n.get("runtime_role") == role
                ))
                for role in [
                    "primary_runtime",
                    "secondary_runtime",
                    "embedded_runtime",
                    "sdk_or_library_runtime",
                    "weak_or_blocked_runtime",
                ]
            },
            "levels": sorted(set(n["ontology_level"] for n in nodes.values())),
        }
    }

    path = target / "universal_runtime_ontology_v3.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m ontology.universal_runtime_ontology_v3 output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
