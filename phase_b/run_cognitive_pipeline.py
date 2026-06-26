#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


STEPS = [
    ("semantic_entities", "phase_b.semantic_entities.entity_builder", "semantic_entities_v1_1_pruned.json"),
    ("quality", "phase_b.semantic_entities.quality_scorer_v1_1", "semantic_entity_quality_v1_1.json"),
    ("causal_stories", "phase_b.semantic_entities.causal_story_builder_v1_1", "causal_stories_v1_1.json"),
    ("ranked_stories", "phase_b.semantic_entities.causal_story_ranker_v1_1", "ranked_causal_stories_v1_1.json"),
    ("hypotheses", "phase_b.hypotheses.hypothesis_generator", "hypotheses_v1.json"),
    ("questions", "phase_b.questions.question_generator", "questions_v1.json"),
    ("proof_plans", "phase_b.proof_planner.proof_planner", "proof_plans_v1.json"),
]


def run(cmd):
    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.run_cognitive_pipeline <research_objects.json> <out_dir>")
        sys.exit(1)

    research_objects = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    semantic_graph = out_dir / "semantic_entities_v1_1_pruned.json"
    quality = out_dir / "semantic_entity_quality_v1_1.json"
    causal = out_dir / "causal_stories_v1_1.json"
    ranked = out_dir / "ranked_causal_stories_v1_1.json"
    hypotheses = out_dir / "hypotheses_v1.json"
    questions = out_dir / "questions_v1.json"
    proof = out_dir / "proof_plans_v1.json"
    joern_tasks = out_dir / "joern_tasks_v1.json"
    joern_queries = out_dir / "joern_query_requests_v1.json"
    capabilities = out_dir / "semantic_capabilities_v1.json"
    cap_graphs = out_dir / "capability_graphs_v1.json"
    effects = out_dir / "security_effects_v1.json"
    aggregated = out_dir / "security_effects_aggregated_v1.json"
    evidence_models = out_dir / "evidence_models_v1.json"

    run(["python3", "-m", "phase_b.semantic_entities.entity_builder", str(research_objects), str(semantic_graph)])
    run(["python3", "-m", "phase_b.semantic_entities.quality_scorer_v1_1", str(semantic_graph), str(quality)])
    run(["python3", "-m", "phase_b.semantic_entities.causal_story_builder_v1_1", str(semantic_graph), str(causal)])
    run(["python3", "-m", "phase_b.semantic_entities.causal_story_ranker_v1_1", str(causal), str(ranked)])
    run(["python3", "-m", "phase_b.hypotheses.hypothesis_generator", str(ranked), str(hypotheses)])
    run(["python3", "-m", "phase_b.questions.question_generator", str(hypotheses), str(questions)])
    run(["python3", "-m", "phase_b.proof_planner.proof_planner", str(questions), str(proof)])
    run(["python3", "-m", "phase_b.joern_tasks.joern_task_builder", str(proof), str(ranked), str(joern_tasks)])
    run(["python3", "-m", "phase_b.joern_tasks.joern_query_materializer", str(joern_tasks), str(joern_queries)])
    run(["python3", "-m", "phase_b.capabilities.semantic_capability_builder", str(joern_queries), str(capabilities)])
    run(["python3", "-m", "phase_b.capability_graph.capability_graph_builder", str(capabilities), str(cap_graphs)])
    run(["python3", "-m", "phase_b.security_effects.security_effect_inference", str(cap_graphs), str(effects)])
    run(["python3", "-m", "phase_b.security_effects.security_effect_aggregator", str(effects), str(aggregated)])
    run(["python3", "-m", "phase_b.evidence_model.evidence_model_builder", str(aggregated), str(evidence_models)])

    print("\nOK cognitive pipeline complete")
    print(f"OUTPUT_DIR={out_dir}")


if __name__ == "__main__":
    main()
