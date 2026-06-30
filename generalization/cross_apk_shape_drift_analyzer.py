#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

def load(p):
    p=Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--reports", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    rows=[]
    dist={}
    for r in args.reports:
        data=load(r)
        s=data.get("orchestrator_summary", data.get("summary", {}))
        shape_dist=s.get("primary_shape_distribution", {})
        for shape,count in shape_dist.items():
            dist[shape]=dist.get(shape,0)+count
        rows.append({
            "report":r,
            "primary_shape_distribution":shape_dist,
            "avg_policy_score":s.get("avg_policy_score"),
            "avg_proof_score":s.get("avg_proof_score"),
            "proof_graph_completed":s.get("proof_graph_completed"),
            "training_completed":s.get("training_completed"),
        })

    total=sum(dist.values()) or 1
    risks=[]
    for shape,count in dist.items():
        ratio=count/total
        if total>=2 and ratio>=0.75:
            risks.append({
                "risk":"shape_overdominance",
                "shape":shape,
                "count":count,
                "total":total,
                "ratio":round(ratio,3),
                "recommendation":"verify shape-specific evidence and inspect alternative ranked shapes before accepting primary driver"
            })

    out={
        "schema_version":"cross_apk_shape_drift_analyzer.v1",
        "summary":{
            "reports":len(rows),
            "total_primary_shapes":total,
            "shape_distribution":dist,
            "risk_count":len(risks),
            "passed":len(risks)==0
        },
        "risks":risks,
        "rows":rows
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out,indent=2),encoding="utf-8")
    print(json.dumps(out["summary"],indent=2))

if __name__=="__main__":
    main()
