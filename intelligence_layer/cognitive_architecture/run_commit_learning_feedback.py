import json
import sys
from pathlib import Path

from intelligence_layer.cognitive_architecture.learning_feedback_committer import LearningFeedbackCommitter


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m intelligence_layer.cognitive_architecture.run_commit_learning_feedback <states.json> <feedback_store.json> <require_approval:true|false>")
        sys.exit(1)

    states_path = Path(sys.argv[1])
    feedback_path = sys.argv[2]
    require_approval = sys.argv[3].lower() == "true"

    data = json.loads(states_path.read_text())
    states = data.get("cognitive_states", [])

    result = LearningFeedbackCommitter(feedback_path).commit_from_states(
        states,
        require_analyst_approval=require_approval,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
