#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def normalize_item(item: Any, source_file: str) -> Dict[str, Any]:
    if isinstance(item, dict):
        method = (
            item.get("method")
            or item.get("fullName")
            or item.get("name")
            or item.get("callee")
            or item.get("caller")
        )

        return {
            "type": "joern_execution_result",
            "source_file": source_file,
            "raw_kind": item.get("kind") or item.get("type") or "unknown",
            "method": method,
            "class": item.get("class") or item.get("declaringType") or item.get("typeDecl"),
            "file": item.get("file") or item.get("filename"),
            "line": item.get("line") or item.get("lineNumber"),
            "sink": item.get("sink"),
            "source": item.get("source"),
            "edge": item.get("edge"),
            "evidence": item,
            "normalized_confidence": "low",
        }

    return {
        "type": "joern_execution_result",
        "source_file": source_file,
        "raw_kind": "scalar",
        "method": None,
        "class": None,
        "file": None,
        "line": None,
        "sink": None,
        "source": None,
        "edge": None,
        "evidence": item,
        "normalized_confidence": "low",
    }


def normalize_payload(payload: Any, source_file: str) -> List[Dict[str, Any]]:
    if payload is None:
        return []

    if isinstance(payload, list):
        return [normalize_item(x, source_file) for x in payload]

    if isinstance(payload, dict):
        for key in ("results", "data", "findings", "matches", "rows"):
            if isinstance(payload.get(key), list):
                return [normalize_item(x, source_file) for x in payload[key]]
        return [normalize_item(payload, source_file)]

    return [normalize_item(payload, source_file)]


def normalize_directory(input_dir: Path) -> List[Dict[str, Any]]:
    normalized = []

    for path in input_dir.rglob("*.json"):
        payload = load_json(path)
        normalized.extend(normalize_payload(payload, str(path)))

    return normalized


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 -m phase_b.joern_results.joern_execution_result_normalizer <joern_results_dir> <output_json>")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])
    output_json.parent.mkdir(parents=True, exist_ok=True)

    normalized = normalize_directory(input_dir)

    output_json.write_text(
        json.dumps(
            {
                "schema": "vulnlab_ai.joern.normalized_results.v1",
                "count": len(normalized),
                "results": normalized,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"[OK] normalized_joern_results={len(normalized)} -> {output_json}")


if __name__ == "__main__":
    main()
