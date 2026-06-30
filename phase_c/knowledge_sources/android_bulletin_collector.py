import json
import sys
from pathlib import Path

from phase_c.knowledge_sources.source_collector_base import make_raw_item, write_raw_item


ANDROID_RELEVANCE_MAP = {
    "intent": [
        "external_app_to_app_internal_boundary",
        "exported_component",
        "intent_extra",
        "intent_action",
        "privileged_action_execution",
        "missing_permission_check"
    ],
    "webview": [
        "web_content_to_native_code_boundary",
        "javascript_interface",
        "webview_add_javascript_interface",
        "webview_evaluate_javascript",
        "missing_origin_check",
        "native_bridge_invocation"
    ],
    "file": [
        "content_uri_to_filesystem_boundary",
        "fileprovider_paths",
        "content_uri_grant",
        "file_read",
        "path_scope_validation",
        "unauthorized_file_read"
    ],
    "storage": [
        "app_internal_storage_to_attacker_boundary",
        "token_read",
        "credential_use",
        "local_storage",
        "backup_exposure",
        "sensitive_data_exfiltration"
    ]
}


def infer_family(tags):
    tags = set(tags)

    if "webview" in tags:
        return "webview_js_bridge_origin_confusion"
    if "file" in tags:
        return "fileprovider_exposure"
    if "intent" in tags:
        return "exported_component_intent_injection"
    if "storage" in tags:
        return "token_storage_exposure"

    return "android_platform_security_pattern"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python3 -m phase_c.knowledge_sources.android_bulletin_collector "
            "<bulletin_import_json> <raw_items_output_dir>"
        )

    import_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    with import_path.open("r", encoding="utf-8") as f:
        doc = json.load(f)

    items = doc.get("items", [])
    written = []

    for i, src in enumerate(items, start=1):
        tags = src.get("android_relevance_tags", [])
        relevance = []

        for tag in tags:
            relevance.extend(ANDROID_RELEVANCE_MAP.get(tag, []))

        source_id = src.get("source_id") or f"RAW-ANDROID-BULLETIN-{i:04d}"

        item = make_raw_item(
            source_id=source_id,
            source=src.get("source", "android_security_bulletin_manual_import"),
            source_type="android_security_bulletin",
            title=src["title"],
            summary=src["summary"],
            ecosystem="android",
            references=src.get("references", []),
            known_security_relevance=sorted(set(relevance)),
            expected_case_family=src.get("expected_case_family") or infer_family(tags),
            human_reviewed=bool(src.get("human_reviewed", False))
        )

        path = write_raw_item(item, output_dir)
        written.append(str(path))

    print(json.dumps({
        "status": "ok",
        "collector": "android_bulletin_collector",
        "items_imported": len(written),
        "outputs": written
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
