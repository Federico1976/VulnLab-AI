#!/usr/bin/env python3
import json, sys
from pathlib import Path

def load(p):
    p=Path(p)
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def candidates(payload):
    if isinstance(payload, list): return [x for x in payload if isinstance(x,dict)]
    if isinstance(payload, dict):
        for k in ("findings","candidates","webview_candidates","items"):
            if isinstance(payload.get(k), list): return [x for x in payload[k] if isinstance(x,dict)]
    return []

def build(c, i, apk_out):
    loc=c.get("file") or c.get("path") or c.get("class") or c.get("method") or f"webview_candidate_{i}"
    reasons=c.get("reasons") or []
    return {
        "schema":"vulnlab_ai.research_object.v2",
        "research_object_id":f"RO-WEBVIEW-{i:03d}",
        "type":"webview_runtime_research_object",
        "title":f"WebView candidate surface: {Path(str(loc)).name}",
        "status":"candidate_evidence_only",
        "confidence":"medium",
        "source":"phase_a_to_b.webview_research_object_builder.v2",
        "paradigm":"android_webview",
        "component_or_file":str(loc),
        "evidence":[{
            "kind":"webview_static_candidate",
            "source_file":str(apk_out/"webview_static_candidates.json"),
            "reasons":reasons,
            "raw":c
        }],
        "capability_hints":[
            "webview_url_loading",
            "javascript_execution_surface",
            "javascript_interface_bridge",
            "ssl_error_handling_surface",
            "external_url_or_content_loading"
        ],
        "security_effect_hints":[
            "possible_untrusted_url_load",
            "possible_js_bridge_exposure",
            "possible_ssl_error_bypass_candidate",
            "possible_deeplink_to_webview_flow"
        ],
        "proof_requirements":[
            "webview_callsite_identification",
            "url_source_controllability",
            "javascript_enabled_state",
            "javascript_interface_inventory",
            "ssl_error_handler_behavior",
            "deeplink_or_external_entrypoint_correlation",
            "source_to_sink_causal_path",
            "dynamic_validation_before_finding"
        ],
        "unknowns":[
            "Can external input influence the loaded URL?",
            "Is JavaScript enabled?",
            "Are JavaScript interfaces exposed to untrusted content?",
            "Does WebView handle SSL errors safely?",
            "Is there a deeplink-to-WebView causal path?",
            "Can the candidate be reproduced dynamically?"
        ],
        "trust_boundary_hints":[
            "external_uri_to_webview_boundary",
            "web_content_to_native_bridge_boundary"
        ],
        "dynamic_validation_seeds":[
            "launch_candidate_webview_flow",
            "supply_safe_controlled_url",
            "observe_loadurl_or_evaluatejavascript",
            "check_javascript_interface_exposure",
            "check_ssl_error_behavior"
        ],
        "research_strategy_tags":["webview","loadurl","javascript_bridge","candidate_only"],
        "finding_policy":{
            "may_declare_vulnerability":False,
            "candidate_only":True,
            "requires_causal_reachability":True,
            "requires_dynamic_validation":True
        }
    }

def main():
    if len(sys.argv)!=3:
        print("Usage: python3 -m phase_a_to_b.builders.webview_research_object_builder <apk_out> <out_json>")
        sys.exit(1)

    apk_out=Path(sys.argv[1]); out=Path(sys.argv[2])
    payload=load(apk_out/"webview_static_candidates.json")
    cs=candidates(payload)
    ros=[build(c,i+1,apk_out) for i,c in enumerate(cs[:25])]
    save(out, {"schema":"vulnlab_ai.research_objects.webview.v2","count":len(ros),"research_objects":ros})
    print(f"[OK] webview_research_objects={len(ros)} -> {out}")

if __name__=="__main__":
    main()
