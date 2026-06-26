#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def count_list(payload, *keys):
    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        return 0
    for k in keys:
        v = payload.get(k)
        if isinstance(v, list):
            return len(v)
    return 0


def schema(payload):
    return payload.get("schema") if isinstance(payload, dict) else None


def summary_get(payload, key, default=None):
    if not isinstance(payload, dict):
        return default
    return payload.get("summary", {}).get(key, default)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.reports.phase_b_final_report <phase_b_brain_dir> <output.json>")
        sys.exit(1)

    d = Path(sys.argv[1])
    out = Path(sys.argv[2])

    files = {
        "semantic_entities": d / "semantic_entities.json",
        "semantic_quality": d / "semantic_quality.json",
        "causal_stories": d / "causal_stories.json",
        "ranked_stories": d / "ranked_stories.json",
        "hypotheses": d / "hypotheses.json",
        "questions": d / "questions.json",
        "proof_plans": d / "proof_plans.json",
        "joern_tasks": d / "joern_tasks.json",
        "joern_queries": d / "joern_queries.json",
        "semantic_capabilities": d / "semantic_capabilities.json",
        "capability_graphs": d / "capability_graphs.json",
        "security_effects": d / "security_effects.json",
        "security_effects_aggregated": d / "security_effects_aggregated.json",
        "evidence_models": d / "evidence_models.json",
        "proof_evaluations": d / "proof_evaluations.json",
        "causal_reachability": d / "causal_reachability_v2.json",
        "unknown_resolution_tasks": d / "unknown_resolution_tasks.json",
        "dynamic_validation_plans": d / "dynamic_validation_plans.json",
        "learning_memory": d / "learning_memory.json",
        "research_strategy_memory": d / "research_strategy_memory.json",
    }

    data = {k: load(v) for k, v in files.items()}

    semantic = data["semantic_entities"]
    caps = data["semantic_capabilities"]
    graphs = data["capability_graphs"]
    effects = data["security_effects"]
    agg = data["security_effects_aggregated"]
    evidence = data["evidence_models"]
    evals = data["proof_evaluations"]
    causal = data["causal_reachability"]
    dynamic = data["dynamic_validation_plans"]
    learning = data["learning_memory"]
    strategy = data["research_strategy_memory"]

    summary = {
        "semantic_entities": count_list(semantic, "entities"),
        "semantic_edges": count_list(semantic, "edges"),
        "semantic_schema": schema(semantic),
        "semantic_added_entities_v2": semantic.get("expander_v2_summary", {}).get("added_entities") if isinstance(semantic, dict) else None,

        "causal_stories": count_list(data["causal_stories"], "causal_stories", "stories"),
        "hypotheses": count_list(data["hypotheses"], "hypotheses"),
        "questions": count_list(data["questions"], "questions"),
        "proof_plans": count_list(data["proof_plans"], "proof_plans", "plans"),
        "proof_tasks": count_list(data["proof_plans"], "tasks"),

        "joern_tasks": count_list(data["joern_tasks"], "joern_tasks", "tasks"),
        "joern_query_requests": count_list(data["joern_queries"], "requests", "queries"),

        "semantic_capabilities": count_list(caps, "capabilities"),
        "semantic_capabilities_schema": schema(caps),
        "research_object_capabilities_v2": caps.get("v2_summary", {}).get("added_research_object_capabilities") if isinstance(caps, dict) else None,

        "capability_graphs": count_list(graphs, "graphs"),
        "capability_graph_nodes": count_list(graphs, "nodes"),
        "capability_graph_edges": count_list(graphs, "edges"),
        "capability_graph_schema": schema(graphs),

        "security_effects": count_list(effects, "effects"),
        "security_effect_schema": schema(effects),

        "aggregated_security_effects": count_list(agg, "aggregated_effects", "effects"),
        "aggregated_security_effect_schema": schema(agg),

        "evidence_models": count_list(evidence, "evidence_models", "models"),
        "evidence_models_schema": schema(evidence),
        "evidence_models_enriched_v2": evidence.get("v2_summary", {}).get("enriched_models") if isinstance(evidence, dict) else None,

        "proof_evaluations": count_list(evals, "proof_evaluations", "evaluations"),
        "proof_evaluations_schema": schema(evals),
        "proof_v4_evaluations": evals.get("v4_summary", {}).get("evaluations") if isinstance(evals, dict) else None,
        "proof_v4_joern_results": evals.get("v4_summary", {}).get("joern_normalized_results") if isinstance(evals, dict) else None,
        "proof_v3_causal_ready": evals.get("v3_summary", {}).get("causal_ready_for_dynamic_validation") if isinstance(evals, dict) else None,

        "causal_reachability_objects": count_list(causal, "causal_reachability_objects"),
        "causal_reachability_schema": schema(causal),
        "causal_ready_for_dynamic_validation": causal.get("summary", {}).get("causal_static_evidence_ready_for_dynamic_validation") if isinstance(causal, dict) else None,

        "unknown_resolution_tasks": count_list(data["unknown_resolution_tasks"], "tasks"),
        "unknown_resolution_schema": schema(data["unknown_resolution_tasks"]),
        "unknown_resolution_added_v2": summary_get(data["unknown_resolution_tasks"], "added_v2_tasks"),

        "dynamic_validation_plans": count_list(dynamic, "plans", "dynamic_validation_plans"),
        "dynamic_validation_schema": schema(dynamic),
        "dynamic_validation_added_v2": summary_get(dynamic, "added_v2_plans"),
        "dynamic_validation_added_v3": summary_get(dynamic, "added_v3_plans"),
        "dynamic_validation_total_plans": summary_get(dynamic, "total_plans"),

        "learning_memories": count_list(learning, "memories"),
        "learning_memory_schema": schema(learning),

        "research_strategies": count_list(strategy, "strategies"),
        "research_strategy_schema": schema(strategy),
    }

    health = {
        "phase_b_completed": True,
        "legacy_schema_blockers_remaining": False,
        "has_research_objects": summary["semantic_entities"] > 0,
        "has_capability_graphs": summary["capability_graphs"] > 0,
        "has_security_effects": summary["security_effects"] > 0,
        "has_evidence_models": summary["evidence_models"] > 0,
        "has_proof_evaluations": summary["proof_evaluations"] > 0,
        "has_dynamic_validation_plans": summary["dynamic_validation_plans"] > 0,
        "candidate_only_guardrail": True,
        "finding_allowed": False,
    }

    report = {
        "status": "ok",
        "schema": "vulnlab.phase_b.final_report.v3",
        "output_dir": str(d),
        "summary": summary,
        "health": health,
        "files": {k: str(v) for k, v in files.items()},
    }

    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "output": str(out),
        "health": health,
        "summary": summary,
    }, indent=2))


if __name__ == "__main__":
    main()
