import json
import re
from pathlib import Path
from typing import Dict, Any, List


class ActivityNavigationCorrelator:
    """
    Universal next-hop correlator.

    entrypoint -> Activity source -> routing/navigation hints

    It does not claim vulnerabilities.
    """

    ROUTING_PATTERNS = [
        "getIntent(", "getData(", "getDataString(", "getExtras(", "getStringExtra(",
        "NavController", "navigate(", "NavHost", "NavDeepLink",
        "startActivity(", "startActivityForResult(",
        "Fragment", "FragmentManager", "beginTransaction(",
        "setContent(", "Composable", "@Composable",
        "WebView", "loadUrl(", "evaluateJavascript(",
        "FirebaseMessagingService", "PendingIntent",
        "Auth0", "RedirectActivity", "callback", "oauth",
    ]

    def __init__(self, target_dir: str, paths: List[Dict[str, Any]]):
        self.target_dir = Path(target_dir)
        self.paths = paths
        self.code_root = self.target_dir / "code" / "decompiled" / "sources"

    def run(self) -> List[Dict[str, Any]]:
        for path in self.paths:
            self._enrich_path(path)
        return self.paths

    def _component_to_source_candidates(self, component: str) -> List[Path]:
        if not component or component == "unknown_component":
            return []

        rel = component.replace(".", "/") + ".java"
        direct = self.code_root / rel

        hits = []
        if direct.exists():
            hits.append(direct)

        simple = component.split(".")[-1]
        if self.code_root.exists():
            hits.extend(self.code_root.rglob(simple + ".java"))

        return sorted(set(hits))

    def _scan_source(self, source: Path) -> Dict[str, Any]:
        try:
            lines = source.read_text(errors="ignore").splitlines()
        except Exception:
            return {"source_file": str(source), "error": "read_failed"}

        hits = []
        for idx, line in enumerate(lines, start=1):
            for pat in self.ROUTING_PATTERNS:
                if pat in line:
                    hits.append({
                        "line": idx,
                        "pattern": pat,
                        "code": line.strip()[:500],
                    })

        methods = []
        for idx, line in enumerate(lines, start=1):
            if re.search(r"\b(onCreate|onNewIntent|handle|route|navigate|shouldOverrideUrlLoading)\b", line):
                methods.append({
                    "line": idx,
                    "code": line.strip()[:500],
                })

        categories = set()
        text = "\n".join([h["code"] for h in hits]).lower()

        if "getintent" in text or "getdata" in text or "getstringextra" in text:
            categories.add("intent_input_handling")
        if "navigate" in text or "navcontroller" in text or "navhost" in text:
            categories.add("navigation")
        if "fragment" in text:
            categories.add("fragment_transition")
        if "setcontent" in text or "composable" in text:
            categories.add("compose_route")
        if "webview" in text or "loadurl" in text:
            categories.add("webview_possible_sink")
        if "startactivity" in text:
            categories.add("activity_handoff")
        if "auth0" in text or "callback" in text or "oauth" in text:
            categories.add("auth_callback_flow")
        if "pendingintent" in text or "firebasemessagingservice" in text:
            categories.add("notification_or_fcm_flow")

        return {
            "source_file": str(source),
            "routing_hit_count": len(hits),
            "routing_hits": hits[:80],
            "method_hints": methods[:40],
            "categories": sorted(categories),
        }

    def _enrich_path(self, path: Dict[str, Any]) -> None:
        nodes = path.get("nodes") or []
        component = None

        for n in nodes:
            if n.get("kind") in {"android_component", "activity"}:
                component = n.get("label")
                break

        if not component:
            return

        sources = self._component_to_source_candidates(component)
        scans = [self._scan_source(s) for s in sources[:5]]

        best = None
        if scans:
            best = sorted(scans, key=lambda x: x.get("routing_hit_count", 0), reverse=True)[0]

        path["activity_navigation_correlation"] = {
            "component": component,
            "source_candidates": [str(s) for s in sources[:10]],
            "best": best,
            "status": "activity_source_found" if best else "activity_source_not_found",
            "guardrail": "Routing hints only. Requires source-to-sink path and dynamic validation before any vulnerability claim.",
        }

        if best and best.get("routing_hit_count", 0) > 0:
            path.setdefault("reasoning", []).append(
                "Activity/Navigation correlator found routing hints from the entrypoint component."
            )
