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
    ap=argparse.ArgumentParser(description="Generic Research Closure Report v1")
    ap.add_argument("--target", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--proof", required=True)
    ap.add_argument("--runtime", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    proof=load(args.proof)
    runtime=load(args.runtime)
    top=(proof.get("proof_graphs") or [{}])[0]
    schemes=list(runtime.get("summary",{}).get("by_scheme",{}).keys())

    supported=[]
    for s, v in runtime.get("summary",{}).get("by_scheme",{}).items():
        supported.append({
            "scheme": s,
            "states": v.get("states", {}),
            "confidence_delta": v.get("normalized_confidence_delta", v.get("confidence_delta"))
        })

    report={
        "schema_version":"research_closure_report.v1",
        "created_at":int(time.time()),
        "target":args.target,
        "package":args.package,
        "primary_shape":top.get("target_shape") or proof.get("summary",{}).get("top_shape"),
        "top_component":top.get("component") or proof.get("summary",{}).get("top_component"),
        "schemes_tested":schemes,
        "what_agent_found":{
            "candidate":"externally triggerable application routing surface",
            "confirmed":[
                "external probe reached target package or activity",
                "runtime activity transition was observed",
                "candidate route is safe to continue investigating",
            ],
            "runtime_scheme_support":supported,
            "not_confirmed":[
                "security-sensitive sink behavior",
                "attacker-controlled source-to-sink causal chain",
                "authorization or guard bypass",
                "business/security impact",
                "reportable vulnerability"
            ]
        },
        "decision":{
            "state":"continue_research_not_reportable",
            "finding_allowed":False,
            "candidate_only":True,
            "reason":"Runtime routing support exists, but sink behavior and impact are not proven."
        },
        "next_best_experiments":[
            {
                "name":"prove_source_to_sink_causal_path",
                "goal":"Trace external URI data from entrypoint to router, WebView, OAuth, file provider, API, or privileged state.",
                "priority":"high"
            },
            {
                "name":"prove_actual_sink_behavior_per_route",
                "goal":"Determine whether each route opens normal UI, WebView, auth flow, file/content handler, or blocked path.",
                "priority":"high"
            },
            {
                "name":"resolve_counterevidence_and_guards",
                "goal":"Separate real app guards from platform noise and verify authorization checks.",
                "priority":"high"
            }
        ],
        "learning_value":{
            "generalizable_pattern":"external entrypoint to internal navigation surface with route-specific proof requirements",
            "memory_update":"store routing proof mode, activity-aware validation, and guard/noise normalization; do not store target-specific finding",
            "training_status":"valid research episode, not vulnerability case"
        }
    }

    save(args.out, report)
    print(json.dumps(report["decision"], indent=2))

if __name__=="__main__":
    main()
