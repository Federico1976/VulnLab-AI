#!/usr/bin/env python3
from __future__ import annotations
import json, re, time
from pathlib import Path
from typing import Any, Dict, List

SINK_KEYWORDS = {
    "webview": ["webview", "loadurl", "evaluatejavascript", "addjavascriptinterface", "setjavascriptenabled"],
    "oauth": ["oauth", "redirect", "auth", "signin", "callback"],
    "fileprovider": ["fileprovider", "provider_paths", "content_uri", "granturipermissions", "external-path"],
    "api_network": ["retrofit", "okhttp", "graphql", "api", "request", "authorization"],
    "internal_navigation": ["globalnav", "navigation", "router", "deeplink", "destination"]
}

def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def text_of(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False).lower()

def score_path(entry: Dict[str,Any], ros: List[Dict[str,Any]]) -> Dict[str,Any]:
    comp = entry.get("component") or ""
    schemes = entry.get("schemes") or []
    cmd_count = len(entry.get("safe_dynamic_probe_commands") or [])
    entry_text = text_of(entry)

    candidate_sinks = []
    for ro in ros:
        t = text_of(ro)
        sink_hits = {}
        for sink, keys in SINK_KEYWORDS.items():
            hits = [k for k in keys if k in t]
            if hits:
                sink_hits[sink] = hits

        if not sink_hits:
            continue

        # generic weak correlation: same package/app surface or deeplink/webview terms
        corr = 0
        if comp and comp.lower() in t:
            corr += 4
        if "deeplink" in entry_text and "deeplink" in t:
            corr += 2
        if any(s in t for s in schemes):
            corr += 2
        if "oauth" in t and "oauth" in entry_text:
            corr += 4
        if "webview" in t and ("deeplink" in entry_text or schemes):
            corr += 2

        if corr == 0:
            corr = 1

        candidate_sinks.append({
            "research_object_id": ro.get("research_object_id"),
            "type": ro.get("type"),
            "title": ro.get("title"),
            "component_or_file": ro.get("component_or_file") or ro.get("component"),
            "sink_hits": sink_hits,
            "correlation_score": corr,
            "candidate_only": True,
            "finding_allowed": False
        })

    candidate_sinks.sort(key=lambda x: (x["correlation_score"], len(x["sink_hits"])), reverse=True)

    strongest = candidate_sinks[0] if candidate_sinks else None
    path_score = 0.0
    if comp:
        path_score += 0.2
    if schemes:
        path_score += 0.2
    if cmd_count:
        path_score += 0.15
    if strongest:
        path_score += min(0.35, strongest["correlation_score"] / 20)
    path_score = round(min(path_score, 1.0), 3)

    if not strongest:
        state = "no_sink_candidate_found"
        next_step = "treat_as_internal_ui_routing_until_more_evidence"
    elif path_score >= 0.65:
        state = "candidate_source_to_sink_path"
        next_step = "prove_runtime_source_to_sink_with_instrumentation"
    elif path_score >= 0.45:
        state = "weak_candidate_path_needs_trace"
        next_step = "resolve_static_call_chain_between_entrypoint_and_sink"
    else:
        state = "sink_present_but_causality_weak"
        next_step = "do_not_prioritize_until_correlation_improves"

    return {
        "entry_component": comp,
        "schemes": schemes,
        "actions": entry.get("actions") or [],
        "source": "external_intent_data_or_extras",
        "candidate_sinks": candidate_sinks[:8],
        "path_score": path_score,
        "causal_state": state,
        "next_step": next_step,
        "missing_evidence": [
            "ordered static call chain",
            "runtime instrumentation proving source reaches sink",
            "sanitizer/guard decision",
            "security impact"
        ],
        "candidate_only": True,
        "finding_allowed": False
    }

def main():
    import argparse
    ap=argparse.ArgumentParser(description="Source-to-Sink Causal Path Resolver v1")
    ap.add_argument("--local-plan", required=True)
    ap.add_argument("--research-objects", required=True)
    ap.add_argument("--runtime", required=False)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    plan=load(args.local_plan)
    ros=load(args.research_objects)
    if isinstance(ros, dict):
        ros = ros.get("research_objects") or ros.get("items") or []

    entries=plan.get("selected_plans") or []
    resolved=[score_path(e, ros) for e in entries if e.get("component")]

    resolved.sort(key=lambda x: x["path_score"], reverse=True)

    out={
        "schema_version":"source_to_sink_causal_path_resolver.v1",
        "created_at":int(time.time()),
        "summary":{
            "entries_seen":len(entries),
            "paths_resolved":len(resolved),
            "top_entry_component":resolved[0]["entry_component"] if resolved else None,
            "top_causal_state":resolved[0]["causal_state"] if resolved else None,
            "top_path_score":resolved[0]["path_score"] if resolved else 0,
            "candidate_only":True,
            "finding_allowed":False,
            "next_step":resolved[0]["next_step"] if resolved else "no_path"
        },
        "resolved_paths":resolved
    }
    save(args.out,out)
    print(json.dumps(out["summary"], indent=2))

if __name__=="__main__":
    main()
