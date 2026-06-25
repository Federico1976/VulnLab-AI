#!/usr/bin/env python3
import json, re, sys
from pathlib import Path

BUILTIN_RE = re.compile(r"^flutter/[a-z0-9_./-]+$")
PIGEON_RE = re.compile(r"[./0-9]*dev\.flutter\.pigeon\.([A-Za-z0-9_.]+)\.([A-Za-z0-9_]+)")
PLUGIN_CLASS_RE = re.compile(r"([A-Za-z0-9_.]+Plugin)")
PROVIDER_RE = re.compile(r"([A-Za-z0-9_.]+FileProvider)")

def clean(v):
    v = v.strip()
    v = re.sub(r'^[^A-Za-z0-9_.]+', '', v)
    v = re.sub(r'\s+', ' ', v)
    return v

def capability_from_text(v):
    l = v.lower()
    caps = set()
    if any(x in l for x in ["pathprovider", "path_provider", "file", "storage", "cache", "external"]):
        caps.add("file_storage")
    if any(x in l for x in ["sharedpreferences", "shared_preferences", "preferences"]):
        caps.add("preferences")
    if any(x in l for x in ["imagepicker", "image_picker", "camera", "gallery", "photo", "video", "cropper", "ucrop"]):
        caps.add("media_camera")
    if any(x in l for x in ["permission", "permissions"]):
        caps.add("permissions")
    if any(x in l for x in ["url", "uri", "webview", "http"]):
        caps.add("webview_url")
    return sorted(caps)

def classify_one(a):
    raw = a["value"]
    v = clean(raw)

    if BUILTIN_RE.match(v):
        return "builtin_channels", {
            "kind": "BuiltInFlutterChannel",
            "name": v,
            "source": a,
            "capability_families": capability_from_text(v),
            "confidence": "high",
        }

    pm = PIGEON_RE.search(v)
    if pm:
        api, method = pm.group(1), pm.group(2)
        return "pigeon_rpc", {
            "kind": "PigeonRPC",
            "api": api,
            "method": method,
            "name": f"{api}.{method}",
            "source": a,
            "capability_families": capability_from_text(v),
            "confidence": a.get("confidence", "medium"),
        }

    if "Error registering plugin" in v:
        cls = PLUGIN_CLASS_RE.findall(v)
        plugin = cls[-1] if cls else v
        return "plugin_registrations", {
            "kind": "PluginRegistration",
            "plugin": plugin,
            "name": plugin,
            "source": a,
            "capability_families": capability_from_text(v),
            "confidence": "high",
        }

    prov = PROVIDER_RE.search(v)
    if prov:
        return "native_capabilities", {
            "kind": "NativeCapabilityProvider",
            "provider": prov.group(1),
            "name": prov.group(1),
            "source": a,
            "capability_families": capability_from_text(v),
            "confidence": "medium",
        }

    plugin_cls = PLUGIN_CLASS_RE.search(v)
    if plugin_cls and "io.flutter" in v:
        return "native_capabilities", {
            "kind": "NativePluginClass",
            "plugin": plugin_cls.group(1),
            "name": plugin_cls.group(1),
            "source": a,
            "capability_families": capability_from_text(v),
            "confidence": "medium",
        }

    if a.get("capability_families"):
        return "native_capabilities", {
            "kind": "RuntimeCapabilitySignal",
            "name": v,
            "source": a,
            "capability_families": a.get("capability_families", []),
            "confidence": a.get("confidence", "low"),
        }

    return "noise", {
        "kind": "NoiseOrLowValueRuntimeString",
        "name": v,
        "source": a,
        "confidence": a.get("confidence", "low"),
    }

def dedupe(items, key):
    out = {}
    for i in items:
        k = i.get(key) or i.get("name")
        if k not in out:
            out[k] = i
    return list(out.values())

def classify(target_dir):
    target = Path(target_dir).resolve()
    art_path = target / "universal_runtime_artifacts.json"
    data = json.loads(art_path.read_text())

    result = {
        "target": str(target),
        "builtin_channels": [],
        "plugin_channels": [],
        "pigeon_rpc": [],
        "plugin_registrations": [],
        "native_capabilities": [],
        "noise": [],
    }

    for a in data.get("artifacts", []):
        bucket, obj = classify_one(a)
        result[bucket].append(obj)

    result["builtin_channels"] = dedupe(result["builtin_channels"], "name")
    result["pigeon_rpc"] = dedupe(result["pigeon_rpc"], "name")
    result["plugin_registrations"] = dedupe(result["plugin_registrations"], "name")
    result["native_capabilities"] = dedupe(result["native_capabilities"], "name")

    result["summary"] = {
        "builtin_channels": len(result["builtin_channels"]),
        "plugin_channels": len(result["plugin_channels"]),
        "pigeon_rpc": len(result["pigeon_rpc"]),
        "plugin_registrations": len(result["plugin_registrations"]),
        "native_capabilities": len(result["native_capabilities"]),
        "noise": len(result["noise"]),
        "capability_families": sorted(set(
            fam
            for bucket in ["pigeon_rpc", "plugin_registrations", "native_capabilities"]
            for x in result[bucket]
            for fam in x.get("capability_families", [])
        )),
    }

    out = target / "runtime_artifact_classification.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"[+] wrote {out}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m runtime_graph.runtime_artifact_classifier output/<target_dir>")
        sys.exit(1)
    classify(sys.argv[1])
