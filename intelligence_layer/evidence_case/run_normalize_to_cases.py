import json
import sys
from pathlib import Path

from intelligence_layer.evidence_case.normalizer import EvidenceCaseNormalizer
from intelligence_layer.causal_reachability.builder import CausalReachabilityBuilder
from intelligence_layer.confidence_learning.learner import DynamicConfidenceLearner
from intelligence_layer.research_case.builder import ResearchCaseBuilder
from validation_feedback.store import ValidationFeedbackStore


def load_candidates(path: Path):
    data = json.loads(path.read_text())

    if isinstance(data, list):
        return data

    for key in ["candidates", "findings", "evidence", "items", "results"]:
        if isinstance(data.get(key), list):
            return data[key]

    return [data]


def main():
    if len(sys.argv) != 5:
        print(
            "Usage: python3 -m intelligence_layer.evidence_case.run_normalize_to_cases "
            "<feedback.json> <apk_id> <input_candidates.json> <output_cases.json>"
        )
        sys.exit(1)

    feedback_path = sys.argv[1]
    apk_id = sys.argv[2]
    input_path = Path(sys.argv[3])
    output_path = Path(sys.argv[4])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_candidates = load_candidates(input_path)

    normalizer = EvidenceCaseNormalizer()
    feedback = ValidationFeedbackStore(feedback_path).load()
    learner = DynamicConfidenceLearner(feedback)
    causal_builder = CausalReachabilityBuilder()
    case_builder = ResearchCaseBuilder()

    cases = []

    for raw in raw_candidates:
        normalized = normalizer.normalize(raw, apk_id=apk_id)
        confidence = learner.adjust_candidate_confidence(normalized)
        causal_graph = causal_builder.build(normalized)
        case = case_builder.build(
            candidate=normalized,
            causal_graph=causal_graph,
            confidence=confidence,
        )
        cases.append(case)

    output = {
        "apk_id": apk_id,
        "input": str(input_path),
        "research_cases": cases,
        "summary": {
            "total_cases": len(cases),
            "by_verdict": {},
            "by_runtime_family": {},
            "by_proof_level": {},
        }
    }

    for case in cases:
        verdict = case.get("current_verdict", "unknown")
        runtime = case.get("runtime_family", "unknown")
        proof = case.get("causal_graph", {}).get("proof_level", "unknown")

        output["summary"]["by_verdict"][verdict] = output["summary"]["by_verdict"].get(verdict, 0) + 1
        output["summary"]["by_runtime_family"][runtime] = output["summary"]["by_runtime_family"].get(runtime, 0) + 1
        output["summary"]["by_proof_level"][proof] = output["summary"]["by_proof_level"].get(proof, 0) + 1

    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(json.dumps(output["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
