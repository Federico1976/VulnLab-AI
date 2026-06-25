#!/usr/bin/env python3
import sys
from pathlib import Path

from runtime_family.runtime_evidence_weight_engine import build as build_weights
from runtime_family.universal_runtime_family_engine import build as build_family
from runtime_family.runtime_capability_provider_engine import build as build_providers
from runtime_family.runtime_artifact_layer import build as build_artifacts
from runtime_family.runtime_role_ranker import build as build_roles
from runtime_family.runtime_artifact_confidence import build as build_artifact_confidence
from evidence_graph.build_evidence_graph_v4 import build as build_ev4
from evidence_graph.build_evidence_graph_v5 import build as build_ev5
from ontology.universal_runtime_ontology_v3 import build as build_onto3
from ontology.universal_runtime_ontology_v4 import build as build_onto4

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
        print(f"===== Universal Runtime Modeling v4: {t} =====")
        build_weights(t)
        build_family(t)
        build_providers(t)
        build_artifacts(t)
        build_roles(t)
        build_artifact_confidence(t)
        build_ev4(t)
        build_ev5(t)
        build_onto3(t)
        build_onto4(t)
