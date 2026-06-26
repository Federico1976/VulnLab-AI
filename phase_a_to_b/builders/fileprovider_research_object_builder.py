#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


FILEPROVIDER_TERMS = [
    "FileProvider",
    "androidx.core.content.FileProvider",
    "android.support.v4.content.FileProvider",
    "provider",
    "grantUriPermissions",
    "android:authorities",
    "android:exported",
    "android:resource",
    "file_paths",
    "external-path",
    "root-path",
    "cache-path",
    "external-files-path",
]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def collect_manifest_candidates(apk_out: Path) -> List[Dict[str, Any]]:
    candidates = []

    for path in apk_out.rglob("AndroidManifest.xml"):
        text = read_text(path)
        if "FileProvider" not in text and "provider" not in text:
            continue

        if any(term in text for term in FILEPROVIDER_TERMS):
            candidates.append({
                "kind": "manifest_provider_candidate",
                "file": str(path),
                "signals": [t for t in FILEPROVIDER_TERMS if t in text],
                "snippet": text[:5000],
            })

    return candidates


def collect_paths_xml_candidates(apk_out: Path) -> List[Dict[str, Any]]:
    candidates = []

    for path in apk_out.rglob("*.xml"):
        name = path.name.lower()
        text = read_text(path)

        if (
            "file_paths" in name
            or "paths" in name
            or "external-path" in text
            or "root-path" in text
            or "cache-path" in text
            or "external-files-path" in text
        ):
            candidates.append({
                "kind": "fileprovider_paths_candidate",
                "file": str(path),
                "signals": [t for t in FILEPROVIDER_TERMS if t in text or t in name],
                "snippet": text[:5000],
            })

    return candidates


def build_research_objects(apk_out: Path) -> List[Dict[str, Any]]:
    manifest_candidates = collect_manifest_candidates(apk_out)
    paths_candidates = collect_paths_xml_candidates(apk_out)

    if not manifest_candidates and not paths_candidates:
        return []

    evidence = manifest_candidates + paths_candidates

    ro = {
        "schema": "vulnlab_ai.research_object.v1",
        "research_object_id": "RO-FILEPROVIDER-001",
        "type": "fileprovider_exposure_research_object",
        "title": "FileProvider exposure candidate",
        "status": "candidate_evidence_only",
        "confidence": "medium",
        "semantic_completeness_v2": "native_fileprovider_research_object",
        "source": "phase_a_to_b.fileprovider_research_object_builder.v2",
        "paradigm": "android_fileprovider",
        "capability_hints": [
            "content_uri_file_sharing",
            "uri_permission_granting",
            "path_mapping_based_file_access",
        ],
        "security_effect_hints": [
            "possible_unintended_file_exposure",
            "possible_overbroad_path_mapping",
            "possible_authority_abuse_if_reachable",
        ],
        "evidence": evidence,
        "unknowns": [
            "Is the FileProvider externally reachable through an exported component?",
            "Can an external caller trigger URI creation or URI consumption?",
            "Are URI permissions granted only intentionally?",
            "Which file system paths are mapped?",
            "Do mapped paths include broad or sensitive locations?",
            "Can attacker-controlled input influence the selected path or file name?",
            "Is there canonicalization against traversal or path confusion?",
            "Is there a causal source-to-sink path from external input to file access or sharing?",
            "What dynamic validation is required to reproduce or disprove the candidate?",
        ],
        "proof_requirements": [
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
        ],
        "trust_boundary_hints": [
            "external_intent_or_component_boundary",
            "content_uri_permission_boundary",
            "app_private_storage_to_external_storage_boundary"
        ],
        "asset_hints": [
            "shared_cache_files",
            "external_download_files",
            "content_uri_targets"
        ],
        "dynamic_validation_seeds": [
            "install_apk_in_instrumented_device",
            "trigger_candidate_entrypoint",
            "capture_logcat_and_runtime_trace",
            "verify_source_controllability",
            "verify_sink_reachability",
            "confirm_or_disprove_with_dynamic_validation"
        ],
        "research_strategy_tags": [
            "fileprovider",
            "content_uri",
            "path_mapping",
            "candidate_only",
            "requires_dynamic_validation"
        ],
        "evidence_weight": {
            "manifest_provider_attributes": "medium",
            "paths_xml_mapping": "medium",
            "callsite_reachability": "high",
            "dynamic_validation": "mandatory"
        },
        "finding_policy": {
            "may_declare_vulnerability": False,
            "candidate_only": True,
            "requires_causal_reachability": True,
            "requires_dynamic_validation": True,
            "reason": "Research object only. Needs causal reachability and dynamic validation.",
        },
    }

    return [ro]


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 -m phase_a_to_b.builders.fileprovider_research_object_builder <apk_output_dir> <output_json>")
        sys.exit(1)

    apk_out = Path(sys.argv[1])
    output_json = Path(sys.argv[2])
    output_json.parent.mkdir(parents=True, exist_ok=True)

    ros = build_research_objects(apk_out)

    output_json.write_text(
        json.dumps(
            {
                "schema": "vulnlab_ai.research_objects.fileprovider.v2",
                "count": len(ros),
                "research_objects": ros,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"[OK] fileprovider_research_objects={len(ros)} -> {output_json}")


if __name__ == "__main__":
    main()
