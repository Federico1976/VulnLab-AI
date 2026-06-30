from __future__ import annotations

import json
import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{h}"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def counterevidence_from_failure(failure: Dict[str, Any]) -> Dict[str, Any]:
    failure_type = failure.get("failure_type", "unknown")
    shape = failure.get("strategy_shape", "unknown")
    experiment = failure.get("experiment_type", "unknown")

    if failure_type == "runtime_unreachable_path":
        ce_type = "reachability_counterevidence"
        question = "Can the candidate path be reached from a realistic runtime entry condition?"

    elif failure_type == "security_control_blocked_path":
        ce_type = "control_counterevidence"
        question = "Does an observed security control block the candidate path?"

    elif failure_type == "source_to_sink_not_confirmed":
        ce_type = "flow_counterevidence"
        question = "Can candidate-controlled data actually reach the sink at runtime?"

    elif failure_type == "scope_or_safety_stop":
        ce_type = "scope_counterevidence"
        question = "Would testing this candidate exceed authorized or safe scope?"

    elif failure_type == "static_story_contradicted":
        ce_type = "semantic_counterevidence"
        question = "Does runtime behavior contradict the static causal story?"

    else:
        ce_type = "generic_counterevidence"
        question = "What observation would falsify this candidate story?"

    return {
        "counterevidence_id": stable_id("CE1", ce_type, shape, experiment, failure.get("reason")),
        "candidate_only": True,
        "finding_allowed": False,
        "counterevidence_type": ce_type,
        "strategy_shape": shape,
        "experiment_type": experiment,
        "falsification_question": question,
        "observed_reason": failure.get("reason"),
        "invalidates_or_weakens": [
            shape,
            experiment,
        ],
        "recommended_future_check": {
            "before_prioritizing": [
                question
            ],
            "before_reporting": [
                "Require dynamic validation evidence",
                "Require proof evaluation",
                "Keep finding_allowed=false until proof gate"
            ],
        },
        "learning": {
            "times_seen": failure.get("learning", {}).get("times_seen", 1),
        },
        "source_failure_id": failure.get("failure_id"),
    }


def build_counterevidence_memory(failure_memory: Dict[str, Any]) -> Dict[str, Any]:
    items: Dict[str, Dict[str, Any]] = {}

    for failure in failure_memory.get("failures", []):
        ce = counterevidence_from_failure(failure)
        cid = ce["counterevidence_id"]

        if cid in items:
            items[cid]["learning"]["times_seen"] += ce["learning"]["times_seen"]
        else:
            items[cid] = ce

    counterevidence = sorted(
        items.values(),
        key=lambda x: x.get("learning", {}).get("times_seen", 0),
        reverse=True,
    )

    by_type: Dict[str, int] = {}
    for ce in counterevidence:
        by_type[ce["counterevidence_type"]] = by_type.get(ce["counterevidence_type"], 0) + ce["learning"]["times_seen"]

    return {
        "schema": "counterevidence_memory_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "remember observations and questions that falsify or weaken candidate causal stories",
        "summary": {
            "counterevidence_patterns": len(counterevidence),
            "by_counterevidence_type": by_type,
        },
        "counterevidence": counterevidence,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 -m memory.counterevidence_memory_v1 <failure_memory_v1.json> <counterevidence_memory_v1.json>")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2])

    failure_memory = load_json(inp)
    memory = build_counterevidence_memory(failure_memory)
    save_json(out, memory)

    print(json.dumps(memory["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
