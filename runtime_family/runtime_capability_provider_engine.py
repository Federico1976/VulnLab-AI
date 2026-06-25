#!/usr/bin/env python3
import json, sys
from pathlib import Path

FAMILY_CAPABILITIES = {
    "android_native": ["intent_routing", "file_storage", "permissions", "ipc"],
    "flutter": ["dart_bridge", "plugin_runtime", "file_storage", "preferences", "media_camera"],
    "react_native": ["js_native_bridge", "native_module", "file_storage", "crypto", "webview_url"],
    "hybrid_web": ["js_bridge", "webview_url", "file_storage", "preferences", "media_camera", "permissions"],
    "unity": ["native_engine", "asset_loading", "file_storage", "network", "rendering", "permissions"],
    "xamarin_maui": ["managed_runtime", "native_binding", "file_storage", "preferences", "network"],
    "kotlin_compose": ["android_ui_runtime", "intent_routing", "file_storage", "webview_url"],
}

CAPABILITY_TO_SINK = {
    "intent_routing": ["Intent", "Uri", "startActivity"],
    "file_storage": ["java.io.File", "ContentResolver", "Uri"],
    "permissions": ["requestPermissions", "checkSelfPermission"],
    "ipc": ["Binder", "ContentProvider", "Intent"],
    "dart_bridge": ["BinaryMessenger", "MethodChannel", "EventChannel"],
    "plugin_runtime": ["PluginRegistry", "GeneratedPluginRegistrant"],
    "preferences": ["SharedPreferences", "SharedPreferences.Editor"],
    "media_camera": ["FileProvider", "MediaStore", "Uri"],
    "js_native_bridge": ["ReactMethod", "NativeModule"],
    "native_module": ["NativeModule", "ReactPackage"],
    "crypto": ["Cipher", "MessageDigest"],
    "webview_url": ["WebView.loadUrl", "Uri", "Intent"],
    "js_bridge": ["addJavascriptInterface", "cordova.exec", "Capacitor.Plugins"],
    "native_engine": ["libunity.so", "libil2cpp.so", "UnityPlayer"],
    "asset_loading": ["AssetManager", "StreamingAssets", "assets/bin/Data"],
    "network": ["URLConnection", "OkHttp", "UnityWebRequest"],
    "rendering": ["SurfaceView", "GLSurfaceView", "UnityPlayer"],
    "managed_runtime": ["MonoRuntime", "assemblies", "JNI"],
    "native_binding": ["JNI", "NativeLibrary"],
    "android_ui_runtime": ["Activity", "Fragment", "Composable"],
}

def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def build(target_dir):
    target = Path(target_dir).resolve()
    fam = load(target / "universal_runtime_families.json")

    providers = []

    for rf in fam.get("runtime_families", []):
        family = rf["runtime_family"]
        for cap in FAMILY_CAPABILITIES.get(family, []):
            providers.append({
                "runtime_family": family,
                "capability_provider": cap,
                "confidence_score": rf["confidence_score"],
                "confidence_label": rf["confidence_label"],
                "sink_candidates": CAPABILITY_TO_SINK.get(cap, []),
                "status": "capability_provider_candidate_not_vulnerability"
            })

    out = {
        "target": str(target),
        "model": "runtime_capability_provider_engine_v1",
        "providers": providers,
        "summary": {
            "providers": len(providers),
            "runtime_families": sorted(set(p["runtime_family"] for p in providers)),
            "capability_providers": sorted(set(p["capability_provider"] for p in providers)),
        }
    }

    path = target / "runtime_capability_providers.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m runtime_family.runtime_capability_provider_engine output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
