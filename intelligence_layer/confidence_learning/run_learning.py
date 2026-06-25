import json
import sys
from pathlib import Path

from validation_feedback.store import ValidationFeedbackStore
from intelligence_layer.confidence_learning.learner import DynamicConfidenceLearner


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m intelligence_layer.confidence_learning.run_learning <feedback.json> <candidate.json>")
        sys.exit(1)

    feedback_path = sys.argv[1]
    candidate_path = Path(sys.argv[2])

    store = ValidationFeedbackStore(feedback_path)
    learner = DynamicConfidenceLearner(store.load())

    candidate = json.loads(candidate_path.read_text())
    enriched = learner.adjust_candidate_confidence(candidate)

    print(json.dumps({
        "learned_adjustments": learner.learn_adjustments(),
        "candidate": enriched,
    }, indent=2))


if __name__ == "__main__":
    main()
