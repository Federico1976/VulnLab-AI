#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def build_evidence_model(hyp):
    evidence_models = []

    for eff in hyp.get("effects", []):
        evidence_for = []
        counter_evidence = []
        unknowns = []

        if eff.get("task_support_count", 0) >= 2:
            evidence_for.append({
                "type": "multi_task_support",
                "detail": f"Effect supported by {eff.get('task_support_count')} proof task types",
                "supporting_task_types": eff.get("supporting_task_types", []),
            })

        if eff.get("confidence") == "high":
            evidence_for.append({
                "type": "high_semantic_confidence",
                "detail": "Aggregated capability/effect confidence is high",
            })

        if "sanitizer_or_guard_present_requires_effectiveness_evaluation" in eff.get("modifiers", []):
            counter_evidence.append({
                "type": "possible_sanitizer_or_guard",
                "detail": "A sanitizer/guard exists and must be evaluated before any conclusion",
            })
            unknowns.append({
                "type": "sanitizer_effectiveness_unknown",
                "question": "Does the sanitizer validate the dangerous value semantically or only check presence/type?",
            })

        for focus in eff.get("proof_focus", []):
            unknowns.append({
                "type": "proof_focus_unknown",
                "question": focus,
            })

        status = "needs_proof"
        if evidence_for and not counter_evidence:
            status = "supported_but_unproven"
        elif evidence_for and counter_evidence:
            status = "contested_needs_resolution"
        elif not evidence_for:
            status = "weak_needs_more_evidence"

        evidence_models.append({
            "evidence_model_id": f"EM-{hyp['hypothesis_id']}-{eff['effect_type']}",
            "hypothesis_id": hyp["hypothesis_id"],
            "effect_type": eff["effect_type"],
            "status": status,
            "severity_floor": eff.get("severity_floor"),
            "semantic_confidence": eff.get("confidence"),
            "evidence_for": evidence_for,
            "counter_evidence": counter_evidence,
            "unknowns": unknowns,
            "declares_vulnerability": False,
            "quality_gates": {
                "candidate_evidence_only": True,
                "requires_proof_evaluator": True,
                "requires_unknown_resolution": True,
                "requires_dynamic_validation_for_disclosure": True,
            }
        })

    return evidence_models


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.evidence_model.evidence_model_builder <aggregated_security_effects.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())
    hypotheses = data.get("hypotheses", [])

    models = []
    for hyp in hypotheses:
        models.extend(build_evidence_model(hyp))

    summary = {}
    for m in models:
        summary[m["status"]] = summary.get(m["status"], 0) + 1

    output = {
        "schema": "vulnlab.evidence_models.v1",
        "input_schema": data.get("schema"),
        "evidence_model_count": len(models),
        "summary": summary,
        "evidence_models": models,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "evidence_model_is_epistemic_not_finding": True,
            "requires_proof_evaluator": True,
            "requires_dynamic_validation_for_disclosure": True,
        }
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "evidence_models": len(models),
        "summary": summary,
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
