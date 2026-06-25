#!/usr/bin/env python3
import json, sys, re
from pathlib import Path

BRIDGE_RULES = [
    {
        "bridge": "react_native_bridge",
        "patterns": ["ReactMethod", "ReactPackage", "ReactNativeHost", "NativeModule"],
        "semantic_kind": "ReactNativeBridgeMethod",
        "capabilities": {
            "file_storage": ["File", "FileInputStream", "FileOutputStream", "path", "uri"],
            "webview_url": ["url", "Uri", "Intent", "loadUrl"],
            "crypto": ["Cipher", "MessageDigest", "hash", "digest"],
            "preferences": ["SharedPreferences"],
        },
    },
    {
        "bridge": "webview_deeplink_bridge",
        "patterns": ["WebView", "loadUrl", "shouldOverrideUrlLoading", "Intent", "Uri", "deepLink"],
        "semantic_kind": "WebViewDeepLinkRoute",
        "capabilities": {
            "webview_url": ["loadUrl", "shouldOverrideUrlLoading", "Uri", "Intent", "http", "https"],
        },
    },
    {
        "bridge": "activity_intent_router_bridge",
        "patterns": ["getIntent", "Intent", "Bundle", "Uri", "startActivity"],
        "semantic_kind": "ActivityIntentRoute",
        "capabilities": {
            "webview_url": ["Uri", "Intent", "startActivity"],
            "file_storage": ["File", "ContentResolver", "Uri"],
        },
    },
]

def read(p):
    try:
        return p.read_text(errors="ignore")
    except Exception:
        return ""

def iter_sources(root):
    for ext in ("*.java", "*.kt", "*.smali", "*.xml"):
        yield from root.rglob(ext)

def find_workspace(target):
    for c in [target / "code" / "decompiled", target / "decompiled", target / "jadx", target / "sources", target]:
        if c.exists():
            return c
    return target

def extract_method_like(txt):
    m = re.search(r'(?:public|private|protected|fun|\.method)[^\n]{0,180}', txt)
    return m.group(0).strip() if m else None

def build(target_dir):
    target = Path(target_dir).resolve()
    workspace = find_workspace(target)

    objects = []

    for f in iter_sources(workspace):
        txt = read(f)
        rel = str(f.relative_to(workspace))

        for rule in BRIDGE_RULES:
            hits = [p for p in rule["patterns"] if p in txt]
            if len(hits) < 2:
                continue

            caps = []
            for cap, keys in rule["capabilities"].items():
                if any(k in txt for k in keys):
                    caps.append(cap)

            if not caps:
                continue

            objects.append({
                "kind": rule["semantic_kind"],
                "bridge": rule["bridge"],
                "name": extract_method_like(txt) or rel,
                "file": rel,
                "capability_families": sorted(set(caps)),
                "confidence": "medium" if len(hits) >= 3 else "low",
                "evidence": {
                    "matched_patterns": hits,
                    "snippet": txt[:500]
                },
                "status": "semantic_bridge_candidate_not_vulnerability"
            })

    dedup = {}
    for o in objects:
        key = (o["kind"], o["name"], o["file"])
        dedup[key] = o

    out = {
        "target": str(target),
        "bridge_objects": list(dedup.values()),
        "summary": {
            "bridge_objects": len(dedup),
            "bridges": sorted(set(o["bridge"] for o in dedup.values())),
            "capability_families": sorted(set(c for o in dedup.values() for c in o["capability_families"])),
        }
    }

    path = target / "universal_semantic_bridges.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m semantic_bridges.universal_semantic_bridge output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
