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

def classify(result, package):
    interp=result.get("interpretation",{})
    resumed=(result.get("after",{}).get("resumed",{}).get("stdout") or "").lower()
    log=(result.get("filtered_log",{}).get("stdout") or "").lower()
    combined=resumed+"\n"+log
    package=package.lower()

    marker=interp.get("marker_seen") is True
    sink_words=interp.get("sink_words_seen") or []

    external_handoff = package not in resumed and "resumedactivity" in resumed
    target_activity = package in resumed

    if marker and sink_words and target_activity:
        state="confirmed_marker_to_target_sink_runtime"
        delta=0.25
        decision="continue_high_priority"
    elif marker and target_activity:
        state="marker_reaches_target_runtime_but_sink_not_confirmed"
        delta=0.12
        decision="continue_with_more_precise_sink_observation"
    elif external_handoff and not marker:
        state="external_app_handoff_without_marker_propagation"
        delta=-0.08
        decision="deprioritize_this_route_or_test_app_link_specific_host"
    elif target_activity and sink_words and not marker:
        state="target_runtime_sink_words_without_source_marker"
        delta=0.03
        decision="needs_static_or_instrumented_trace_before_claim"
    elif target_activity:
        state="target_runtime_no_marker_no_sink"
        delta=0.0
        decision="treat_as_normal_navigation_until_more_evidence"
    else:
        state="inconclusive"
        delta=0.0
        decision="repeat_with_better_observation"

    return {
        "interpreted_state":state,
        "confidence_delta":delta,
        "decision":decision,
        "target_activity_observed":target_activity,
        "external_handoff_observed":external_handoff,
        "marker_seen":marker,
        "sink_words_seen":sink_words,
        "candidate_only":True,
        "finding_allowed":False
    }

def main():
    import argparse
    ap=argparse.ArgumentParser(description="Source-to-Sink Probe Interpreter v1")
    ap.add_argument("--results", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    data=load(args.results)
    interpreted=[]
    for r in data.get("results",[]):
        interpreted.append({
            "entry_component":r.get("entry_component"),
            "probe_type":r.get("probe_type"),
            "command":r.get("command"),
            "interpretation":classify(r,args.package)
        })

    by_state={}
    for i in interpreted:
        st=i["interpretation"]["interpreted_state"]
        by_state[st]=by_state.get(st,0)+1

    total_delta=sum(i["interpretation"]["confidence_delta"] for i in interpreted)

    if by_state.get("confirmed_marker_to_target_sink_runtime",0)>0:
        next_step="build_high_fidelity_proof_trace"
        research_state="strong_candidate_continue"
    elif by_state.get("target_runtime_sink_words_without_source_marker",0)>0:
        next_step="resolve_static_or_instrumented_trace_before_more_dynamic_testing"
        research_state="candidate_needs_trace"
    elif by_state.get("external_app_handoff_without_marker_propagation",0)>0:
        next_step="test_app_link_specific_hosts_and_reduce_generic_http_priority"
        research_state="deprioritize_generic_http_routes"
    else:
        next_step="select_next_candidate_path_or_next_apk"
        research_state="weak_or_inconclusive"

    out={
        "schema_version":"source_to_sink_probe_interpreter.v1",
        "created_at":int(time.time()),
        "source_results":args.results,
        "summary":{
            "probes_interpreted":len(interpreted),
            "by_state":by_state,
            "confidence_delta_total":round(total_delta,3),
            "research_state":research_state,
            "next_step":next_step,
            "candidate_only":True,
            "finding_allowed":False
        },
        "interpreted_results":interpreted
    }

    save(args.out,out)
    print(json.dumps(out["summary"], indent=2))

if __name__=="__main__":
    main()
