#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import defaultdict


ACTION_MAP = {
    "prove_external_or_attacker_controllable_entrypoint": {
        "task_type": "entrypoint_reachability_proof",
        "engine": "static_manifest_runtime_correlation",
        "priority": 1,
    },
    "recover_candidate_level_entrypoint": {
        "task_type": "candidate_entrypoint_recovery",
        "engine": "research_object_context_correlation",
        "priority": 1,
    },
    "prove_source_controllability": {
        "task_type": "source_controllability_proof",
        "engine": "static_semantic_slice",
        "priority": 2,
    },
    "prove_source_to_sink_data_or_control_flow": {
        "task_type": "source_to_sink_causal_flow_proof",
        "engine": "joern",
        "priority": 3,
    },
    "prove_sink_security_impact": {
        "task_type": "sink_impact_assessment",
        "engine": "semantic_impact_classifier",
        "priority": 4,
    },
    "prove_asset_security_relevance": {
        "task_type": "asset_relevance_proof",
        "engine": "semantic_asset_classifier",
        "priority": 5,
    },
    "evaluate_sanitizer_effectiveness": {
        "task_type": "sanitizer_effectiveness_proof",
        "engine": "static_semantic_slice",
        "priority": 6,
    },
    "collect_counter_evidence": {
        "task_type": "counter_evidence_collection",
        "engine": "static_and_runtime_negative_evidence",
        "priority": 7,
    },
    "compact_large_story": {
        "task_type": "minimal_causal_slice_compaction",
        "engine": "semantic_entity_compactor",
        "priority": 0,
    },
    "recover_security_asset": {
        "task_type": "security_asset_recovery",
        "engine": "semantic_asset_classifier",
        "priority": 5,
    },
}


def build_tasks(question_set):
    grouped = defaultdict(list)

    for q in question_set.get("questions", []):
        grouped[q["proof_requirement"]].append(q)

    tasks = []

    for proof_requirement, questions in grouped.items():
        action = ACTION_MAP.get(proof_requirement, {
            "task_type": "generic_evidence_task",
            "engine": "manual_or_llm_reasoning",
            "priority": 99,
        })

        tasks.append({
            "task_id": f"{question_set['hypothesis_id']}-{proof_requirement}",
            "hypothesis_id": question_set["hypothesis_id"],
            "story_id": question_set["story_id"],
            "research_object_id": question_set["research_object_id"],
            "candidate_id": question_set["candidate_id"],
            "proof_requirement": proof_requirement,
            "task_type": action["task_type"],
            "recommended_engine": action["engine"],
            "execution_priority": action["priority"],
            "questions": questions,
            "expected_output": {
                "evidence": [],
                "counter_evidence": [],
                "confidence_delta": None,
                "proof_status": "unanswered"
            },
            "quality_gates": {
                "declares_vulnerability": False,
                "candidate_evidence_only": True,
                "requires_evidence_before_status_change": True,
            }
        })

    tasks.sort(key=lambda t: t["execution_priority"])
    return tasks


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.proof_planner.proof_planner <questions.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())

    plans = []
    total_tasks = 0

    for qs in data.get("question_sets", []):
        tasks = build_tasks(qs)
        total_tasks += len(tasks)

        plans.append({
            "proof_plan_id": f"PP-{qs['hypothesis_id']}",
            "hypothesis_id": qs["hypothesis_id"],
            "story_id": qs["story_id"],
            "research_object_id": qs["research_object_id"],
            "candidate_id": qs["candidate_id"],
            "priority": qs["priority"],
            "rank_score": qs["rank_score"],
            "task_count": len(tasks),
            "tasks": tasks,
            "quality_gates": {
                "declares_vulnerability": False,
                "candidate_evidence_only": True,
                "dynamic_validation_required_for_disclosure": True,
            }
        })

    output = {
        "schema": "vulnlab.proof_plans.v1",
        "input_schema": data.get("schema"),
        "proof_plan_count": len(plans),
        "task_count": total_tasks,
        "summary": {
            "critical": sum(1 for p in plans if p["priority"] == "critical_compact_proof_candidate"),
            "high": sum(1 for p in plans if p["priority"] == "high_proof_candidate"),
            "medium": sum(1 for p in plans if p["priority"] == "medium_proof_candidate"),
        },
        "proof_plans": plans,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "proof_planner_only": True,
            "requires_joern_or_static_evidence": True,
            "requires_dynamic_validation_before_disclosure": True,
        }
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "proof_plans": len(plans),
        "tasks": total_tasks,
        "summary": output["summary"],
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
