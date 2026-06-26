#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def infer_hypothesis_type(story):
    s = story.get("summary", {})

    if s.get("has_trust_boundary") and s.get("has_bridge") and s.get("has_sink"):
        if s.get("has_asset"):
            return "cross_runtime_sensitive_operation_candidate"
        return "cross_runtime_sink_reachability_candidate"

    if s.get("has_source") and s.get("has_propagation") and s.get("has_sink"):
        return "source_to_sink_reachability_candidate"

    return "weak_investigation_candidate"


def build_hypothesis(story, index):
    htype = infer_hypothesis_type(story)

    required_proofs = [
        "prove_external_or_attacker_controllable_entrypoint",
        "prove_source_controllability",
        "prove_source_to_sink_data_or_control_flow",
        "prove_sink_security_impact",
        "collect_counter_evidence",
    ]

    if story.get("summary", {}).get("has_sanitizer"):
        required_proofs.append("evaluate_sanitizer_effectiveness")

    if story.get("summary", {}).get("has_asset"):
        required_proofs.append("prove_asset_security_relevance")

    return {
        "hypothesis_id": f"HYP-{index:04d}",
        "story_id": story["story_id"],
        "research_object_id": story["research_object_id"],
        "candidate_id": story["candidate_id"],
        "hypothesis_type": htype,
        "priority": story["priority"],
        "rank_score": story["rank_score"],
        "status": "candidate_hypothesis",
        "claim": {
            "statement": "A candidate controllable source may reach a security-sensitive sink through a cross-runtime or local propagation path.",
            "declares_vulnerability": False,
            "requires_causal_reachability": True,
            "requires_dynamic_validation": True,
        },
        "supporting_story_summary": story.get("summary"),
        "compact_causal_sequence": story.get("compact_causal_sequence"),
        "required_proofs": required_proofs,
        "known_gaps": story.get("rank_penalties", []),
        "next_stage": "question_generator",
        "quality_gates": {
            "candidate_evidence_only": True,
            "not_a_finding": True,
            "not_disclosure_ready": True,
        },
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.hypotheses.hypothesis_generator <ranked_causal_stories.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())
    stories = data.get("ranked_stories", [])

    hypotheses = []
    for i, story in enumerate(stories, 1):
        hypotheses.append(build_hypothesis(story, i))

    output = {
        "schema": "vulnlab.hypotheses.v1",
        "input_schema": data.get("schema"),
        "hypothesis_count": len(hypotheses),
        "summary": {
            "candidate_hypotheses": len(hypotheses),
            "critical": sum(1 for h in hypotheses if h["priority"] == "critical_compact_proof_candidate"),
            "high": sum(1 for h in hypotheses if h["priority"] == "high_proof_candidate"),
            "medium": sum(1 for h in hypotheses if h["priority"] == "medium_proof_candidate"),
        },
        "hypotheses": hypotheses,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "requires_question_generator": True,
            "requires_proof_planner": True,
            "requires_dynamic_validation": True,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "hypothesis_count": len(hypotheses),
        "summary": output["summary"],
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
