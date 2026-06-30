import json
import sys
from pathlib import Path

from intelligence_layer.causal_reachability.proof_request import CausalProofRequestBuilder


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m intelligence_layer.causal_reachability.run_proof_requests <reasoned_states.json> <output.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(input_path.read_text())
    builder = CausalProofRequestBuilder()

    proof_requests = []

    for state in data.get("cognitive_states", []):
        decision = state.get("current_decision", {})
        action = decision.get("selected_action", {}).get("action_type")

        if action == "prove_causal_reachability":
            proof_requests.append(builder.build_from_state(state))

    output = {
        "apk_id": data.get("apk_id", "unknown"),
        "proof_requests": proof_requests,
        "summary": {
            "total_proof_requests": len(proof_requests),
            "by_upgrade": {}
        }
    }

    for req in proof_requests:
        upgrade = req.get("requested_upgrade", "unknown")
        output["summary"]["by_upgrade"][upgrade] = output["summary"]["by_upgrade"].get(upgrade, 0) + 1

    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(json.dumps(output["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
