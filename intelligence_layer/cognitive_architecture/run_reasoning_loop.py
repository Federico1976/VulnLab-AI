import json
import sys
from pathlib import Path

from intelligence_layer.cognitive_architecture.reasoning_loop import ReasoningLoop


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m intelligence_layer.cognitive_architecture.run_reasoning_loop <cognitive_states.json> <output.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(input_path.read_text())
    loop = ReasoningLoop()

    states = [
        loop.run_once(state)
        for state in data.get("cognitive_states", [])
    ]

    data["cognitive_states"] = states
    data["summary"]["reasoning_loop_executed"] = len(states)
    data["summary"]["selected_actions"] = {}

    for state in states:
        action = state.get("current_decision", {}).get("selected_action", {}).get("action_type", "none")
        data["summary"]["selected_actions"][action] = data["summary"]["selected_actions"].get(action, 0) + 1

    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(json.dumps(data["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
