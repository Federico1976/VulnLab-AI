#!/usr/bin/env python3
import json
import sys
from pathlib import Path


QUESTION_TEMPLATES = {
    "prove_external_or_attacker_controllable_entrypoint": [
        "Which externally reachable Android, runtime, IPC, deeplink, WebView, push, notification, or exported component can trigger this candidate?",
        "Is the bridge method reachable only from trusted bundled JavaScript, or can attacker-influenced input reach it?",
        "Can this candidate be linked to a recovered entrypoint from the Research Object context?"
    ],
    "prove_source_controllability": [
        "Which source values are attacker-controlled, user-controlled, remotely controlled, or configuration-controlled?",
        "Are the source arguments derived from trusted constants or from untrusted runtime input?",
        "Can the source be influenced without local privileged access?"
    ],
    "prove_source_to_sink_data_or_control_flow": [
        "Is there a causal data/control path from the source entity to the sink entity?",
        "Does propagation preserve attacker influence, or is the value transformed into a safe constant?",
        "Which Joern query should prove or refute the source-to-sink path?"
    ],
    "prove_sink_security_impact": [
        "What exact security-sensitive operation is performed by the sink?",
        "Does the sink affect WebView loading, file access, IPC, intent launching, crypto, storage, network, BLE, or permissions?",
        "What concrete impact would exist if the source is controllable?"
    ],
    "collect_counter_evidence": [
        "Is there any sanitizer, permission check, allowlist, origin check, signature check, authentication check, or runtime guard?",
        "Is the path blocked by lifecycle, component visibility, internal-only routing, or impossible runtime state?",
        "What evidence would downgrade this candidate to benign behavior?"
    ],
    "evaluate_sanitizer_effectiveness": [
        "Does the sanitizer validate the dangerous value itself or only check key presence?",
        "Is validation semantic, such as URL scheme/host allowlist, file path canonicalization, permission check, or origin verification?",
        "Can the sanitizer be bypassed by alternate input shape, encoding, nullability, or runtime state?"
    ],
    "prove_asset_security_relevance": [
        "Which protected asset, component, capability, or trust boundary is affected?",
        "Is the asset security-sensitive or merely functional?",
        "Does the asset create confidentiality, integrity, authentication, authorization, or local privilege impact?"
    ],
}


def generate_questions(hypothesis):
    questions = []

    for proof in hypothesis.get("required_proofs", []):
        for idx, q in enumerate(QUESTION_TEMPLATES.get(proof, []), 1):
            questions.append({
                "question_id": f"{hypothesis['hypothesis_id']}-{proof}-Q{idx}",
                "proof_requirement": proof,
                "question": q,
                "expected_answer_type": "evidence_or_counter_evidence",
                "must_not_conclude_vulnerability": True,
            })

    for gap in hypothesis.get("known_gaps", []):
        if gap == "missing_candidate_level_entrypoint":
            questions.append({
                "question_id": f"{hypothesis['hypothesis_id']}-gap-entrypoint-Q1",
                "proof_requirement": "recover_candidate_level_entrypoint",
                "question": "Recover the concrete candidate-level entrypoint that can invoke this bridge/candidate path, or prove that it is internal-only.",
                "expected_answer_type": "entrypoint_or_internal_only_counter_evidence",
                "must_not_conclude_vulnerability": True,
            })

        if gap in {"large_story", "very_large_story"}:
            questions.append({
                "question_id": f"{hypothesis['hypothesis_id']}-gap-compaction-Q1",
                "proof_requirement": "compact_large_story",
                "question": "Which minimal subset of entities is necessary to prove or refute this causal path?",
                "expected_answer_type": "minimal_causal_slice",
                "must_not_conclude_vulnerability": True,
            })

        if gap == "missing_asset":
            questions.append({
                "question_id": f"{hypothesis['hypothesis_id']}-gap-asset-Q1",
                "proof_requirement": "recover_security_asset",
                "question": "Identify whether the sink affects a security-relevant asset or only a non-sensitive functional component.",
                "expected_answer_type": "asset_or_no_security_asset",
                "must_not_conclude_vulnerability": True,
            })

    return questions


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.questions.question_generator <hypotheses.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())
    hypotheses = data.get("hypotheses", [])

    objects = []

    for h in hypotheses:
        qs = generate_questions(h)
        objects.append({
            "hypothesis_id": h["hypothesis_id"],
            "story_id": h["story_id"],
            "research_object_id": h["research_object_id"],
            "candidate_id": h["candidate_id"],
            "priority": h["priority"],
            "rank_score": h["rank_score"],
            "hypothesis_type": h["hypothesis_type"],
            "question_count": len(qs),
            "questions": qs,
            "quality_gates": {
                "declares_vulnerability": False,
                "candidate_evidence_only": True,
                "questions_require_evidence_answers": True,
                "requires_proof_planner": True,
            },
        })

    output = {
        "schema": "vulnlab.investigative_questions.v1",
        "input_schema": data.get("schema"),
        "hypothesis_count": len(objects),
        "question_count": sum(o["question_count"] for o in objects),
        "summary": {
            "critical": sum(1 for o in objects if o["priority"] == "critical_compact_proof_candidate"),
            "high": sum(1 for o in objects if o["priority"] == "high_proof_candidate"),
            "medium": sum(1 for o in objects if o["priority"] == "medium_proof_candidate"),
        },
        "question_sets": objects,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "used_for_investigation_planning": True,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "hypotheses": len(objects),
        "questions": output["question_count"],
        "summary": output["summary"],
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
