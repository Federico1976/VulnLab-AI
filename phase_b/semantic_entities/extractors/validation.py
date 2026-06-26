from .base import EntityExtractor
from ..ontology import ENTITY_TYPES, make_entity


class ValidationEvidenceExtractor(EntityExtractor):
    name = "validation_evidence"

    def extract_from_candidate(self, ro, candidate):
        out = []
        rid = ro.get("object_id")
        cid = candidate.get("candidate_id")
        runtime = candidate.get("runtime_family") or ro.get("runtime_family")

        if candidate.get("reachability_result"):
            out.append(make_entity(
                ENTITY_TYPES["validation_evidence"], rid, cid, runtime,
                "candidate_reachability_result",
                {
                    "reachability_result": candidate.get("reachability_result"),
                    "confidence_score": candidate.get("confidence_score"),
                    "qualification": candidate.get("qualification"),
                },
                "candidate.reachability_result",
            ))

        return out
