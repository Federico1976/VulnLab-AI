#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sh(cmd, timeout=20):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout)
    return {
        "cmd": cmd,
        "returncode": r.returncode,
        "stdout": r.stdout[-6000:],
        "stderr": r.stderr[-3000:],
        "ok": r.returncode == 0,
    }


def classify_scheme(command: str) -> str:
    c = command.lower()
    if "about:" in c:
        return "about"
    if "content://" in c:
        return "content"
    if "file://" in c:
        return "file"
    if "http://" in c:
        return "http"
    if "https://" in c:
        return "https"
    if "bitcoin:" in c:
        return "bitcoin"
    if "ethereum:" in c:
        return "ethereum"
    return "custom_or_unknown"


def interpret(command, before, after, log):
    scheme = classify_scheme(command)
    text = (json.dumps(after) + "\n" + log).lower()

    evidence = []
    counters = []

    if "com.opera.browser" in text:
        evidence.append("opera_process_or_activity_observed")

    if "mainlauncheractivity" in text:
        evidence.append("main_launcher_activity_seen")

    if "welcomeactivity" in text:
        counters.append("onboarding_or_welcome_intercepted")

    if "chromium" in text or "networksecurityconfig" in text:
        evidence.append("browser_runtime_stack_seen")

    if "securityexception" in text or "permission denial" in text or "denied" in text:
        counters.append("platform_or_permission_guard_seen")

    if "not allowed" in text or "background start not allowed" in text:
        counters.append("runtime_start_restriction_seen")

    if scheme in ("file", "content", "about"):
        expected_risk = "sensitive_scheme_handling"
    elif scheme in ("http", "https"):
        expected_risk = "normal_navigation_handling"
    else:
        expected_risk = "custom_scheme_dispatch"

    if "onboarding_or_welcome_intercepted" in counters:
        state = "blocked_or_intercepted_by_app_state"
        delta = -0.03
    elif evidence and not counters:
        state = "ui_runtime_supported"
        delta = 0.08
    elif evidence and counters:
        state = "partially_supported_with_guards"
        delta = 0.03
    else:
        state = "inconclusive_ui_state"
        delta = 0.0

    return {
        "scheme": scheme,
        "expected_risk_class": expected_risk,
        "ui_scheme_state": state,
        "confidence_delta": delta,
        "positive_evidence": evidence,
        "counter_evidence": counters,
        "finding_allowed": False,
        "candidate_only": True,
    }


def current_state():
    return {
        "resumed_activity": sh("adb shell dumpsys activity activities | grep -E 'mResumedActivity|ResumedActivity|topResumedActivity' | tail -10"),
        "focused_window": sh("adb shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp' | tail -10"),
        "top_activity": sh("adb shell dumpsys activity top | grep -E 'ACTIVITY|Hist|Intent|processName|realActivity' | head -80"),
    }


def main():
    import argparse

    ap = argparse.ArgumentParser(description="UI State + Scheme Handling Collector v1")
    ap.add_argument("--proof-graph", required=True)
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sleep", type=float, default=2.0)
    args = ap.parse_args()

    proof = load(args.proof_graph)
    validations = proof["proof_graphs"][0].get("validation_evidence", [])[:args.limit]

    results = []

    for v in validations:
        cmd = v.get("command", "")
        if not cmd or cmd.strip().startswith("#"):
            continue

        sh("adb logcat -c")
        before = current_state()
        run = sh(cmd)
        time.sleep(args.sleep)
        after = current_state()

        log = sh(
            "adb logcat -d -t 400 | grep -iE 'opera|activity|intent|url|uri|scheme|navigation|chromium|webview|denied|blocked|exception|security|file|content|about' | tail -160"
        )

        interp = interpret(cmd, before, after, log.get("stdout", ""))

        results.append({
            "validation_id": v.get("validation_id"),
            "validates_node": v.get("validates_node"),
            "validates_edge": v.get("validates_edge"),
            "command": cmd,
            "run": run,
            "before_state": before,
            "after_state": after,
            "filtered_log": log,
            "scheme_interpretation": interp,
        })

    total_delta = sum(r["scheme_interpretation"]["confidence_delta"] for r in results)

    by_scheme = {}
    for r in results:
        scheme = r["scheme_interpretation"]["scheme"]
        by_scheme.setdefault(scheme, {
            "count": 0,
            "states": {},
            "confidence_delta": 0.0,
        })
        by_scheme[scheme]["count"] += 1
        state = r["scheme_interpretation"]["ui_scheme_state"]
        by_scheme[scheme]["states"][state] = by_scheme[scheme]["states"].get(state, 0) + 1
        by_scheme[scheme]["confidence_delta"] += r["scheme_interpretation"]["confidence_delta"]

    for s in by_scheme.values():
        s["confidence_delta"] = round(s["confidence_delta"], 3)

    out = {
        "schema_version": "ui_state_scheme_collector.v1",
        "created_at": int(time.time()),
        "source_proof_graph": args.proof_graph,
        "summary": {
            "validations_observed": len(results),
            "by_scheme": by_scheme,
            "confidence_delta_total": round(total_delta, 3),
            "candidate_only": True,
            "finding_allowed": False,
            "next_step": "update_evidence_proof_graph_with_ui_scheme_results",
        },
        "results": results,
    }

    save(args.out, out)
    print(json.dumps(out["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
