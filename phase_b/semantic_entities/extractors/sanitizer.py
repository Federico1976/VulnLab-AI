from .base import EntityExtractor
from ..ontology import ENTITY_TYPES, make_entity


SANITIZER_HINTS = ["validate", "sanitize", "escape", "allowlist", "whitelist", "hasKey", "check", "verify"]


class SanitizerEntityExtractor(EntityExtractor):
    name = "sanitizer"

    def extract_from_candidate(self, ro, candidate):
        out = []
        rid = ro.get("object_id")
        cid = candidate.get("candidate_id")
        runtime = candidate.get("runtime_family") or ro.get("runtime_family")

        raw = candidate.get("raw", {})
        evidence = raw.get("evidence") or candidate.get("evidence_type") or ""

        hits = [h for h in SANITIZER_HINTS if h.lower() in evidence.lower()]
        if hits:
            out.append(make_entity(
                ENTITY_TYPES["sanitizer"], rid, cid, runtime,
                "possible_guard_or_validation_hint",
                {"hits": hits, "evidence_preview": evidence[:1500]},
                "raw.evidence",
                confidence="weak_candidate",
            ))

        return out
