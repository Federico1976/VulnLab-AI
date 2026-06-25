#!/usr/bin/env python3
import json, sys
from pathlib import Path

def promote(target_dir):
    target = Path(target_dir).resolve()
    kg_path = target / "universal_runtime_kg.json"
    art_path = target / "universal_runtime_artifacts.json"

    kg = json.loads(kg_path.read_text())
    arts = json.loads(art_path.read_text())

    existing = {(c.get("name"), c.get("file")) for c in kg.get("channels", [])}

    for a in arts["artifacts"]:
        if a["confidence"] not in ("high", "medium"):
            continue

        name = a["value"]
        file = a["file"]
        if (name, file) in existing:
            continue

        ch_type = "MethodChannel"
        if "event" in name.lower():
            ch_type = "EventChannel"
        elif "message" in name.lower():
            ch_type = "BasicMessageChannel"

        kg.setdefault("channels", []).append({
            "type": ch_type,
            "name": name,
            "file": file,
            "runtime_surface": "runtime_artifact",
            "confidence": f"promoted_{a['confidence']}",
            "score": a["score"],
            "capability_families": a["capability_families"],
            "evidence": a["raw"],
        })

        kg.setdefault("nodes", []).append({
            "kind": "runtime_artifact_channel",
            "name": name,
            "file": file,
            "evidence": a["raw"],
        })

        kg.setdefault("edges", []).append({
            "from": {"kind": "runtime_artifact", "name": file},
            "to": {"kind": "runtime_artifact_channel", "name": name},
            "reason": "promoted runtime artifact",
            "file": file,
        })

    kg["summary"] = {
        "total_nodes": len(kg.get("nodes", [])),
        "total_edges": len(kg.get("edges", [])),
        "total_channels": len(kg.get("channels", [])),
        "runtime_kinds": sorted(set(n.get("kind") for n in kg.get("nodes", []))),
        "channel_types": sorted(set(c.get("type") for c in kg.get("channels", []))),
        "channel_confidence": {
            k: sum(1 for c in kg.get("channels", []) if c.get("confidence") == k)
            for k in sorted(set(c.get("confidence") for c in kg.get("channels", [])))
        },
    }

    kg_path.write_text(json.dumps(kg, indent=2), encoding="utf-8")
    print(json.dumps(kg["summary"], indent=2))
    print(f"[+] promoted artifacts into {kg_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m runtime_graph.promote_runtime_artifacts_to_kg output/<target_dir>")
        sys.exit(1)
    promote(sys.argv[1])
