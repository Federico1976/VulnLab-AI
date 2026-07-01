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
    ap=argparse.ArgumentParser(description="Runtime Source-to-Sink Instrumentation Planner v1")
    ap.add_argument("--paths", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    paths=load(args.paths).get("resolved_paths", [])
    plans=[]

    for p in paths:
        if p.get("causal_state") != "candidate_source_to_sink_path":
            continue

        comp=p.get("entry_component")
        schemes=p.get("schemes") or ["https"]
        sinks=p.get("candidate_sinks", [])[:5]

        probes=[]
        for s in schemes:
            if s in ("http","https"):
                probes.append({
                    "probe_type":"benign_route_marker",
                    "command":f"adb shell am start -n {args.package}/{comp} -a android.intent.action.VIEW -d '{s}://example.com/vulnlab-safe-marker'",
                    "expected_observation":["activity transition","route marker in logs/ui if propagated","blocked/normalized route if guarded"]
                })
            else:
                probes.append({
                    "probe_type":"benign_custom_scheme_marker",
                    "command":f"adb shell am start -n {args.package}/{comp} -a android.intent.action.VIEW -d '{s}:vulnlab-safe-marker'",
                    "expected_observation":["internal router decision","scheme handler decision","blocked/normalized custom route"]
                })

        plans.append({
            "entry_component":comp,
            "path_score":p.get("path_score"),
            "candidate_sinks":sinks,
            "instrumentation_goal":"prove whether external URI marker reaches router/WebView/OAuth/API/FileProvider sink",
            "safe_probes":probes,
            "log_filters":[args.package,"vulnlab-safe-marker","deeplink","oauth","webview","loadUrl","redirect","authorization","navigation","router"],
            "success_criteria":[
                "marker appears in target-app logs or UI route",
                "activity transition reaches sink-related component",
                "WebView/OAuth/router logs reference marker or transformed URL"
            ],
            "failure_criteria":[
                "marker ignored",
                "route normalized to safe default",
                "guard blocks before sink",
                "only generic UI navigation occurs"
            ],
            "candidate_only":True,
            "finding_allowed":False
        })

    out={
        "schema_version":"runtime_source_to_sink_instrumentation_planner.v1",
        "created_at":int(time.time()),
        "summary":{
            "candidate_paths":len(plans),
            "top_entry_component":plans[0]["entry_component"] if plans else None,
            "candidate_only":True,
            "finding_allowed":False,
            "next_step":"execute_safe_source_to_sink_probes"
        },
        "plans":plans
    }

    save(args.out,out)
    print(json.dumps(out["summary"], indent=2))

if __name__=="__main__":
    main()
