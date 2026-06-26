#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


FILEPROVIDER_CAPABILITIES = [
    "content_uri_file_sharing",
    "uri_permission_granting",
    "path_mapping_based_file_access",
    "external_storage_surface",
]

FILEPROVIDER_EFFECTS = [
    "possible_unintended_file_exposure",
    "possible_overbroad_path_mapping",
    "possible_authority_abuse_if_reachable",
    "possible_external_storage_data_exposure",
]

FILEPROVIDER_PROOF_REQUIREMENTS = [
    "manifest_provider_attributes",
    "provider_exported_state",
    "grant_uri_permissions_state",
    "file_paths_xml_semantics",
    "authority_resolution",
    "mapped_path_scope_analysis",
    "caller_reachability",
    "uri_generation_or_consumption_callsite",
    "attacker_influence_over_uri_or_path",
    "source_to_sink_causal_path",
    "sanitizer_or_canonicalization_check",
    "dynamic_validation_before_finding",
]

FILEPROVIDER_UNKNOWNS = [
    "Is the FileProvider externally reachable through an exported component?",
    "Can an external caller trigger URI creation or URI consumption?",
    "Are URI permissions granted only intentionally?",
    "Which file system paths are mapped?",
    "Do mapped paths include broad or sensitive locations?",
    "Can attacker-controlled input influence the selected path or file name?",
    "Is there canonicalization against traversal or path confusion?",
    "Is there a causal source-to-sink path from external input to file access or sharing?",
    "What dynamic validation is required to reproduce or disprove the candidate?",
]

KOTLIN_COMPOSE_CAPABILITIES = [
    "ui_state_to_logic_dispatch",
    "compose_event_handler_entrypoint",
    "kotlin_coroutine_async_flow",
]

KOTLIN_COMPOSE_EFFECTS = [
    "possible_ui_reachable_sensitive_operation",
    "possible_async_flow_to_sensitive_sink",
]

KOTLIN_COMPOSE_PROOF_REQUIREMENTS = [
    "compose_entrypoint_identification",
    "event_handler_to_viewmodel_or_logic_path",
    "coroutine_boundary_resolution",
    "source_to_sink_causal_path",
    "state_validation_or_guard_check",
    "dynamic_validation_before_finding",
]

KOTLIN_COMPOSE_UNKNOWNS = [
    "Which Compose event handlers are externally user-triggerable?",
    "Which ViewModel or controller methods receive UI-controlled state?",
    "Do coroutine boundaries preserve attacker-controlled data?",
    "Which sensitive sinks are reachable from UI actions?",
    "Are validation or authorization checks present before the sink?",
]

GENERIC_POLICY = {
    "may_declare_vulnerability": False,
    "candidate_only": True,
    "requires_causal_reachability": True,
    "requires_dynamic_validation": True,
    "reason": "Research Object only. Do not declare a vulnerability without causal reachability and dynamic validation.",
}

