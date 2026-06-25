#!/usr/bin/env python3
import json, sys, re
from pathlib import Path

HYBRID_MARKERS = [
    "cordova.js",
    "capacitor.config",
    "cordova_plugins.js",
    "Capacitor.Plugins",
    "cordova.exec",
    "PluginManager",
    "CordovaPlugin",
    "BridgeActivity",
    "CapacitorWebView",
]

PLUGIN_HINTS = {
    "webview_url": ["InAppBrowser", "Browser", "loadUrl", "openUrl", "window.open", "http", "https"],
    "file_storage": ["File", "Filesystem", "FileTransfer", "ContentResolver", "Uri", "external"],
    "preferences": ["Preferences", "Storage", "SharedPreferences"],
    "media_camera": ["Camera", "ImagePicker", "Media", "Photo", "Gallery"],
    "permissions": ["Permissions", "requestPermissions", "checkSelfPermission"],
    "crypto": ["Crypto", "Cipher", "MessageDigest"],
}

def read(p):
    try:
        return p.read_text(errors="ignore")
    except Exception:
        return ""

def iter_files(root):
    for ext in ("*.java", "*.kt", "*.smali", "*.js", "*.json", "*.html", "*.xml"):
        yield from root.rglob(ext)

def find_workspace(target):
    for c in [
        target / "code" / "decompiled",
        target / "code" / "decompiled" / "sources",
        target / "decompiled",
        target,
    ]:
        if c.exists():
            return c
    return target

def classify_file(txt):
    markers = [m for m in HYBRID_MARKERS if m in txt]
    caps = []
    for cap, hints in PLUGIN_HINTS.items():
        if any(h in txt for h in hints):
            caps.append(cap)
    return markers, sorted(set(caps))

def build(target_dir):
    target = Path(target_dir).resolve()
    workspace = find_workspace(target)

    objects = []

    for f in iter_files(workspace):
        txt = read(f)
        if not txt:
            continue

        markers, caps = classify_file(txt)
        if not markers or not caps:
            continue

        rel = str(f.relative_to(workspace))

        if "cordova.exec" in txt or "CordovaPlugin" in txt:
            kind = "CordovaPluginBridge"
            confidence = "high"
        elif "Capacitor" in txt or "BridgeActivity" in txt:
            kind = "CapacitorPluginBridge"
            confidence = "high"
        else:
            kind = "HybridWebRuntimeBridge"
            confidence = "medium"

        name = rel
        m = re.search(r'class\s+([A-Za-z0-9_]+)', txt)
        if m:
            name = m.group(1)

        objects.append({
            "kind": kind,
            "bridge": "hybrid_web_runtime_bridge",
            "name": name,
            "file": rel,
            "capability_families": caps,
            "confidence": confidence,
            "evidence": {
                "markers": markers,
                "snippet": txt[:500]
            },
            "status": "semantic_bridge_candidate_not_vulnerability"
        })

    dedup = {}
    for o in objects:
        dedup[(o["kind"], o["name"], o["file"])] = o

    out = {
        "target": str(target),
        "hybrid_bridge_objects": list(dedup.values()),
        "summary": {
            "hybrid_bridge_objects": len(dedup),
            "kinds": sorted(set(o["kind"] for o in dedup.values())),
            "capability_families": sorted(set(c for o in dedup.values() for c in o["capability_families"])),
        }
    }

    path = target / "hybrid_web_runtime_bridges.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m semantic_bridges.hybrid_web_runtime_bridge output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
