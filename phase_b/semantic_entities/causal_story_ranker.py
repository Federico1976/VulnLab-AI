#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def score_story(story):
    s = story.get("summary", {})
    score = 0
    reasons = []

    if s.get("has_bridge"):
        score += 10
        reasons.append("bridge_present")
    if s.get("has_trust_boundary"):
        score += 15
        reasons.append("trust_boundary_present")
    if s.get("has_source"):
        score += 15
        reasons.append("source_present")
    if s.get("has_propagation"):
        score += 20
        reasons.append("propagation_present")
    if s.get("has_sink"):
        score += 20
        reasons.append("sink_present")
    if s.get("has_asset"):
        score += 10
        reasons.append("asset_present")
    if s.get("has_sanitizer"):
        score += 5
        reasons.append("sanitizer_present")
    if s.get("has_validation"):
        score += 15
        reasons.append("validation_present")
    if s.get("has_counter_evidence"):
        score -= 20
        reasons.append("counter_evidence_present")

    entity_count = story.get("candidate_entity_count", 0)

    if entity_count > 80:
        score -= 10
        reasons.append("large_story_needs_compaction")
    elif entity_count <= 15:
        score += 5
        reasons.append("compact_story")

    score = max(0, min(score, 100))

    if score >= 85:
        priority = "critical_proof_candidate"
    elif score >= 70:
        priority = "high_proof_candidate"
    elif score >= 50:
        priority = "medium_investigation_candidate"
    else:
        priority = "low_priority_candidate"

    return score, priority, reasons


def compact_sequence(story, max_per_type=3):
    compacted = {}

    for entity_type, ents in story.get("causal_sequence", {}).items():
        compacted[entity_type] = ents[:max_per_type]

    return compacted


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.semantic_entities.causal_story_ranker <causal_stories.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())
    ranked = []

    for story in data.get("stories", []):
        score, priority, reasons = score_story(story)
        new_story = {
            "story_id": story["story_id"],
            "research_object_id": story["research_object_id"],
            "candidate_id": story["candidate_id"],
            "readiness": story["readiness"],
            "priority": priority,
            "rank_score": score,
            "rank_reasons": reasons,
            "summary": story.get("summary"),
            "candidate_entity_count": story.get("candidate_entity_count"),
            "research_object_context_entity_count": story.get("research_object_context_entity_count"),
            "compact_causal_sequence": compact_sequence(story),
            "quality_gates": {
                "declares_vulnerability": False,
                "candidate_evidence_only": True,
                "used_for_proof_planning_prioritization": True,
            },
        }
        ranked.append(new_story)

    ranked.sort(key=lambda x: x["rank_score"], reverse=True)

    output = {
        "schema": "vulnlab.causal_story_ranker.v1",
        "input_schema": data.get("schema"),
        "story_count": len(ranked),
        "summary": {
            "critical_proof_candidate": sum(1 for s in ranked if s["priority"] == "critical_proof_candidate"),
            "high_proof_candidate": sum(1 for s in ranked if s["priority"] == "high_proof_candidate"),
            "medium_investigation_candidate": sum(1 for s in ranked if s["priority"] == "medium_investigation_candidate"),
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
