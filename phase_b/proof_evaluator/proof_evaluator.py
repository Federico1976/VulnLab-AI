#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def evaluate(model):
    ef = len(model.get("evidence_for", []))
    ce = len(model.get("counter_evidence", []))
    un = len(model.get("unknowns", []))
    status = model.get("status")

    if status == "weak_needs_more_evidence":
        verdict = "needs_more_static_evidence"
    elif ce > 0 and un > 0:
        verdict = "needs_unknown_resolution"
    elif ef >= 2 and ce == 0 and un > 0:
        verdict = "candidate_supported_needs_dynamic_validation"
    elif ef >= 2 and ce == 0 and un == 0:
        verdict = "candidate_supported_not_proven"
    else:
        verdict = "inconclusive"

    return {
        "proof_evaluation_id": "PE-" + model["evidence_model_id"],
        "evidence_model_id": model["evidence_model_id"],
        "hypothesis_id": model["hypothesis_id"],
        "effect_type": model["effect_type"],
        "verdict": verdict,
        "severity_floor": model.get("severity_floor"),
        "semantic_confidence": model.get("semantic_confidence"),
        "evidence_for_count": ef,
        "counter_evidence_count": ce,
        "unknown_count": un,
        "next_required_stage": (
            "unknown_resolver" if verdict == "needs_unknown_resolution"
            else "static_evidence_collection" if verdict == "needs_more_static_evidence"
            else "dynamic_validation_planner" if verdict == "candidate_supported_needs_dynamic_validation"
            else "manual_review"
        ),
        "declares_vulnerability": False,
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.proof_evaluator.proof_evaluator <evidence_models.json> <out.json>")
        sys.exit(1)

    data = json.loads(Path(sys.argv[1]).read_text())
    evaluations = [evaluate(m) for m in data.get("evidence_models", [])]

    summary = {}
    for e in evaluations:
        summary[e["verdict"]] = summary.get(e["verdict"], 0) + 1

    out = {
        "schema": "vulnlab.proof_evaluations.v1",
        "input_schema": data.get("schema"),
        "evaluation_count": len(evaluations),
        "summary": summary,
        "evaluations": evaluations,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "requires_dynamic_validation_for_disclosure": True,
        }
    }

    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({"status": "ok", "evaluations": len(evaluations), "summary": summary, "output": sys.argv[2]}, indent=2))


if __name__ == "__main__":
    main()
