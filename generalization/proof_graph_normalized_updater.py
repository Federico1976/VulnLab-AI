#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path

def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--proof-graph", required=True)
    ap.add_argument("--normalized-runtime", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    graph=load(args.proof_graph)
    norm=load(args.normalized_runtime)

    edge_updates={}
    for r in norm.get("normalized_results", []):
        edge=r.get("validates_edge")
        if edge:
            edge_updates.setdefault(edge, []).append(r)

    for pg in graph.get("proof_graphs", []):
        for e in pg.get("evidence_edges", []):
            updates=edge_updates.get(e.get("edge_id"), [])
            if not updates:
                continue

            delta=sum(float(u.get("normalized_confidence_delta") or 0.0) for u in updates)
            states=sorted(set(u.get("normalized_ui_scheme_state") for u in updates if u.get("normalized_ui_scheme_state")))
            guards=sorted(set(u.get("log_classification", {}).get("guard_classification") for u in updates if u.get("log_classification", {}).get("guard_classification")))
            schemes=sorted(set(u.get("scheme") for u in updates if u.get("scheme")))

            e["normalized_runtime_evidence"]={
                "schemes": schemes,
                "states": states,
                "guard_classes": guards,
                "confidence_delta": round(delta,3),
                "updates": updates
            }

            e["confidence"]=round(max(0.0, min(1.0, float(e.get("confidence") or 0.0)+delta)),3)

            if all(g=="platform_or_environment_noise_guard" for g in guards):
                e["proof_state"]="supported_runtime_ui_noise_guard_demoted"
            elif any("target" in str(g) or "app" in str(g) for g in guards):
                e["proof_state"]="supported_runtime_ui_with_target_guard"
            else:
                e["proof_state"]="supported_runtime_ui"

        scores=[float(e.get("confidence") or 0.0) for e in pg.get("evidence_edges", [])]
        pg["normalized_runtime_proof_score"]=round(sum(scores)/len(scores),3) if scores else 0.0
        pg["updated_decision_after_normalization"]={
            "continue_investigation": True,
            "finding_allowed": False,
            "candidate_only": True,
            "recommended_next_step": "prove_actual_sink_behavior_per_scheme",
            "reason": "External intents reach Opera runtime; guards observed so far look platform/environmental, but actual navigation/sink behavior and security impact are not proven."
        }

    graph["updated_at"]=int(time.time())
    graph["summary"]["updated_after_normalized_runtime"]=True
    graph["summary"]["next_step"]="prove_actual_sink_behavior_per_scheme"
    graph["summary"]["finding_allowed"]=False
    graph["summary"]["candidate_only"]=True

    save(args.out, graph)
    print(json.dumps(graph["summary"], indent=2, ensure_ascii=False))

if __name__=="__main__":
    main()
