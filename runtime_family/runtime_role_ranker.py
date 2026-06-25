#!/usr/bin/env python3
import json, sys
from pathlib import Path

PRIMARY_CAPABLE = {
    "flutter",
    "react_native",
    "hybrid_web",
    "unity",
    "xamarin_maui",
    "kotlin_compose",
    "android_native",
}

FRAMEWORK_SPECIFIC_ARTIFACTS = {
    "flutter": {"FlutterEngine", "FlutterMessaging", "FlutterAssets"},
    "react_native": {"RNHost", "RNBridge", "RNJNI"},
    "hybrid_web": {"HybridJSBridge", "HybridWebView", "HybridConfig"},
    "unity": {"UnityEngine", "UnityAssets", "UnityRendering"},
    "xamarin_maui": {"ManagedRuntime", "NativeBinding"},
    "kotlin_compose": {"ComposeRuntime", "KotlinRuntime"},
    "android_native": {"AndroidComponent", "IntentRouter"},
}

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def role_for(family, score, artifact_kinds, primary):
    if family == primary:
        return "primary_runtime"

    specific = FRAMEWORK_SPECIFIC_ARTIFACTS.get(family, set())
    matched = specific.intersection(set(artifact_kinds))

    if family == "android_native":
        return "secondary_runtime"

    if score >= 0.85 and len(matched) >= 2:
        return "embedded_runtime"

    if score >= 0.70 and len(matched) >= 1:
        return "sdk_or_library_runtime"

    return "weak_or_blocked_runtime"

def build(target_dir):
    target = Path(target_dir).resolve()

    families = load(target / "universal_runtime_families.json")
    artifacts = load(target / "runtime_artifact_layer.json")
    weights = load(target / "runtime_evidence_weights.json")

    artifact_by_family = {}
    for a in artifacts.get("runtime_artifacts", []):
        artifact_by_family.setdefault(a["runtime_family"], set()).add(a["artifact_kind"])

    fams = families.get("runtime_families", [])
    primary = families.get("primary_runtime_family", "unknown_runtime")

    roles = []
    for f in fams:
        fam = f["runtime_family"]
        score = f.get("confidence_score", 0)
        kinds = sorted(artifact_by_family.get(fam, []))
        role = role_for(fam, score, kinds, primary)

        roles.append({
            "runtime_family": fam,
            "role": role,
            "confidence_score": score,
            "confidence_label": f.get("confidence_label"),
            "artifact_kinds": kinds,
            "exclusive_hits": f.get("exclusive_hits", []),
            "negative_evidence": f.get("negative_evidence", []),
        })

    blocked = []
    for fam, sc in weights.get("family_scores", {}).items():
        if sc.get("exclusive_score", 0) == 0 and fam not in [r["runtime_family"] for r in roles]:
            blocked.append({
                "runtime_family": fam,
                "role": "blocked_runtime",
                "confidence_score": 0.0,
                "negative_evidence": sc.get("negative_evidence", []),
            })

    out = {
        "target": str(target),
        "model": "runtime_role_ranker_v1",
        "runtime_roles": roles + blocked,
        "summary": {
            "primary_runtime": [
                r["runtime_family"] for r in roles if r["role"] == "primary_runtime"
            ],
            "secondary_runtime": [
                r["runtime_family"] for r in roles if r["role"] == "secondary_runtime"
            ],
            "embedded_runtime": [
                r["runtime_family"] for r in roles if r["role"] == "embedded_runtime"
            ],
            "sdk_or_library_runtime": [
                r["runtime_family"] for r in roles if r["role"] == "sdk_or_library_runtime"
            ],
            "weak_or_blocked_runtime": [
                r["runtime_family"] for r in roles if r["role"] == "weak_or_blocked_runtime"
            ],
            "blocked_runtime": [
                r["runtime_family"] for r in blocked
            ],
        }
    }

    path = target / "runtime_roles.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m runtime_family.runtime_role_ranker output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