GENERIC_DYNAMIC_SEEDS = [
    "install_apk_in_instrumented_device",
    "trigger_candidate_entrypoint",
    "capture_logcat_and_runtime_trace",
    "verify_source_controllability",
    "verify_sink_reachability",
    "confirm_or_disprove_with_dynamic_validation",
]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: Any):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_ros(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("research_objects", "objects", "items"):
            if isinstance(payload.get(key), list):
                return [x for x in payload[key] if isinstance(x, dict)]
    return []


def as_text(ro: Dict[str, Any]) -> str:
    fields = [
        ro.get("research_object_id"),
        ro.get("object_id"),
        ro.get("id"),
        ro.get("type"),
        ro.get("object_type"),
        ro.get("title"),
        ro.get("runtime_family"),
        ro.get("paradigm"),
        ro.get("primary_capability"),
        ro.get("category"),
    ]
    return " ".join(str(x).lower() for x in fields if x)


def merge_list(ro: Dict[str, Any], key: str, values: List[str]) -> int:
    existing = ro.get(key)
    if not isinstance(existing, list):
        existing = []

    before = len(existing)
    seen = set(str(x) for x in existing)

    for v in values:
        if v not in seen:
            existing.append(v)
            seen.add(v)

    ro[key] = existing
    return len(existing) - before


def ensure_policy(ro: Dict[str, Any]) -> int:
    policy = ro.get("finding_policy")
    changed = 0

    if not isinstance(policy, dict):
        ro["finding_policy"] = dict(GENERIC_POLICY)
        return 1

    for k, v in GENERIC_POLICY.items():
        if k not in policy:
            policy[k] = v
            changed += 1

    ro["finding_policy"] = policy
    return changed


def enrich_fileprovider(ro: Dict[str, Any]) -> int:
    changed = 0
    changed += merge_list(ro, "capability_hints", FILEPROVIDER_CAPABILITIES)
    changed += merge_list(ro, "security_effect_hints", FILEPROVIDER_EFFECTS)
    changed += merge_list(ro, "proof_requirements", FILEPROVIDER_PROOF_REQUIREMENTS)
    changed += merge_list(ro, "unknowns", FILEPROVIDER_UNKNOWNS)
    changed += merge_list(ro, "dynamic_validation_seeds", GENERIC_DYNAMIC_SEEDS)

    ro.setdefault("trust_boundary_hints", [
        "external_intent_or_component_boundary",
        "content_uri_permission_boundary",
        "app_private_storage_to_external_storage_boundary",
    ])

    ro.setdefault("asset_hints", [
        "shared_cache_files",
        "external_download_files",
        "content_uri_targets",
    ])

    ro.setdefault("research_strategy_tags", [
        "fileprovider",
        "content_uri",
        "path_mapping",
        "candidate_only",
        "requires_dynamic_validation",
    ])

    ro.setdefault("evidence_weight", {
        "manifest_provider_attributes": "medium",
        "paths_xml_mapping": "medium",
        "callsite_reachability": "high",
        "dynamic_validation": "mandatory",
    })

    changed += ensure_policy(ro)
    ro["semantic_completeness_v2"] = "research_object_v2_enriched"
    return changed


def enrich_kotlin_compose(ro: Dict[str, Any]) -> int:
    changed = 0
    changed += merge_list(ro, "capability_hints", KOTLIN_COMPOSE_CAPABILITIES)
    changed += merge_list(ro, "security_effect_hints", KOTLIN_COMPOSE_EFFECTS)
    changed += merge_list(ro, "proof_requirements", KOTLIN_COMPOSE_PROOF_REQUIREMENTS)
    changed += merge_list(ro, "unknowns", KOTLIN_COMPOSE_UNKNOWNS)
    changed += merge_list(ro, "dynamic_validation_seeds", GENERIC_DYNAMIC_SEEDS)

    ro.setdefault("trust_boundary_hints", [
        "user_interface_to_application_logic_boundary",
        "compose_state_to_viewmodel_boundary",
        "coroutine_async_execution_boundary",
    ])

    ro.setdefault("research_strategy_tags", [
        "kotlin",
        "jetpack_compose",
        "ui_reachability",
        "candidate_only",
    ])

    changed += ensure_policy(ro)
    ro["semantic_completeness_v2"] = "research_object_v2_enriched"
    return changed


def enrich_generic(ro: Dict[str, Any]) -> int:
    changed = 0
    changed += merge_list(ro, "proof_requirements", [
        "source_identification",
        "sink_identification",
        "reachability_analysis",
        "guard_or_sanitizer_analysis",
        "causal_path_validation",
        "dynamic_validation_before_finding",
    ])
    changed += merge_list(ro, "unknowns", [
        "What is the attacker-controlled source?",
        "What is the security-sensitive sink?",
        "Is there a causal and reachable path?",
        "Are there guards, sanitizers, authorization checks, or platform constraints?",
        "What dynamic validation is required?",
    ])
    changed += merge_list(ro, "dynamic_validation_seeds", GENERIC_DYNAMIC_SEEDS)
    changed += ensure_policy(ro)
    ro.setdefault("research_strategy_tags", ["generic_candidate", "candidate_only"])
    ro["semantic_completeness_v2"] = "research_object_v2_generic_enriched"
    return changed


def enrich_ro(ro: Dict[str, Any]) -> int:
    text = as_text(ro)

    if "fileprovider" in text or "file_provider" in text or "content_uri" in text:
        return enrich_fileprovider(ro)

    if "compose" in text or "kotlin" in text or "ui_runtime_surface" in text:
        return enrich_kotlin_compose(ro)

    return enrich_generic(ro)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_a_to_b.research_object_enricher_v2 <input_research_objects.json> <output_research_objects.json>")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2])

    payload = load(inp)
    ros = get_ros(payload)

    enriched = 0
    total_changes = 0

    for ro in ros:
        changes = enrich_ro(ro)
        if changes > 0:
            enriched += 1
            total_changes += changes

    if isinstance(payload, list):
        result = ros
    else:
        result = payload
        if isinstance(result, dict):
            result["schema"] = "vulnlab_ai.research_objects.v2_enriched"
            result["v2_summary"] = {
                "research_objects": len(ros),
                "enriched_research_objects": enriched,
                "total_semantic_additions": total_changes,
            }

    save(out, result)

    print(json.dumps({
        "status": "ok",
        "research_objects": len(ros),
        "enriched_research_objects": enriched,
        "total_semantic_additions": total_changes,
        "output": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
