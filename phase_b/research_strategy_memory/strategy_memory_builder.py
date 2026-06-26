#!/usr/bin/env python3
import json, sys
from pathlib import Path
from collections import Counter, defaultdict

def main():
    if len(sys.argv) != 5:
        print("Usage: python3 -m phase_b.research_strategy_memory.strategy_memory_builder <proof_evaluations.json> <unknown_tasks.json> <dynamic_plans.json> <out.json>")
        sys.exit(1)

    evals = json.loads(Path(sys.argv[1]).read_text())
    unknowns = json.loads(Path(sys.argv[2]).read_text())
    dynamics = json.loads(Path(sys.argv[3]).read_text())

    verdicts = Counter(e["verdict"] for e in evals.get("evaluations", []))
    unknown_types = Counter(t["task_type"] for t in unknowns.get("unknown_resolution_tasks", []))
    dynamic_effects = Counter(p["effect_type"] for p in dynamics.get("dynamic_validation_plans", []))

    strategies = []

    for task_type, count in unknown_types.most_common():
        strategies.append({
            "strategy_type": "unknown_resolution_strategy",
            "task_type": task_type,
            "priority_hint": "high" if count >= 10 else "medium",
            "observed_count": count,
            "lesson": f"Prioritize reusable resolver for {task_type}; observed {count} unresolved instances.",
            "reuse_scope": "universal_cross_apk"
        })

    for effect, count in dynamic_effects.most_common():
        strategies.append({
            "strategy_type": "dynamic_validation_strategy",
            "effect_type": effect,
            "priority_hint": "high" if count >= 3 else "medium",
            "observed_count": count,
            "lesson": f"Create reusable benign dynamic validation recipe for {effect}.",
            "reuse_scope": "universal_cross_runtime"
        })

    out = {
        "schema": "vulnlab.research_strategy_memory.v1",
        "summary": {
            "verdicts": dict(verdicts),
            "unknown_task_types": dict(unknown_types),
            "dynamic_effects": dict(dynamic_effects),
        },
        "strategy_count": len(strategies),
        "strategies": strategies,
        "quality_gates": {
            "stores_strategy_not_target_specific_detector": True,
            "declares_vulnerability": False,
            "candidate_evidence_only": True
        }
    }

    Path(sys.argv[4]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[4]).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({"status": "ok", "strategies": len(strategies), "output": sys.argv[4]}, indent=2))

if __name__ == "__main__":
    main()
