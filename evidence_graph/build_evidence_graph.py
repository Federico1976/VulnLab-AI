#!/usr/bin/env python3
import json, sys, hashlib
from pathlib import Path

def eid(*parts):
    h = hashlib.sha1("::".join(str(p) for p in parts).encode()).hexdigest()[:12]
    return f"EV-{h}"

def evidence_from_node(n):
    src = n.get("source", {})
    if isinstance(src, dict):
        file = src.get("file")
        raw = src.get("raw") or src.get("value")
        score = src.get("score")
        source_conf = src.get("confidence")
    else:
        file, raw, score, source_conf = None, None, None, None

    return {
        "evidence_id": eid(n.get("kind"), n.get("name"), file, raw),
        "subject": {
            "kind": n.get("kind"),
            "name": n.get("name"),
        },
        "evidence_type": "node_origin",
        "file": file,
        "raw": raw,
        "score": score,
        "source_confidence": source_conf,
        "confidence_score": n.get("confidence_score"),
        "confidence_label": n.get("confidence_label"),
        "explanation": f"{n.get('kind')} node derived from runtime artifact or semantic classification."
    }

def evidence_from_edge(e):
    return {
        "evidence_id": eid(e["from"]["kind"], e["from"]["name"], e["to"]["kind"], e["to"]["name"], e.get("reason")),
        "subject": {
            "from": e["from"],
            "to": e["to"],
        },
        "evidence_type": "edge_derivation",
        "reason": e.get("reason"),
        "confidence_score": e.get("confidence_score"),
        "confidence_label": e.get("confidence_label"),
        "confidence_origin": e.get("confidence_origin"),
        "explanation": f"Edge created because: {e.get('reason')}."
    }

def build(target_dir):
    target = Path(target_dir).resolve()
    kg_path = target / "semantic_runtime_kg_confidence.json"
    kg = json.loads(kg_path.read_text())

    evidence = {
        "target": str(target),
        "nodes": [],
        "edges": [],
        "chains": [],
        "summary": {},
    }

    for n in kg.get("nodes", []):
        evidence["nodes"].append(evidence_from_node(n))

    for e in kg.get("edges", []):
        evidence["edges"].append(evidence_from_edge(e))

    # Build short reasoning chains:
    # source concept -> CapabilityFamily -> NativeSinkFamily
    edges = kg.get("edges", [])
    by_from = {}
    for e in edges:
        k = (e["from"]["kind"], e["from"]["name"])
        by_from.setdefault(k, []).append(e)

    chain_id = 0
    for e1 in edges:
        if e1["to"]["kind"] != "CapabilityFamily":
            continue

        cap = e1["to"]["name"]
        next_edges = by_from.get(("CapabilityFamily", cap), [])

        for e2 in next_edges:
            if e2["to"]["kind"] != "NativeSinkFamily":
                continue

            score = min(
                e1.get("confidence_score", 0.0),
                e2.get("confidence_score", 0.0),
            )

            if score >= 0.70:
                label = "high"
            elif score >= 0.50:
                label = "medium"
            elif score >= 0.30:
                label = "low"
            else:
                label = "very_low"

            chain_id += 1
            evidence["chains"].append({
                "chain_id": f"CHAIN-{chain_id:04d}",
                "status": "candidate_only_not_vulnerability",
                "path": [
                    e1["from"],
                    e1["to"],
                    e2["to"],
                ],
                "capability_family": cap,
                "sink_family": e2["to"]["name"],
                "confidence_score": round(score, 4),
                "confidence_label": label,
                "requires": [
                    "entrypoint correlation",
                    "reachability proof",
                    "dynamic validation",
                    "exploitability reasoning"
                ],
                "why_it_exists": [
                    e1.get("reason"),
                    e2.get("reason")
                ],
            })

    evidence["summary"] = {
        "node_evidence": len(evidence["nodes"]),
        "edge_evidence": len(evidence["edges"]),
        "chains": len(evidence["chains"]),
        "chains_by_confidence": {
            lab: sum(1 for c in evidence["chains"] if c["confidence_label"] == lab)
            for lab in ["high", "medium", "low", "very_low"]
        },
        "capability_families": sorted(set(c["capability_family"] for c in evidence["chains"])),
    }

    out = target / "semantic_evidence_graph.json"
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    print(json.dumps(evidence["summary"], indent=2))
    print(f"[+] wrote {out}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m evidence_graph.build_evidence_graph output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
