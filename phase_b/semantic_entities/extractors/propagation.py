from .base import EntityExtractor
from ..ontology import ENTITY_TYPES, make_entity


class PropagationEntityExtractor(EntityExtractor):
    name = "propagation"

    def extract_from_candidate(self, ro, candidate):
        out = []
        rid = ro.get("object_id")
        cid = candidate.get("candidate_id")
        runtime = candidate.get("runtime_family") or ro.get("runtime_family")

        raw = candidate.get("raw", {})
        execution = raw.get("execution_path") or candidate.get("execution_path")

        if execution:
            out.append(make_entity(
                ENTITY_TYPES["propagation"], rid, cid, runtime,
                "candidate_execution_path",
                execution,
                "execution_path",
            ))

        return out
