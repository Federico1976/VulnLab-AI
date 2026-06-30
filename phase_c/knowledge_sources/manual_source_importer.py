import json
import sys
from pathlib import Path

from phase_c.knowledge_sources.source_collector_base import make_raw_item, write_raw_item


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python3 -m phase_c.knowledge_sources.manual_source_importer "
            "<manual_import_json> <raw_items_output_dir>"
        )

    import_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    with import_path.open("r", encoding="utf-8") as f:
        src = json.load(f)

    item = make_raw_item(
        source_id=src["source_id"],
        source=src.get("source", "manual_import"),
        source_type=src.get("source_type", "manual_research_note"),
        title=src["title"],
        summary=src["summary"],
        ecosystem=src.get("ecosystem", "android"),
        references=src.get("references", []),
        known_security_relevance=src.get("known_security_relevance", []),
        expected_case_family=src.get("expected_case_family", "unknown"),
        human_reviewed=bool(src.get("human_reviewed", False))
    )

    path = write_raw_item(item, output_dir)

    print(json.dumps({
        "status": "ok",
        "imported": True,
        "raw_item": str(path),
        "source_id": item["source_id"],
        "expected_case_family": item["expected_case_family"]
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
