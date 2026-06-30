from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def failure_index(failure_memory: Dict[str, Any]) -> Dict[str, int]:
    idx: Dict[str, int] = {}

    for f in failure_memory.get("failures", []):
        shape = f.get("strategy_shape", "unknown")
        idx[shape] = idx.get(shape, 0) + f.get("learning", {}).get("times_seen", 1)

    return idx


def counterevidence_index(counter_memory: Dict[str, Any]) -> Dict[str, int]:
    idx: Dict[str, int] = {}

    for ce in counter_memory.get("counterevidence", []):
        shape = ce.get("strategy_shape", "unknown")
        idx[shape] = idx.get(shape, 0) + ce.get("learning", {}).get("times_seen", 1)

    return idx


def calibrate_profile(profile: Dict[str, Any], failures: Dict[str, int], counter: Dict[str, int]) -> Dict[str, Any]:
    shape = profile.get("strategy_shape", "unknown")

    base = float(profile.get("decision_score", 0.5))
    times_seen = int(profile.get("times_seen", 0))
    failure_count = failures.get(shape, 0)
    counter_count = counter.get(shape, 0)

    experience_bonus = min(times_seen / 500.0, 0.10)
    failure_penalty = min(failure_count * 0.08, 0.35)
    counter_penalty = min(counter_count * 0.06, 0.30)

    calibrated = base + experience_bonus - failure_penalty - counter_penalty
    calibrated = max(0.0, min(round(calibrated, 2), 1.0))

    if calibrated >= 0.85:
        priority = "high"
    elif calibrated >= 0.65:
        priority = "medium"
    elif calibrated >= 0.40:
        priority = "low"
    else:
        priority = "deprioritize"

    return {
        "strategy_id": profile.get("strategy_id"),
        "strategy_shape": shape,
        "maturity": profile.get("maturity"),
        "base_decision_score": base,
        "times_seen": times_seen,
        "failure_count": failure_count,
        "counterevidence_count": counter_count,
        "calibrated_confidence": calibrated,
        "priority": priority,
        "reasoning": {
            "experience_bonus": round(experience_bonus, 2),
            "failure_penalty": round(failure_penalty, 2),
            "counterevidence_penalty": round(counter_penalty, 2),
        },
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "requires_dynamic_validation": True,
        },
    }


def calibrate(strategy_v3: Dict[str, Any], failure_memory: Dict[str, Any], counter_memory: Dict[str, Any]) -> Dict[str, Any]:
    failures = failure_index(failure_memory)
    counter = counterevidence_index(counter_memory)

    calibrated = [
        calibrate_profile(p, failures, counter)
        for p in strategy_v3.get("decision_profiles", [])
    ]

    by_priority: Dict[str, int] = {}
    for c in calibrated:
        by_priority[c["priority"]] = by_priority.get(c["priority"], 0) + 1

    return {
        "schema": "confidence_calibration_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "calibrate strategy priority using experience, failure memory and counterevidence memory",
        "summary": {
            "strategies": len(calibrated),
            "by_priority": by_priority,
        },
        "calibrated_strategies": calibrated,
    }


def main() -> None:
    if len(sys.argv) != 5:
        print("Usage: python3 -m memory.confidence_calibration_v1 <strategy_memory_v3.json> <failure_memory_v1.json> <counterevidence_memory_v1.json> <confidence_calibration_v1.json>")
        sys.exit(1)

    strategy_v3 = load_json(Path(sys.argv[1]))
    failure_memory = load_json(Path(sys.argv[2]))
    counter_memory = load_json(Path(sys.argv[3]))
    out = Path(sys.argv[4])

    report = calibrate(strategy_v3, failure_memory, counter_memory)
    save_json(out, report)

    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
