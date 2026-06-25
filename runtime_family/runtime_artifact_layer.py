#!/usr/bin/env python3
import json, sys
from pathlib import Path

ARTIFACT_MAP = {
    "flutter": {
        "FlutterEngine": ["FlutterEngine", "DartExecutor"],
        "FlutterMessaging": ["BinaryMessenger", "MethodChannel", "EventChannel"],
        "FlutterAssets": ["flutter_assets", "libflutter.so"],
    },
    "react_native": {
        "RNHost": ["ReactNativeHost", "ReactActivity"],
        "RNBridge": ["ReactMethod", "NativeModule", "ReactPackage"],
        "RNJNI": ["libreactnativejni.so"],
    },
    "hybrid_web": {
        "HybridJSBridge": ["cordova.exec", "Capacitor.Plugins", "addJavascriptInterface"],
        "HybridWebView": ["CapacitorWebView", "CordovaWebView", "WebView"],
        "HybridConfig": ["capacitor.config", "cordova.js"],
    },
    "unity": {
        "UnityEngine": ["UnityPlayer", "libunity.so", "libil2cpp.so"],
        "UnityAssets": ["assets/bin/Data", "StreamingAssets"],
        "UnityRendering": ["GLSurfaceView", "SurfaceView"],
    },
    "xamarin_maui": {
        "ManagedRuntime": ["libmonodroid.so", "Mono.Android", "assemblies/"],
        "NativeBinding": ["JNI", "NativeLibrary"],
    },
    "android_native": {
        "AndroidComponent": ["Activity", "Service", "BroadcastReceiver", "ContentProvider"],
        "IntentRouter": ["Intent", "Uri", "startActivity"],
    },
    "kotlin_compose": {
        "ComposeRuntime": ["androidx.compose.runtime", "androidx.compose.ui", "@Composable"],
        "KotlinRuntime": ["kotlinx.coroutines", "kotlin.Metadata"],
    },
}

def read(p):
    try:
        return Path(p).read_text(errors="ignore")
    except Exception:
        return ""

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def collect(target):
    parts = []
    for p in [target / "apk_characterization.json", target / "universal_apk_summary.json"]:
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
                    parts.append(txt[:6000])
    return "\n".join(parts)

def build(target_dir):
    target = Path(target_dir).resolve()
    fam = load(target / "universal_runtime_families.json")
    corpus = collect(target)

    artifacts = []

    detected = [f["runtime_family"] for f in fam.get("runtime_families", [])]

    for runtime in detected:
        for artifact_kind, markers in ARTIFACT_MAP.get(runtime, {}).items():
            hits = [m for m in markers if m in corpus]
            if not hits:
                continue

            score = min(0.98, 0.55 + len(hits) * 0.12)
            artifacts.append({
                "runtime_family": runtime,
                "artifact_kind": artifact_kind,
                "name": f"{runtime}:{artifact_kind}",
                "markers": hits,
                "confidence_score": round(score, 4),
                "confidence_label": "high" if score >= 0.75 else "medium",
                "status": "runtime_artifact_candidate"
            })

    out = {
        "target": str(target),
        "model": "runtime_artifact_layer_v1",
        "runtime_artifacts": artifacts,
        "summary": {
            "artifacts": len(artifacts),
            "runtime_families": sorted(set(a["runtime_family"] for a in artifacts)),
            "artifact_kinds": sorted(set(a["artifact_kind"] for a in artifacts)),
        }
    }

    path = target / "runtime_artifact_layer.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m runtime_family.runtime_artifact_layer output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
