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


def classify_failure(result: Dict[str, Any]) -> str:
    text = json.dumps(result, ensure_ascii=False).lower()

    if "not reachable" in text or "unreachable" in text:
        return "runtime_unreachable_path"

    if "blocked" in text or "security control" in text or "permission denied" in text:
        return "security_control_blocked_path"

    if (
        "no flow" in text
        or "not reach sink" in text
        or "sink not reached" in text
        or "source to sink runtime flow not confirmed" in text
        or "source-to-sink runtime flow not confirmed" in text
        or "flow not confirmed" in text
    ):
        return "source_to_sink_not_confirmed"

    if "out of scope" in text or "unsafe" in text:
        return "scope_or_safety_stop"

    if "contradict" in text or "false positive" in text:
        return "static_story_contradicted"

    return "unknown_failure"


def extract_failure(result: Dict[str, Any]) -> Dict[str, Any]:
    failure_type = classify_failure(result)

    strategy_shape = (
        result.get("strategy_shape")
        or result.get("plan", {}).get("strategy_shape")
        or result.get("evidence_story", {}).get("strategy_shape")
        or "unknown"
    )

    experiment_type = (
        result.get("experiment_type")
        or result.get("plan", {}).get("experiment_type")
        or "unknown"
    )

    reason = (
        result.get("reason")
        or result.get("outcome_reason")
        or result.get("summary")
        or failure_type
    )

    return {
        "failure_id": stable_id("FAIL1", failure_type, strategy_shape, experiment_type, reason),
        "candidate_only": True,
        "finding_allowed": False,
        "failure_type": failure_type,
        "strategy_shape": strategy_shape,
        "experiment_type": experiment_type,
        "reason": reason,
        "applies_when": {
            "strategy_shape": strategy_shape,
            "experiment_type": experiment_type,
        },
        "avoid_repeating_when": [
            reason,
            failure_type,
        ],
        "learning": {
            "times_seen": 1,
        },
        "source": {
            "validation_plan_id": result.get("validation_plan_id"),
            "evidence_story_id": result.get("evidence_story_id"),
            "apk": result.get("apk") or result.get("target"),
        },
    }


def merge_failure(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    existing["learning"]["times_seen"] = existing.get("learning", {}).get("times_seen", 0) + 1

    for key in ["avoid_repeating_when"]:
        existing[key] = list(dict.fromkeys(existing.get(key, []) + new.get(key, [])))

    return existing


def build_failure_memory(results_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    failures: Dict[str, Dict[str, Any]] = {}
    total_results = 0

    for doc in results_docs:
        items = doc.get("results", doc if isinstance(doc, list) else [])
        for result in items:
            total_results += 1

            outcome = str(result.get("outcome", "")).lower()
            status = str(result.get("status", "")).lower()

            if outcome not in {"failed", "rejected", "blocked", "not_reachable", "false_positive"} and status not in {"failed", "rejected", "blocked"}:
                continue

            f = extract_failure(result)
            fid = f["failure_id"]

            if fid in failures:
                failures[fid] = merge_failure(failures[fid], f)
            else:
                failures[fid] = f

    failure_list = sorted(
        failures.values(),
        key=lambda x: x.get("learning", {}).get("times_seen", 0),
        reverse=True,
    )

    by_type: Dict[str, int] = {}
    for f in failure_list:
        by_type[f["failure_type"]] = by_type.get(f["failure_type"], 0) + f["learning"]["times_seen"]

    return {
        "schema": "failure_memory_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "remember failed, blocked, unreachable or contradicted investigations to avoid repeated low-value work",
        "summary": {
            "source_results": total_results,
            "failure_patterns": len(failure_list),
            "by_failure_type": by_type,
        },
        "failures": failure_list,
    }


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python3 -m memory.failure_memory_v1 <failure_memory.json> <validation_results.json> [...]")
        sys.exit(1)

    out = Path(sys.argv[1])
    inputs = [Path(x) for x in sys.argv[2:]]

    docs = [load_json(p) for p in inputs]
    memory = build_failure_memory(docs)
    save_json(out, memory)

    print(json.dumps(memory["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
