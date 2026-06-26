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

def main():
    if len(sys.argv)!=3:
        print("Usage: python3 -m phase_a_to_b.builders.react_native_research_object_builder <apk_out> <out_json>")
        sys.exit(1)

    apk_out=Path(sys.argv[1]); out=Path(sys.argv[2])
    char=load(apk_out/"apk_characterization.json")
    text=json.dumps(char).lower()
    ros=[]

    if "react_native" in text or "rn_multilayer_hunt" in text or "hermes" in text:
        ros.append({
            "schema":"vulnlab_ai.research_object.v2",
            "research_object_id":"RO-REACT-NATIVE-001",
            "type":"react_native_bridge_runtime_research_object",
            "title":"React Native / Hermes bridge and JS bundle candidate surface",
            "status":"candidate_evidence_only",
            "confidence":"medium",
            "source":"phase_a_to_b.react_native_research_object_builder.v2",
            "paradigm":"react_native_hermes_android",
            "runtime_family":"react_native",
            "evidence":[{
                "kind":"apk_characterization_feature",
                "source_file":str(apk_out/"apk_characterization.json"),
                "features":char.get("detected_features") or char.get("features"),
                "recommended_pipelines":char.get("recommended_pipelines") or char.get("recommended")
            }],
            "capability_hints":[
                "javascript_bundle_execution",
                "native_module_bridge_invocation",
                "hermes_runtime_execution",
                "js_to_native_data_flow",
                "async_storage_or_network_surface"
            ],
            "security_effect_hints":[
                "possible_js_to_native_sensitive_operation",
                "possible_bridge_argument_influence",
                "possible_storage_or_crypto_sensitive_flow",
                "possible_network_request_surface"
            ],
            "proof_requirements":[
                "js_bundle_presence",
                "native_module_inventory",
                "bridge_method_mapping",
                "js_callsite_to_native_method_resolution",
                "argument_controllability",
                "source_to_sink_causal_path",
                "guard_or_authorization_check",
                "dynamic_validation_before_finding"
            ],
            "unknowns":[
                "Which native modules are exposed to JavaScript?",
                "Which JS callsites invoke sensitive native methods?",
                "Can user-controlled input influence bridge arguments?",
                "Are storage, crypto, network, file, or account APIs reachable through the bridge?",
                "Are there authorization, validation, or runtime guards?",
                "Can the candidate be reproduced dynamically?"
            ],
            "trust_boundary_hints":[
                "javascript_to_native_bridge_boundary",
                "hermes_runtime_to_android_api_boundary",
                "user_input_to_js_state_boundary"
            ],
            "dynamic_validation_seeds":[
                "exercise_react_native_ui",
                "capture_js_bridge_runtime_logs",
                "trace_native_module_invocations",
                "verify_argument_controllability",
                "verify_sensitive_sink_reachability"
            ],
            "research_strategy_tags":["react_native","hermes","bridge","js_to_native","candidate_only"],
            "finding_policy":{
                "may_declare_vulnerability":False,
                "candidate_only":True,
                "requires_causal_reachability":True,
                "requires_dynamic_validation":True
            }
        })

    save(out, {"schema":"vulnlab_ai.research_objects.react_native.v2","count":len(ros),"research_objects":ros})
    print(f"[OK] react_native_research_objects={len(ros)} -> {out}")

if __name__=="__main__":
    main()
