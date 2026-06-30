import json
import sys
from pathlib import Path

from intelligence_layer.cognitive_architecture.controller import CognitiveController


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m intelligence_layer.cognitive_architecture.run_cognitive_state <enriched_research_cases.json> <output.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(input_path.read_text())
    controller = CognitiveController()

    states = [
        controller.initialize(case)
        for case in data.get("research_cases", [])
    ]

    output = {
        "apk_id": data.get("apk_id", "unknown"),
        "cognitive_states": states,
        "summary": {
            "total_states": len(states),
            "by_verdict": {},
            "top_next_actions": {}
        }
    }

    for state in states:
        verdict = state.get("current_verdict", "unknown")
        output["summary"]["by_verdict"][verdict] = output["summary"]["by_verdict"].get(verdict, 0) + 1

        for action in state.get("next_actions", []):
            t = action["action_type"]
            output["summary"]["top_next_actions"][t] = output["summary"]["top_next_actions"].get(t, 0) + 1

    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(json.dumps(output["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
