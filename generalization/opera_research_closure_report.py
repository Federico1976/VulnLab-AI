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
    ap.add_argument("--proof", required=True)
    ap.add_argument("--runtime", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    proof=load(args.proof)
    runtime=load(args.runtime)

    schemes=list(runtime.get("summary",{}).get("by_scheme",{}).keys())
    top=proof.get("proof_graphs",[{}])[0]

    report={
        "schema_version":"research_closure_report.v1",
        "created_at":int(time.time()),
        "target":"Opera for Android",
        "package":"com.opera.browser",
        "primary_shape":"webview_external_input_to_load",
        "top_component":top.get("component"),
        "schemes_tested":schemes,
        "what_agent_found":{
            "candidate":"external intent controlled navigation/browser-surface",
            "confirmed":[
                "MainLauncherActivity is the highest priority local plan",
                "external probes reach Opera runtime after onboarding",
                "browser/chromium runtime signals observed",
                "platform noise guards were demoted by runtime evidence normalizer"
            ],
            "not_confirmed":[
                "actual URL/scheme sink behavior",
                "security impact",
                "guard bypass",
                "file/content/about dangerous handling",
                "reportable vulnerability"
            ]
        },
        "decision":{
            "state":"continue_research_not_reportable",
            "finding_allowed":False,
            "candidate_only":True,
            "reason":"Reachability and runtime support exist, but security impact and sink behavior are not proven."
        },
        "next_best_experiments":[
            {
                "name":"prove_actual_sink_behavior_per_scheme",
                "goal":"Determine whether each scheme opens a tab, search, internal page, blocked page, or external handler.",
                "priority":"high"
            },
            {
                "name":"capture_current_url_or_ui_text",
                "goal":"Collect observable UI/current page state after each probe.",
                "priority":"high"
            },
            {
                "name":"file_content_about_security_boundary_check",
                "goal":"Verify whether file://, content:// or about: reach sensitive browser contexts.",
                "priority":"high"
            },
            {
                "name":"second_apk_generalization_check",
                "goal":"Run a non-browser bounty APK to verify the agent does not overfit to navigation shapes.",
                "priority":"medium"
            }
        ],
        "learning_value":{
            "generalizable_pattern":"external entrypoint to browser/navigation runtime with scheme-specific proof requirements",
            "memory_update":"store proof mode, guard demotion logic, and scheme handling strategy; do not store Opera-specific finding",
            "training_status":"valid research episode, not vulnerability case"
        }
    }

    save(args.out, report)
    print(json.dumps(report["decision"], indent=2))

if __name__=="__main__":
    main()
