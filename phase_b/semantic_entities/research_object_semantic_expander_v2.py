#!/usr/bin/env python3
import json
import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(str(p) for p in parts)
    return f"{prefix}-{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


def get_research_objects(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("research_objects", "objects", "items"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
    return []


def get_entities_payload(data: Any) -> Dict[str, Any]:
    if isinstance(data, dict):
        data.setdefault("entities", [])
        data.setdefault("edges", [])
        return data
    return {"schema": "vulnlab.semantic_entities.v2", "entities": [], "edges": []}


def ro_id(ro: Dict[str, Any]) -> str:
    return (
        ro.get("research_object_id")
        or ro.get("object_id")
        or ro.get("id")
        or ro.get("title")
        or stable_id("RO", json.dumps(ro, sort_keys=True))
    )


def make_entity(entity_type: str, research_object_id: str, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    eid = stable_id(entity_type, research_object_id, name, json.dumps(payload, sort_keys=True))
    return {
        "entity_id": eid,
        "id": eid,
        "type": entity_type,
        "name": name,
        "research_object_id": research_object_id,
        "source": "research_object_semantic_expander_v2",
        "payload": payload,
    }


def make_edge(src: str, dst: str, edge_type: str, research_object_id: str) -> Dict[str, Any]:
    eid = stable_id("EDGE", src, dst, edge_type, research_object_id)
    return {
        "edge_id": eid,
        "id": eid,
        "type": edge_type,
        "source": src,
        "target": dst,
        "research_object_id": research_object_id,
    }


def expand(research_objects_path: Path, semantic_entities_path: Path, output_path: Path):
    ro_payload = load_json(research_objects_path)
    sem_payload = get_entities_payload(load_json(semantic_entities_path))

    research_objects = get_research_objects(ro_payload)

    entities = sem_payload.setdefault("entities", [])
    edges = sem_payload.setdefault("edges", [])

    existing_ids = set()
    for e in entities:
        if isinstance(e, dict):
            existing_ids.add(e.get("entity_id") or e.get("id"))

    added_entities = []
    added_edges = []

    for ro in research_objects:
        rid = ro_id(ro)

        root = make_entity(
            "ResearchObjectEntity",
            rid,
            ro.get("title") or rid,
            {
                "object_type": ro.get("type") or ro.get("object_type"),
                "status": ro.get("status"),
                "confidence": ro.get("confidence"),
                "paradigm": ro.get("paradigm") or ro.get("runtime_family"),
                "source_file": ro.get("_source_file"),
            },
        )

        if root["entity_id"] not in existing_ids:
            entities.append(root)
            added_entities.append(root)
            existing_ids.add(root["entity_id"])

        root_id = root["entity_id"]

        for cap in ro.get("capability_hints", []) or []:
            ent = make_entity(
                "CapabilityHintEntity",
                rid,
                str(cap),
                {
                    "capability": cap,
                    "candidate_only": True,
                    "requires_proof": True,
                },
            )
            if ent["entity_id"] not in existing_ids:
                entities.append(ent)
                added_entities.append(ent)
                existing_ids.add(ent["entity_id"])
            added_edges.append(make_edge(root_id, ent["entity_id"], "HAS_CAPABILITY_HINT", rid))

        for effect in ro.get("security_effect_hints", []) or []:
            ent = make_entity(
                "SecurityEffectHintEntity",
                rid,
                str(effect),
                {
                    "security_effect": effect,
                    "candidate_only": True,
                    "finding_allowed": False,
                    "requires_causal_reachability": True,
                    "requires_dynamic_validation": True,
                },
            )
            if ent["entity_id"] not in existing_ids:
                entities.append(ent)
                added_entities.append(ent)
                existing_ids.add(ent["entity_id"])
            added_edges.append(make_edge(root_id, ent["entity_id"], "HAS_SECURITY_EFFECT_HINT", rid))

        for req in ro.get("proof_requirements", []) or []:
            ent = make_entity(
                "ProofRequirementEntity",
                rid,
                str(req),
                {
                    "proof_requirement": req,
                    "mandatory_before_finding": True,
                },
            )
            if ent["entity_id"] not in existing_ids:
                entities.append(ent)
                added_entities.append(ent)
                existing_ids.add(ent["entity_id"])
            added_edges.append(make_edge(root_id, ent["entity_id"], "REQUIRES_PROOF", rid))

        for unknown in ro.get("unknowns", []) or []:
            ent = make_entity(
                "UnknownEntity",
                rid,
                str(unknown),
                {
                    "unknown": unknown,
                    "resolution_required": True,
                },
            )
            if ent["entity_id"] not in existing_ids:
                entities.append(ent)
                added_entities.append(ent)
                existing_ids.add(ent["entity_id"])
            added_edges.append(make_edge(root_id, ent["entity_id"], "HAS_UNKNOWN", rid))

        policy = ro.get("finding_policy")
        if isinstance(policy, dict):
            ent = make_entity(
                "FindingPolicyEntity",
                rid,
                "finding_policy",
                {
                    "may_declare_vulnerability": bool(policy.get("may_declare_vulnerability")),
                    "reason": policy.get("reason"),
                    "candidate_only_guardrail": not bool(policy.get("may_declare_vulnerability")),
                },
            )
            if ent["entity_id"] not in existing_ids:
                entities.append(ent)
                added_entities.append(ent)
                existing_ids.add(ent["entity_id"])
            added_edges.append(make_edge(root_id, ent["entity_id"], "GOVERNED_BY_FINDING_POLICY", rid))

    edge_ids = set()
    dedup_edges = []
    for edge in edges + added_edges:
        eid = edge.get("edge_id") or edge.get("id")
        if eid in edge_ids:
            continue
        edge_ids.add(eid)
        dedup_edges.append(edge)

    sem_payload["edges"] = dedup_edges
    sem_payload["schema"] = "vulnlab.semantic_entities.v2_expanded"
    sem_payload["expander_v2_summary"] = {
        "research_objects": len(research_objects),
        "added_entities": len(added_entities),
        "added_edges": len(added_edges),
        "total_entities": len(sem_payload["entities"]),
        "total_edges": len(sem_payload["edges"]),
    }

    save_json(output_path, sem_payload)

    print(json.dumps({
        "status": "ok",
        "schema": sem_payload["schema"],
        **sem_payload["expander_v2_summary"],
        "output": str(output_path),
    }, indent=2))


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.semantic_entities.research_object_semantic_expander_v2 <research_objects.json> <semantic_entities.json> <output.json>")
        sys.exit(1)

    expand(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))


if __name__ == "__main__":
    main()
