from .base import EntityExtractor
from ..ontology import ENTITY_TYPES, make_entity


class TrustBoundaryEntityExtractor(EntityExtractor):
    name = "trust_boundary"

    def extract_from_candidate(self, ro, candidate):
        out = []
        rid = ro.get("object_id")
        cid = candidate.get("candidate_id")
        runtime = candidate.get("runtime_family") or ro.get("runtime_family")
        category = candidate.get("raw_category") or candidate.get("raw", {}).get("category")

        if runtime == "react_native" or category == "react_native_bridge":
            out.append(make_entity(
                ENTITY_TYPES["trust_boundary"], rid, cid, runtime,
                "javascript_to_native_runtime_boundary",
                {
                    "from": "javascript_runtime",
                    "to": "native_android_runtime",
                    "reason": "React Native bridge candidate",
                    "category": category,
                },
                "runtime_family/raw_category",
            ))

        return out
