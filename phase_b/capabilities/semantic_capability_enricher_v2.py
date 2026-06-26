#!/usr/bin/env python3
import json
import sys
import hashlib
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sid(prefix, *parts):
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}-{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


def entities_by_type(payload, t):
    return [
        e for e in payload.get("entities", [])
        if isinstance(e, dict) and e.get("type") == t
    ]


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.capabilities.semantic_capability_enricher_v2 <semantic_entities.json> <semantic_capabilities.json> <output.json>")
        sys.exit(1)

    semantic = load(sys.argv[1])
    caps = load(sys.argv[2])

    caps.setdefault("capabilities", [])
    caps.setdefault("capability_objects", [])

    existing = set()
    for c in caps.get("capabilities", []):
        if isinstance(c, dict):
            existing.add(c.get("capability_id") or c.get("id") or json.dumps(c, sort_keys=True))

    added = []

    for ent in entities_by_type(semantic, "CapabilityHintEntity"):
        payload = ent.get("payload", {})
        capability = payload.get("capability") or ent.get("name")
        rid = ent.get("research_object_id")

        cap = {
            "capability_id": sid("CAPV2", rid, capability),
            "type": "ResearchObjectCapabilityCandidate",
            "name": capability,
            "research_object_id": rid,
            "source": "semantic_capability_enricher_v2",
            "candidate_only": True,
            "requires_proof": True,
            "verification_state": "unverified",
            "derived_from_entity": ent.get("entity_id") or ent.get("id"),
        }

        if cap["capability_id"] not in existing:
            caps["capabilities"].append(cap)
            added.append(cap)
            existing.add(cap["capability_id"])

    caps["schema"] = "vulnlab.semantic_capabilities.v2_enriched"
    caps["v2_summary"] = {
        "added_research_object_capabilities": len(added),
        "total_capabilities": len(caps.get("capabilities", [])),
    }

    save(sys.argv[3], caps)

    print(json.dumps({
        "status": "ok",
        "added_research_object_capabilities": len(added),
        "total_capabilities": len(caps.get("capabilities", [])),
        "output": sys.argv[3],
    }, indent=2))


if __name__ == "__main__":
    main()
