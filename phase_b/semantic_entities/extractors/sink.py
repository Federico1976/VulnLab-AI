from .base import EntityExtractor
from ..ontology import ENTITY_TYPES, make_entity


class SinkEntityExtractor(EntityExtractor):
    name = "sink"

    def extract_from_research_object(self, ro):
        out = []
        rid = ro.get("object_id")
        runtime = ro.get("runtime_family")

        for sink in ro.get("merged_sinks") or []:
            out.append(make_entity(
                ENTITY_TYPES["sink"], rid, None, runtime,
                "merged_research_object_sink",
                sink,
                "merged_sinks",
            ))

        return out

    def extract_from_candidate(self, ro, candidate):
        out = []
        rid = ro.get("object_id")
        cid = candidate.get("candidate_id")
        runtime = candidate.get("runtime_family") or ro.get("runtime_family")

        for sink in candidate.get("sinks") or []:
            out.append(make_entity(
                ENTITY_TYPES["sink"], rid, cid, runtime,
                "candidate_declared_sink",
                sink,
                "candidate.sinks",
            ))

        raw = candidate.get("raw", {})
        execution = raw.get("execution_path") or candidate.get("execution_path")
        if execution and execution.get("sink_lines"):
            out.append(make_entity(
                ENTITY_TYPES["sink"], rid, cid, runtime,
                "execution_path_sink_lines",
                execution.get("sink_lines"),
                "execution_path.sink_lines",
            ))

        rn = raw.get("rn_enrichment") or candidate.get("rn_enrichment")
        if rn and rn.get("sink_hits"):
            out.append(make_entity(
                ENTITY_TYPES["sink"], rid, cid, runtime,
                "runtime_enrichment_sink_hits",
                rn.get("sink_hits"),
                "rn_enrichment.sink_hits",
            ))

        return out
