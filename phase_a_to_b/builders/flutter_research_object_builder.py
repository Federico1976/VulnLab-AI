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
        print("Usage: python3 -m phase_a_to_b.builders.flutter_research_object_builder <apk_out> <out_json>")
        sys.exit(1)

    apk_out=Path(sys.argv[1]); out=Path(sys.argv[2])
    char=load(apk_out/"apk_characterization.json")
    text=json.dumps(char).lower()
    ros=[]

    if "flutter" in text or "flutter_surface_hunt" in text or "libflutter.so" in text:
        ros.append({
            "schema":"vulnlab_ai.research_object.v2",
            "research_object_id":"RO-FLUTTER-001",
            "type":"flutter_runtime_research_object",
            "title":"Flutter runtime / platform channel candidate surface",
            "status":"candidate_evidence_only",
            "confidence":"medium",
            "source":"phase_a_to_b.flutter_research_object_builder.v2",
            "paradigm":"flutter_android",
            "runtime_family":"flutter",
            "evidence":[{
                "kind":"apk_characterization_feature",
                "source_file":str(apk_out/"apk_characterization.json"),
                "features":char.get("detected_features") or char.get("features"),
                "recommended_pipelines":char.get("recommended_pipelines") or char.get("recommended")
            }],
            "capability_hints":[
                "dart_runtime_execution",
                "flutter_platform_channel_invocation",
                "method_channel_to_native_bridge",
                "flutter_asset_or_storage_access",
                "network_or_file_surface"
            ],
            "security_effect_hints":[
                "possible_dart_to_native_sensitive_operation",
                "possible_platform_channel_argument_influence",
                "possible_file_or_network_access_from_flutter_surface"
            ],
            "proof_requirements":[
                "flutter_assets_presence",
                "platform_channel_inventory",
                "method_channel_handler_mapping",
                "dart_or_ui_source_controllability",
                "native_handler_sink_resolution",
                "source_to_sink_causal_path",
                "guard_or_permission_check",
                "dynamic_validation_before_finding"
            ],
            "unknowns":[
                "Which platform channels are registered?",
                "Which native handlers receive Dart-controlled arguments?",
                "Can user-controlled input influence channel calls?",
                "Which file, network, storage, or permission sinks are reachable?",
                "Are guards, permissions, or validation checks present?",
                "Can the candidate be reproduced dynamically?"
            ],
            "trust_boundary_hints":[
                "dart_to_native_platform_channel_boundary",
                "flutter_ui_state_to_native_handler_boundary"
            ],
            "dynamic_validation_seeds":[
                "exercise_flutter_ui",
                "trace_platform_channel_calls",
                "capture_logcat_runtime_trace",
                "verify_native_handler_reachability",
                "verify_argument_controllability"
            ],
            "research_strategy_tags":["flutter","platform_channel","dart_to_native","candidate_only"],
            "finding_policy":{
                "may_declare_vulnerability":False,
                "candidate_only":True,
                "requires_causal_reachability":True,
                "requires_dynamic_validation":True
            }
        })

    save(out, {"schema":"vulnlab_ai.research_objects.flutter.v2","count":len(ros),"research_objects":ros})
    print(f"[OK] flutter_research_objects={len(ros)} -> {out}")

if __name__=="__main__":
    main()
