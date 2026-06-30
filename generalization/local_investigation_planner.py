#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def hid(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


PROTOCOL_WEIGHTS = {
    "file": 0.95,
    "content": 0.90,
    "about": 0.85,
    "http": 0.70,
    "https": 0.70,
    "ipfs": 0.65,
    "ipns": 0.65,
    "bitcoin": 0.55,
    "ethereum": 0.55,
}


COMPONENT_BONUS = {
    "MainLauncherActivity": 0.30,
    "WebappLauncherActivity": 0.25,
    "WebSearchActivity": 0.18,
    "SearchInOpera": 0.16,
    "PrivateSearch": 0.16,
    "MyFlowSendActivity": 0.15,
}


def get_raw(ro: Dict[str, Any]) -> Dict[str, Any]:
    ev = ro.get("evidence") or []
    if ev and isinstance(ev[0], dict):
        return ev[0].get("raw") or {}
    return {}


def protocol_score(schemes: List[str]) -> float:
    if not schemes:
        return 0.15
    vals = [PROTOCOL_WEIGHTS.get(str(s).lower(), 0.35) for s in schemes]
    return max(vals)


def component_score(component: str) -> float:
    score = 0.0
    for k, v in COMPONENT_BONUS.items():
        if k in component:
            score += v
    return min(score, 0.35)


def evidence_score(raw: Dict[str, Any]) -> float:
    score = 0.0
    if raw.get("exported") is True:
        score += 0.20
    if raw.get("has_intent_filter") is True:
        score += 0.15
    if "android.intent.action.VIEW" in raw.get("actions", []):
        score += 0.20
    if "android.intent.category.BROWSABLE" in raw.get("categories", []):
        score += 0.20
    if "*" in raw.get("hosts", []):
        score += 0.15
    if raw.get("paths"):
        score += 0.10
    return min(score, 1.0)


def infer_source_to_sink_path(ro: Dict[str, Any], target_shape: str) -> List[Dict[str, Any]]:
    raw = get_raw(ro)
    component = raw.get("component_name") or ro.get("component")
    schemes = raw.get("schemes", [])
    actions = raw.get("actions", [])

    source = "Intent.getData()/Intent extras"
    if "android.intent.action.PROCESS_TEXT" in actions:
        source = "Intent.EXTRA_PROCESS_TEXT"
    elif "android.intent.action.SEND" in actions:
        source = "Intent.EXTRA_TEXT / Intent.EXTRA_STREAM"
    elif "android.intent.action.WEB_SEARCH" in actions:
        source = "SearchManager.QUERY / WEB_SEARCH intent"

    sink = "browser navigation / URL loading sink"
    if target_shape == "webview_external_input_to_load":
        sink = "navigation dispatcher -> browser tab / WebView-like loadUrl sink"

    return [
        {"order": 1, "stage": "entrypoint", "node": component, "evidence_needed": "exported activity and matching intent-filter"},
        {"order": 2, "stage": "source", "node": source, "evidence_needed": "attacker-controlled URI/text/query"},
        {"order": 3, "stage": "normalization", "node": "URI parser / scheme dispatcher", "evidence_needed": f"accepted schemes: {schemes}"},
        {"order": 4, "stage": "propagation", "node": "navigation/router layer", "evidence_needed": "trace from source to internal navigation call"},
        {"order": 5, "stage": "sink", "node": sink, "evidence_needed": "confirmed load/open/navigation behavior"},
        {"order": 6, "stage": "counter-evidence", "node": "guards/sanitizers", "evidence_needed": "domain allowlist, scheme restrictions, file/content blocking, auth checks"},
    ]


def required_commands(ro: Dict[str, Any]) -> List[str]:
    raw = get_raw(ro)
    component = raw.get("component_name")
    schemes = raw.get("schemes", [])
    paths = raw.get("paths", [])
    actions = raw.get("actions", [])

    cmds = []

    if "android.intent.action.VIEW" in actions and component:
        for scheme in schemes[:6]:
            if scheme in ("http", "https"):
                cmds.append(f"adb shell am start -n com.opera.browser/{component} -a android.intent.action.VIEW -d '{scheme}://example.com/'")
            elif scheme == "file":
                cmds.append(f"adb shell am start -n com.opera.browser/{component} -a android.intent.action.VIEW -d 'file:///sdcard/Download/vulnlab_safe_test.html'")
            elif scheme == "content":
                cmds.append(f"adb shell am start -n com.opera.browser/{component} -a android.intent.action.VIEW -d 'content://com.opera.browser.safe.test/item'")
            elif scheme == "about":
                cmds.append(f"adb shell am start -n com.opera.browser/{component} -a android.intent.action.VIEW -d 'about:blank'")
            else:
                cmds.append(f"adb shell am start -n com.opera.browser/{component} -a android.intent.action.VIEW -d '{scheme}:vulnlab-safe-test'")

        for path in paths[:3]:
            cmds.append(f"# Path-focused benign probe: {path}")

    elif "android.intent.action.PROCESS_TEXT" in actions and component:
        cmds.append(f"adb shell am start -n com.opera.browser/{component} -a android.intent.action.PROCESS_TEXT --es android.intent.extra.PROCESS_TEXT 'vulnlab safe query'")

    elif "android.intent.action.WEB_SEARCH" in actions and component:
        cmds.append(f"adb shell am start -n com.opera.browser/{component} -a android.intent.action.WEB_SEARCH --es query 'vulnlab safe query'")

    elif "android.intent.action.SEND" in actions and component:
        cmds.append(f"adb shell am start -n com.opera.browser/{component} -a android.intent.action.SEND -t text/plain --es android.intent.extra.TEXT 'https://example.com/'")

    return cmds


