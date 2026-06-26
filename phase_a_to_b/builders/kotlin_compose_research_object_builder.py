#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def load(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def has_kotlin_compose(char):
    features = char.get("detected_features") or char.get("features") or {}
    recommended = char.get("recommended_pipelines") or char.get("recommended") or []

    text = json.dumps({"features": features, "recommended": recommended}).lower()
    return "kotlin" in text or "compose" in text or "kotlin_compose_static_hunt" in text


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_a_to_b.builders.kotlin_compose_research_object_builder <apk_output_dir> <output_json>")
        sys.exit(1)

    apk_out = Path(sys.argv[1])
    output = Path(sys.argv[2])
    char = load(apk_out / "apk_characterization.json")

    ros = []

    if has_kotlin_compose(char):
        ros.append({
            "schema": "vulnlab_ai.research_object.v2",
            "research_object_id": "RO-KOTLIN-COMPOSE-001",
            "type": "kotlin_compose_runtime_research_object",
            "title": "Kotlin/Compose UI-to-logic reachability candidate",
            "status": "candidate_evidence_only",
            "confidence": "medium",
            "source": "phase_a_to_b.kotlin_compose_research_object_builder.v2",
            "paradigm": "android_kotlin_jetpack_compose",
            "runtime_family": "android_native_kotlin_compose",
            "evidence": [
                {
                    "kind": "apk_characterization_feature",
                    "source_file": str(apk_out / "apk_characterization.json"),
                    "features": char.get("detected_features") or char.get("features"),
                    "recommended_pipelines": char.get("recommended_pipelines") or char.get("recommended"),
                }
            ],
            "capability_hints": [
                "compose_ui_event_entrypoint",
                "ui_state_to_viewmodel_dispatch",
                "kotlin_coroutine_async_execution",
                "navigation_route_to_logic_handler",
            ],
            "security_effect_hints": [
                "possible_ui_reachable_sensitive_operation",
                "possible_async_flow_to_sensitive_sink",
                "possible_navigation_argument_influence",
            ],
            "proof_requirements": [
                "compose_entrypoint_identification",
                "click_or_input_handler_mapping",
                "state_holder_or_viewmodel_resolution",
                "navigation_argument_resolution",
                "coroutine_boundary_resolution",
                "source_to_sink_causal_path",
                "guard_or_authorization_check",
                "dynamic_validation_before_finding",
            ],
            "unknowns": [
                "Which Compose handlers are user-triggerable?",
                "Which state variables or navigation arguments are externally controllable?",
                "Which ViewModel or controller methods receive UI-controlled data?",
                "Do coroutine boundaries preserve the candidate data flow?",
                "Which sensitive sinks are reachable from UI actions?",
                "Are validation, authorization, or lifecycle guards present?",
            ],
            "trust_boundary_hints": [
                "user_interface_to_application_logic_boundary",
                "compose_state_to_viewmodel_boundary",
                "navigation_argument_boundary",
                "coroutine_async_execution_boundary",
            ],
            "dynamic_validation_seeds": [
                "launch_activity_and_exercise_ui",
                "trigger_candidate_compose_action",
                "capture_logcat_runtime_trace",
                "observe_navigation_or_viewmodel_dispatch",
                "verify_sink_reachability",
            ],
            "research_strategy_tags": [
                "kotlin",
                "jetpack_compose",
                "ui_reachability",
                "coroutines",
                "candidate_only",
                "requires_dynamic_validation",
            ],
            "finding_policy": {
                "may_declare_vulnerability": False,
                "candidate_only": True,
                "requires_causal_reachability": True,
                "requires_dynamic_validation": True,
                "reason": "Kotlin/Compose Research Object only. Needs causal reachability and dynamic validation.",
            },
        })

    save(output, {
        "schema": "vulnlab_ai.research_objects.kotlin_compose.v2",
        "count": len(ros),
        "research_objects": ros,
    })

    print(f"[OK] kotlin_compose_research_objects={len(ros)} -> {output}")


if __name__ == "__main__":
    main()
