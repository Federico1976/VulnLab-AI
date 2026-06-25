#!/usr/bin/env python3
import json, sys
from pathlib import Path

ONTOLOGY_LEVELS = [
    "Runtime",
    "BridgeObject",
    "CapabilityProvider",
    "SemanticObject",
    "NativeAPI",
    "Sink",
    "Reachability",
    "Validation",
    "Disclosure"
]

RUNTIME_KIND_MAP = {
    "PigeonRPC": "FlutterRuntime",
    "PluginRegistration": "FlutterRuntime",
    "CapacitorPluginBridge": "HybridWebRuntime",
    "CordovaPluginBridge": "HybridWebRuntime",
    "HybridWebRuntimeBridge": "HybridWebRuntime",
    "ReactNativeBridgeMethod": "ReactNativeRuntime",
    "ActivityIntentRoute": "AndroidRuntime",
    "WebViewDeepLinkRoute": "WebViewRuntime",
    "NativeCapabilityProvider": "NativeAndroidRuntime",
}

def load(p):
    p = Path(p)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def classify_runtime(kind):
    return RUNTIME_KIND_MAP.get(kind, "UnknownRuntime")

def build(target_dir):
    target = Path(target_dir).resolve()
    ev = load(target / "semantic_evidence_graph_v2.json")
    reach = load(target / "universal_reachability_v2.json")
    validation = load(target / "dynamic_validation_plans.json")
    disclosure = load(target / "responsible_disclosure_candidates.json")

    nodes = []
    edges = []
    seen = set()

    def add_node(kind, name, level, extra=None):
        key = (kind, name, level)
        if key in seen:
            return
        seen.add(key)
        obj = {"kind": kind, "name": name, "ontology_level": level}
        if extra:
            obj.update(extra)
        nodes.append(obj)

    def add_edge(a_kind, a_name, b_kind, b_name, reason):
        edges.append({
            "from": {"kind": a_kind, "name": a_name},
            "to": {"kind": b_kind, "name": b_name},
            "reason": reason
        })

    reach_by_story = {p["story_id"]: p for p in reach.get("paths", [])}
    val_by_story = {p["story_id"]: p for p in validation.get("plans", [])}

    for s in ev.get("stories", []):
        story_id = s["story_id"]
        src = s["causal_path"][0]
        src_kind = src["kind"]
        src_name = src["name"]
        runtime = classify_runtime(src_kind)
        cap = s["capability_family"]
        sink = s["sink_candidate"]

        add_node("Runtime", runtime, "Runtime")
        add_node(src_kind, src_name, "BridgeObject", {
            "story_id": story_id,
            "confidence_score": s.get("confidence_score"),
            "confidence_label": s.get("confidence_label"),
        })
        add_node("CapabilityProvider", cap, "CapabilityProvider")
        add_node("SemanticObject", f"{src_kind}:{src_name}", "SemanticObject")
        add_node("NativeAPI", sink, "NativeAPI")
        add_node("Sink", sink, "Sink")

        r = reach_by_story.get(story_id, {})
        reach_state = r.get("reachability_status", "unknown")
        add_node("Reachability", reach_state, "Reachability", {
            "reachable": r.get("reachable", False)
        })

        v = val_by_story.get(story_id, {})
        val_state = v.get("validation_status", "pending")
        add_node("Validation", val_state, "Validation")

        add_node("Disclosure", "candidate_only_not_ready", "Disclosure")

        add_edge("Runtime", runtime, src_kind, src_name, "runtime owns bridge object")
        add_edge(src_kind, src_name, "CapabilityProvider", cap, "bridge object implies capability provider")
        add_edge("CapabilityProvider", cap, "SemanticObject", f"{src_kind}:{src_name}", "capability contextualizes semantic object")
        add_edge("SemanticObject", f"{src_kind}:{src_name}", "NativeAPI", sink, "semantic object maps to native API candidate")
        add_edge("NativeAPI", sink, "Sink", sink, "native API acts as sink candidate")
        add_edge("Sink", sink, "Reachability", reach_state, "sink requires reachability decision")
        add_edge("Reachability", reach_state, "Validation", val_state, "reachability gates dynamic validation")
        add_edge("Validation", val_state, "Disclosure", "candidate_only_not_ready", "validation gates disclosure")

    out = {
        "target": str(target),
        "model": "universal_runtime_ontology_v1",
        "levels": ONTOLOGY_LEVELS,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "runtimes": sorted(set(n["name"] for n in nodes if n["kind"] == "Runtime")),
            "levels_present": sorted(set(n["ontology_level"] for n in nodes)),
        }
    }

    path = target / "universal_runtime_ontology.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m ontology.universal_runtime_ontology output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
