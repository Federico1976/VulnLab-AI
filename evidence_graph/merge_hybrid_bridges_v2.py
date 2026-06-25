#!/usr/bin/env python3
import json, sys, hashlib
from pathlib import Path

SINKS = {
    "webview_url": ["WebView.loadUrl", "Uri", "Intent"],
    "file_storage": ["java.io.File", "ContentResolver", "Uri"],
    "preferences": ["SharedPreferences", "SharedPreferences.Editor"],
    "media_camera": ["FileProvider", "MediaStore", "Uri"],
    "permissions": ["requestPermissions", "checkSelfPermission"],
    "crypto": ["Cipher", "MessageDigest"],
}

def sid(*parts):
    return hashlib.sha1("::".join(str(p) for p in parts).encode()).hexdigest()[:10]

def label(score):
    if score >= 0.85: return "very_high"
    if score >= 0.70: return "high"
    if score >= 0.50: return "medium"
    if score >= 0.30: return "low"
    return "very_low"

def build(target_dir):
    target = Path(target_dir).resolve()
    ev_path = target / "semantic_evidence_graph_v2.json"
    hy_path = target / "hybrid_web_runtime_bridges.json"

    ev = json.loads(ev_path.read_text()) if ev_path.exists() else {"stories": []}
    hy = json.loads(hy_path.read_text()) if hy_path.exists() else {"hybrid_bridge_objects": []}

    existing = {
        (
            s["causal_path"][0]["kind"],
            s["causal_path"][0]["name"],
            s["capability_family"],
            s["sink_candidate"]
        )
        for s in ev.get("stories", [])
    }

    for h in hy.get("hybrid_bridge_objects", []):
        base_score = 0.78 if h["confidence"] == "high" else 0.62

        for cap in h.get("capability_families", []):
            for sink in SINKS.get(cap, [])[:3]:
                key = (h["kind"], h["name"], cap, sink)
                if key in existing:
                    continue
                score = round(base_score * 0.9, 4)

                ev.setdefault("stories", []).append({
                    "story_id": f"STORY-{sid(target, h['kind'], h['name'], cap, sink)}",
                    "status": "candidate_only_not_vulnerability",
                    "causal_path": [
                        {
                            "kind": h["kind"],
                            "name": h["name"],
                            "role": "hybrid_web_runtime_semantic_object",
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
                        "Hybrid Cordova/Capacitor/Ionic runtime artifact detected.",
                        f"{h['kind']} maps to {cap}.",
                        "Sink selected by hybrid-runtime-aware mapping, candidate only."
                    ],
                    "evidence_source": h,
                    "validation": {
                        "status": "candidate_only_not_vulnerability",
                        "reachability_state": "unknown",
                        "dynamic_validation_state": "pending",
                        "requires": [
                            "JS bridge call correlation",
                            "native plugin implementation confirmation",
                            "entrypoint correlation",
                            "dynamic validation"
                        ]
                    }
                })

    stories = ev.get("stories", [])
    stories = sorted(
        stories,
        key=lambda s: (
            {"very_high": 5, "high": 4, "medium": 3, "low": 2, "very_low": 1}.get(s.get("confidence_label"), 0),
            s.get("confidence_score", 0)
        ),
        reverse=True
    )

    ev["stories"] = stories[:160]
    ev["summary"] = {
        "stories": len(ev["stories"]),
        "stories_by_confidence": {
            lab: sum(1 for s in ev["stories"] if s.get("confidence_label") == lab)
            for lab in ["very_high", "high", "medium", "low", "very_low"]
        },
        "capability_families": sorted(set(s["capability_family"] for s in ev["stories"])),
        "source_kinds": sorted(set(s["causal_path"][0]["kind"] for s in ev["stories"])),
        "top_sink_candidates": sorted(set(s["sink_candidate"] for s in ev["stories"]))[:50],
    }

    ev_path.write_text(json.dumps(ev, indent=2), encoding="utf-8")
    print(json.dumps(ev["summary"], indent=2))
    print(f"[+] merged hybrid bridges into {ev_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m evidence_graph.merge_hybrid_bridges_v2 output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
