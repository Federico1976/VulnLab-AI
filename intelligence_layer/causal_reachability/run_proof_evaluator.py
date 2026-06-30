import json
import sys
from pathlib import Path

from intelligence_layer.causal_reachability.proof_evaluator import CausalProofEvaluator


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m intelligence_layer.causal_reachability.run_proof_evaluator <proof_requests.json> <proof_results.json> <output.json>")
        sys.exit(1)

    requests_path = Path(sys.argv[1])
    results_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    requests = json.loads(requests_path.read_text()).get("proof_requests", [])
    results = json.loads(results_path.read_text()).get("proof_results", [])

    by_case = {r.get("case_id"): r for r in results}

    evaluator = CausalProofEvaluator()
    evaluations = []

    for req in requests:
        case_id = req.get("case_id")
        result = by_case.get(case_id, {})
        evaluations.append(evaluator.evaluate(req, result))

    output = {
        "proof_evaluations": evaluations,
        "summary": {
            "total": len(evaluations),
            "by_decision": {}
        }
    }

    for ev in evaluations:
        d = ev["proof_decision"]
        output["summary"]["by_decision"][d] = output["summary"]["by_decision"].get(d, 0) + 1

    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(json.dumps(output["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
