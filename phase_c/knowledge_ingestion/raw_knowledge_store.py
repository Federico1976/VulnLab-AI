import json
from pathlib import Path
from typing import Any, Dict, List

from phase_c.knowledge_ingestion.knowledge_source_validator import validate_raw_knowledge_item


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def scan_raw_items(raw_dir: str) -> Dict[str, Any]:
    base = Path(raw_dir)
    valid = []
    quarantine = []

    for path in sorted(base.glob("*.json")):
        item = load_json(path)
        validation = validate_raw_knowledge_item(item)

        record = {
            "path": str(path),
            "source_id": item.get("source_id"),
            "title": item.get("title"),
            "source_type": item.get("source_type"),
            "validation": validation,
            "item": item
        }

        if validation["status"] == "valid":
            valid.append(record)
        else:
            quarantine.append(record)

    return {
        "status": "ok",
        "schema": "vulnlab.raw_knowledge_store.v1",
        "valid_items": len(valid),
        "quarantined_items": len(quarantine),
        "items": valid,
        "quarantine": quarantine
    }


def main() -> None:
    import sys

    raw_dir = sys.argv[1] if len(sys.argv) > 1 else "phase_c/knowledge_ingestion/raw_items"
    result = scan_raw_items(raw_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
