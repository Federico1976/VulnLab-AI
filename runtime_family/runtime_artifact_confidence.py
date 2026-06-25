#!/usr/bin/env python3
import json, sys
from pathlib import Path

ARTIFACT_STRENGTH = {
    "FlutterEngine": 0.95,
    "FlutterMessaging": 0.90,
    "FlutterAssets": 0.96,
    "RNHost": 0.94,
    "RNBridge": 0.92,
    "RNJNI": 0.96,
    "HybridJSBridge": 0.95,
    "HybridWebView": 0.90,
    "HybridConfig": 0.92,
    "UnityEngine": 0.96,
    "UnityAssets": 0.94,
    "UnityRendering": 0.86,
    "ManagedRuntime": 0.95,
    "NativeBinding": 0.88,
    "AndroidComponent": 0.78,
    "IntentRouter": 0.82,
    "ComposeRuntime": 0.90,
    "KotlinRuntime": 0.76,
}

ROLE_WEIGHT = {
    "primary_runtime": 1.00,
    "secondary_runtime": 0.82,
    "embedded_runtime": 0.76,
    "sdk_or_library_runtime": 0.58,
    "weak_or_blocked_runtime": 0.30,
}

def label(x):
    if x >= 0.85: return "very_high"
    if x >= 0.70: return "high"
    if x >= 0.50: return "medium"
    if x >= 0.30: return "low"
    return "very_low"

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def build(target_dir):
    target = Path(target_dir).resolve()
    artifacts = load(target / "runtime_artifact_layer.json")
    roles = load(target / "runtime_roles.json")

    role_by_family = {
        r["runtime_family"]: r["role"]
        for r in roles.get("runtime_roles", [])
    }

    enriched = []

    for a in artifacts.get("runtime_artifacts", []):
        family = a["runtime_family"]
        kind = a["artifact_kind"]
        role = role_by_family.get(family, "unknown_role")

        base = ARTIFACT_STRENGTH.get(kind, 0.55)
        role_w = ROLE_WEIGHT.get(role, 0.45)
        marker_bonus = min(len(a.get("markers", [])) * 0.03, 0.09)

        score = min(0.99, round((base * role_w) + marker_bonus, 4))

        obj = dict(a)
        obj["runtime_role"] = role
        obj["artifact_weight"] = base
        obj["role_weight"] = role_w
        obj["artifact_confidence_score"] = score
        obj["artifact_confidence_label"] = label(score)
        obj["confidence_reason"] = [
            f"artifact_strength={base}",
            f"runtime_role={role}",
            f"role_weight={role_w}",
            f"marker_bonus={round(marker_bonus, 4)}",
        ]
        enriched.append(obj)

    out = {
        "target": str(target),
        "model": "runtime_artifact_confidence_v2_final",
        "runtime_artifacts": enriched,
        "summary": {
            "artifacts": len(enriched),
            "by_confidence": {
                lab: sum(1 for a in enriched if a["artifact_confidence_label"] == lab)
                for lab in ["very_high", "high", "medium", "low", "very_low"]
            },
            "by_role": {
                role: sum(1 for a in enriched if a["runtime_role"] == role)
                for role in sorted(set(a["runtime_role"] for a in enriched))
            },
            "artifact_kinds": sorted(set(a["artifact_kind"] for a in enriched)),
        }
    }

    path = target / "runtime_artifact_confidence.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m runtime_family.runtime_artifact_confidence output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
