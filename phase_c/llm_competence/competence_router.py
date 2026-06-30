import json
import sys
from pathlib import Path


SUPPORTED_COMPETENCES = {
    "extract_root_cause",
    "extract_trust_boundary",
    "extract_counterevidence",
    "extract_dynamic_validation_idea"
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def deterministic_stub_review(packet):
    """
    Safe placeholder.
    No external LLM call yet.
    Produces structured 'needs_human_or_llm_review' output.
    """
    case = packet.get("current_candidate", {})
    causal = case.get("causal_shape", {})
    learning = case.get("learning_model", {})
    counter = case.get("counterevidence_model", {})
    evidence = case.get("evidence_model", {})

    return {
        "schema": "vulnlab.llm_review_result.v1",
        "packet_id": packet.get("packet_id"),
        "case_id": packet.get("case_id"),
        "review_mode": "deterministic_stub_no_llm",
        "refined_root_cause": learning.get("root_cause", "unknown"),
        "refined_trust_boundary": causal.get("trust_boundary", {}).get("boundary_type", "unknown"),
        "attacker_position": causal.get("attacker_position", {}).get("value", "unknown"),
        "attacker_controlled_input": causal.get("attacker_controlled_input", {}).get("type", "unknown"),
        "sensitive_operation": causal.get("sensitive_operation", {}).get("type", "unknown"),
        "security_effect": causal.get("security_effect", {}).get("type", "unknown"),
        "exploit_primitive": causal.get("exploit_primitive", {}).get("type", "unknown"),
        "counterevidence": counter.get("counter_signals", []),
        "dynamic_validation_idea": [
            x.get("description")
            for x in evidence.get("dynamic_evidence_required", [])
            if isinstance(x, dict)
        ],
        "patch_or_mitigation_lesson": "unknown_until_llm_or_human_review",
        "confidence": "low",
        "unknowns": [
            "patch_semantics_not_extracted",
            "source_specific_root_cause_not_verified",
            "requires_llm_or_human_review"
        ],
        "promotion_recommendation": "keep_quarantined",
        "guardrail": {
            "finding_allowed": False,
            "candidate_only": True,
            "safe_for_memory_promotion": False
        }
    }


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: python3 -m phase_c.llm_competence.competence_router "
            "<review_packets_dir> <review_results_dir> <mode>"
        )

    packets_dir = Path(sys.argv[1])
    results_dir = Path(sys.argv[2])
    mode = sys.argv[3]

    if mode != "stub":
        raise SystemExit("only mode supported now: stub")

    results_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for path in sorted(packets_dir.glob("*.json")):
        packet = load_json(path)
        result = deterministic_stub_review(packet)
        out = results_dir / path.name.replace(".llm_review_packet.json", ".llm_review_result.json")
        with out.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        count += 1

    print(json.dumps({
        "status": "ok",
        "mode": mode,
        "review_results": count,
        "output_dir": str(results_dir),
        "promotion_allowed": False
    }, indent=2))


if __name__ == "__main__":
    main()
