from .base import EntityExtractor
from ..ontology import ENTITY_TYPES, make_entity


class SourceEntityExtractor(EntityExtractor):
    name = "source"

    def extract_from_research_object(self, ro):
        out = []
        rid = ro.get("object_id")
        runtime = ro.get("runtime_family")

        for src in ro.get("merged_sources") or []:
            out.append(make_entity(
                ENTITY_TYPES["source"], rid, None, runtime,
                "merged_research_object_source",
                src,
                "merged_sources",
            ))

        return out

    def extract_from_candidate(self, ro, candidate):
        out = []
        rid = ro.get("object_id")
        cid = candidate.get("candidate_id")
        runtime = candidate.get("runtime_family") or ro.get("runtime_family")

        for src in candidate.get("sources") or []:
            out.append(make_entity(
                ENTITY_TYPES["source"], rid, cid, runtime,
                "candidate_declared_source",
                src,
                "candidate.sources",
            ))

        raw = candidate.get("raw", {})
        execution = raw.get("execution_path") or candidate.get("execution_path")
        if execution and execution.get("source_argument_usage"):
            out.append(make_entity(
                ENTITY_TYPES["source"], rid, cid, runtime,
                "source_argument_usage",
                execution.get("source_argument_usage"),
                "execution_path.source_argument_usage",
            ))

        return out
