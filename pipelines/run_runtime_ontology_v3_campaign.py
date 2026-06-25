#!/usr/bin/env python3
import sys
from pathlib import Path

from runtime_family.universal_runtime_family_engine import build as build_family
from runtime_family.runtime_capability_provider_engine import build as build_providers
from evidence_graph.build_evidence_graph_v3 import build as build_ev3
from ontology.universal_runtime_ontology_v2 import build as build_ontology_v2

TARGETS = [
    "output/base_449df7fd46",
    "output/vienna_lab",
    "output/seek_lab",
    "output/linktree_lab",
    "output/mashop_lab",
    "output/ionic_code_play_lab",
    "output/gltfast_demo_lab",
]

if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else TARGETS

    for t in targets:
        if not Path(t).exists():
            continue
        print(f"===== Runtime Ontology v3: {t} =====")
        build_family(t)
        build_providers(t)
        build_ev3(t)
        build_ontology_v2(t)
