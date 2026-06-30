from __future__ import annotations

import json
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{h}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def empty_state() -> Dict[str, Any]:
    return {
        "schema": "brain_state_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "created_at": now(),
        "updated_at": now(),
        "version": 0,
        "counters": {
            "episodes": 0,
            "reasoning_sessions": 0,
            "validation_results": 0,
            "external_knowledge_items": 0,
            "learning_updates": 0,
        },
        "memory_refs": {},
        "history": [],
    }


def summarize_doc(path: Path, doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": str(path),
        "schema": doc.get("schema"),
        "summary": doc.get("summary", {}),
    }


def apply_update(state: Dict[str, Any], update_name: str, docs: List[Path]) -> Dict[str, Any]:
    loaded = []

    for p in docs:
        doc = load_json(p, {})
        loaded.append(summarize_doc(p, doc))

        schema = doc.get("schema", "")

        if schema == "investigation_experience_memory_v1":
            state["counters"]["episodes"] = doc.get("summary", {}).get("episodes", state["counters"]["episodes"])

        elif schema == "reasoning_session_v1":
            state["counters"]["reasoning_sessions"] += 1

        elif schema == "continuous_learning_update_v1":
            state["counters"]["learning_updates"] += 1
            state["counters"]["validation_results"] += doc.get("summary", {}).get("validation_results", 0)

        elif schema == "knowledge_merge_v1":
            state["counters"]["external_knowledge_items"] += doc.get("summary", {}).get("external_items", 0)

        state["memory_refs"][schema or p.stem] = str(p)

    state["version"] += 1
    state["updated_at"] = now()

    delta = {
        "delta_id": stable_id("BRAINDELTA1", update_name, state["version"], now()),
        "update_name": update_name,
        "created_at": now(),
        "new_version": state["version"],
        "candidate_only": True,
        "finding_allowed": False,
        "docs": loaded,
        "counters": state["counters"],
    }

    state["history"].append(delta)

    return delta


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: python3 -m memory.incremental_memory_updater_v1 <brain_state.json> <update_name> <doc1.json> [doc2.json ...]")
        sys.exit(1)

    state_path = Path(sys.argv[1])
    update_name = sys.argv[2]
    docs = [Path(x) for x in sys.argv[3:]]

    state = load_json(state_path, empty_state())
    delta = apply_update(state, update_name, docs)

    save_json(state_path, state)

    delta_path = state_path.with_name("brain_delta_latest_v1.json")
    changelog_path = state_path.with_name("brain_changelog_v1.json")

    save_json(delta_path, delta)
    save_json(changelog_path, {
        "schema": "brain_changelog_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "history": state.get("history", []),
    })

    print(json.dumps({
        "brain_state": str(state_path),
        "delta": str(delta_path),
        "changelog": str(changelog_path),
        "version": state["version"],
        "counters": state["counters"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
