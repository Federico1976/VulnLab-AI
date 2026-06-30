#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path

def load(p):
    if not p:
        return {}
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() and p.is_file() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False))

def first_file(base, patterns):
    base=Path(base)
    for pat in patterns:
        found=sorted(base.rglob(pat))
        found=[x for x in found if x.is_file()]
        if found:
            return found[-1]
    return None

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--targets", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    rows=[]; shape_dist={}; states={}

    for base in args.targets:
        b=Path(base)
        report_path=first_file(b, ["*complete*report.json", "*orchestrated_report.json"])
        probe_path=first_file(b, ["source_to_sink_probe_interpretation_v1.json"])

        report=load(report_path)
        orch=report.get("orchestrator_summary", report.get("summary", {}))

        for k,v in orch.get("primary_shape_distribution", {}).items():
            shape_dist[k]=shape_dist.get(k,0)+v

        probe=load(probe_path)
        for k,v in probe.get("summary",{}).get("by_state",{}).items():
            states[k]=states.get(k,0)+v

        rows.append({
            "base":str(b),
            "report":str(report_path) if report_path else None,
            "probe":str(probe_path) if probe_path else None,
            "primary_shape_distribution":orch.get("primary_shape_distribution",{}),
            "avg_policy_score":orch.get("avg_policy_score"),
            "avg_proof_score":orch.get("avg_proof_score"),
            "probe_state":probe.get("summary",{}).get("research_state"),
            "probe_by_state":probe.get("summary",{}).get("by_state",{})
        })

    out={
        "schema_version":"five_apk_training_evaluation.v1",
        "created_at":int(time.time()),
        "summary":{
            "targets":len(rows),
            "shape_distribution":shape_dist,
            "probe_state_distribution":states,
            "finding_allowed":False,
            "main_observation":"Agent identifies high-value surfaces but frequently lacks marker propagation proof; Universal Causal Graph Builder is the next required upgrade."
        },
        "rows":rows
    }
    save(args.out,out)
    print(json.dumps(out["summary"], indent=2))

if __name__=="__main__":
    main()
