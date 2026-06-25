#!/usr/bin/env python3
import json, sys
from pathlib import Path

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def build(target_dir):
    target = Path(target_dir).resolve()
    weights_path = target / "runtime_evidence_weights.json"

    if not weights_path.exists():
        from runtime_family.runtime_evidence_weight_engine import build as build_weights
        build_weights(str(target))

    weights = load(weights_path)
    scores = weights.get("family_scores", {})

    families = []

    for fam, sc in scores.items():
        if sc.get("decision") == "blocked_runtime":
            continue

        families.append({
            "runtime_family": fam,
            "confidence_score": sc.get("confidence_score", 0.0),
            "confidence_label": sc.get("confidence_label", "unknown"),
            "weighted_score": sc.get("weighted_score", 0.0),
            "hits": sc.get("hits", []),
            "negative_evidence": sc.get("negative_evidence", []),
            "status": sc.get("decision"),
        })

    families = sorted(families, key=lambda x: x["confidence_score"], reverse=True)

    # Android native is usually secondary if another strong runtime exists.
    non_android = [f for f in families if f["runtime_family"] != "android_native"]
    primary = non_android[0]["runtime_family"] if non_android else (
        families[0]["runtime_family"] if families else "unknown_runtime"
    )

    out = {
        "target": str(target),
        "model": "universal_runtime_family_engine_v4_weighted_final",
        "primary_runtime_family": primary,
        "runtime_families": families,
        "summary": {
            "families_detected": len(families),
            "primary_runtime_family": primary,
            "families": [f["runtime_family"] for f in families],
        }
    }

    path = target / "universal_runtime_families.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m runtime_family.universal_runtime_family_engine output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
