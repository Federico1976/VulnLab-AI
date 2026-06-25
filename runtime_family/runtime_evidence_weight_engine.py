#!/usr/bin/env python3
import json, sys
from pathlib import Path

MARKERS = {
    "flutter": {
        "very_strong": ["libflutter.so", "flutter_assets"],
        "strong": ["FlutterActivity", "FlutterEngine"],
        "medium": ["DartExecutor", "BinaryMessenger"],
        "weak": ["MethodChannel", "EventChannel"],
    },
    "react_native": {
        "very_strong": ["libreactnativejni.so", "ReactNativeHost"],
        "strong": ["ReactActivity", "ReactPackage", "ReactMethod"],
        "medium": ["NativeModule", "CatalystInstance"],
        "weak": ["ReadableMap", "WritableMap"],
    },
    "hybrid_web": {
        "very_strong": ["cordova.js", "cordova.exec", "capacitor.config"],
        "strong": ["Capacitor.Plugins", "BridgeActivity"],
        "medium": ["CordovaPlugin", "PluginManager", "CapacitorWebView"],
        "weak": ["addJavascriptInterface"],
    },
    "unity": {
        "very_strong": ["libunity.so", "libil2cpp.so", "assets/bin/Data"],
        "strong": ["com.unity3d.player.UnityPlayerActivity"],
        "medium": ["UnityPlayer", "StreamingAssets"],
        "weak": ["UnityWebRequest", "GLSurfaceView", "SurfaceView"],
    },
    "xamarin_maui": {
        "very_strong": ["libmonodroid.so", "assemblies/", "Mono.Android"],
        "strong": ["Microsoft.Maui"],
        "medium": ["Xamarin", "MonoRuntime"],
        "weak": ["System.Private.CoreLib"],
    },
    "kotlin_compose": {
        "very_strong": ["androidx.compose.runtime", "androidx.compose.ui"],
        "strong": ["@Composable"],
        "medium": ["kotlinx.coroutines", "kotlin.Metadata"],
        "weak": ["Composable"],
    },
}

WEIGHTS = {
    "very_strong": 1.00,
    "strong": 0.75,
    "medium": 0.42,
    "weak": 0.16,
}

def read(p):
    try:
        return Path(p).read_text(errors="ignore")
    except Exception:
        return ""

def collect(target):
    parts = []
    for p in [
        target / "apk_characterization.json",
        target / "universal_apk_summary.json",
        target / "README.md",
        target / "zip_listing.txt",
    ]:
        if p.exists():
            parts.append(read(p))

    root = target / "code" / "decompiled"
    if root.exists():
        for f in root.rglob("*"):
            if f.is_file():
                parts.append(str(f.relative_to(target)))
        for ext in ("*.java", "*.kt", "*.smali", "*.xml", "*.js", "*.json"):
            for f in root.rglob(ext):
                txt = read(f)
                if txt:
                    parts.append(txt[:9000])
    return "\n".join(parts)

def score_family(corpus, fam, groups):
    hits = []
    score = 0.0

    for strength, markers in groups.items():
        for m in markers:
            if m in corpus:
                hits.append({
                    "marker": m,
                    "strength": strength,
                    "weight": WEIGHTS[strength],
                })
                score += WEIGHTS[strength]

    has_exclusive = any(h["strength"] in ("very_strong", "strong") for h in hits)

    if not hits:
        return {
            "runtime_family": fam,
            "weighted_score": 0.0,
            "confidence_score": 0.0,
            "confidence_label": "blocked",
            "hits": [],
            "negative_evidence": ["no_runtime_marker"],
            "decision": "blocked_runtime",
        }

    if not has_exclusive:
        return {
            "runtime_family": fam,
            "weighted_score": round(score, 4),
            "confidence_score": 0.0,
            "confidence_label": "blocked",
            "hits": hits,
            "negative_evidence": ["no_exclusive_runtime_marker"],
            "decision": "blocked_runtime",
        }

    normalized = min(0.99, 0.48 + min(score, 4.0) * 0.12)

    if normalized >= 0.85:
        label = "very_high"
    elif normalized >= 0.74:
        label = "high"
    elif normalized >= 0.58:
        label = "medium"
    else:
        label = "low"

    return {
        "runtime_family": fam,
        "weighted_score": round(score, 4),
        "confidence_score": round(normalized, 4),
        "confidence_label": label,
        "hits": hits,
        "negative_evidence": [],
        "decision": "runtime_family_candidate",
    }

def build(target_dir):
    target = Path(target_dir).resolve()
    corpus = collect(target)

    family_scores = {
        fam: score_family(corpus, fam, groups)
        for fam, groups in MARKERS.items()
    }

    android_score = 0.68 if any(x in corpus for x in ["Activity", "Intent", "Service", "ContentProvider"]) else 0.0
    family_scores["android_native"] = {
        "runtime_family": "android_native",
        "weighted_score": android_score,
        "confidence_score": android_score,
        "confidence_label": "medium" if android_score else "blocked",
        "hits": [],
        "negative_evidence": [] if android_score else ["no_android_runtime_marker"],
        "decision": "baseline_android_runtime" if android_score else "blocked_runtime",
    }

    out = {
        "target": str(target),
        "model": "runtime_evidence_weight_engine_v2_strength_exclusivity",
        "family_scores": family_scores,
        "summary": {
            "runtime_candidates": sorted(
                k for k, v in family_scores.items()
                if v["decision"] != "blocked_runtime"
            ),
            "blocked_runtime": sorted(
                k for k, v in family_scores.items()
                if v["decision"] == "blocked_runtime"
            ),
        }
    }

    path = target / "runtime_evidence_weights.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m runtime_family.runtime_evidence_weight_engine output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
