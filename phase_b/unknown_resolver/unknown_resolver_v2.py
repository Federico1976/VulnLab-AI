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


def get_models(payload):
    return payload.get("evidence_models") or payload.get("models") or payload.get("items") or []


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.unknown_resolver.unknown_resolver_v2 <evidence_models.json> <existing_unknown_tasks.json> <output.json>")
        sys.exit(1)

    evidence = load(sys.argv[1])
    existing = load(sys.argv[2])

    models = get_models(evidence)
    old_tasks = existing.get("tasks") or existing.get("unknown_resolution_tasks") or []

    tasks = list(old_tasks) if isinstance(old_tasks, list) else []
    seen = set(json.dumps(t, sort_keys=True) for t in tasks if isinstance(t, dict))

    added = 0

    for mi, model in enumerate(models):
        if not isinstance(model, dict):
            continue

        rid = model.get("research_object_id")
        req = model.get("v2_semantic_requirements", {})

        unknowns = req.get("unknowns") or []
        proof_requirements = req.get("proof_requirements") or model.get("evidence_requirements") or []

        for idx, u in enumerate(unknowns):
            task = {
                "task_id": sid("URV2", rid, "unknown", idx, u),
                "schema": "vulnlab.unknown_resolution_task.v2",
                "research_object_id": rid,
                "source": "unknown_resolver_v2",
                "task_type": "resolve_semantic_unknown",
                "status": "open",
                "candidate_only": True,
                "question": str(u),
                "resolution_method": "static_or_dynamic_evidence_required",
                "feeds": [
                    "proof_evaluator",
                    "dynamic_validation_planner",
                    "learning_memory"
                ],
                "finding_allowed": False
            }
            key = json.dumps(task, sort_keys=True)
            if key not in seen:
                tasks.append(task)
                seen.add(key)
                added += 1

        for idx, r in enumerate(proof_requirements):
            task = {
                "task_id": sid("URV2", rid, "proof", idx, r),
                "schema": "vulnlab.unknown_resolution_task.v2",
                "research_object_id": rid,
                "source": "unknown_resolver_v2",
                "task_type": "satisfy_proof_requirement",
                "status": "open",
                "candidate_only": True,
                "proof_requirement": str(r),
                "resolution_method": "collect_evidence_or_disprove",
                "finding_allowed": False
            }
            key = json.dumps(task, sort_keys=True)
            if key not in seen:
                tasks.append(task)
                seen.add(key)
                added += 1

    out = {
        "schema": "vulnlab.unknown_resolution_tasks.v2",
        "tasks": tasks,
        "summary": {
            "existing_tasks": len(old_tasks) if isinstance(old_tasks, list) else 0,
            "added_v2_tasks": added,
            "total_tasks": len(tasks)
        }
    }

    save(sys.argv[3], out)

    print(json.dumps({
        "status": "ok",
        "added_v2_tasks": added,
        "total_tasks": len(tasks),
        "output": sys.argv[3]
    }, indent=2))


if __name__ == "__main__":
    main()
