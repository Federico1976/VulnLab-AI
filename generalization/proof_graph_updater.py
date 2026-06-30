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
    ap=argparse.ArgumentParser(description="Proof Graph Updater v1")
    ap.add_argument("--proof-graph", required=True)
    ap.add_argument("--ui-scheme", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    graph=load(args.proof_graph)
    ui=load(args.ui_scheme)

    edge_updates={}
    for r in ui.get("results", []):
        edge=r.get("validates_edge")
        interp=r.get("scheme_interpretation", {})
        if not edge:
            continue
        edge_updates.setdefault(edge, []).append(interp)

    for pg in graph.get("proof_graphs", []):
        for e in pg.get("evidence_edges", []):
            updates=edge_updates.get(e.get("edge_id"), [])
            if not updates:
                continue

            delta=sum(float(u.get("confidence_delta") or 0.0) for u in updates)
            states=list({u.get("ui_scheme_state") for u in updates if u.get("ui_scheme_state")})
            counters=[]
            for u in updates:
                counters.extend(u.get("counter_evidence", []))

            e["ui_scheme_validation"]={
                "updates": updates,
                "confidence_delta": round(delta,3),
                "observed_states": states,
                "counter_evidence": sorted(set(counters)),
            }

            e["confidence"]=round(max(0.0, min(1.0, float(e.get("confidence") or 0.0)+delta)),3)

            if "blocked_or_intercepted_by_app_state" in states:
                e["proof_state"]="blocked_by_app_state_precondition"
            elif any("supported" in str(s) for s in states):
                e["proof_state"]="supported_runtime_ui"
            else:
                e["proof_state"]="runtime_inconclusive"

        scores=[float(e.get("confidence") or 0.0) for e in pg.get("evidence_edges", [])]
        pg["updated_proof_score_after_ui_scheme"]=round(sum(scores)/len(scores),3) if scores else 0.0
        pg["updated_decision"]={
            "continue_investigation": True,
            "finding_allowed": False,
            "candidate_only": True,
            "recommended_next_step": "satisfy_or_bypass_app_state_precondition_then_repeat_scheme_probes",
            "reason": "Current probes reach Opera but are intercepted by onboarding/welcome state; navigation sink not yet proven."
        }

    graph["updated_at"]=int(time.time())
    graph["summary"]["updated_after_ui_scheme"]=True
    graph["summary"]["next_step"]="satisfy_or_bypass_app_state_precondition_then_repeat_scheme_probes"
    graph["summary"]["finding_allowed"]=False
    graph["summary"]["candidate_only"]=True

    save(args.out, graph)
    print(json.dumps(graph["summary"], indent=2, ensure_ascii=False))

if __name__=="__main__":
    main()
