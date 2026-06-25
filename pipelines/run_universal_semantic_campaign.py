#!/usr/bin/env python3
import sys
from pathlib import Path

from pipelines.run_semantic_runtime_kg import extract, classify, build_kg, calibrate, build_evidence_v1, build_evidence_v2
from coverage.universal_coverage_matrix import build as build_matrix
from reasoning_api.export_reasoning_context import build as build_reasoning

DEFAULT_TARGETS = [
    "output/base_449df7fd46",
    "output/vienna_lab",
    "output/seek_lab",
    "output/linktree_lab",
    "output/mashop_lab",
]

if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TARGETS
    valid = [t for t in targets if Path(t).exists()]

    for t in valid:
        print(f"===== semantic campaign: {t} =====")
        extract(t)
        classify(t)
        build_kg(t)
        calibrate(t)
        build_evidence_v1(t)
        build_evidence_v2(t)

    build_matrix(valid)

    for t in valid:
        build_reasoning(t)
