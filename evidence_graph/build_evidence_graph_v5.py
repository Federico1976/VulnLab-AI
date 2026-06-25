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
    "AndroidComponent": ["intent_routing", "ipc"],
    "IntentRouter": ["intent_routing", "webview_url"],
    "ComposeRuntime": ["android_ui_runtime"],
    "KotlinRuntime": ["android_ui_runtime"],
    "ManagedRuntime": ["managed_runtime"],
    "NativeBinding": ["native_binding"],
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
    "intent_routing": ["Intent", "Uri", "startActivity"],
    "ipc": ["Binder", "ContentProvider", "Intent"],
    "android_ui_runtime": ["Activity", "Fragment"],
    "managed_runtime": ["MonoRuntime", "assemblies"],
    "native_binding": ["JNI", "NativeLibrary"],
}

ROLE_MULTIPLIER = {
    "primary_runtime": 1.00,
    "secondary_runtime": 0.86,
    "embedded_runtime": 0.78,
    "sdk_or_library_runtime": 0.62,
    "weak_or_blocked_runtime": 0.30,
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
    artifacts = load(target / "runtime_artifact_confidence.json")
    ev2 = load(target / "semantic_evidence_graph_v2.json")

    stories = []

    # Preserve concrete high stories from older pipeline.
    for s in ev2.get("stories", []):
        if s.get("confidence_label") in ("very_high", "high"):
            s = dict(s)
            s["graph_generation"] = "preserved_concrete_high_story"
            stories.append(s)

    for a in artifacts.get("runtime_artifacts", []):
        role = a.get("runtime_role", "unknown")
        if role == "weak_or_blocked_runtime":
            continue

        artifact_kind = a["artifact_kind"]
        runtime = a["runtime_family"]
        artifact_score = a.get("artifact_confidence_score", a.get("confidence_score", 0.5))
        role_mult = ROLE_MULTIPLIER.get(role, 0.45)

        for provider in ARTIFACT_TO_PROVIDER.get(artifact_kind, []):
            provider_score = 0.92 if role == "primary_runtime" else 0.76
            for sink in PROVIDER_TO_SINK.get(provider, [])[:3]:
                score = round(artifact_score * role_mult * provider_score, 4)

                stories.append({
                    "story_id": f"STORY-{sid(target, runtime, artifact_kind, provider, sink)}",
                    "status": "candidate_only_not_vulnerability",
                    "graph_generation": "artifact_confidence_causal_v5",
                    "causal_path": [
                        {
                            "kind": "RuntimeFamily",
                            "name": runtime,
                            "role": "detected_runtime_family",
                            "runtime_role": role,
                        },
                        {
                            "kind": "RuntimeArtifact",
                            "name": a["name"],
                            "artifact_kind": artifact_kind,
                            "role": "runtime_artifact",
                            "artifact_confidence_score": artifact_score,
                            "artifact_confidence_label": a.get("artifact_confidence_label"),
                            "markers": a.get("markers", []),
                        },
                        {
                            "kind": "RuntimeCapabilityProvider",
                            "name": f"{runtime}:{provider}",
                            "role": "capability_provider_from_artifact",
                            "provider_confidence_score": provider_score,
                        },
                        {
                            "kind": "SemanticObject",
                            "name": f"{runtime}:{artifact_kind}:{provider}",
                            "role": "semantic_runtime_object",
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
                    "confidence_formula": {
                        "artifact_confidence": artifact_score,
                        "runtime_role_multiplier": role_mult,
                        "provider_confidence": provider_score,
                    },
                    "why_this_chain_exists": [
                        f"{runtime} is classified as {role}.",
                        f"Runtime artifact {artifact_kind} was observed with artifact confidence {artifact_score}.",
                        f"{artifact_kind} supports provider {provider}.",
                        f"{provider} maps to sink candidate {sink}.",
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
        path = s.get("causal_path", [])
        key = (
            tuple((x.get("kind"), x.get("name")) for x in path[:5]),
            s.get("capability_family"),
            s.get("sink_candidate")
        )
        if key not in dedup or s.get("confidence_score", 0) > dedup[key].get("confidence_score", 0):
            dedup[key] = s

    ranked = sorted(
        dedup.values(),
        key=lambda s: (
            {"very_high": 5, "high": 4, "medium": 3, "low": 2, "very_low": 1}.get(s.get("confidence_label"), 0),
            s.get("confidence_score", 0)
        ),
        reverse=True
    )

    out = {
        "target": str(target),
        "model": "semantic_evidence_graph_v5_artifact_confidence_causal",
        "principle": "RuntimeFamily -> RuntimeArtifact -> Provider -> SemanticObject -> Sink -> Reachability -> Validation",
        "stories": ranked[:160],
        "summary": {
            "stories": len(ranked[:160]),
            "stories_by_confidence": {
                lab: sum(1 for s in ranked[:160] if s.get("confidence_label") == lab)
                for lab in ["very_high", "high", "medium", "low", "very_low"]
            },
            "capability_families": sorted(set(s["capability_family"] for s in ranked[:160])),
            "artifact_kinds": sorted(set(
                x.get("artifact_kind")
                for s in ranked[:160]
                for x in s.get("causal_path", [])
                if x.get("kind") == "RuntimeArtifact"
            )),
            "runtime_roles": sorted(set(
                x.get("runtime_role")
                for s in ranked[:160]
                for x in s.get("causal_path", [])
                if x.get("kind") == "RuntimeFamily" and x.get("runtime_role")
            )),
        }
    }

    path = target / "semantic_evidence_graph_v5.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m evidence_graph.build_evidence_graph_v5 output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
