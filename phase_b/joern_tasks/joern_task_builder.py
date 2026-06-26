#!/usr/bin/env python3
import json
import sys
from pathlib import Path


JOERN_RELEVANT_TYPES = {
    "source_to_sink_causal_flow_proof",
    "source_controllability_proof",
    "sanitizer_effectiveness_proof",
}


def extract_entities(seq, entity_type):
    return seq.get(entity_type, []) if isinstance(seq, dict) else []


def compact_evidence(entity):
    ev = entity.get("evidence")
    if isinstance(ev, str):
        ev = ev[:2000]
    return {
        "entity_id": entity.get("id"),
        "type": entity.get("type"),
        "role": entity.get("role"),
        "source_field": entity.get("source_field"),
        "evidence": ev,
    }


def build_query_hints(story):
    seq = story.get("compact_causal_sequence", {})

    bridges = extract_entities(seq, "BridgeMethodEntity")
    sources = extract_entities(seq, "SourceEntity")
    propagations = extract_entities(seq, "PropagationEntity")
    sinks = extract_entities(seq, "SinkEntity")
    sanitizers = extract_entities(seq, "SanitizerEntity")

    hints = {
        "bridge_entities": [compact_evidence(e) for e in bridges],
        "source_entities": [compact_evidence(e) for e in sources],
        "propagation_entities": [compact_evidence(e) for e in propagations],
        "sink_entities": [compact_evidence(e) for e in sinks],
        "sanitizer_entities": [compact_evidence(e) for e in sanitizers],
    }

    return hints


def build_joern_task(plan, task):
    hints = build_query_hints(plan)

    return {
        "joern_task_id": f"JT-{task['task_id']}",
        "proof_plan_id": plan["proof_plan_id"],
        "hypothesis_id": plan["hypothesis_id"],
        "story_id": plan["story_id"],
        "research_object_id": plan["research_object_id"],
        "candidate_id": plan["candidate_id"],
        "proof_requirement": task["proof_requirement"],
        "task_type": task["task_type"],
        "recommended_engine": "joern",
        "query_goal": describe_query_goal(task["task_type"]),
        "query_hints": hints,
        "expected_outputs": [
            "matched_methods",
            "matched_calls",
            "source_to_sink_paths",
            "sanitizer_or_guard_nodes",
            "negative_evidence",
        ],
        "status": "planned_not_executed",
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "requires_result_evaluation": True,
        },
    }


def describe_query_goal(task_type):
    if task_type == "source_to_sink_causal_flow_proof":
        return "Find or refute a causal data/control path between source entities and sink entities."
    if task_type == "source_controllability_proof":
        return "Identify how source arguments are assigned, read, transformed, or constrained before propagation."
    if task_type == "sanitizer_effectiveness_proof":
        return "Identify validation, guard, allowlist, permission, origin, or sanitization logic on the path."
    return "Collect Joern evidence for this proof task."


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.joern_tasks.joern_task_builder <proof_plans.json> <ranked_stories.json> <out.json>")
        sys.exit(1)

    proof_path = Path(sys.argv[1])
    stories_path = Path(sys.argv[2])
    out_path = Path(sys.argv[3])

    proof_data = json.loads(proof_path.read_text())
    story_data = json.loads(stories_path.read_text())

    stories_by_id = {
        s["story_id"]: s for s in story_data.get("ranked_stories", [])
    }

    joern_tasks = []

    for plan in proof_data.get("proof_plans", []):
        story = stories_by_id.get(plan["story_id"], {})
        enriched_plan = dict(plan)
        enriched_plan["compact_causal_sequence"] = story.get("compact_causal_sequence", {})

        for task in plan.get("tasks", []):
            if task.get("task_type") in JOERN_RELEVANT_TYPES:
                joern_tasks.append(build_joern_task(enriched_plan, task))

    output = {
        "schema": "vulnlab.joern_tasks.v1",
        "input_schemas": {
            "proof_plans": proof_data.get("schema"),
            "ranked_stories": story_data.get("schema"),
        },
        "joern_task_count": len(joern_tasks),
        "summary": {
            "source_to_sink_causal_flow_proof": sum(1 for t in joern_tasks if t["task_type"] == "source_to_sink_causal_flow_proof"),
            "source_controllability_proof": sum(1 for t in joern_tasks if t["task_type"] == "source_controllability_proof"),
            "sanitizer_effectiveness_proof": sum(1 for t in joern_tasks if t["task_type"] == "sanitizer_effectiveness_proof"),
        },
        "joern_tasks": joern_tasks,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "planned_tasks_only": True,
            "requires_joern_execution": True,
            "requires_proof_evaluator": True,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "joern_tasks": len(joern_tasks),
        "summary": output["summary"],
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
