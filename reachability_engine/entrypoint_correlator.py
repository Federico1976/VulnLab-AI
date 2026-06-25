import json
import re
from pathlib import Path
from typing import Any, Dict, List


class UniversalEntryPointCorrelator:
    """
    Correlates external entrypoints with normalized reachability paths.

    No vulnerability claims.
    Output = candidate external reachability evidence only.
    """

    ENTRY_KEYWORDS = [
        "deeplink", "deep_link", "intent", "intent-filter", "exported",
        "manifest", "oauth", "callback", "auth", "notification",
        "pendingintent", "firebase", "fcm", "broadcast", "receiver"
    ]

    def __init__(self, target_dir: str, paths: List[Dict[str, Any]]):
        self.target_dir = Path(target_dir)
        self.paths = paths
        self.entrypoints = []

    def run(self) -> List[Dict[str, Any]]:
        self.entrypoints = self._discover_entrypoint_artifacts()
        return [self._correlate_path(p) for p in self.paths]

    def _read_json(self, p: Path):
        try:
            return json.loads(p.read_text(errors="ignore"))
        except Exception:
            return None

    def _discover_entrypoint_artifacts(self) -> List[Dict[str, Any]]:
        out = []

        for p in self.target_dir.rglob("*.json"):
            low = str(p).lower()

            # Ignore internal Joern/scoped manifests: they describe analysis scope, not app entrypoints.
            if "scoped_joern" in low or "scoped_sources" in low or low.endswith("scope_manifest.json"):
                continue

            if not any(k in low for k in self.ENTRY_KEYWORDS):
                continue

            data = self._read_json(p)
            if not data:
                continue

            items = data if isinstance(data, list) else [data]

            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    continue

                text = json.dumps(item, ensure_ascii=False).lower()

                kind = "unknown_entrypoint"
                if "deeplink" in low or "deep_link" in low or "scheme" in text:
                    kind = "deeplink"
                elif "oauth" in low or "callback" in text or "auth" in text:
                    kind = "oauth_or_auth_callback"
                elif "pendingintent" in text or "notification" in text:
                    kind = "notification_or_pendingintent"
                elif "receiver" in text or "broadcast" in text:
                    kind = "broadcast_receiver"
                elif "exported" in text or "intent-filter" in text or "intent_filter" in text:
                    kind = "manifest_exported_surface"
                elif "firebase" in text or "fcm" in text:
                    kind = "firebase_or_push"

                component = (
                    item.get("component")
                    or item.get("class")
                    or item.get("activity")
                    or item.get("name")
                    or item.get("target")
                    or item.get("file")
                    or "unknown_component"
                )

                out.append({
                    "entry_id": f"{p.name}:{i}",
                    "kind": kind,
                    "artifact": str(p),
                    "component": component,
                    "raw": item,
                    "text": text,
                })

        return out

    def _path_text(self, path: Dict[str, Any]) -> str:
        return json.dumps(path, ensure_ascii=False).lower()

    def _extract_class_tokens(self, text: str) -> List[str]:
        tokens = set()

        for m in re.findall(r"[a-zA-Z_][\\w$]*(?:\\.[a-zA-Z_][\\w$]*)+", text):
            if "." in m:
                tokens.add(m.lower())

        for m in re.findall(r"[A-Z][A-Za-z0-9_$]*(?:Activity|Fragment|Service|Receiver|WebView)[A-Za-z0-9_$]*", text):
            tokens.add(m.lower())

        return sorted(tokens)

    def _score_entrypoint_to_path(self, ep: Dict[str, Any], path: Dict[str, Any]) -> Dict[str, Any]:
        ptxt = self._path_text(path)
        etxt = ep.get("text", "")

        score = 0
        reasons = []

        component = str(ep.get("component") or "").lower()
        if component and component != "unknown_component" and component in ptxt:
            score += 60
            reasons.append("entrypoint component appears in path evidence")

        ep_tokens = self._extract_class_tokens(etxt + " " + component)
        path_tokens = self._extract_class_tokens(ptxt)
        overlap = sorted(set(ep_tokens) & set(path_tokens))

        if overlap:
            score += min(40, len(overlap) * 10)
            reasons.append(f"class/token overlap: {overlap[:5]}")

        if "webview" in ptxt and ep["kind"] in {
            "deeplink",
            "oauth_or_auth_callback",
            "manifest_exported_surface",
            "notification_or_pendingintent",
        }:
            score += 5
            reasons.append("external entrypoint kind is generically relevant to WebView sink")

        if "react_native_bridge" in ptxt and ep["kind"] in {
            "deeplink",
            "notification_or_pendingintent",
            "firebase_or_push",
        }:
            score += 3
            reasons.append("external entrypoint kind may generically influence JS/bridge surface")

        if "loadurl" in ptxt and ("url" in etxt or "uri" in etxt or "scheme" in etxt):
            score += 20
            reasons.append("URL-like entrypoint may correlate with loadUrl sink")

        artifact = str(ep.get("artifact") or "").lower()
        if "deeplink_webview_correlation" in artifact and "webview" in ptxt:
            score += 65
            reasons.append("prior deeplink-webview correlation artifact supports this path")

        if "deeplink_manifest_candidates" in artifact and "webview" in ptxt:
            score += 10
            reasons.append("deeplink manifest candidate is relevant to WebView path")

        strong_structural = any(
            r.startswith("entrypoint component appears")
            or r.startswith("class/token overlap")
            or r.startswith("prior deeplink-webview correlation")
            for r in reasons
        )

        if score >= 80 and strong_structural:
            confidence = "high"
            status = "externally_reachable_candidate"
        elif score >= 40:
            confidence = "medium"
            status = "possible_external_reachability"
        elif score > 0:
            confidence = "low"
            status = "weak_external_correlation"
        else:
            confidence = "none"
            status = "no_external_correlation_observed"

        return {
            "entrypoint": {
                "entry_id": ep["entry_id"],
                "kind": ep["kind"],
                "artifact": ep["artifact"],
                "component": ep["component"],
            },
            "score": score,
            "confidence": confidence,
            "status": status,
            "reasons": reasons,
        }

    def _correlate_path(self, path: Dict[str, Any]) -> Dict[str, Any]:
        correlations = []

        for ep in self.entrypoints:
            c = self._score_entrypoint_to_path(ep, path)
            if c["score"] > 0:
                correlations.append(c)

        correlations.sort(key=lambda x: x["score"], reverse=True)

        best = correlations[0] if correlations else None

        path["entrypoint_correlation"] = {
            "entrypoint_count": len(self.entrypoints),
            "correlation_count": len(correlations),
            "best": best,
            "all": correlations[:10],
            "guardrail": "Candidate external reachability only. Do not claim vulnerability without source-to-sink proof and dynamic validation.",
        }

        if best:
            path["entrypoint_correlation"]["correlated_status"] = best["status"]
            path["entrypoint_correlation"]["correlated_confidence"] = best["confidence"]

            if path.get("status") != "entrypoint_only_candidate":
                path["status"] = best["status"]
                path["confidence"] = best["confidence"]

            path.setdefault("reasoning", []).append(
                "Universal Entry Point Correlator found candidate external reachability evidence."
            )
        else:
            path.setdefault("reasoning", []).append(
                "No external entrypoint correlation observed yet."
            )

        return path
