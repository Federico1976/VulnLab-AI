import json, sys
from pathlib import Path

def load(path):
    return json.load(open(path, "r", encoding="utf-8"))

def main():
    report_path = Path(sys.argv[1]) if len(sys.argv)>1 else Path("phase_c/knowledge_ingestion/candidate_review_report.json")
    candidates_dir = Path(sys.argv[2]) if len(sys.argv)>2 else Path("phase_c/knowledge_ingestion/vulnerability_case_candidates")
    out_dir = Path(sys.argv[3]) if len(sys.argv)>3 else Path("phase_c/knowledge_ingestion/llm_review_packets")
    out_dir.mkdir(parents=True, exist_ok=True)

    report = load(report_path)
    count = 0

    for r in report["records"]:
        if r["review_status"] != "needs_review":
            continue

        case_path = Path(r["path"])
        case = load(case_path)

        packet = {
            "schema": "vulnlab.llm_review_packet.v1",
            "packet_id": "LRP-" + case["identity"]["case_id"],
            "case_id": case["identity"]["case_id"],
            "source_quality": case["identity"]["source_quality"],
            "family": case["identity"]["vulnerability_family"],
            "title": case["identity"]["title"],
            "source_refs": case["identity"].get("source_refs", []),
            "current_candidate": {
                "affected_context": case.get("affected_context", {}),
                "causal_shape": case.get("causal_shape", {}),
                "exploitability_model": case.get("exploitability_model", {}),
                "evidence_model": case.get("evidence_model", {}),
                "counterevidence_model": case.get("counterevidence_model", {}),
                "learning_model": case.get("learning_model", {})
            },
            "llm_task": {
                "role": "semantic_vulnerability_case_reviewer",
                "objective": "Improve candidate semantic quality without inventing target-specific facts.",
                "required_outputs": [
                    "refined_root_cause",
                    "refined_trust_boundary",
                    "attacker_position",
                    "attacker_controlled_input",
                    "sensitive_operation",
                    "security_effect",
                    "exploit_primitive",
                    "counterevidence",
                    "dynamic_validation_idea",
                    "patch_or_mitigation_lesson",
                    "confidence",
                    "unknowns"
                ],
                "hard_rules": [
                    "Do not claim the APK or any target is vulnerable.",
                    "Do not invent exploitation details absent from the source.",
                    "If evidence is insufficient, mark unknown.",
                    "Prefer counterevidence and demotion rules.",
                    "Output must be structured JSON only."
                ]
            },
            "expected_response_schema": {
                "refined_root_cause": "string",
                "refined_trust_boundary": "string",
                "attacker_position": "string",
                "attacker_controlled_input": "string",
                "sensitive_operation": "string",
                "security_effect": "string",
                "exploit_primitive": "string",
                "counterevidence": ["string"],
                "dynamic_validation_idea": ["string"],
                "patch_or_mitigation_lesson": "string",
                "confidence": "low|medium|high",
                "unknowns": ["string"],
                "promotion_recommendation": "keep_quarantined|human_review|promotion_candidate"
            },
            "guardrail": {
                "finding_allowed": False,
                "candidate_only": True,
                "requires_validator_after_llm": True,
                "requires_human_or_policy_review_before_promotion": True
            }
        }

        out = out_dir / (case_path.stem + ".llm_review_packet.json")
        json.dump(packet, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        count += 1

    print(json.dumps({
        "status": "ok",
        "packets": count,
        "output_dir": str(out_dir)
    }, indent=2))

if __name__ == "__main__":
    main()
