#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def score_story(story):
    s = story.get("summary", {})
    score = 0
    reasons = []
    penalties = []

    # Core causal chain
    if s.get("has_bridge"):
        score += 10; reasons.append("bridge_present")
    if s.get("has_trust_boundary"):
        score += 10; reasons.append("trust_boundary_present")
    if s.get("has_source"):
        score += 15; reasons.append("source_present")
    if s.get("has_propagation"):
        score += 20; reasons.append("propagation_present")
    if s.get("has_sink"):
        score += 20; reasons.append("sink_present")
    if s.get("has_validation"):
        score += 10; reasons.append("validation_present")

    # Supporting evidence
    if s.get("has_asset"):
        score += 5; reasons.append("asset_present")
    if s.get("has_sanitizer"):
        score += 3; reasons.append("sanitizer_present")
    if s.get("has_counter_evidence"):
        score -= 20; penalties.append("counter_evidence_present")

    entity_count = story.get("candidate_entity_count", 0)

    # Cognitive load penalties
    if entity_count <= 15:
        score += 7; reasons.append("compact_story")
    elif entity_count <= 40:
        score += 3; reasons.append("manageable_story")
    elif entity_count <= 90:
        score -= 8; penalties.append("large_story")
    else:
        score -= 15; penalties.append("very_large_story")

    # Missing entrypoint is not fatal, but proof should recover it
    if not s.get("has_entrypoint"):
        score -= 5
        penalties.append("missing_candidate_level_entrypoint")

    # Missing asset lowers exploitability clarity
    if not s.get("has_asset"):
        score -= 5
        penalties.append("missing_asset")

    score = max(0, min(score, 100))

    if score >= 90 and entity_count <= 40:
        priority = "critical_compact_proof_candidate"
    elif score >= 80:
        priority = "high_proof_candidate"
    elif score >= 60:
        priority = "medium_proof_candidate"
    elif score >= 40:
        priority = "question_generator_candidate"
    else:
        priority = "low_priority_candidate"

    return score, priority, reasons, penalties


def compact_sequence(story, max_per_type=2):
    compacted = {}

    for entity_type, ents in story.get("causal_sequence", {}).items():
        compacted[entity_type] = ents[:max_per_type]

    return compacted


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.semantic_entities.causal_story_ranker_v1_1 <causal_stories.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())
    ranked = []

    for story in data.get("stories", []):
        score, priority, reasons, penalties = score_story(story)

        ranked.append({
            "story_id": story["story_id"],
            "research_object_id": story["research_object_id"],
            "candidate_id": story["candidate_id"],
            "readiness": story["readiness"],
            "priority": priority,
            "rank_score": score,
            "rank_reasons": reasons,
            "rank_penalties": penalties,
            "summary": story.get("summary"),
            "candidate_entity_count": story.get("candidate_entity_count"),
            "research_object_context_entity_count": story.get("research_object_context_entity_count"),
            "compact_causal_sequence": compact_sequence(story),
            "quality_gates": {
                "declares_vulnerability": False,
                "candidate_evidence_only": True,
                "ranker_is_prioritization_only": True,
                "requires_proof_planner": True,
                "requires_dynamic_validation": True,
            },
        })

    ranked.sort(key=lambda x: x["rank_score"], reverse=True)

    output = {
        "schema": "vulnlab.causal_story_ranker.v1_1",
        "input_schema": data.get("schema"),
        "story_count": len(ranked),
        "summary": {
            "critical_compact_proof_candidate": sum(1 for s in ranked if s["priority"] == "critical_compact_proof_candidate"),
            "high_proof_candidate": sum(1 for s in ranked if s["priority"] == "high_proof_candidate"),
            "medium_proof_candidate": sum(1 for s in ranked if s["priority"] == "medium_proof_candidate"),
            "question_generator_candidate": sum(1 for s in ranked if s["priority"] == "question_generator_candidate"),
            "low_priority_candidate": sum(1 for s in ranked if s["priority"] == "low_priority_candidate"),
        },
        "ranked_stories": ranked,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "story_count": len(ranked),
        "summary": output["summary"],
        "top_story": ranked[0]["story_id"] if ranked else None,
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
