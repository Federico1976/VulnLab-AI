import json
import sys
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_raw_item(item: Dict[str, Any]) -> Dict[str, Any]:
    rel = set(str(x).lower() for x in item.get("known_security_relevance", []))
    family = item.get("expected_case_family", "unknown")

    normalized = {
        "schema": "vulnlab.normalized_knowledge_item.v1",
        "source_id": item.get("source_id"),
        "title": item.get("title"),
        "source_type": item.get("source_type"),
        "ecosystem": item.get("ecosystem"),
        "family_hint": family,
        "semantic_security_relevance": {
            "trust_boundaries": [],
            "entrypoints": [],
            "sensitive_operations": [],
            "security_effects": [],
            "controls_or_validations": []
        },
        "reasoning_seed": {
            "attacker_position": "unknown",
            "attacker_controlled_input": "unknown",
            "trust_boundary": "unknown",
            "sensitive_operation": "unknown",
            "missing_or_weak_control": "unknown",
            "security_effect": "unknown",
            "exploit_primitive": "unknown"
        },
        "guardrail": {
            "candidate_only": True,
            "finding_allowed": False,
            "requires_verification_before_memory": True
        },
        "provenance": {
            "references": item.get("references", []),
            "summary": item.get("summary", ""),
            "ingestion_notes": item.get("ingestion_notes", {})
        }
    }

    def add(bucket: str, value: str):
        arr = normalized["semantic_security_relevance"][bucket]
        if value not in arr:
            arr.append(value)

    if "external_app_to_app_internal_boundary" in rel:
        add("trust_boundaries", "external_app_to_app_internal")
        normalized["reasoning_seed"]["attacker_position"] = "external_app"
        normalized["reasoning_seed"]["trust_boundary"] = "external_app_to_app_internal"

    if "content_uri_to_filesystem_boundary" in rel:
        add("trust_boundaries", "content_uri_to_filesystem")
        normalized["reasoning_seed"]["attacker_position"] = "external_app"
        normalized["reasoning_seed"]["trust_boundary"] = "content_uri_to_filesystem"

    if "web_content_to_native_code_boundary" in rel:
        add("trust_boundaries", "web_content_to_native_code")
        normalized["reasoning_seed"]["attacker_position"] = "malicious_web_content"
        normalized["reasoning_seed"]["trust_boundary"] = "web_content_to_native_code"

    if "app_internal_storage_to_attacker_boundary" in rel:
        add("trust_boundaries", "app_internal_storage_to_attacker")
        normalized["reasoning_seed"]["attacker_position"] = "same_device_app_or_local_attacker"
        normalized["reasoning_seed"]["trust_boundary"] = "app_internal_storage_to_attacker"

    if "uri_routing" in rel:
        for x in ["deeplink", "custom_scheme", "app_link"]:
            add("entrypoints", x)
        normalized["reasoning_seed"]["attacker_controlled_input"] = "intent_data_uri"

    if "exported_component" in rel:
        for x in ["exported_activity", "exported_service", "exported_receiver"]:
            add("entrypoints", x)
        normalized["reasoning_seed"]["attacker_controlled_input"] = "intent_extra_or_action"

    if "fileprovider_paths" in rel or "content_uri_grant" in rel:
        for x in ["content_provider", "fileprovider"]:
            add("entrypoints", x)
        normalized["reasoning_seed"]["attacker_controlled_input"] = "content_uri"

    if "javascript_interface" in rel:
        for x in ["webview_bridge", "javascript_interface"]:
            add("entrypoints", x)
        normalized["reasoning_seed"]["attacker_controlled_input"] = "javascript_payload"

    if "local_storage" in rel or "log_exposure" in rel or "backup_exposure" in rel:
        for x in ["local_storage", "logs", "backup", "exported_file"]:
            add("entrypoints", x)
        normalized["reasoning_seed"]["attacker_controlled_input"] = "local_or_backup_access"

    if "webview_navigation" in rel:
        add("sensitive_operations", "webview_load_url")
        normalized["reasoning_seed"]["sensitive_operation"] = "webview_load_url"
        normalized["reasoning_seed"]["exploit_primitive"] = "webview_navigation_injection"

    if "webview_add_javascript_interface" in rel or "native_bridge_invocation" in rel:
        add("sensitive_operations", "webview_add_javascript_interface")
        normalized["reasoning_seed"]["sensitive_operation"] = "webview_add_javascript_interface"
        normalized["reasoning_seed"]["exploit_primitive"] = "javascript_bridge_abuse"

    if "webview_evaluate_javascript" in rel:
        add("sensitive_operations", "webview_evaluate_javascript")

    if "file_read" in rel:
        add("sensitive_operations", "file_read")
        normalized["reasoning_seed"]["sensitive_operation"] = "file_read"
        normalized["reasoning_seed"]["exploit_primitive"] = "content_uri_confusion"

    if "privileged_action_execution" in rel:
        add("sensitive_operations", "privileged_action_execution")
        normalized["reasoning_seed"]["sensitive_operation"] = "privileged_action_execution"
        normalized["reasoning_seed"]["exploit_primitive"] = "intent_injection"

    if "token_read" in rel or "credential_use" in rel:
        add("sensitive_operations", "token_read")
        normalized["reasoning_seed"]["sensitive_operation"] = "token_read"
        normalized["reasoning_seed"]["exploit_primitive"] = "token_leakage"

    if "attacker_controlled_navigation" in rel:
        add("security_effects", "attacker_controlled_navigation")
        normalized["reasoning_seed"]["security_effect"] = "attacker_controlled_navigation"

    if "unauthorized_file_read" in rel:
        add("security_effects", "unauthorized_file_read")
        normalized["reasoning_seed"]["security_effect"] = "unauthorized_file_read"

    if "native_bridge_invocation" in rel:
        add("security_effects", "native_bridge_invocation")
        normalized["reasoning_seed"]["security_effect"] = "native_bridge_invocation"

    if "sensitive_data_exfiltration" in rel:
        add("security_effects", "sensitive_data_exfiltration")
        normalized["reasoning_seed"]["security_effect"] = "sensitive_data_exfiltration"

    if "privileged_action_execution" in rel:
        add("security_effects", "privileged_action_execution")
        normalized["reasoning_seed"]["security_effect"] = "privileged_action_execution"

    if "origin_validation" in rel or "missing_origin_check" in rel:
        add("controls_or_validations", "origin_validation")
        normalized["reasoning_seed"]["missing_or_weak_control"] = "weak_or_missing_origin_validation"

    if "path_scope_validation" in rel:
        add("controls_or_validations", "path_scope_validation")
        normalized["reasoning_seed"]["missing_or_weak_control"] = "weak_or_missing_path_scope_validation"

    if "missing_permission_check" in rel:
        add("controls_or_validations", "permission_check")
        normalized["reasoning_seed"]["missing_or_weak_control"] = "missing_permission_check"

    if "missing_caller_identity_check" in rel:
        add("controls_or_validations", "caller_identity_check")
        if normalized["reasoning_seed"]["missing_or_weak_control"] == "unknown":
            normalized["reasoning_seed"]["missing_or_weak_control"] = "missing_caller_identity_check"

    if normalized["reasoning_seed"]["security_effect"] == "unknown":
        normalized["reasoning_seed"]["security_effect"] = (
            normalized["semantic_security_relevance"]["security_effects"][0]
            if normalized["semantic_security_relevance"]["security_effects"]
            else "unknown"
        )

    return normalized


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python3 -m phase_c.knowledge_ingestion.knowledge_normalizer "
            "<raw_items_dir> <normalized_items_dir>"
        )

    raw_dir = Path(sys.argv[1])
    normalized_dir = Path(sys.argv[2])
    normalized_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for raw_path in sorted(raw_dir.glob("*.json")):
        item = load_json(raw_path)
        normalized = normalize_raw_item(item)
        out_path = normalized_dir / raw_path.name.replace(".json", ".normalized.json")
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(normalized, f, indent=2, ensure_ascii=False)
        count += 1

    print(json.dumps({
        "status": "ok",
        "normalized_items": count,
        "output_dir": str(normalized_dir)
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
