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

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def build(target_dir):
    target = Path(target_dir).resolve()
    ev2 = load(target / "semantic_evidence_graph_v2.json")
    providers = load(target / "runtime_capability_providers.json")

    stories = list(ev2.get("stories", []))

    existing = {
        (
            s["causal_path"][0]["kind"],
            s["causal_path"][0]["name"],
            s["capability_family"],
            s["sink_candidate"]
        )
        for s in stories
    }

    for p in providers.get("providers", []):
        runtime = p["runtime_family"]
        cap = p["capability_provider"]

        for sink in p.get("sink_candidates", [])[:3]:
            key = ("RuntimeCapabilityProvider", f"{runtime}:{cap}", cap, sink)
            if key in existing:
                continue

            score = round(p["confidence_score"] * 0.82, 4)

            stories.append({
                "story_id": f"STORY-{sid(target, runtime, cap, sink)}",
                "status": "candidate_only_not_vulnerability",
                "causal_path": [
                    {
                        "kind": "RuntimeFamily",
                        "name": runtime,
                        "role": "detected_runtime_family",
                        "confidence_score": p["confidence_score"],
                        "confidence_label": p["confidence_label"],
                    },
                    {
                        "kind": "RuntimeCapabilityProvider",
                        "name": f"{runtime}:{cap}",
                        "role": "universal_capability_provider",
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
                    f"Runtime family {runtime} detected.",
                    f"{runtime} universally exposes provider {cap}.",
                    "Sink selected by runtime-family capability provider mapping."
                ],
                "validation": {
                    "status": "candidate_only_not_vulnerability",
                    "reachability_state": "unknown",
                    "dynamic_validation_state": "pending",
                    "requires": [
                        "runtime-family-specific evidence confirmation",
                        "entrypoint correlation",
                        "source-to-provider proof",
                        "dynamic validation"
                    ]
                }
            })

    stories = sorted(
        stories,
        key=lambda s: (
            {"very_high": 5, "high": 4, "medium": 3, "low": 2, "very_low": 1}.get(s.get("confidence_label"), 0),
            s.get("confidence_score", 0)
        ),
        reverse=True
    )

    # Dynamic pruning: no fixed 120 if fewer high-quality stories.
    high_medium = [s for s in stories if s.get("confidence_label") in ("very_high", "high", "medium")]
    low = [s for s in stories if s.get("confidence_label") == "low"]

    if len(high_medium) >= 30:
        kept = high_medium[:160]
    else:
        kept = high_medium + low[:max(0, 40 - len(high_medium))]

    out = {
        "target": str(target),
        "model": "semantic_evidence_graph_v3_runtime_family_provider",
        "stories": kept,
        "summary": {
            "stories": len(kept),
            "stories_by_confidence": {
                lab: sum(1 for s in kept if s.get("confidence_label") == lab)
                for lab in ["very_high", "high", "medium", "low", "very_low"]
            },
            "capability_families": sorted(set(s["capability_family"] for s in kept)),
            "source_kinds": sorted(set(s["causal_path"][0]["kind"] for s in kept)),
            "top_sink_candidates": sorted(set(s["sink_candidate"] for s in kept))[:50],
        }
    }

    path = target / "semantic_evidence_graph_v3.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m evidence_graph.build_evidence_graph_v3 output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
