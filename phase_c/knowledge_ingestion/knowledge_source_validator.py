from typing import Any, Dict, List


REQUIRED_RAW_FIELDS = [
    "schema",
    "source",
    "source_type",
    "title",
    "summary",
    "ecosystem",
    "references",
    "ingestion_notes"
]


VALID_SOURCE_TYPES = {
    "android_security_bulletin",
    "nvd_cve",
    "github_advisory",
    "osv",
    "public_writeup",
    "patch_diff",
    "manual_research_note"
}


def validate_raw_knowledge_item(item: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    for field in REQUIRED_RAW_FIELDS:
        if field not in item:
            errors.append(f"missing_raw_field:{field}")

    source_type = item.get("source_type")
    if source_type and source_type not in VALID_SOURCE_TYPES:
        warnings.append(f"unknown_source_type:{source_type}")

    refs = item.get("references", [])
    if not isinstance(refs, list) or not refs:
        errors.append("references_empty_or_not_list")

    if not item.get("summary"):
        errors.append("summary_empty")

    status = "valid" if not errors else "quarantine"

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings
    }
