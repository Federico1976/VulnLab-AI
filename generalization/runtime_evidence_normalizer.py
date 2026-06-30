#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


NOISE_TERMS = [
    "samsung", "systemui", "bixby", "galaxyfinder", "facebook",
    "google.android.gms", "knox", "launcher", "badge", "omc_agent",
    "phoneinterfacemanager", "imsresolver", "plugininstancemanager",
]

OPERA_TERMS = [
    "com.opera.browser", "m.opera.browse", "opera", "chromium",
    "com.opera.android", "mainlauncheractivity", "com.opera.opera",
]

GUARD_TERMS = [
    "securityexception", "permission denial", "denied", "blocked",
    "not allowed", "background start not allowed",
]


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def classify_log(log: str):
    text = (log or "").lower()
    lines = [x for x in text.splitlines() if x.strip()]

    opera_lines = []
    noise_lines = []
    guard_lines = []

    for line in lines:
        is_opera = any(t in line for t in OPERA_TERMS)
        is_noise = any(t in line for t in NOISE_TERMS)
        is_guard = any(t in line for t in GUARD_TERMS)

        if is_opera:
            opera_lines.append(line)
        elif is_noise:
            noise_lines.append(line)

        if is_guard:
            guard_lines.append(line)

    real_guard = []
    noise_guard = []

    for line in guard_lines:
        if any(t in line for t in OPERA_TERMS):
            real_guard.append(line)
        else:
            noise_guard.append(line)

    if real_guard:
        guard_class = "app_or_target_relevant_guard"
    elif noise_guard:
        guard_class = "platform_or_environment_noise_guard"
    else:
        guard_class = "no_guard_signal"

    return {
        "opera_signal_lines": opera_lines[-40:],
        "noise_lines": noise_lines[-40:],
        "guard_lines": guard_lines[-40:],
        "real_guard_lines": real_guard[-20:],
        "noise_guard_lines": noise_guard[-20:],
        "guard_classification": guard_class,
        "opera_signal_count": len(opera_lines),
        "noise_count": len(noise_lines),
        "guard_count": len(guard_lines),
    }


def normalize_result(r):
    raw_log = ""
    if isinstance(r.get("filtered_log"), dict):
        raw_log = r["filtered_log"].get("stdout", "")

    cls = classify_log(raw_log)
    interp = r.get("scheme_interpretation", {})

    state = interp.get("ui_scheme_state")
    adjusted_state = state
    delta_adjustment = 0.0

    if cls["guard_classification"] == "platform_or_environment_noise_guard":
        if state == "partially_supported_with_guards":
            adjusted_state = "supported_runtime_ui_noise_guard_demoted"
            delta_adjustment = 0.04

    elif cls["guard_classification"] == "app_or_target_relevant_guard":
        adjusted_state = "supported_runtime_ui_with_target_guard"
        delta_adjustment = -0.02

    return {
        "validation_id": r.get("validation_id"),
        "validates_node": r.get("validates_node"),
        "validates_edge": r.get("validates_edge"),
        "command": r.get("command"),
        "scheme": interp.get("scheme"),
        "original_ui_scheme_state": state,
        "normalized_ui_scheme_state": adjusted_state,
        "original_confidence_delta": interp.get("confidence_delta", 0.0),
        "normalization_delta_adjustment": round(delta_adjustment, 3),
        "normalized_confidence_delta": round(float(interp.get("confidence_delta") or 0.0) + delta_adjustment, 3),
        "log_classification": cls,
        "candidate_only": True,
        "finding_allowed": False,
    }


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Runtime Evidence Normalizer v1")
    ap.add_argument("--ui-scheme", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ui = load(args.ui_scheme)
    normalized = [normalize_result(r) for r in ui.get("results", [])]

    by_scheme = {}
    for n in normalized:
        scheme = n.get("scheme") or "unknown"
        by_scheme.setdefault(scheme, {
            "count": 0,
            "states": {},
            "normalized_confidence_delta": 0.0,
            "guard_classes": {},
        })
        by_scheme[scheme]["count"] += 1
        st = n.get("normalized_ui_scheme_state")
        by_scheme[scheme]["states"][st] = by_scheme[scheme]["states"].get(st, 0) + 1
        by_scheme[scheme]["normalized_confidence_delta"] += n.get("normalized_confidence_delta", 0.0)
        gc = n.get("log_classification", {}).get("guard_classification")
        by_scheme[scheme]["guard_classes"][gc] = by_scheme[scheme]["guard_classes"].get(gc, 0) + 1

    for s in by_scheme.values():
        s["normalized_confidence_delta"] = round(s["normalized_confidence_delta"], 3)

    out = {
        "schema_version": "runtime_evidence_normalizer.v1",
        "created_at": int(time.time()),
        "source_ui_scheme": args.ui_scheme,
        "summary": {
            "results_normalized": len(normalized),
            "by_scheme": by_scheme,
            "candidate_only": True,
            "finding_allowed": False,
            "next_step": "update_proof_graph_with_normalized_runtime_evidence",
        },
        "normalized_results": normalized,
    }

    save(args.out, out)
    print(json.dumps(out["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
