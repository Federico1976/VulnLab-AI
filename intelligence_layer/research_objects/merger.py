import hashlib
from typing import Dict, Any, List


class ResearchObjectMerger:
    """
    Merges duplicate/fragmented normalized candidates into Research Objects.

    The agent should reason over Research Objects, not raw findings.
    """

    def merge(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets = {}

        for c in candidates:
            key = self._merge_key(c)
            buckets.setdefault(key, []).append(c)

        objects = []

        for key, items in buckets.items():
            first = items[0]
            obj = {
                "object_id": self._object_id(first, key),
                "apk_id": first.get("apk_id", "unknown"),
                "runtime_family": first.get("runtime_family", "unknown"),
                "object_type": self._object_type(items),
                "primary_capability": self._primary_capability(items),
                "normalized_candidates": items,
                "merged_entrypoints": self._merge_list(items, "entrypoints"),
                "merged_sources": self._merge_list(items, "sources"),
                "merged_sinks": self._merge_list(items, "sinks"),
                "evidence_sources": self._evidence_sources(items),
                "qualification": {}
            }
            objects.append(obj)

        return sorted(objects, key=lambda x: len(x["normalized_candidates"]), reverse=True)

    def _merge_key(self, c: Dict[str, Any]) -> str:
        runtime = c.get("runtime_family", "unknown")
        entry = "|".join(sorted(c.get("entrypoints", []))) or "no_entry"
        sinks = "|".join(sorted(c.get("sinks", []))) or self._capability_from_blob(c)
        category = c.get("raw_category") or self._capability_from_blob(c)

        return f"{runtime}::{entry}::{sinks}::{category}"

    def _object_id(self, c: Dict[str, Any], key: str) -> str:
        digest = hashlib.sha1(key.encode()).hexdigest()[:10]
        return f"RO-{c.get('apk_id','unknown')}-{digest}"

    def _object_type(self, items: List[Dict[str, Any]]) -> str:
        blob = " ".join(str(i).lower() for i in items)

        if "reactmethod" in blob or "bridge" in blob:
            return "runtime_bridge_surface"
        if "webview" in blob or "loadurl" in blob:
            return "webview_surface"
        if "intent" in blob or "deeplink" in blob:
            return "intent_or_deeplink_surface"
        if "file" in blob or "path" in blob:
            return "file_path_surface"

        return "generic_security_surface"

    def _primary_capability(self, items: List[Dict[str, Any]]) -> str:
        blob = " ".join(str(i).lower() for i in items)

        if "fileinputstream" in blob or "new file" in blob or "path" in blob:
            return "file_access"
        if "loadurl" in blob or "webview" in blob:
            return "web_content_loading"
        if "intent" in blob or "uri.fromfile" in blob:
            return "intent_handoff"
        if "crypto" in blob:
            return "crypto"
        if "network" in blob:
            return "network"

        return "unknown_capability"

    def _merge_list(self, items: List[Dict[str, Any]], key: str) -> List[str]:
        merged = []
        for item in items:
            for value in item.get(key, []):
                if value not in merged:
                    merged.append(value)
        return merged

    def _evidence_sources(self, items: List[Dict[str, Any]]) -> List[str]:
        sources = []
        for item in items:
            src = item.get("raw", {}).get("_source_file") if isinstance(item.get("raw"), dict) else None
            if src and src not in sources:
                sources.append(src)
        return sources

    def _capability_from_blob(self, c: Dict[str, Any]) -> str:
        blob = str(c).lower()
        if "file" in blob or "path" in blob:
            return "file_access"
        if "webview" in blob or "loadurl" in blob:
            return "webview"
        if "intent" in blob or "uri" in blob:
            return "intent"
        return "unknown"
