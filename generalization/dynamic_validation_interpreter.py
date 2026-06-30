#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def classify_result(result):
    runtime = result.get("runtime_result", {})
    log = (result.get("log_observation") or "").lower()
    cmd = runtime.get("command") or ""

    if not runtime.get("success"):
        return {
            "validation_state": "rejected_runtime",
            "confidence_delta": -0.12,
            "reason": "adb command failed or component was not reachable",
        }

    positive = []
    negative = []

    if "activityrecord" in log or "start proc" in log or "className : com.opera.browser" in log:
        positive.append("activity_launch_observed")

    if "welcomeactivity" in log:
        positive.append("opera_ui_transition_observed")

    if "chromium" in log or "networksecurityconfig" in log:
        positive.append("browser_runtime_stack_observed")

    if "denied" in log or "securityexception" in log or "not allowed" in log:
        negative.append("platform_or_runtime_guard_observed")

    if "file://" in cmd:
        target = "file_scheme_probe"
    elif "content://" in cmd:
        target = "content_scheme_probe"
    elif "about:" in cmd:
        target = "about_scheme_probe"
    elif "http://" in cmd or "https://" in cmd:
        target = "network_scheme_probe"
    else:
        target = "custom_scheme_probe"

    if positive and not negative:
        state = "supported_runtime"
        delta = 0.10
    elif positive and negative:
        state = "partially_supported_with_counterevidence"
        delta = 0.04
    elif negative:
        state = "guarded_or_blocked_runtime"
        delta = -0.05
    else:
        state = "runtime_inconclusive"
        delta = 0.0

    return {
        "validation_state": state,
        "confidence_delta": delta,
        "target": target,
        "positive_observations": positive,
        "negative_observations": negative,
        "reason": "runtime command executed and logs were interpreted conservatively",
    }


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Dynamic Validation Interpreter v1")
    ap.add_argument("--results", required=True)
    ap.add_argument("--proof-graph", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    results = load(args.results)
    proof = load(args.proof_graph)

    interpreted = []
    total_delta = 0.0

    for r in results.get("results", []):
        interp = classify_result(r)
        total_delta += interp.get("confidence_delta", 0.0)
        interpreted.append({
            "validation_id": r.get("validation_id"),
            "validates_node": r.get("validates_node"),
            "validates_edge": r.get("validates_edge"),
            "command": r.get("runtime_result", {}).get("command"),
            "interpretation": interp,
            "finding_allowed": False,
            "candidate_only": True,
        })

    supported = sum(1 for x in interpreted if x["interpretation"]["validation_state"] == "supported_runtime")
    partial = sum(1 for x in interpreted if x["interpretation"]["validation_state"] == "partially_supported_with_counterevidence")
    rejected = sum(1 for x in interpreted if x["interpretation"]["validation_state"] == "rejected_runtime")
    guarded = sum(1 for x in interpreted if x["interpretation"]["validation_state"] == "guarded_or_blocked_runtime")

    old_score = proof.get("summary", {}).get("top_proof_score") or 0.0
    updated_score = max(0.0, min(1.0, old_score + total_delta))

    out = {
        "schema_version": "dynamic_validation_interpreter.v1",
        "created_at": int(time.time()),
        "source_results": args.results,
        "source_proof_graph": args.proof_graph,
        "summary": {
            "validations_interpreted": len(interpreted),
            "supported_runtime": supported,
            "partial_with_counterevidence": partial,
            "guarded_or_blocked": guarded,
            "rejected_runtime": rejected,
            "old_top_proof_score": round(old_score, 3),
            "confidence_delta_total": round(total_delta, 3),
            "updated_top_proof_score_estimate": round(updated_score, 3),
            "disclosure_readiness_estimate": int(round(updated_score * 100)),
            "candidate_only": True,
            "finding_allowed": False,
        },
        "interpreted_results": interpreted,
        "next_decision": {
            "continue_investigation": updated_score >= 0.10 and guarded == 0,
            "needs_more_precise_observation": True,
            "recommended_next_step": "capture_current_activity_ui_state_and_scheme_handling",
            "reason": "runtime reachability alone is not sufficient; must prove actual navigation/sink behavior and guard behavior",
        },
    }

    save(args.out, out)
    print(json.dumps(out["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
