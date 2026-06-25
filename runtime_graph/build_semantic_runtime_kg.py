#!/usr/bin/env python3
import json, sys
from pathlib import Path

SINK_BY_CAPABILITY = {
    "file_storage": ["java.io.File", "FileInputStream", "FileOutputStream", "ContentResolver", "FileProvider", "Uri"],
    "preferences": ["SharedPreferences", "SharedPreferences.Editor"],
    "media_camera": ["Camera", "MediaStore", "FileProvider", "ContentResolver", "Uri"],
    "permissions": ["requestPermissions", "checkSelfPermission", "onRequestPermissionsResult"],
    "webview_url": ["Intent", "Uri", "WebView.loadUrl", "URLConnection"],
}

VALIDATION_BY_CAPABILITY = {
    "file_storage": [
        "Run app with controlled file/path inputs where reachable.",
        "Trace whether runtime API writes, reads, shares, or exposes files.",
        "Validate with app-private/external-storage boundary checks."
    ],
    "preferences": [
        "Identify preference keys and value sensitivity.",
        "Validate whether untrusted runtime input can modify security-relevant settings.",
        "Check backup/export/log exposure."
    ],
    "media_camera": [
        "Trigger image/video picker flow from UI or intent path.",
        "Observe FileProvider URI grants and temporary file lifecycle.",
        "Validate whether external URI/file inputs are accepted unsafely."
    ],
    "permissions": [
        "Trigger permission request flow.",
        "Validate permission result handling and fallback states.",
        "Check whether denied permissions still allow sensitive path continuation."
    ],
    "webview_url": [
        "Trigger URL/URI controlled flows.",
        "Validate scheme filtering and external intent handling.",
        "Check WebView/Intent sink behavior with benign controlled payloads."
    ],
}

def add_node(nodes, seen, kind, name, extra=None):
    key = (kind, name)
    if key in seen:
        return
    seen.add(key)
    obj = {"kind": kind, "name": name}
    if extra:
        obj.update(extra)
    nodes.append(obj)

def add_edge(edges, src_kind, src, dst_kind, dst, reason):
    edges.append({
        "from": {"kind": src_kind, "name": src},
        "to": {"kind": dst_kind, "name": dst},
        "reason": reason,
    })

def build(target_dir):
    target = Path(target_dir).resolve()
    cls = json.loads((target / "runtime_artifact_classification.json").read_text())

    kg = {
        "target": str(target),
        "nodes": [],
        "edges": [],
        "validation_plan_stubs": [],
    }
    seen = set()

    for ch in cls["builtin_channels"]:
        add_node(kg["nodes"], seen, "BuiltInFlutterChannel", ch["name"], {
            "confidence": ch["confidence"]
        })

    for rpc in cls["pigeon_rpc"]:
        add_node(kg["nodes"], seen, "PigeonRPC", rpc["name"], {
            "api": rpc["api"],
            "method": rpc["method"],
            "confidence": rpc["confidence"],
            "capability_families": rpc["capability_families"],
        })
        for cap in rpc["capability_families"]:
            add_node(kg["nodes"], seen, "CapabilityFamily", cap)
            add_edge(kg["edges"], "PigeonRPC", rpc["name"], "CapabilityFamily", cap, "rpc implies native capability")

    for pr in cls["plugin_registrations"]:
        add_node(kg["nodes"], seen, "PluginRegistration", pr["name"], {
            "confidence": pr["confidence"],
            "capability_families": pr["capability_families"],
        })
        for cap in pr["capability_families"]:
            add_node(kg["nodes"], seen, "CapabilityFamily", cap)
            add_edge(kg["edges"], "PluginRegistration", pr["name"], "CapabilityFamily", cap, "plugin implies native capability")

    for nc in cls["native_capabilities"]:
        add_node(kg["nodes"], seen, nc["kind"], nc["name"], {
            "confidence": nc["confidence"],
            "capability_families": nc.get("capability_families", []),
        })
        for cap in nc.get("capability_families", []):
            add_node(kg["nodes"], seen, "CapabilityFamily", cap)
            add_edge(kg["edges"], nc["kind"], nc["name"], "CapabilityFamily", cap, "artifact implies native capability")

    for cap, sinks in SINK_BY_CAPABILITY.items():
        if any(n["kind"] == "CapabilityFamily" and n["name"] == cap for n in kg["nodes"]):
            for sink in sinks:
                add_node(kg["nodes"], seen, "NativeSinkFamily", sink)
                add_edge(kg["edges"], "CapabilityFamily", cap, "NativeSinkFamily", sink, "capability maps to native sink family")

            kg["validation_plan_stubs"].append({
                "capability_family": cap,
                "status": "candidate_only_not_vulnerability",
                "requires": [
                    "entrypoint correlation",
                    "reachability proof",
                    "dynamic validation",
                    "exploitability reasoning"
                ],
                "steps": VALIDATION_BY_CAPABILITY.get(cap, []),
            })

    kg["summary"] = {
        "nodes": len(kg["nodes"]),
        "edges": len(kg["edges"]),
        "validation_plan_stubs": len(kg["validation_plan_stubs"]),
        "node_kinds": sorted(set(n["kind"] for n in kg["nodes"])),
        "capability_families": sorted(n["name"] for n in kg["nodes"] if n["kind"] == "CapabilityFamily"),
    }

    out = target / "semantic_runtime_kg.json"
    out.write_text(json.dumps(kg, indent=2), encoding="utf-8")
    print(json.dumps(kg["summary"], indent=2))
    print(f"[+] wrote {out}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m runtime_graph.build_semantic_runtime_kg output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
