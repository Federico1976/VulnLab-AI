from .base import EntityExtractor
from ..ontology import ENTITY_TYPES, make_entity


class EntrypointEntityExtractor(EntityExtractor):
    name = "entrypoint"

    def extract_from_research_object(self, ro):
        out = []
        rid = ro.get("object_id")
        runtime = ro.get("runtime_family")

        for ep in ro.get("merged_entrypoints") or []:
            out.append(make_entity(
                ENTITY_TYPES["entrypoint"], rid, None, runtime,
                "merged_research_object_entrypoint",
                ep,
                "merged_entrypoints",
            ))

        for field in ["entrypoint_recovery", "entrypoint_quality"]:
            if ro.get(field):
                out.append(make_entity(
                    ENTITY_TYPES["entrypoint"], rid, None, runtime,
                    field,
                    ro.get(field),
                    field,
                ))

        return out

    def extract_from_candidate(self, ro, candidate):
        out = []
        rid = ro.get("object_id")
        cid = candidate.get("candidate_id")
        runtime = candidate.get("runtime_family") or ro.get("runtime_family")

        for ep in candidate.get("entrypoints") or []:
            out.append(make_entity(
                ENTITY_TYPES["entrypoint"], rid, cid, runtime,
                "candidate_declared_entrypoint",
                ep,
                "candidate.entrypoints",
            ))

        return out
