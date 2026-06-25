import re
from typing import Dict, Any, List


class NextHopExtractor:
    """
    Converts routing hits into graph next-hop candidates.

    Produces:
    entrypoint -> activity -> intent_read / fragment / activity_handoff / webview_hint

    Candidate evidence only.
    """

    def __init__(self, paths: List[Dict[str, Any]]):
        self.paths = paths

    def run(self) -> List[Dict[str, Any]]:
        for path in self.paths:
            self._extract(path)
        return self.paths

    def _kind_for_hit(self, hit: Dict[str, Any]) -> str:
        code = (hit.get("code") or "").lower()
        pat = (hit.get("pattern") or "").lower()

        if "getintent" in code or "getdata" in code or "getstringextra" in code or "getextras" in code:
            return "intent_input_read"
        if "loadurl" in code or "webview" in code or "evaluatejavascript" in code:
            return "webview_hint"
        if "fragment" in code or "begintransaction" in code:
            return "fragment_hint"
        if "startactivity" in code:
            return "activity_handoff"
        if "navigate" in code or "navcontroller" in code or "navhost" in code:
            return "navigation_hint"
        if "setcontent" in code or "composable" in code:
            return "compose_hint"
        if "auth0" in code or "callback" in code or "oauth" in code:
            return "auth_callback_hint"
        if "firebase" in code or "pendingintent" in code:
            return "notification_or_fcm_hint"

        return "routing_hint"

    def _extract_target_tokens(self, code: str) -> List[str]:
        tokens = set()

        for m in re.findall(r'new\s+([A-Za-z0-9_.$]+)', code):
            tokens.add(m)

        for m in re.findall(r'([A-Za-z0-9_.$]+Activity)\b', code):
            tokens.add(m)

        for m in re.findall(r'([A-Za-z0-9_.$]+Fragment)\b', code):
            tokens.add(m)

        for m in re.findall(r'R\.id\.([A-Za-z0-9_]+)', code):
            tokens.add("R.id." + m)

        for m in re.findall(r'R\.navigation\.([A-Za-z0-9_]+)', code):
            tokens.add("R.navigation." + m)

        for m in re.findall(r'R\.string\.([A-Za-z0-9_]+)', code):
            tokens.add("R.string." + m)

        return sorted(tokens)

    def _extract(self, path: Dict[str, Any]) -> None:
        nav = path.get("activity_navigation_correlation") or {}
        best = nav.get("best") or {}
        hits = best.get("routing_hits") or []

        hops = []
        for i, hit in enumerate(hits):
            code = hit.get("code") or ""
            kind = self._kind_for_hit(hit)
            hops.append({
                "hop_id": f"{path.get('path_id')}:hop:{i}",
                "kind": kind,
                "line": hit.get("line"),
                "pattern": hit.get("pattern"),
                "code": code,
                "target_tokens": self._extract_target_tokens(code),
                "confidence": "medium" if kind != "routing_hint" else "low",
            })

        grouped = {}
        for h in hops:
            grouped[h["kind"]] = grouped.get(h["kind"], 0) + 1

        path["next_hop_extraction"] = {
            "status": "next_hops_observed" if hops else "no_next_hops_observed",
            "hop_count": len(hops),
            "kinds": grouped,
            "hops": hops[:120],
            "guardrail": "Next-hop candidates are static routing evidence only; require source-to-sink proof and dynamic validation.",
        }

        if hops:
            path.setdefault("reasoning", []).append(
                "Next Hop Extractor converted Activity routing hints into graph hop candidates."
            )
