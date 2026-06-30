from typing import Dict, Any, List


class EvidenceCaseNormalizer:
    """
    Normalizes heterogeneous engine outputs into a stable candidate format
    consumable by the Phase B Research Case Layer.
    """

    def normalize(self, raw: Dict[str, Any], apk_id: str = "unknown") -> Dict[str, Any]:
        candidate_id = (
            raw.get("candidate_id")
            or raw.get("finding_id")
            or raw.get("id")
            or raw.get("title")
            or "unknown-candidate"
        )

        runtime_family = (
            raw.get("runtime_family")
            or raw.get("family")
            or raw.get("framework")
            or self._infer_runtime_family(raw)
        )

        evidence_type = (
            raw.get("evidence_type")
            or raw.get("status")
            or raw.get("evidence")
            or self._infer_evidence_type(raw)
        )

        reachability_result = (
            raw.get("reachability_result")
            or raw.get("reachability")
            or self._infer_reachability(raw)
        )

        return {
            "candidate_id": str(candidate_id),
            "apk_id": raw.get("apk_id", apk_id),
            "runtime_family": runtime_family,
            "evidence_type": evidence_type,
            "reachability_result": reachability_result,
            "entrypoints": self._extract_entrypoints(raw),
            "sources": self._extract_sources(raw),
            "sinks": self._extract_sinks(raw),
            "confidence_score": self._extract_confidence(raw),
            "raw_title": raw.get("title", ""),
            "raw_category": raw.get("category", raw.get("type", "")),
            "raw": raw,
        }

    def normalize_many(self, items: List[Dict[str, Any]], apk_id: str = "unknown") -> List[Dict[str, Any]]:
        return [self.normalize(item, apk_id=apk_id) for item in items]

    def _infer_runtime_family(self, raw: Dict[str, Any]) -> str:
        blob = str(raw).lower()
        if "reactmethod" in blob or "react native" in blob or "rnfs" in blob:
            return "react_native"
        if "flutter" in blob or "dart" in blob:
            return "flutter"
        if "webview" in blob or "cordova" in blob or "capacitor" in blob:
            return "hybrid_web"
        if "unity" in blob or "il2cpp" in blob:
            return "unity"
        return "android_native"

    def _infer_evidence_type(self, raw: Dict[str, Any]) -> str:
        blob = str(raw).lower()
        if "cpg" in blob or "joern" in blob or "proven" in blob:
            return "cpg_local_proven"
        if "source_text" in blob or "fallback" in blob:
            return "source_text_fallback"
        if "semantic" in blob:
            return "semantic_object_only"
        if "sink" in blob:
            return "static_sink_only"
        return "raw_signal"

    def _infer_reachability(self, raw: Dict[str, Any]) -> str:
        blob = str(raw).lower()
        if "not_reachable" in blob or "not reachable" in blob:
            return "not_reachable"
        if "proven" in blob or "externally_reachable\": true" in blob:
            return "proven"
        if "predicted" in blob or "candidate" in blob:
            return "predicted"
        return "unknown"

    def _extract_entrypoints(self, raw: Dict[str, Any]) -> List[str]:
        for key in ["entrypoints", "entrypoint", "external_entrypoints", "react_methods"]:
            if key in raw:
                return self._as_list(raw[key])

        result = []
        for key in ["method", "class", "component"]:
            value = raw.get(key)
            if value and ("ReactMethod" in str(value) or "Activity" in str(value) or "Receiver" in str(value)):
                result.append(str(value))

        return result

    def _extract_sources(self, raw: Dict[str, Any]) -> List[str]:
        for key in ["sources", "source", "input_sources"]:
            if key in raw:
                return self._as_list(raw[key])

        blob = str(raw).lower()
        if "path" in blob:
            return ["path:String"]
        if "intent" in blob:
            return ["Intent data"]
        if "url" in blob or "uri" in blob:
            return ["url_or_uri:String"]

        return []

    def _extract_sinks(self, raw: Dict[str, Any]) -> List[str]:
        for key in ["sinks", "sink", "dangerous_sinks"]:
            if key in raw:
                return self._as_list(raw[key])

        result = []
        blob = str(raw).lower()

        if "fileinputstream" in blob:
            result.append("FileInputStream(path)")
        if "new file" in blob or "file(" in blob:
            result.append("new File(path)")
        if "loadurl" in blob:
            result.append("WebView.loadUrl(url)")
        if "uri.fromfile" in blob:
            result.append("Uri.fromFile(file)")
        if "intent.setdata" in blob:
            result.append("Intent.setDataAndType(uri, mime)")

        return list(dict.fromkeys(result))

    def _extract_confidence(self, raw: Dict[str, Any]) -> float:
        value = raw.get("confidence_score", raw.get("confidence", 0.5))

        if isinstance(value, (int, float)):
            return float(value)

        mapping = {
            "low": 0.35,
            "medium": 0.55,
            "high": 0.75,
            "critical": 0.90,
        }

        return mapping.get(str(value).lower(), 0.5)

    def _as_list(self, value) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, str):
                    result.append(item)
                elif isinstance(item, dict):
                    result.append(
                        item.get("method")
                        or item.get("name")
                        or item.get("value")
                        or item.get("sink")
                        or item.get("source")
                        or str(item)
                    )
                else:
                    result.append(str(item))
            return result
        if isinstance(value, dict):
            return [value.get("method") or value.get("name") or value.get("value") or str(value)]
        return [str(value)]
