#!/usr/bin/env python3
import json, sys, hashlib
from pathlib import Path

def load(p):
    p=Path(p)
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except Exception: return {}

def sid(*x):
    return "DISC-"+hashlib.sha1("|".join(map(str,x)).encode()).hexdigest()[:12]

def main():
    if len(sys.argv)!=3:
        print("Usage: python3 -m phase_b.freeze.universal_discovery_engine <phase_b_brain_dir> <out.json>")
        sys.exit(1)

    d=Path(sys.argv[1])
    final=load(d/"phase_b_final_report.json")
    summary=final.get("summary",{})

    directions=[]

    if summary.get("causal_ready_for_dynamic_validation"):
        directions.append({
            "id":sid("dynamic",summary.get("causal_ready_for_dynamic_validation")),
            "priority":"high",
            "type":"dynamic_validation_followup",
            "reason":"Causal static evidence is ready; runtime confirmation is the next required step.",
            "candidate_only":True,
            "finding_allowed":False
        })

    if summary.get("unknown_resolution_tasks",0)>0:
        directions.append({
            "id":sid("unknowns",summary.get("unknown_resolution_tasks")),
            "priority":"high",
            "type":"unknown_resolution_campaign",
            "reason":"Open proof requirements and unknowns remain before any disclosure decision.",
            "candidate_only":True,
            "finding_allowed":False
        })

    if summary.get("capability_graphs",0)>50:
        directions.append({
            "id":sid("prioritize",summary.get("capability_graphs")),
            "priority":"medium",
            "type":"prioritization_needed",
            "reason":"Large capability graph should be clustered and prioritized before manual review.",
            "candidate_only":True,
            "finding_allowed":False
        })

    if not directions:
        directions.append({
            "id":sid("more_coverage"),
            "priority":"medium",
            "type":"coverage_expansion",
            "reason":"No dominant follow-up found; continue heterogeneous APK campaign.",
            "candidate_only":True,
            "finding_allowed":False
        })

    out={
        "schema":"vulnlab.universal_discovery_engine.v1",
        "phase_b_brain_dir":str(d),
        "directions":directions,
        "summary":{
            "directions":len(directions),
            "candidate_only":True,
            "finding_allowed":False
        }
    }

    Path(sys.argv[2]).write_text(json.dumps(out,indent=2,ensure_ascii=False))
    print(json.dumps({"status":"ok","directions":len(directions),"output":sys.argv[2]},indent=2))

if __name__=="__main__":
    main()
