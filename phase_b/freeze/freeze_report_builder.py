#!/usr/bin/env python3
import json, sys
from pathlib import Path

def load(p):
    p=Path(p)
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except Exception: return {}

def main():
    if len(sys.argv)!=4:
        print("Usage: python3 -m phase_b.freeze.freeze_report_builder <apk_output_dir> <phase_b_brain_dir> <out.json>")
        sys.exit(1)

    apk_out=Path(sys.argv[1])
    brain=Path(sys.argv[2])
    final=load(brain/"phase_b_final_report.json")
    factory=load(apk_out/"phase_b/research_object_factory_report.json")
    dedup=load(brain/"freeze_dedup_report.json")
    discovery=load(brain/"universal_discovery.json")

    health=final.get("health",{})
    summary=final.get("summary",{})

    criteria={
        "pipeline_stable": bool(health.get("phase_b_completed")) and not health.get("legacy_schema_blockers_remaining"),
        "schema_unified": "vulnlab.phase_b.final_report.v3" == final.get("schema"),
        "factory_declarative": factory.get("schema")=="vulnlab_ai.research_object_builder_factory.v2_declarative",
        "coverage_measurable": summary.get("semantic_entities",0)>0 and summary.get("evidence_models",0)>0,
        "candidate_guardrail": health.get("candidate_only_guardrail") is True and health.get("finding_allowed") is False,
        "dynamic_path_present": summary.get("dynamic_validation_plans",0)>0,
        "unknowns_tracked": summary.get("unknown_resolution_tasks",0)>=0,
        "discovery_present": discovery.get("schema")=="vulnlab.universal_discovery_engine.v1"
    }

    frozen=all(criteria.values())

    out={
        "schema":"vulnlab.phase_ab.freeze_report.v1",
        "apk_output_dir":str(apk_out),
        "phase_b_brain_dir":str(brain),
        "freeze_ready":frozen,
        "criteria":criteria,
        "summary":summary,
        "factory_summary":factory.get("summary",{}),
        "dedup_summary":dedup.get("artifacts",{}),
        "discovery_summary":discovery.get("summary",{}),
        "guardrail":{
            "candidate_only":True,
            "finding_allowed":False,
            "requires_causal_reachability":True,
            "requires_dynamic_validation":True
        }
    }

    Path(sys.argv[3]).write_text(json.dumps(out,indent=2,ensure_ascii=False))
    print(json.dumps({"status":"ok","freeze_ready":frozen,"output":sys.argv[3],"criteria":criteria},indent=2))

if __name__=="__main__":
    main()