def score_ro(ro: Dict[str, Any], target_shape: str) -> Dict[str, Any]:
    raw = get_raw(ro)
    component = raw.get("component_name") or ro.get("component") or ""
    schemes = raw.get("schemes", [])

    base = 0.20
    ps = protocol_score(schemes)
    es = evidence_score(raw)
    cb = component_score(component)

    shape_bonus = 0.15 if target_shape == "webview_external_input_to_load" and any(s in schemes for s in ["http", "https", "file", "content", "about"]) else 0.0

    probability = min(base + (ps * 0.30) + (es * 0.30) + cb + shape_bonus, 0.99)

    return {
        "success_probability": round(probability, 3),
        "components": {
            "protocol_score": round(ps, 3),
            "evidence_score": round(es, 3),
            "component_bonus": round(cb, 3),
            "shape_bonus": round(shape_bonus, 3),
        },
    }


def build_plan(policy: Dict[str, Any], director: Dict[str, Any], research_objects: List[Dict[str, Any]], max_plans: int) -> Dict[str, Any]:
    target_shape = policy.get("summary", {}).get("top_candidate_shape") or director.get("summary", {}).get("top_global_shape")
    nbe = policy.get("summary", {}).get("next_best_experiment") or {}

    candidates = []
    for ro in research_objects:
        raw = get_raw(ro)
        text = json.dumps(ro).lower()
        if target_shape == "webview_external_input_to_load":
            if not any(x in text for x in ["deeplink", "webview", "url", "uri", "intent", "load"]):
                continue

        sc = score_ro(ro, target_shape)
        raw = get_raw(ro)

        candidate = {
            "plan_id": hid("local-plan", ro.get("research_object_id"), target_shape),
            "research_object_id": ro.get("research_object_id"),
            "title": ro.get("title"),
            "component": raw.get("component_name") or ro.get("component"),
            "actions": raw.get("actions", []),
            "categories": raw.get("categories", []),
            "schemes": raw.get("schemes", []),
            "hosts": raw.get("hosts", []),
            "paths": raw.get("paths", []),
            "risk_reasons": raw.get("risk_reasons", []),
            "target_shape": target_shape,
            "next_best_experiment": nbe,
            "success_probability": sc["success_probability"],
            "score_components": sc["components"],
            "ordered_call_chain_hypothesis": infer_source_to_sink_path(ro, target_shape),
            "evidence_required_to_confirm": [
                "component is externally triggerable",
                "attacker controls Intent data/text/query",
                "input reaches navigation/router layer",
                "navigation reaches browser/WebView-like load sink",
                "no allowlist/scheme guard blocks unsafe route",
                "dynamic test reproduces behavior safely",
            ],
            "evidence_required_to_disprove": [
                "component rejects external caller",
                "input is ignored or normalized to safe search only",
                "scheme/domain allowlist blocks candidate route",
                "file/content/about/internal schemes are blocked",
                "sink is unreachable from external input",
            ],
            "safe_dynamic_probe_commands": required_commands(ro),
            "finding_policy": {
                "candidate_only": True,
                "finding_allowed": False,
                "requires_manual_review": True,
                "requires_dynamic_validation": True,
            },
        }
        candidates.append(candidate)

    candidates.sort(key=lambda x: x["success_probability"], reverse=True)

    return {
        "schema_version": "local_investigation_planner.v1",
        "created_at": int(time.time()),
        "summary": {
            "target_shape": target_shape,
            "research_objects_seen": len(research_objects),
            "candidate_plans": len(candidates),
            "selected_plans": min(len(candidates), max_plans),
            "top_component": candidates[0].get("component") if candidates else None,
            "top_success_probability": candidates[0].get("success_probability") if candidates else None,
            "candidate_only": True,
            "finding_allowed": False,
        },
        "selected_plans": candidates[:max_plans],
        "all_ranked_plans": candidates,
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Local Investigation Planner v1")
    ap.add_argument("--policy", required=True)
    ap.add_argument("--director", required=True)
    ap.add_argument("--research-objects", required=True)
    ap.add_argument("--max-plans", type=int, default=5)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    policy = load_json(args.policy)
    director = load_json(args.director)
    ros = load_json(args.research_objects)

    if isinstance(ros, dict):
        ros = ros.get("research_objects") or ros.get("items") or []

    result = build_plan(policy, director, ros, args.max_plans)
    save_json(args.out, result)

    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
