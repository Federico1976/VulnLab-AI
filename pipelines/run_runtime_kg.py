#!/usr/bin/env python3
import sys
from runtime_graph.universal_runtime_kg import build_runtime_kg

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m pipelines.run_runtime_kg output/<target_dir>")
        sys.exit(1)

    build_runtime_kg(sys.argv[1])
