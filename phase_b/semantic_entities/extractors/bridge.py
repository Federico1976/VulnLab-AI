from .base import EntityExtractor
from ..ontology import ENTITY_TYPES, make_entity


class BridgeEntityExtractor(EntityExtractor):
    name = "bridge"

    def extract_from_research_object(self, ro):
        out = []
        rid = ro.get("object_id")
        runtime = ro.get("runtime_family")

        recovery = ro.get("bridge_method_recovery")
        if recovery:
            out.append(make_entity(
                ENTITY_TYPES["bridge"], rid, None, runtime,
                "recovered_runtime_bridge_surface",
                recovery,
                "bridge_method_recovery",
            ))

        return out

    def extract_from_candidate(self, ro, candidate):
        out = []
        rid = ro.get("object_id")
        cid = candidate.get("candidate_id")
        runtime = candidate.get("runtime_family") or ro.get("runtime_family")

        raw = candidate.get("raw", {})
        rn = raw.get("rn_enrichment") or candidate.get("rn_enrichment")
        execution = raw.get("execution_path") or candidate.get("execution_path")

        source = None
        if execution:
            source = execution.get("source")

        if source:
            out.append(make_entity(
                ENTITY_TYPES["bridge"], rid, cid, runtime,
                "candidate_runtime_bridge_method",
                source,
                "execution_path.source",
            ))
        elif rn and rn.get("method_name"):
            out.append(make_entity(
                ENTITY_TYPES["bridge"], rid, cid, runtime,
                "candidate_runtime_bridge_method",
                rn,
                "rn_enrichment",
            ))
        elif raw.get("signature") or raw.get("class"):
            out.append(make_entity(
                ENTITY_TYPES["bridge"], rid, cid, runtime,
                "candidate_runtime_bridge_method",
                {
                    "class": raw.get("class"),
                    "signature": raw.get("signature"),
                    "line": raw.get("line"),
                    "file": raw.get("file"),
                },
                "raw.signature",
            ))

        return out
