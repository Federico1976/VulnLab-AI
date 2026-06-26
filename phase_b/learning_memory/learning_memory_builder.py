#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.learning_memory.learning_memory_builder <proof_evaluations.json> <unknown_tasks.json> <out.json>")
        sys.exit(1)

    evals = json.loads(Path(sys.argv[1]).read_text())
    unknowns = json.loads(Path(sys.argv[2]).read_text())

    memories = []

    for e in evals.get("evaluations", []):
        memories.append({
            "memory_type": "proof_evaluation_pattern",
            "hypothesis_id": e["hypothesis_id"],
            "effect_type": e["effect_type"],
            "verdict": e["verdict"],
            "lesson": f"{e['effect_type']} currently resolves to {e['verdict']} with {e['unknown_count']} unknowns and {e['counter_evidence_count']} counter-evidence items.",
            "reuse": "future_prioritization_and_strategy",
        })

    task_counts = unknowns.get("summary", {})
    for t, count in task_counts.items():
        memories.append({
            "memory_type": "unknown_resolution_strategy",
            "task_type": t,
            "observed_count": count,
            "lesson": f"{t} appeared {count} times and should have a reusable resolver strategy.",
            "reuse": "research_strategy_memory",
        })

    out = {
        "schema": "vulnlab.learning_memory.v1",
        "memory_count": len(memories),
        "memories": memories,
        "quality_gates": {
            "stores_semantic_lessons_not_target_specific_detectors": True,
            "declares_vulnerability": False,
        }
    }

    Path(sys.argv[3]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[3]).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({"status": "ok", "memories": len(memories), "output": sys.argv[3]}, indent=2))


if __name__ == "__main__":
    main()
