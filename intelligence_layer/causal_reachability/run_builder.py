import json
import sys
from pathlib import Path

from intelligence_layer.causal_reachability.builder import CausalReachabilityBuilder


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 -m intelligence_layer.causal_reachability.run_builder <candidate.json>")
        sys.exit(1)

    candidate = json.loads(Path(sys.argv[1]).read_text())
    graph = CausalReachabilityBuilder().build(candidate)
    print(json.dumps(graph, indent=2))


if __name__ == "__main__":
    main()
