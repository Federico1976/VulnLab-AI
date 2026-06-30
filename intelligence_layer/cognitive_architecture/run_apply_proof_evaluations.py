import json
import sys
from pathlib import Path

from intelligence_layer.cognitive_architecture.state_updater import CognitiveStateUpdater


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m intelligence_layer.cognitive_architecture.run_apply_proof_evaluations <reasoned_states.json> <proof_evaluations.json> <output.json>")
        sys.exit(1)

    states_path = Path(sys.argv[1])
    evaluations_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    states_data = json.loads(states_path.read_text())
    evals = json.loads(evaluations_path.read_text()).get("proof_evaluations", [])
    eval_by_case = {e.get("case_id"): e for e in evals}

    updater = CognitiveStateUpdater()

    updated_states = []
    for state in states_data.get("cognitive_states", []):
        ev = eval_by_case.get(state.get("case_id"))
        if ev:
            updated_states.append(updater.apply_proof_evaluation(state, ev))
        else:
            updated_states.append(state)

    states_data["cognitive_states"] = updated_states
    states_data["summary"]["proof_evaluations_applied"] = len(evals)
    states_data["summary"]["updated_verdicts"] = {}

    for s in updated_states:
        verdict = s.get("current_verdict", "unknown")
        states_data["summary"]["updated_verdicts"][verdict] = states_data["summary"]["updated_verdicts"].get(verdict, 0) + 1

    output_path.write_text(json.dumps(states_data, indent=2, ensure_ascii=False))
    print(json.dumps(states_data["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
