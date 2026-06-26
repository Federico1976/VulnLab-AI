#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, List


CANDIDATE_FILES = [
    "phase_b/native_research_objects.json",
    "phase_b/fileprovider_research_objects.json",
    "phase_b/deeplink_research_objects.json",
    "phase_b/kotlin_compose_research_objects.json",
    "phase_b/flutter_research_objects.json",
    "phase_b/react_native_research_objects.json",
    "phase_b/webview_research_objects.json",
    "phase_b/fallback_research_objects.json",
]


def _load_research_objects(path: Path) -> List[Any]:
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("research_objects", "objects", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def find_research_objects(phase_a_output_dir) -> List[Any]:
    base = Path(phase_a_output_dir)
    all_objects = []
    seen = set()

    for rel in CANDIDATE_FILES:
        path = base / rel
        objects = _load_research_objects(path)

        if objects:
            print(f"[PHASE_B] research_objects source: {path} count={len(objects)}")

        for obj in objects:
            if isinstance(obj, dict):
                rid = (
                    obj.get("research_object_id")
                    or obj.get("id")
                    or obj.get("title")
                    or json.dumps(obj, sort_keys=True)
                )
                obj["_source_file"] = str(path)
            else:
                rid = json.dumps(obj, sort_keys=True)

            if rid in seen:
                continue

            seen.add(rid)
            all_objects.append(obj)

    return all_objects


def write_merged_research_objects(phase_a_output_dir, output_json=None) -> Path:
    base = Path(phase_a_output_dir)
    phase_b_dir = base / "phase_b"
    phase_b_dir.mkdir(parents=True, exist_ok=True)

    if output_json is None:
        output_json = phase_b_dir / "merged_research_objects.json"
    else:
        output_json = Path(output_json)

    objects = find_research_objects(base)

    payload = {
        "schema": "vulnlab_ai.research_objects.merged.v1",
        "count": len(objects),
        "research_objects": objects,
    }

    output_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[PHASE_B] merged_research_objects={len(objects)} -> {output_json}")
    return output_json
