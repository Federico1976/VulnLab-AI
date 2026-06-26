#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


def run(cmd):
    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.run_cognitive_pipeline_v2 <research_objects.json> <out_dir>")
        sys.exit(1)

    ro = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    normalized_joern = ro.parent / "normalized_joern_results.json"

    semantic = out / "semantic_entities.json"
    quality = out / "semantic_quality.json"
    causal = out / "causal_stories.json"
    ranked = out / "ranked_stories.json"
    hypotheses = out / "hypotheses.json"
    questions = out / "questions.json"
    proof = out / "proof_plans.json"
    joern_tasks = out / "joern_tasks.json"
    joern_queries = out / "joern_queries.json"
    caps = out / "semantic_capabilities.json"
    cap_graphs = out / "capability_graphs.json"
    effects = out / "security_effects.json"
    agg = out / "security_effects_aggregated.json"
    evidence = out / "evidence_models.json"
    evals = out / "proof_evaluations.json"
    unknowns = out / "unknown_resolution_tasks.json"
    dynamic = out / "dynamic_validation_plans.json"
    causal_reachability = out / "causal_reachability_v2.json"
    memory = out / "learning_memory.json"

    run(["python3", "-m", "phase_b.semantic_entities.entity_builder_v3", str(ro), str(semantic)])
    run(["python3", "-m", "phase_b.semantic_entities.quality_scorer_v1_1", str(semantic), str(quality)])
    run(["python3", "-m", "phase_b.semantic_entities.causal_story_builder_v1_1", str(semantic), str(causal)])
    run(["python3", "-m", "phase_b.semantic_entities.causal_story_ranker_v1_1", str(causal), str(ranked)])
    run(["python3", "-m", "phase_b.hypotheses.hypothesis_generator", str(ranked), str(hypotheses)])
    run(["python3", "-m", "phase_b.questions.question_generator", str(hypotheses), str(questions)])
    run(["python3", "-m", "phase_b.proof_planner.proof_planner", str(questions), str(proof)])
    run(["python3", "-m", "phase_b.joern_tasks.joern_task_builder", str(proof), str(ranked), str(joern_tasks)])
    run(["python3", "-m", "phase_b.joern_tasks.joern_query_materializer", str(joern_tasks), str(joern_queries)])
    run(["python3", "-m", "phase_b.capabilities.semantic_capability_builder", str(joern_queries), str(caps)])
    run(["python3", "-m", "phase_b.capabilities.semantic_capability_enricher_v2", str(semantic), str(caps), str(caps)])
    run(["python3", "-m", "phase_b.capability_graph.capability_graph_builder", str(caps), str(cap_graphs)])
    run(["python3", "-m", "phase_b.capability_graph.capability_graph_builder_v2", str(caps), str(cap_graphs), str(cap_graphs)])
    run(["python3", "-m", "phase_b.security_effects.security_effect_inference", str(cap_graphs), str(effects)])
    run(["python3", "-m", "phase_b.security_effects.security_effect_inference_v2", str(cap_graphs), str(effects), str(effects)])
    run(["python3", "-m", "phase_b.security_effects.security_effect_aggregator", str(effects), str(agg)])
    run(["python3", "-m", "phase_b.security_effects.security_effect_aggregator_v2", str(effects), str(agg)])
    run(["python3", "-m", "phase_b.evidence_model.evidence_model_builder", str(agg), str(evidence)])
    run(["python3", "-m", "phase_b.evidence_model.evidence_model_builder_v3", str(agg), str(evidence), str(evidence)])
    run(["python3", "-m", "phase_b.evidence_model.evidence_model_enricher_v2", str(semantic), str(evidence), str(evidence), str(ranked), str(causal), str(agg)])
    run(["python3", "-m", "phase_b.proof_evaluator.proof_evaluator_v4", str(evidence), str(normalized_joern), str(evals)])
    run(["python3", "-m", "phase_b.proof_evaluator.proof_evaluator_joern_enricher_v2", str(evals), str(evidence), str(normalized_joern), str(evals)])
    run(["python3", "-m", "phase_b.causal_reachability.causal_reachability_engine_v2", str(semantic), str(evidence), str(normalized_joern), str(causal_reachability)])
    run(["python3", "-m", "phase_b.proof_evaluator.proof_evaluator_v3_causal_enricher", str(evals), str(causal_reachability), str(evals)])
    run(["python3", "-m", "phase_b.unknown_resolver.unknown_resolver", str(evidence), str(unknowns)])
    run(["python3", "-m", "phase_b.unknown_resolver.unknown_resolver_v2", str(evidence), str(unknowns), str(unknowns)])
    # Legacy planner expects old proof_evaluator verdict schema.
    # Bootstrap empty dynamic plan file; v2/v3 planners consume Proof v4/v3 safely.
    dynamic.write_text('{"schema":"vulnlab.dynamic_validation_plans.bootstrap","plans":[],"summary":{"bootstrap":true}}', encoding="utf-8")
    run(["python3", "-m", "phase_b.dynamic_validation.dynamic_validation_planner_v2", str(evals), str(evidence), str(dynamic), str(dynamic)])
    run(["python3", "-m", "phase_b.dynamic_validation.dynamic_validation_planner_v3", str(evals), str(evidence), str(dynamic), str(dynamic)])
    run(["python3", "-m", "phase_b.learning_memory.learning_memory_builder_v2", str(evals), str(unknowns), str(memory)])

    print("\nOK Phase B cognitive brain complete")
    print(f"OUTPUT_DIR={out}")


if __name__ == "__main__":
    main()
