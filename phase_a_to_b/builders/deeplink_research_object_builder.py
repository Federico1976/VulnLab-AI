#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_candidates(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("findings", "candidates", "deeplink_candidates", "items"):
            if isinstance(payload.get(key), list):
                return [x for x in payload[key] if isinstance(x, dict)]
    return []


def build_ro(candidate: Dict[str, Any], idx: int, apk_out: Path) -> Dict[str, Any]:
    component = (
        candidate.get("component")
        or candidate.get("activity")
        or candidate.get("class")
        or candidate.get("name")
        or f"deeplink_component_{idx}"
    )

    priority = candidate.get("priority") or candidate.get("candidate_priority") or candidate.get("score")
    schemes = candidate.get("schemes") or []
    hosts = candidate.get("hosts") or []
    paths = candidate.get("paths") or []

    return {
        "schema": "vulnlab_ai.research_object.v2",
        "research_object_id": f"RO-DEEPLINK-{idx:03d}",
        "type": "deeplink_entrypoint_research_object",
        "title": f"DeepLink entrypoint candidate: {component}",
        "status": "candidate_evidence_only",
        "confidence": "medium" if priority else "low",
        "source": "phase_a_to_b.deeplink_research_object_builder.v2",
        "paradigm": "android_deeplink_intent_entrypoint",
        "component": component,
        "priority": priority,
        "evidence": [
            {
                "kind": "deeplink_manifest_candidate",
                "source_file": str(apk_out / "deeplink_manifest_candidates.json"),
                "component": component,
                "schemes": schemes,
                "hosts": hosts,
                "paths": paths,
                "raw": candidate,
            }
        ],
        "capability_hints": [
            "external_intent_entrypoint",
            "uri_based_navigation",
            "content_uri_or_file_uri_input",
            "media_uri_consumption",
        ],
        "security_effect_hints": [
            "possible_external_uri_to_file_access",
            "possible_untrusted_uri_to_media_parser",
            "possible_deeplink_triggered_sensitive_operation",
            "possible_path_or_scheme_confusion",
        ],
        "proof_requirements": [
            "manifest_intent_filter_attributes",
            "exported_component_state",
            "scheme_host_path_scope_analysis",
            "external_triggerability",
            "uri_source_controllability",
            "intent_extra_or_data_flow_resolution",
            "source_to_sink_causal_path",
            "guard_or_permission_check",
            "dynamic_validation_before_finding",
        ],
        "unknowns": [
            "Is the component externally exported and triggerable?",
            "Can an external app control the Intent data URI?",
            "Which URI schemes, hosts, and paths are accepted?",
            "Does the URI reach file, media, network, parser, or storage sinks?",
            "Are content:// and file:// inputs handled safely?",
            "Are permissions, MIME checks, or validation guards present?",
            "Can the candidate be reproduced dynamically without unsafe side effects?",
        ],
        "trust_boundary_hints": [
            "external_app_to_exported_component_boundary",
            "intent_data_uri_boundary",
            "uri_scheme_to_internal_parser_boundary",
        ],
        "asset_hints": [
            "intent_data_uri",
            "media_file_reference",
            "content_provider_uri",
            "network_stream_uri",
        ],
        "dynamic_validation_seeds": [
            "adb_am_start_with_candidate_uri",
            "adb_am_start_with_content_uri",
            "adb_am_start_with_file_uri_if_safe",
            "capture_logcat_and_activity_launch",
            "verify_sink_reachability",
            "verify_guard_or_rejection_behavior",
        ],
        "research_strategy_tags": [
            "deeplink",
            "intent_filter",
            "external_entrypoint",
            "uri_input",
            "candidate_only",
            "requires_dynamic_validation",
        ],
        "finding_policy": {
            "may_declare_vulnerability": False,
            "candidate_only": True,
            "requires_causal_reachability": True,
            "requires_dynamic_validation": True,
            "reason": "DeepLink Research Object only. Needs causal reachability and dynamic validation.",
        },
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_a_to_b.builders.deeplink_research_object_builder <apk_output_dir> <output_json>")
        sys.exit(1)

    apk_out = Path(sys.argv[1])
    output = Path(sys.argv[2])

    payload = load(apk_out / "deeplink_manifest_candidates.json")
    candidates = get_candidates(payload)

    ros = [build_ro(c, i + 1, apk_out) for i, c in enumerate(candidates)]

    save(output, {
        "schema": "vulnlab_ai.research_objects.deeplink.v2",
        "count": len(ros),
        "research_objects": ros,
    })

    print(f"[OK] deeplink_research_objects={len(ros)} -> {output}")


if __name__ == "__main__":
    main()
