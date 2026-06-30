from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from core.semantic_entity_builder_v4 import build_entities, save_json


def find_inputs(root: Path) -> List[Path]:
    return sorted(root.glob("*/phase_b/merged_research_objects.json"))


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output")
    inputs = find_inputs(root)

    runs: List[Dict[str, Any]] = []

    for inp in inputs:
        out = inp.parent / "semantic_entities_v4.json"

        try:
            result = build_entities(inp)
            save_json(out, result)

            runs.append({
                "input": str(inp),
                "output": str(out),
                "ok": True,
                "summary": result.get("summary", {}),
            })

            print(f"[OK] {inp} -> {out}")

        except Exception as e:
            runs.append({
                "input": str(inp),
                "output": str(out),
                "ok": False,
                "error": str(e),
            })
            print(f"[ERR] {inp}: {e}")

    report = {
        "schema": "semantic_entity_batch_runner_v4",
        "candidate_only": True,
        "finding_allowed": False,
        "root": str(root),
        "runs": runs,
        "total_inputs": len(inputs),
        "ok": sum(1 for r in runs if r["ok"]),
        "failed": sum(1 for r in runs if not r["ok"]),
    }

    report_path = root / "semantic_entities_v4_batch_report.json"
    save_json(report_path, report)

    print(json.dumps({
        "report": str(report_path),
        "total_inputs": report["total_inputs"],
        "ok": report["ok"],
        "failed": report["failed"],
    }, indent=2))


if __name__ == "__main__":
    main()
