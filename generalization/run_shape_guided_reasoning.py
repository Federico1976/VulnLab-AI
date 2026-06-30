#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run shape-guided reasoning context for VulnLab-AI")
    parser.add_argument("apk_output_dir")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    base = Path(args.apk_output_dir)
    gen = base / "generalization"
    phase_b = base / "phase_b"

    semantic_graph = phase_b / "semantic_entity_graph_v4.json"
    research_objects = phase_b / "merged_research_objects.json"
    shape_matches = gen / "semantic_shape_matches_v1.json"
    shape_context = gen / "reasoning_shape_context_v1.json"

    subprocess.run([
        sys.executable, "-m", "generalization.semantic_shape_matcher",
        str(semantic_graph),
        "--research-objects", str(research_objects),
        "--out", str(shape_matches),
    ], check=True)

    subprocess.run([
        sys.executable, "-m", "generalization.shape_reasoning_bridge",
        str(shape_matches),
        "--out", str(shape_context),
    ], check=True)

    context = load_json(shape_context) or {}

    result: Dict[str, Any] = {
        "schema_version": "shape_guided_reasoning_run.v1",
        "apk_output_dir": str(base),
        "shape_matches_path": str(shape_matches),
        "reasoning_shape_context_path": str(shape_context),
        "has_shape_context": context.get("has_shape_context", False),
        "primary_shape_id": (context.get("primary_shape") or {}).get("shape_id"),
        "primary_recommended_next_step": (context.get("primary_shape") or {}).get("recommended_next_step"),
        "proof_priorities": context.get("proof_priorities", []),
        "confidence_adjustments": context.get("confidence_adjustments", []),
        "status": "ready_for_reasoning_executor_integration",
    }

    out = Path(args.out) if args.out else gen / "shape_guided_reasoning_run_v1.json"
    write_json(out, result)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
