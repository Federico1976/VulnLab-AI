from .base import EntityExtractor
from ..ontology import ENTITY_TYPES, make_entity


ASSET_KEYWORDS = [
    "WebView", "Activity", "Intent", "File", "Uri", "URL", "url",
    "storage", "path", "token", "secret", "permission"
]


class AssetEntityExtractor(EntityExtractor):
    name = "asset"

    def extract_from_candidate(self, ro, candidate):
        out = []
        rid = ro.get("object_id")
        cid = candidate.get("candidate_id")
        runtime = candidate.get("runtime_family") or ro.get("runtime_family")
        raw = candidate.get("raw", {})

        evidence = {
            "class": raw.get("class"),
            "file": raw.get("file"),
            "risky_keywords": raw.get("risky_keywords"),
            "title": raw.get("title"),
        }

        if any(k in str(evidence) for k in ASSET_KEYWORDS):
            out.append(make_entity(
                ENTITY_TYPES["asset"], rid, cid, runtime,
                "candidate_sensitive_asset_or_component",
                evidence,
                "raw.class/raw.risky_keywords",
            ))

        return out
