#!/usr/bin/env python3
import sys, json
from pathlib import Path

from pipelines.run_semantic_runtime_kg import extract, classify, build_kg, calibrate, build_evidence_v1, build_evidence_v2
from semantic_bridges.universal_semantic_bridge import build as build_bridges
from evidence_graph.merge_semantic_bridges_v2 import build as merge_bridges
from coverage.universal_coverage_matrix import build as build_matrix
from reasoning_api.export_reasoning_context import build as build_reasoning

TARGETS = [
    "output/base_449df7fd46",
    "output/vienna_lab",
    "output/seek_lab",
    "output/linktree_lab",
    "output/mashop_lab",
]

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def save(p, obj):
    Path(p).write_text(json.dumps(obj, indent=2), encoding="utf-8")

def prune_stories(target):
    p = Path(target) / "semantic_evidence_graph_v2.json"
    ev = load(p)
    stories = ev.get("stories", [])

    # Keep high/medium first, then top low only if useful.
    ranked = sorted(
        stories,
        key=lambda s: (
            {"very_high": 5, "high": 4, "medium": 3, "low": 2, "very_low": 1}.get(s.get("confidence_label"), 0),
            s.get("confidence_score", 0)
        ),
        reverse=True
    )

    kept = []
    seen = set()
    for s in ranked:
        src = s["causal_path"][0]
        key = (src["kind"], src["name"], s["capability_family"], s["sink_candidate"])
        if key in seen:
            continue
        seen.add(key)

        if s.get("confidence_label") in ("very_high", "high", "medium"):
            kept.append(s)
        elif len(kept) < 50:
            kept.append(s)

        if len(kept) >= 120:
            break

    ev["stories"] = kept
    ev["summary"] = {
        "stories": len(kept),
        "stories_by_confidence": {
            lab: sum(1 for s in kept if s.get("confidence_label") == lab)
            for lab in ["very_high", "high", "medium", "low", "very_low"]
        },
        "capability_families": sorted(set(s["capability_family"] for s in kept)),
        "source_kinds": sorted(set(s["causal_path"][0]["kind"] for s in kept)),
        "top_sink_candidates": sorted(set(s["sink_candidate"] for s in kept))[:50],
    }
    save(p, ev)
    print(json.dumps({"target": target, "pruned_v2_summary": ev["summary"]}, indent=2))

def build_reachability(target):
    ev = load(Path(target) / "semantic_evidence_graph_v2.json")
    stories = ev.get("stories", [])

    out = {
        "target": target,
        "model": "universal_reachability_v2",
        "principle": "no vulnerability claim; reachability is unknown until entrypoint and path proof exist",
        "paths": []
    }

    for s in stories:
        src = s["causal_path"][0]
        confidence = s.get("confidence_score", 0)

        status = "needs_entrypoint_correlation"
        if src["kind"] in ("ActivityIntentRoute", "WebViewDeepLinkRoute"):
            status = "entrypoint_surface_candidate"
        elif src["kind"] in ("ReactNativeBridgeMethod", "PigeonRPC", "PluginRegistration"):
            status = "runtime_method_candidate"

        out["paths"].append({
            "story_id": s["story_id"],
            "source_kind": src["kind"],
            "source_name": src["name"],
            "capability_family": s["capability_family"],
            "sink_candidate": s["sink_candidate"],
            "reachability_status": status,
            "reachable": False,
            "confidence_score": confidence,
            "requires": [
                "entrypoint proof",
                "source-to-semantic-object correlation",
                "semantic-object-to-sink proof",
                "dynamic validation"
            ]
        })

    out["summary"] = {
        "paths": len(out["paths"]),
        "by_status": {
            st: sum(1 for p in out["paths"] if p["reachability_status"] == st)
            for st in sorted(set(p["reachability_status"] for p in out["paths"]))
        }
    }

    save(Path(target) / "universal_reachability_v2.json", out)
    print(json.dumps(out["summary"], indent=2))

def build_validation(target):
    reach = load(Path(target) / "universal_reachability_v2.json")
    plans = []

    for p in reach.get("paths", []):
        cap = p["capability_family"]

        steps = [
            "Use benign inputs only.",
            "Do not access third-party/customer data.",
            "Record observable evidence without exploitation.",
        ]

        if cap == "webview_url":
            steps += ["Test benign custom URL/deeplink.", "Observe Intent/WebView routing.", "Confirm scheme/host filtering."]
        elif cap == "file_storage":
            steps += ["Use app-private temp file.", "Observe read/write/share behavior.", "Confirm storage boundary."]
        elif cap == "preferences":
            steps += ["Use non-sensitive test preference value.", "Observe read/write behavior.", "Confirm no security impact without proof."]
        elif cap == "crypto":
            steps += ["Identify algorithm usage.", "Check static keys/weak modes only from local evidence.", "Validate with local test data."]
        elif cap == "media_camera":
            steps += ["Use benign local image/video.", "Observe FileProvider/URI grants.", "Check temporary file lifecycle."]

        plans.append({
            "story_id": p["story_id"],
            "validation_status": "pending",
            "safe_to_run": True,
            "capability_family": cap,
            "steps": steps,
            "stop_conditions": [
                "requires real user/customer account data",
                "requires production service interaction beyond normal app use",
                "could cause DoS or volumetric traffic",
                "cannot be reproduced safely"
            ]
        })

    out = {
        "target": target,
        "model": "universal_dynamic_validation_planner_v1",
        "plans": plans,
        "summary": {
            "plans": len(plans),
            "capability_families": sorted(set(p["capability_family"] for p in plans))
        }
    }

    save(Path(target) / "dynamic_validation_plans.json", out)
    print(json.dumps(out["summary"], indent=2))

def build_disclosure(target):
    reach = load(Path(target) / "universal_reachability_v2.json")
    val = load(Path(target) / "dynamic_validation_plans.json")

    out = {
        "target": target,
        "model": "responsible_disclosure_candidate_engine_v1",
        "status": "no_vulnerability_claims_generated",
        "reason": "All items remain candidate-only until reachability and dynamic validation are proven.",
        "candidate_count": len(reach.get("paths", [])),
        "disclosure_ready": [],
        "blocked_candidates": [
            {
                "story_id": p["story_id"],
                "blocked_by": [
                    "reachability_not_proven",
                    "dynamic_validation_pending",
                    "exploitability_not_assessed"
                ]
            }
            for p in reach.get("paths", [])
        ],
        "summary": {
            "candidate_only": len(reach.get("paths", [])),
            "disclosure_ready": 0,
            "validation_plans": len(val.get("plans", []))
        }
    }

    save(Path(target) / "responsible_disclosure_candidates.json", out)
    print(json.dumps(out["summary"], indent=2))

if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else TARGETS
    valid = [t for t in targets if Path(t).exists()]

    for t in valid:
        print(f"===== PHASE2 COMPLETE: {t} =====")
        extract(t)
        classify(t)
        build_kg(t)
        calibrate(t)
        build_evidence_v1(t)
        build_evidence_v2(t)
        build_bridges(t)
        merge_bridges(t)
        prune_stories(t)
        build_reachability(t)
        build_validation(t)
        build_disclosure(t)

    build_matrix(valid)

    for t in valid:
        build_reasoning(t)
