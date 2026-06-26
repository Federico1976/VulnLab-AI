#!/usr/bin/env python3
import json
import sys
import hashlib
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sid(prefix, *parts):
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}-{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


def get_evals(payload):
    return payload.get("proof_evaluations") or payload.get("evaluations") or []


def get_tasks(payload):
    return payload.get("tasks") or payload.get("unknown_resolution_tasks") or []


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.learning_memory.learning_memory_builder_v2 <proof_evaluations.json> <unknown_resolution_tasks.json> <output.json>")
        sys.exit(1)

    evals = get_evals(load(sys.argv[1]))
    tasks = get_tasks(load(sys.argv[2]))

    memories = []

    for idx, e in enumerate(evals):
        if not isinstance(e, dict):
            continue

        rid = e.get("research_object_id") or e.get("causal_reachability_v3", {}).get("research_object_id")

        memories.append({
            "memory_id": sid("LMV2", rid, idx),
            "schema": "vulnlab.learning_memory.v2",
            "research_object_id": rid,
            "source": "learning_memory_builder_v2",
            "memory_type": "proof_pipeline_observation",
            "candidate_only": True,
            "decision_v4": e.get("decision_v4"),
            "decision_v3": e.get("decision_v3"),
            "dynamic_validation_allowed": bool(
                e.get("dynamic_validation_allowed_v3")
                or e.get("dynamic_validation_allowed_v4")
            ),
            "finding_allowed": False,
            "joern_normalized_results": e.get("joern_normalized_results"),
            "static_context_available": e.get("static_context_available"),
            "lesson": "Research-object based proof evaluation reached candidate dynamic validation planning without allowing findings.",
            "next_actions": [
                "run_dynamic_validation_if_in_scope",
                "confirm_or_disprove_candidate",
                "update evidence model after runtime results"
            ],
            "guardrails": {
                "no_vulnerability_claim_without_dynamic_validation": True,
                "responsible_disclosure_only": True
            }
        })

    for idx, t in enumerate(tasks):
        if not isinstance(t, dict):
            continue

        rid = t.get("research_object_id")

        memories.append({
            "memory_id": sid("LMV2-UNKNOWN", rid, idx),
            "schema": "vulnlab.learning_memory.v2",
            "research_object_id": rid,
            "source": "learning_memory_builder_v2",
            "memory_type": "unknown_resolution_observation",
            "candidate_only": True,
            "task_type": t.get("type") or t.get("task_type"),
            "lesson": "Unknown resolution remains part of the proof path before any disclosure decision."
        })

    out = {
        "schema": "vulnlab.learning_memory.v2",
        "memories": memories,
        "summary": {
            "memories": len(memories),
            "proof_evaluations_consumed": len(evals),
            "unknown_tasks_consumed": len(tasks)
        }
    }

    save(sys.argv[3], out)

    print(json.dumps({
        "status": "ok",
        "memories": len(memories),
        "output": sys.argv[3]
    }, indent=2))


if __name__ == "__main__":
    main()
