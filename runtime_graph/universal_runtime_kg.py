#!/usr/bin/env python3
import json, re, sys, subprocess
from pathlib import Path

RUNTIME_PATTERNS = {
    "flutter_activity": ["FlutterActivity", "FlutterFragmentActivity"],
    "flutter_engine": ["FlutterEngine"],
    "dart_executor": ["DartExecutor"],
    "binary_messenger": ["BinaryMessenger"],
    "method_channel": ["MethodChannel", "Lio/flutter/plugin/common/MethodChannel;"],
    "event_channel": ["EventChannel", "Lio/flutter/plugin/common/EventChannel;"],
    "basic_message_channel": ["BasicMessageChannel", "Lio/flutter/plugin/common/BasicMessageChannel;"],
    "generated_plugin_registrant": ["GeneratedPluginRegistrant"],
    "react_native": ["ReactActivity", "ReactApplication", "ReactNativeHost", "ReactPackage"],
    "webview": ["WebView", "loadUrl", "shouldOverrideUrlLoading"],
}

SINKS = [
    "getSystemService", "startActivity", "openConnection",
    "FileInputStream", "FileOutputStream", "SharedPreferences",
    "ContentResolver", "getExternalStorage", "requestPermissions",
    "checkSelfPermission", "Cipher", "MessageDigest",
    "SQLiteDatabase", "WebView", "loadUrl"
]

CHANNEL_HINTS = [
    "flutter", "plugins", "plugin", "channel",
    "method", "event", "binary",
    "firebase", "maps", "camera", "location",
    "path_provider", "shared_preferences", "url_launcher",
    "webview", "connectivity", "package_info", "device_info",
    "permission", "file", "storage", "secure"
]

TEXT_EXTS = ("*.java", "*.kt", "*.smali", "*.xml")
BIN_EXTS = ("*.so", "*.arsc", "*.dex", "*.dat", "*.bin", "*.json", "*.txt")

CTOR_RE = re.compile(r'(MethodChannel|EventChannel|BasicMessageChannel)\s*\([^,\n]+,\s*"([^"]+)"')
SMALI_STRING_RE = re.compile(r'const-string(?:/jumbo)?\s+[vp]\d+,\s+"([^"]+)"')

def read_text(p):
    try:
        return p.read_text(errors="ignore")
    except Exception:
        return ""

def strings_of_file(p):
    try:
        r = subprocess.run(
            ["strings", "-a", "-n", "4", str(p)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
        return r.stdout.splitlines()
    except Exception:
        return []

def find_workspace(target):
    for c in [
        target / "decompiled",
        target / "jadx",
        target / "src",
        target / "sources",
        target,
    ]:
        if c.exists():
            return c
    return target

def iter_files(root, patterns):
    for pat in patterns:
        yield from root.rglob(pat)

def likely_channel_name(s):
    s = s.strip()
    if len(s) < 4 or len(s) > 180:
        return False
    if " " in s:
        return False
    if s.startswith(("http://", "https://", "Landroid/", "Ljava/", "Lkotlin/")):
        return False
    if "/" in s or "." in s:
        return any(h in s.lower() for h in CHANNEL_HINTS)
    return any(h in s.lower() for h in CHANNEL_HINTS)

def infer_channel_type(s):
    l = s.lower()
    if "event" in l:
        return "EventChannel"
    if "basic" in l or "message" in l:
        return "BasicMessageChannel"
    return "MethodChannel"

def build_runtime_kg(target_dir):
    target = Path(target_dir).resolve()
    workspace = find_workspace(target)

    graph = {
        "target": str(target),
        "workspace": str(workspace),
        "nodes": [],
        "edges": [],
        "channels": [],
        "summary": {},
    }

    node_seen = set()
    channel_seen = set()

    def add_node(kind, name, file, evidence):
        key = (kind, name, file)
        if key in node_seen:
            return
        node_seen.add(key)
        graph["nodes"].append({
            "kind": kind,
            "name": name,
            "file": file,
            "evidence": evidence[:240],
        })

    def add_edge(src_kind, src, dst_kind, dst, reason, file):
        graph["edges"].append({
            "from": {"kind": src_kind, "name": src},
            "to": {"kind": dst_kind, "name": dst},
            "reason": reason,
            "file": file,
        })

    def add_channel(ch_type, name, file, evidence, confidence):
        key = (ch_type, name, file)
        if key in channel_seen:
            return
        channel_seen.add(key)
        graph["channels"].append({
            "type": ch_type,
            "name": name,
            "file": file,
            "runtime_surface": "flutter",
            "confidence": confidence,
            "evidence": evidence[:240],
        })
        add_node("flutter_channel", name, file, evidence)
        add_edge("flutter_runtime", ch_type, "flutter_channel", name, confidence, file)

    for f in iter_files(workspace, TEXT_EXTS):
        txt = read_text(f)
        rel = str(f.relative_to(workspace))

        for kind, pats in RUNTIME_PATTERNS.items():
            for pat in pats:
                if pat in txt:
                    add_node(kind, pat, rel, pat)

        for m in CTOR_RE.finditer(txt):
            add_channel(m.group(1), m.group(2), rel, m.group(0), "high_ctor_text")

        if "Lio/flutter/plugin/common/" in txt:
            for s in SMALI_STRING_RE.findall(txt):
                if likely_channel_name(s):
                    add_channel(infer_channel_type(s), s, rel, s, "medium_smali_string")

        if "GeneratedPluginRegistrant" in txt:
            for cls in re.findall(r'([A-Za-z0-9_$.]+Plugin)', txt):
                add_node("flutter_plugin", cls, rel, "plugin registration")
                add_edge("flutter_registrant", "GeneratedPluginRegistrant", "flutter_plugin", cls, "registers plugin", rel)

        for sink in SINKS:
            if sink in txt:
                add_node("native_api_sink", sink, rel, sink)

    for f in iter_files(workspace, BIN_EXTS):
        rel = str(f.relative_to(workspace))
        ss = strings_of_file(f)

        joined = "\n".join(ss[:20000])
        for pat in ["Flutter", "Dart", "BinaryMessenger", "MethodChannel", "EventChannel", "BasicMessageChannel"]:
            if pat in joined:
                add_node("flutter_binary_runtime", pat, rel, pat)

        for s in ss:
            if likely_channel_name(s):
                add_channel(infer_channel_type(s), s, rel, s, "low_binary_string")

    channel_files = {c["file"] for c in graph["channels"]}
    for n in graph["nodes"]:
        if n["kind"] == "native_api_sink" and n["file"] in channel_files:
            for c in graph["channels"]:
                if c["file"] == n["file"]:
                    add_edge("flutter_channel", c["name"], "native_api_sink", n["name"], "same-file native capability candidate", n["file"])

    graph["summary"] = {
        "total_nodes": len(graph["nodes"]),
        "total_edges": len(graph["edges"]),
        "total_channels": len(graph["channels"]),
        "runtime_kinds": sorted(set(n["kind"] for n in graph["nodes"])),
        "channel_types": sorted(set(c["type"] for c in graph["channels"])),
        "channel_confidence": {
            k: sum(1 for c in graph["channels"] if c["confidence"] == k)
            for k in sorted(set(c["confidence"] for c in graph["channels"]))
        },
    }

    out = target / "universal_runtime_kg.json"
    out.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print(json.dumps(graph["summary"], indent=2))
    print(f"[+] wrote {out}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python3 -m runtime_graph.universal_runtime_kg output/<target_dir>")
        sys.exit(1)
    build_runtime_kg(sys.argv[1])
