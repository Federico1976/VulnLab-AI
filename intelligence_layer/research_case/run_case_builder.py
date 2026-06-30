import json
import sys
from pathlib import Path

from intelligence_layer.causal_reachability.builder import CausalReachabilityBuilder
from intelligence_layer.confidence_learning.learner import DynamicConfidenceLearner
from intelligence_layer.research_case.builder import ResearchCaseBuilder
from validation_feedback.store import ValidationFeedbackStore


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m intelligence_layer.research_case.run_case_builder <feedback.json> <candidate.json>")
        sys.exit(1)

    feedback_path = sys.argv[1]
    candidate_path = Path(sys.argv[2])

    candidate = json.loads(candidate_path.read_text())

    feedback = ValidationFeedbackStore(feedback_path).load()
    confidence = DynamicConfidenceLearner(feedback).adjust_candidate_confidence(candidate)
    causal_graph = CausalReachabilityBuilder().build(candidate)

    case = ResearchCaseBuilder().build(
        candidate=candidate,
        causal_graph=causal_graph,
        confidence=confidence,
    )

    print(json.dumps(case, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
