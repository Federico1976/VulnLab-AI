import json
from pathlib import Path
from typing import Any, Dict, List

from .models import ReachabilityNode, ReachabilityEdge, ReachabilityPath


class UniversalReachabilityEngine:
    """
    Universal Android reachability graph builder.

    Goal:
    Intent -> Activity -> Navigation -> Fragment -> Compose -> Bridge -> Sink

    This engine does NOT declare vulnerabilities.
    It emits candidate reachability evidence only.
    """

    def __init__(self, target_dir: str):
        self.target_dir = Path(target_dir)
        self.paths: List[ReachabilityPath] = []

    def run(self) -> List[Dict[str, Any]]:
        self._ingest_manifest()
        self._ingest_deeplinks()
        self._ingest_webview()
        self._ingest_flutter()
        self._ingest_rn()
        return [p.to_dict() for p in self.paths]

    def _load_json(self, rel: str, default):
        p = self.target_dir / rel
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(errors="ignore"))
        except Exception:
            return default

    def _find_json_candidates(self, keywords):
        """
        Universal artifact discovery.
        Finds prior pipeline outputs without assuming exact folder names.
        """
        hits = []
        for p in self.target_dir.rglob("*.json"):
            low = str(p).lower()
            if all(k.lower() in low for k in keywords):
                hits.append(p)
        return sorted(hits)

    def _load_first_matching_json(self, keyword_sets, default):
        for keywords in keyword_sets:
            for p in self._find_json_candidates(keywords):
                try:
                    data = json.loads(p.read_text(errors="ignore"))
                    if data:
                        return data
                except Exception:
                    pass
        return default

    def _add_path(self, path: ReachabilityPath):
        self.paths.append(path)

    def _ingest_manifest(self):
        candidates = self._load_first_matching_json([
            ["manifest", "candidate"],
            ["manifest", "finding"],
            ["exported"],
        ], [])
        if not isinstance(candidates, list):
            return

        for i, c in enumerate(candidates):
            component = c.get("component") or c.get("class") or c.get("name")
            if not component:
                continue

            nodes = [
                ReachabilityNode(
                    id=f"manifest:{i}:intent",
                    kind="intent",
                    label="external_intent_candidate",
                    evidence={"exported": c.get("exported"), "intent_filters": c.get("intent_filters")},
                ),
                ReachabilityNode(
                    id=f"manifest:{i}:component",
                    kind=c.get("component_type", "android_component"),
                    label=component,
                    owner=c.get("owner"),
                    evidence=c,
                ),
            ]

            edges = [
                ReachabilityEdge(
                    src=nodes[0].id,
                    dst=nodes[1].id,
                    kind="intent_to_component",
                    confidence=c.get("confidence", "medium"),
                    evidence={"reason": "exported/intent-filter manifest candidate"},
                )
            ]

            self._add_path(
                ReachabilityPath(
                    path_id=f"manifest_reachability_{i}",
                    nodes=nodes,
                    edges=edges,
                    sink={},
                    confidence=c.get("confidence", "medium"),
                    status="candidate_reachability_only",
                    reasoning=[
                        "Manifest candidate creates a possible external entrypoint.",
                        "No vulnerability is claimed without downstream sink and dynamic validation.",
                    ],
                )
            )


    def _ingest_deeplinks(self):
        candidates = self._load_first_matching_json([
            ["deeplink", "manifest", "candidate"],
            ["deeplink", "candidate"],
        ], [])
        if not isinstance(candidates, list):
            return

        for i, c in enumerate(candidates):
            component = (
                c.get("component")
                or c.get("component_name")
                or c.get("class")
                or c.get("activity")
                or c.get("name")
                or "unknown_component"
            )

            nodes = [
                ReachabilityNode(
                    id=f"deeplink:{i}:external",
                    kind="external_deeplink",
                    label="external_uri_candidate",
                    evidence={
                        "schemes": c.get("schemes"),
                        "hosts": c.get("hosts"),
                        "paths": c.get("paths"),
                    },
                ),
                ReachabilityNode(
                    id=f"deeplink:{i}:component",
                    kind="android_component",
                    label=component,
                    owner=c.get("ownership"),
                    evidence=c,
                ),
            ]

            edges = [
                ReachabilityEdge(
                    src=nodes[0].id,
                    dst=nodes[1].id,
                    kind="deeplink_to_component",
                    confidence=c.get("confidence", "medium"),
                    evidence={"reason": "deeplink manifest candidate"},
                )
            ]

            self._add_path(
                ReachabilityPath(
                    path_id=f"deeplink_entrypoint_{i}",
                    nodes=nodes,
                    edges=edges,
                    sink={},
                    confidence=c.get("confidence", "medium"),
                    status="entrypoint_only_candidate",
                    reasoning=[
                        "External deeplink entrypoint was discovered.",
                        "No downstream sink is attached yet.",
                        "This is not a vulnerability; it requires Navigation/Activity/Fragment/Compose correlation.",
                    ],
                )
            )

    def _ingest_webview(self):
        candidates = self._load_first_matching_json([
            ["webview", "candidate"],
            ["webview", "finding"],
            ["webview", "evidence"],
        ], [])
        if not isinstance(candidates, list):
            return

        for i, c in enumerate(candidates):
            sink = c.get("sink") or c.get("method") or c.get("api")
            owner = c.get("owner")

            nodes = [
                ReachabilityNode(
                    id=f"webview:{i}:owner",
                    kind="owner_scope",
                    label=owner or "unknown_owner",
                    evidence={"first_party": c.get("first_party"), "third_party": c.get("third_party")},
                ),
                ReachabilityNode(
                    id=f"webview:{i}:sink",
                    kind="webview_sink",
                    label=sink or "unknown_webview_sink",
                    owner=owner,
                    evidence=c,
                ),
            ]

            edges = [
                ReachabilityEdge(
                    src=nodes[0].id,
                    dst=nodes[1].id,
                    kind="owner_to_webview_sink",
                    confidence=c.get("confidence", "medium"),
                    evidence={"reason": "webview sink candidate"},
                )
            ]

            self._add_path(
                ReachabilityPath(
                    path_id=f"webview_reachability_{i}",
                    nodes=nodes,
                    edges=edges,
                    sink=c,
                    confidence=c.get("confidence", "medium"),
                    status="sink_candidate_without_full_entrypoint",
                    reasoning=[
                        "WebView sink exists in analyzed code.",
                        "Full external reachability requires Intent/Navigation correlation.",
                    ],
                )
            )


    def _ingest_flutter(self):
        candidates = self._load_first_matching_json([
            ["flutter", "surface"],
            ["flutter", "candidate"],
        ], [])
        if not isinstance(candidates, list):
            return

        for i, c in enumerate(candidates):
            pattern = c.get("pattern") or "flutter_runtime"
            evidence_type = c.get("evidence_type") or "unknown"

            nodes = [
                ReachabilityNode(
                    id=f"flutter:{i}:runtime",
                    kind="flutter_runtime",
                    label="Flutter runtime",
                    evidence={"runtime": "flutter", "evidence_type": evidence_type},
                ),
                ReachabilityNode(
                    id=f"flutter:{i}:surface",
                    kind="flutter_surface",
                    label=str(pattern),
                    evidence=c,
                ),
            ]

            edges = [
                ReachabilityEdge(
                    src=nodes[0].id,
                    dst=nodes[1].id,
                    kind="runtime_to_flutter_surface",
                    confidence=c.get("confidence", "medium"),
                    evidence={"reason": "flutter surface candidate"},
                )
            ]

            self._add_path(
                ReachabilityPath(
                    path_id=f"flutter_surface_{i}",
                    nodes=nodes,
                    edges=edges,
                    sink={},
                    confidence=c.get("confidence", "medium"),
                    status="runtime_surface_candidate",
                    reasoning=[
                        "Flutter runtime surface was discovered.",
                        "No Dart-to-native MethodChannel reachability is claimed yet.",
                        "Requires Flutter plugin/channel mapping and dynamic validation.",
                    ],
                )
            )

    def _ingest_rn(self):
        candidates = self._load_json("rn_final_multilayer_evidence.json", [])
        if not isinstance(candidates, list):
            return

        for i, c in enumerate(candidates):
            bridge = c.get("method") or c.get("react_method") or c.get("method_name")
            sink = c.get("sink") or c.get("sink_method") or c.get("local_sink")

            nodes = [
                ReachabilityNode(
                    id=f"rn:{i}:bridge",
                    kind="react_native_bridge",
                    label=bridge or "unknown_bridge",
                    evidence={
                        "evidence_tier": c.get("evidence_tier"),
                        "reachableByFlows": c.get("reachableByFlows"),
                    },
                ),
                ReachabilityNode(
                    id=f"rn:{i}:sink",
                    kind="native_sink",
                    label=str(sink or "unknown_sink"),
                    evidence=c,
                ),
            ]

            edges = [
                ReachabilityEdge(
                    src=nodes[0].id,
                    dst=nodes[1].id,
                    kind="bridge_to_sink",
                    confidence=c.get("confidence", "medium"),
                    evidence={"reason": "RN multilayer evidence candidate"},
                )
            ]

            self._add_path(
                ReachabilityPath(
                    path_id=f"rn_reachability_{i}",
                    nodes=nodes,
                    edges=edges,
                    sink=c,
                    confidence=c.get("confidence", "medium"),
                    status="bridge_to_sink_candidate",
                    reasoning=[
                        "React Native bridge candidate reaches or may reach native sink.",
                        "Exploitability still requires JS callsite, permissions, input control and dynamic validation.",
                    ],
                )
            )
