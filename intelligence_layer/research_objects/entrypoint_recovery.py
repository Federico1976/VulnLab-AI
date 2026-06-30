import re
from typing import Dict, Any, List


class ResearchObjectEntrypointRecovery:
    """
    Recovers entrypoint hints from merged raw evidence.
    This is a pre-Joern enrichment layer.
    """

    PATTERNS = [
        r"ReactMethod\s+[A-Za-z0-9_.$]+",
        r"@[A-Za-z0-9_.]*ReactMethod",
        r"[A-Za-z0-9_.$]+Activity",
        r"[A-Za-z0-9_.$]+Receiver",
        r"[A-Za-z0-9_.$]+Service",
        r"onCreate\s*\(",
        r"shouldOverrideUrlLoading",
        r"onNewIntent",
        r"loadUrl\s*\(",
    ]

    def recover(self, research_object: Dict[str, Any]) -> Dict[str, Any]:
        obj = dict(research_object)

        existing = list(obj.get("merged_entrypoints", []))
        recovered = []

        for candidate in obj.get("normalized_candidates", []):
            recovered.extend(self._from_candidate(candidate))

        merged = []
        for item in existing + recovered:
            if item and item not in merged:
                merged.append(item)

        obj["merged_entrypoints"] = merged
        obj["entrypoint_recovery"] = {
            "recovered": [x for x in recovered if x not in existing],
            "total_entrypoints": len(merged),
            "strategy": "regex/raw_candidate_bridge_activity_recovery"
        }

        return obj

    def _from_candidate(self, candidate: Dict[str, Any]) -> List[str]:
        found = []

        for key in ["candidate_id", "raw_title", "raw_category"]:
            value = candidate.get(key)
            if value:
                found.extend(self._from_text(str(value)))

        raw = candidate.get("raw", {})
        if isinstance(raw, dict):
            for key in ["method", "class", "component", "title", "finding_id", "description"]:
                value = raw.get(key)
                if value:
                    found.extend(self._from_text(str(value)))

            for src in ["sources", "sinks", "entrypoints"]:
                value = raw.get(src)
                if value:
                    found.extend(self._from_text(str(value)))

        found.extend(self._from_text(str(candidate)))

        cleaned = []
        for item in found:
            item = item.strip()
            if item and item not in cleaned:
                cleaned.append(item)

        return cleaned

    def _from_text(self, text: str) -> List[str]:
        found = []
        for pattern in self.PATTERNS:
            for match in re.findall(pattern, text):
                found.append(match)
        return found
