from .base import EntityExtractor
from ..ontology import ENTITY_TYPES, make_entity


class CounterEvidenceExtractor(EntityExtractor):
    name = "counter_evidence"

    def extract_from_research_object(self, ro):
        out = []
        rid = ro.get("object_id")
        runtime = ro.get("runtime_family")

        qualification = ro.get("qualification") or {}
        if qualification:
            out.append(make_entity(
                ENTITY_TYPES["counter_evidence"], rid, None, runtime,
                "qualification_constraints_or_negative_signals",
                qualification,
                "qualification",
                confidence="candidate",
            ))

        return out
