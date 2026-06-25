#!/usr/bin/env python3
import json, sys, hashlib
from pathlib import Path

def sid(*parts):
    return hashlib.sha1("::".join(str(p) for p in parts).encode()).hexdigest()[:10]

def label(score):
    if score >= 0.85: return "very_high"
    if score >= 0.70: return "high"
    if score >= 0.50: return "medium"
    if score >= 0.30: return "low"
    return "very_low"

SINKS = {
    "file_storage": ["java.io.File", "ContentResolver", "Uri"],
    "webview_url": ["Uri", "Intent", "WebView.loadUrl"],
    "crypto": ["Cipher", "MessageDigest"],
    "preferences": ["SharedPreferences", "SharedPreferences.Editor"],
    "media_camera": ["FileProvider", "MediaStore", "Uri"],
    "permissions": ["requestPermissions", "checkSelfPermission"],
}

def build(target_dir):
    target = Path(target_dir).resolve()
    ev_path = target / "semantic_evidence_graph_v2.json"
    br_path = target / "universal_semantic_bridges.json"

    ev = json.loads(ev_path.read_text()) if ev_path.exists() else {
        "target": str(target),
        "model": "semantic_evidence_graph_v2",
        "stories": [],
        "summary": {}
    }

    bridges = json.loads(br_path.read_text()) if br_path.exists() else {"bridge_objects": []}

    existing = {
        (
            s["causal_path"][0]["kind"],
            s["causal_path"][0]["name"],
            s["capability_family"],
            s["sink_candidate"]
        )
        for s in ev.get("stories", [])
    }

    for b in bridges.get("bridge_objects", []):
        base_score = 0.66 if b["confidence"] == "medium" else 0.42

        for cap in b.get("capability_families", []):
            for sink in SINKS.get(cap, [])[:3]:
                key = (b["kind"], b["name"], cap, sink)
                if key in existing:
                    continue

                score = round(base_score * 0.86, 4)

                ev.setdefault("stories", []).append({
                    "story_id": f"STORY-{sid(target, b['kind'], b['name'], cap, sink)}",
                    "status": "candidate_only_not_vulnerability",
                    "causal_path": [
                        {
                            "kind": b["kind"],
                            "name": b["name"],
                            "role": "semantic_bridge_object",
                            "confidence_score": base_score,
                            "confidence_label": label(base_score),
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
                    "confidence_score": score,
                    "confidence_label": label(score),
                    "why_this_chain_exists": [
                        f"{b['bridge']} produced a semantic object.",
                        f"{b['kind']} maps to {cap}.",
                        "Sink selected by bridge-aware mapping, candidate only."
                    ],
                    "evidence_source": b,
                    "validation": {
                        "status": "candidate_only_not_vulnerability",
                        "reachability_state": "unknown",
                        "dynamic_validation_state": "pending",
                        "requires": [
                            "entrypoint correlation",
                            "source-to-sink reachability proof",
                            "dynamic validation",
                            "exploitability reasoning"
                        ]
                    }
                })

    stories = ev.get("stories", [])
    ev["summary"] = {
        "stories": len(stories),
        "stories_by_confidence": {
            lab: sum(1 for s in stories if s.get("confidence_label") == lab)
            for lab in ["very_high", "high", "medium", "low", "very_low"]
        },
        "capability_families": sorted(set(s["capability_family"] for s in stories)),
        "source_kinds": sorted(set(s["causal_path"][0]["kind"] for s in stories)),
        "top_sink_candidates": sorted(set(s["sink_candidate"] for s in stories))[:50],
    }

    ev_path.write_text(json.dumps(ev, indent=2), encoding="utf-8")
    print(json.dumps(ev["summary"], indent=2))
    print(f"[+] merged bridges into {ev_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m evidence_graph.merge_semantic_bridges_v2 output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
