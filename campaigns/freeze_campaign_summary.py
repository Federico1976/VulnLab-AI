#!/usr/bin/env python3
import json, sys
from pathlib import Path

def load(p):
    p=Path(p)
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except Exception: return {}

def main():
    outs=[
      "output/campaign_single_01_nextplayer",
      "output/campaign_single_02_serveit",
      "output/campaign_single_03_webviewkiosk",
      "output/campaign_single_04_lesspass",
      "output/campaign_single_05_opendsp"
    ]

    rows=[]
    for o in outs:
        r=load(Path(o)/"phase_b_brain/phase_ab_freeze_report.json")
        s=r.get("summary",{})
        rows.append({
            "output":o,
            "freeze_ready":r.get("freeze_ready"),
            "semantic_entities":s.get("semantic_entities"),
            "evidence_models":s.get("evidence_models"),
            "proof_evaluations":s.get("proof_evaluations"),
            "causal_ready":s.get("causal_ready_for_dynamic_validation"),
            "unknowns":s.get("unknown_resolution_tasks"),
            "dynamic_plans":s.get("dynamic_validation_plans"),
            "finding_allowed":r.get("guardrail",{}).get("finding_allowed")
        })

    out={
        "schema":"vulnlab.phase_ab.freeze_campaign_summary.v1",
        "apk_count":len(rows),
        "freeze_ready_count":sum(1 for r in rows if r["freeze_ready"]),
        "all_freeze_ready":all(r["freeze_ready"] for r in rows),
        "rows":rows
    }

    Path("output/phase_ab_freeze_campaign_summary.json").write_text(json.dumps(out,indent=2,ensure_ascii=False))
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
