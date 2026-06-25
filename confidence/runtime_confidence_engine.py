#!/usr/bin/env python3
import json, sys
from pathlib import Path

BASE_CONF = {
    "high": 0.92,
    "medium": 0.70,
    "low": 0.38,
    "promoted_high": 0.88,
    "promoted_medium": 0.64,
    "low_binary_string": 0.25,
}

KIND_WEIGHT = {
    "BuiltInFlutterChannel": 0.95,
    "PigeonRPC": 0.92,
    "PluginRegistration": 0.90,
    "NativeCapabilityProvider": 0.82,
    "NativePluginClass": 0.78,
    "RuntimeCapabilitySignal": 0.46,
    "CapabilityFamily": 0.80,
    "NativeSinkFamily": 0.72,
}

EDGE_WEIGHT = {
    "rpc implies native capability": 0.92,
    "plugin implies native capability": 0.88,
    "artifact implies native capability": 0.58,
    "capability maps to native sink family": 0.74,
}

CAPABILITY_PRIOR = {
    "preferences": 0.86,
    "file_storage": 0.82,
    "media_camera": 0.80,
    "permissions": 0.78,
    "webview_url": 0.76,
    "crypto": 0.74,
}

def clamp(x):
    return max(0.01, min(0.99, round(float(x), 4)))

def node_key(n):
    return (n.get("kind"), n.get("name"))

def source_conf(n):
    c = n.get("confidence")
    if c in BASE_CONF:
        return BASE_CONF[c]
    return 0.55

def initial_node_conf(n):
    kind = n.get("kind")
    name = n.get("name")
    base = source_conf(n)
    weight = KIND_WEIGHT.get(kind, 0.55)

    score = base * weight

    if kind == "CapabilityFamily":
        score = CAPABILITY_PRIOR.get(name, 0.72)

    if kind == "NativeSinkFamily":
        score = 0.68

    if kind == "RuntimeCapabilitySignal":
        caps = n.get("capability_families", [])
        if not caps:
            score *= 0.65
        if len(str(name)) > 120:
            score *= 0.75

    return clamp(score)

def build_index(nodes):
    return {node_key(n): n for n in nodes}

def propagate(kg):
    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])

    conf = {node_key(n): initial_node_conf(n) for n in nodes}

    for _ in range(4):
        changed = False

        for e in edges:
            src = (e["from"]["kind"], e["from"]["name"])
            dst = (e["to"]["kind"], e["to"]["name"])
            reason = e.get("reason", "")

            if src not in conf or dst not in conf:
                continue

            edge_w = EDGE_WEIGHT.get(reason, 0.55)
            propagated = conf[src] * edge_w

            if propagated > conf[dst]:
                conf[dst] = clamp((conf[dst] * 0.45) + (propagated * 0.55))
                changed = True

        if not changed:
            break

    return conf

def label(score):
    if score >= 0.85:
        return "very_high"
    if score >= 0.70:
        return "high"
    if score >= 0.50:
        return "medium"
    if score >= 0.30:
        return "low"
    return "very_low"

def calibrate(target_dir):
    target = Path(target_dir).resolve()
    kg_path = target / "semantic_runtime_kg.json"
    kg = json.loads(kg_path.read_text())

    conf = propagate(kg)

    for n in kg.get("nodes", []):
        s = conf.get(node_key(n), initial_node_conf(n))
        n["confidence_score"] = s
        n["confidence_label"] = label(s)
        n["confidence_origin"] = {
            "base_kind_weight": KIND_WEIGHT.get(n.get("kind"), 0.55),
            "source_confidence": n.get("confidence", "implicit"),
        }

    for e in kg.get("edges", []):
        src = (e["from"]["kind"], e["from"]["name"])
        dst = (e["to"]["kind"], e["to"]["name"])
        w = EDGE_WEIGHT.get(e.get("reason", ""), 0.55)
        src_score = conf.get(src, 0.40)
        dst_score = conf.get(dst, 0.40)
        e["confidence_score"] = clamp(src_score * w * 0.6 + dst_score * 0.4)
        e["confidence_label"] = label(e["confidence_score"])
        e["confidence_origin"] = {
            "edge_weight": w,
            "source_node_score": src_score,
            "target_node_score": dst_score,
        }

    kg["confidence_summary"] = {
        "node_labels": {
            lab: sum(1 for n in kg.get("nodes", []) if n.get("confidence_label") == lab)
            for lab in ["very_high", "high", "medium", "low", "very_low"]
        },
        "edge_labels": {
            lab: sum(1 for e in kg.get("edges", []) if e.get("confidence_label") == lab)
            for lab in ["very_high", "high", "medium", "low", "very_low"]
        },
        "average_node_confidence": clamp(
            sum(n["confidence_score"] for n in kg.get("nodes", [])) / max(1, len(kg.get("nodes", [])))
        ),
        "average_edge_confidence": clamp(
            sum(e["confidence_score"] for e in kg.get("edges", [])) / max(1, len(kg.get("edges", [])))
        ),
    }

    out = target / "semantic_runtime_kg_confidence.json"
    out.write_text(json.dumps(kg, indent=2), encoding="utf-8")

    print(json.dumps(kg["confidence_summary"], indent=2))
    print(f"[+] wrote {out}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m confidence.runtime_confidence_engine output/<target_dir>")
        sys.exit(1)
    calibrate(sys.argv[1])
