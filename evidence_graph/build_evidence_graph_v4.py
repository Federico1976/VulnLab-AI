#!/usr/bin/env python3
import json, sys, hashlib
from pathlib import Path

ARTIFACT_TO_PROVIDER = {
    "FlutterEngine": ["dart_bridge", "plugin_runtime"],
    "FlutterMessaging": ["dart_bridge"],
    "FlutterAssets": ["file_storage"],
    "RNHost": ["js_native_bridge"],
    "RNBridge": ["native_module", "js_native_bridge"],
    "RNJNI": ["native_module"],
    "HybridJSBridge": ["js_bridge"],
    "HybridWebView": ["webview_url"],
    "HybridConfig": ["webview_url", "preferences"],
    "UnityEngine": ["native_engine", "rendering"],
    "UnityAssets": ["asset_loading", "file_storage"],
    "UnityRendering": ["rendering"],
    "ManagedRuntime": ["managed_runtime"],
    "NativeBinding": ["native_binding"],
    "AndroidComponent": ["intent_routing", "ipc"],
    "IntentRouter": ["intent_routing", "webview_url"],
    "ComposeRuntime": ["android_ui_runtime"],
    "KotlinRuntime": ["android_ui_runtime"],
}

PROVIDER_TO_SINK = {
    "dart_bridge": ["BinaryMessenger", "MethodChannel", "EventChannel"],
    "plugin_runtime": ["PluginRegistry", "GeneratedPluginRegistrant"],
    "file_storage": ["java.io.File", "ContentResolver", "Uri"],
    "js_native_bridge": ["ReactMethod", "NativeModule"],
    "native_module": ["NativeModule", "ReactPackage"],
    "js_bridge": ["cordova.exec", "Capacitor.Plugins", "addJavascriptInterface"],
    "webview_url": ["WebView.loadUrl", "Uri", "Intent"],
    "preferences": ["SharedPreferences", "SharedPreferences.Editor"],
    "native_engine": ["libunity.so", "libil2cpp.so", "UnityPlayer"],
    "asset_loading": ["AssetManager", "StreamingAssets", "assets/bin/Data"],
    "rendering": ["SurfaceView", "GLSurfaceView", "UnityPlayer"],
    "network": ["URLConnection", "OkHttp", "UnityWebRequest"],
    "permissions": ["requestPermissions", "checkSelfPermission"],
    "intent_routing": ["Intent", "Uri", "startActivity"],
    "ipc": ["Binder", "ContentProvider", "Intent"],
    "android_ui_runtime": ["Activity", "Fragment"],
    "managed_runtime": ["MonoRuntime", "assemblies"],
    "native_binding": ["JNI", "NativeLibrary"],
}

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
    art = load(target / "runtime_artifact_layer.json")
    ev2 = load(target / "semantic_evidence_graph_v2.json")

    stories = []

    # Preserve strong concrete stories from v2
    for s in ev2.get("stories", []):
        if s.get("confidence_label") in ("very_high", "high"):
            stories.append(s)

    for a in art.get("runtime_artifacts", []):
        providers = ARTIFACT_TO_PROVIDER.get(a["artifact_kind"], [])
        for provider in providers:
            for sink in PROVIDER_TO_SINK.get(provider, [])[:3]:
                score = round(a["confidence_score"] * 0.88, 4)
                stories.append({
                    "story_id": f"STORY-{sid(target, a['runtime_family'], a['artifact_kind'], provider, sink)}",
                    "status": "candidate_only_not_vulnerability",
                    "causal_path": [
                        {
                            "kind": "RuntimeFamily",
                            "name": a["runtime_family"],
                            "role": "detected_runtime_family"
                        },
                        {
                            "kind": "RuntimeArtifact",
                            "name": a["name"],
                            "artifact_kind": a["artifact_kind"],
                            "role": "runtime_artifact",
                            "confidence_score": a["confidence_score"],
                            "confidence_label": a["confidence_label"],
                        },
                        {
                            "kind": "RuntimeCapabilityProvider",
                            "name": f"{a['runtime_family']}:{provider}",
                            "role": "capability_provider_from_artifact",
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
                    "capability_family": provider,
                    "sink_candidate": sink,
                    "confidence_score": score,
                    "confidence_label": label(score),
                    "why_this_chain_exists": [
                        f"Runtime family {a['runtime_family']} detected by exclusive evidence.",
                        f"Runtime artifact {a['artifact_kind']} observed.",
                        f"Artifact maps to provider {provider}, which maps to sink candidate {sink}."
                    ],
                    "validation": {
                        "status": "candidate_only_not_vulnerability",
                        "reachability_state": "unknown",
                        "dynamic_validation_state": "pending",
                        "requires": [
                            "artifact-to-provider confirmation",
                            "entrypoint correlation",
                            "source-to-sink path proof",
                            "dynamic validation"
                        ]
                    }
                })

    dedup = {}
    for s in stories:
        key = (
            tuple((x["kind"], x["name"]) for x in s["causal_path"][:4]),
            s["capability_family"],
            s["sink_candidate"]
        )
        if key not in dedup or s["confidence_score"] > dedup[key]["confidence_score"]:
            dedup[key] = s

    stories = sorted(
        dedup.values(),
        key=lambda s: (
            {"very_high": 5, "high": 4, "medium": 3, "low": 2, "very_low": 1}.get(s["confidence_label"], 0),
            s["confidence_score"]
        ),
        reverse=True
    )

    out = {
        "target": str(target),
        "model": "semantic_evidence_graph_v4_artifact_causal",
        "stories": stories[:160],
        "summary": {
            "stories": len(stories[:160]),
            "stories_by_confidence": {
                lab: sum(1 for s in stories[:160] if s["confidence_label"] == lab)
                for lab in ["very_high", "high", "medium", "low", "very_low"]
            },
            "capability_families": sorted(set(s["capability_family"] for s in stories[:160])),
            "source_kinds": sorted(set(s["causal_path"][0]["kind"] for s in stories[:160])),
            "artifact_kinds": sorted(set(
                x.get("artifact_kind")
                for s in stories[:160]
                for x in s["causal_path"]
                if x["kind"] == "RuntimeArtifact"
            )),
        }
    }

    path = target / "semantic_evidence_graph_v4.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m evidence_graph.build_evidence_graph_v4 output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
