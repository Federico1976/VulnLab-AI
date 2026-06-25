#!/usr/bin/env python3
import sys
from runtime_artifacts.extract_runtime_artifacts import build as extract
from runtime_graph.runtime_artifact_classifier import classify
from runtime_graph.build_semantic_runtime_kg import build as build_kg
from confidence.runtime_confidence_engine import calibrate
from evidence_graph.build_evidence_graph import build as build_evidence_v1
from evidence_graph.build_evidence_graph_v2 import build as build_evidence_v2

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m pipelines.run_semantic_runtime_kg output/<target_dir>")
        sys.exit(1)

    target = sys.argv[1]
    extract(target)
    classify(target)
    build_kg(target)
    calibrate(target)
    build_evidence_v1(target)
    build_evidence_v2(target)
