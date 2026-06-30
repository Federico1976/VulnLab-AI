import json
import re
from pathlib import Path
from typing import Any, Dict


def slugify(value: str) -> str:
    value = (value or "unknown").lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "unknown"


def load_json(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def write_raw_item(item: Dict[str, Any], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    source_id = item.get("source_id", "RAW-UNKNOWN")
    filename = slugify(source_id) + ".json"
    path = out / filename

    with path.open("w", encoding="utf-8") as f:
        json.dump(item, f, indent=2, ensure_ascii=False)

    return path


def make_raw_item(
    source_id: str,
    source: str,
    source_type: str,
    title: str,
    summary: str,
    ecosystem: str,
    references: list,
    known_security_relevance: list,
    expected_case_family: str,
    human_reviewed: bool = False
) -> Dict[str, Any]:
    return {
        "schema": "vulnlab.raw_knowledge_item.v1",
        "source_id": source_id,
        "source": source,
        "source_type": source_type,
        "title": title,
        "summary": summary,
        "ecosystem": ecosystem,
        "references": references,
        "known_security_relevance": known_security_relevance,
        "expected_case_family": expected_case_family,
        "ingestion_notes": {
            "human_reviewed": human_reviewed,
            "safe_for_memory_training": human_reviewed,
            "candidate_only": True,
            "do_not_use_as_finding": True
        }
    }
