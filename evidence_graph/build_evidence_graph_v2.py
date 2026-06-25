#!/usr/bin/env python3
import json, sys, hashlib
from pathlib import Path

MIN_NODE_CONF = 0.50

def sid(*parts):
    return hashlib.sha1("::".join(str(p) for p in parts).encode()).hexdigest()[:10]

def label(score):
    if score >= 0.85: return "very_high"
    if score >= 0.70: return "high"
    if score >= 0.50: return "medium"
    if score >= 0.30: return "low"
    return "very_low"

def sinks_for_object(kind, name, caps):
    l = name.lower()
    sinks = []

    if "sharedpreferencesapi" in l or "sharedpreferencesplugin" in l or "preferences" in caps:
        if any(x in l for x in ["set", "remove", "clear"]):
            sinks += ["SharedPreferences.Editor"]
        sinks += ["SharedPreferences"]

    if "pathproviderapi" in l or "pathproviderplugin" in l:
        sinks += ["java.io.File", "Context.getFilesDir", "Context.getExternalFilesDir"]

    if "imagepicker" in l or "image_picker" in l:
        sinks += ["FileProvider", "ContentResolver", "MediaStore", "Uri"]

    if "imagecropper" in l or "ucrop" in l:
        sinks += ["Uri", "java.io.File", "ContentResolver"]

    if "webview" in caps or "webview_url" in caps:
        sinks += ["Uri", "Intent", "WebView.loadUrl"]

    if "permissions" in caps:
        sinks += ["requestPermissions", "checkSelfPermission"]

    if "file_storage" in caps and not sinks:
        sinks += ["java.io.File", "ContentResolver", "Uri"]

    if "media_camera" in caps and not sinks:
        sinks += ["FileProvider", "MediaStore", "Uri"]

    out = []
    for s in sinks:
        if s not in out:
            out.append(s)
    return out[:4]

def validation_for(cap, sink, source_name):
    base = {
        "status": "candidate_only_not_vulnerability",
        "reachability_state": "unknown",
        "dynamic_validation_state": "pending",
        "requires": [
            "entrypoint correlation",
            "source-to-runtime object correlation",
            "native implementation confirmation",
            "dynamic validation",
            "exploitability reasoning"
        ],
    }

    if cap == "preferences":
        base["dynamic_validation_plan"] = [
            "Identify preference keys touched by the RPC/plugin.",
            "Check whether values are security-relevant or user-controlled.",
            "Validate read/write behavior on device with benign test values."
        ]
    elif cap == "file_storage":
        base["dynamic_validation_plan"] = [
            "Trigger the related runtime flow from UI or entrypoint.",
            "Observe path/URI boundaries with app-private and external storage.",
            "Confirm whether file read/write/share occurs at the selected sink."
        ]
    elif cap == "media_camera":
        base["dynamic_validation_plan"] = [
            "Trigger image/video picker or cropper flow.",
            "Inspect URI grants, FileProvider paths, and temporary file lifecycle.",
            "Validate benign external URI/file handling."
        ]
    elif cap == "webview_url":
        base["dynamic_validation_plan"] = [
            "Trigger URL/URI flow with benign controlled input.",
            "Validate scheme allowlist and external intent/WebView behavior.",
            "Confirm whether untrusted input reaches URL sink."
        ]
    elif cap == "permissions":
        base["dynamic_validation_plan"] = [
            "Trigger permission request flow.",
            "Validate denied/partial permission behavior.",
            "Confirm no sensitive continuation without required permission."
        ]
    else:
        base["dynamic_validation_plan"] = [
            "Confirm native implementation.",
            "Prove reachability.",
            "Validate behavior dynamically with benign input."
        ]

    return base

def build(target_dir):
    target = Path(target_dir).resolve()
    kg = json.loads((target / "semantic_runtime_kg_confidence.json").read_text())

    semantic_sources = []
    for n in kg.get("nodes", []):
        if n.get("kind") in {
            "PigeonRPC",
            "PluginRegistration",
            "NativeCapabilityProvider",
            "NativePluginClass"
        } and n.get("confidence_score", 0) >= MIN_NODE_CONF:
            semantic_sources.append(n)

    stories = []

    for n in semantic_sources:
        kind = n["kind"]
        name = n["name"]
        caps = n.get("capability_families", [])
        if not caps:
            continue

        for cap in caps:
            sinks = sinks_for_object(kind, name, caps)
            if not sinks:
                continue

            for sink in sinks:
                source_score = n.get("confidence_score", 0.5)
                if kind == "PigeonRPC":
                    causal_weight = 0.92
                elif kind == "PluginRegistration":
                    causal_weight = 0.88
                elif kind == "NativeCapabilityProvider":
                    causal_weight = 0.74
                else:
                    causal_weight = 0.65

                chain_score = round(source_score * causal_weight, 4)

                story = {
                    "story_id": f"STORY-{sid(target, kind, name, cap, sink)}",
                    "status": "candidate_only_not_vulnerability",
                    "causal_path": [
                        {
                            "kind": kind,
                            "name": name,
                            "role": "runtime_semantic_object",
                            "confidence_score": source_score,
                            "confidence_label": n.get("confidence_label"),
                        },
                        {
                            "kind": "CapabilityFamily",
                            "name": cap,
                            "role": "semantic_capability",
                        },
                        {
                            "kind": "NativeSinkCandidate",
                            "name": sink,
                            "role": "specific_sink_candidate_not_proven",
                        },
                        {
                            "kind": "ReachabilityState",
                            "name": "unknown",
                            "role": "must_be_proven_before_vulnerability_claim",
                        },
                        {
                            "kind": "ValidationState",
                            "name": "pending",
                            "role": "dynamic_validation_required",
                        }
                    ],
                    "capability_family": cap,
                    "sink_candidate": sink,
                    "confidence_score": chain_score,
                    "confidence_label": label(chain_score),
                    "why_this_chain_exists": [
                        f"{kind} is a semantic runtime object, not a raw string.",
                        f"{name} maps specifically to capability family {cap}.",
                        f"{sink} selected by object-aware sink mapping, not generic cartesian expansion."
                    ],
                    "evidence_source": n.get("source", {}),
                    "validation": validation_for(cap, sink, name),
                }

                stories.append(story)

    # dedupe and rank
    dedup = {}
    for s in stories:
        key = (
            s["causal_path"][0]["kind"],
            s["causal_path"][0]["name"],
            s["capability_family"],
            s["sink_candidate"]
        )
        if key not in dedup or s["confidence_score"] > dedup[key]["confidence_score"]:
            dedup[key] = s

    stories = sorted(
        dedup.values(),
        key=lambda x: (-x["confidence_score"], x["capability_family"], x["sink_candidate"])
    )

    out = {
        "target": str(target),
        "model": "semantic_evidence_graph_v2",
        "principle": "causal compact evidence stories; candidate only; no vulnerability claim without reachability and dynamic validation",
        "stories": stories,
        "summary": {
            "stories": len(stories),
            "stories_by_confidence": {
                lab: sum(1 for s in stories if s["confidence_label"] == lab)
                for lab in ["very_high", "high", "medium", "low", "very_low"]
            },
            "capability_families": sorted(set(s["capability_family"] for s in stories)),
            "source_kinds": sorted(set(s["causal_path"][0]["kind"] for s in stories)),
            "top_sink_candidates": sorted(set(s["sink_candidate"] for s in stories))[:50],
        }
    }

    path = target / "semantic_evidence_graph_v2.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m evidence_graph.build_evidence_graph_v2 output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
