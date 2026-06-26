#!/usr/bin/env python3
import json
import sys
import hashlib
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sid(prefix, *parts):
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}-{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


def classify_effect(name):
    n = str(name).lower()

    if "deeplink" in n or "uri" in n or "intent" in n:
        return "ExternalUriEntrypointSecurityEffect"
    if "file" in n or "storage" in n or "content" in n:
        return "FileOrContentUriAccessSecurityEffect"
    if "network" in n or "upload" in n or "http" in n:
        return "NetworkReachableSecurityEffect"
    if "compose" in n or "ui" in n or "navigation" in n:
        return "UIReachableOperationSecurityEffect"
    if "coroutine" in n or "async" in n:
        return "AsyncFlowSecurityEffect"

    return "GenericCandidateSecurityEffect"


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.security_effects.security_effect_inference_v2 <capability_graphs.json> <existing_effects.json> <output.json>")
        sys.exit(1)

    graphs_payload = load(sys.argv[1])
    existing_payload = load(sys.argv[2])

    graphs = graphs_payload.get("graphs") or []

    effects = []

    for g in graphs:
        if not isinstance(g, dict):
            continue

        rid = g.get("research_object_id")
        cap_id = g.get("capability_id")
        nodes = g.get("nodes") or []

        cap_nodes = [n for n in nodes if isinstance(n, dict) and n.get("type") == "CapabilityNode"]

        for n in cap_nodes:
            name = n.get("name") or n.get("capability_type") or cap_id
            effect_type = classify_effect(name)

            effects.append({
                "security_effect_id": sid("SEV2", rid, cap_id, name),
                "type": effect_type,
                "research_object_id": rid,
                "capability_id": cap_id,
                "name": name,
                "candidate_only": True,
                "may_declare_vulnerability": False,
                "requires_causal_reachability": True,
                "requires_dynamic_validation": True,
                "source": "security_effect_inference_v2",
                "evidence_state": "candidate_security_effect_from_capability_graph",
                "reason": "Security effect inferred from capability graph. Requires proof and dynamic validation.",
            })

    out = {
        "schema": "vulnlab.security_effects.v2",
        "effects": effects,
        "summary": {
            "effects": len(effects),
            "previous_schema": existing_payload.get("schema") if isinstance(existing_payload, dict) else None,
        },
    }

    save(sys.argv[3], out)

    print(json.dumps({
        "status": "ok",
        "effects": len(effects),
        "output": sys.argv[3],
    }, indent=2))


if __name__ == "__main__":
    main()
