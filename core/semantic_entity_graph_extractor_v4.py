from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.semantic_entity_builder_v4 import (
    load_json,
    save_json,
    as_list,
    text_blob,
    detect_runtime,
    detect_framework_origin,
    infer_capabilities,
    infer_trust_boundaries,
    infer_related_assets,
    infer_related_sinks,
)
from core.semantic_entities_v4 import stable_id


def make_entity(
    ro: Dict[str, Any],
    ro_index: int,
    entity_type: str,
    name: str,
    runtime: str,
    framework: str,
    observations: List[Dict[str, Any]],
    confidence: float = 0.7,
) -> Dict[str, Any]:
    entity_id = stable_id(
        "UEG4",
        ro_index,
        entity_type,
        name,
        runtime,
        framework,
        ro.get("class"),
        ro.get("method"),
        ro.get("component"),
    )

    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "name": name,
        "source_runtime": runtime,
        "framework_origin": framework,
        "observations": observations,
        "inferred_capabilities": [],
        "trust_boundaries": [],
        "related_assets": [],
        "related_sinks": [],
        "confidence": confidence,
        "uncertainty_reasons": [],
        "counter_evidence": [],
        "source_artifacts": [
            {
                "kind": "research_object",
                "index": ro_index,
                "name": ro.get("name") or ro.get("id") or ro.get("research_object_id"),
            }
        ],
        "raw_ref": {
            "ro_index": ro_index,
            "ro_id": ro.get("id") or ro.get("research_object_id") or ro.get("object_id"),
        },
    }


def add_relation(
    relations: List[Dict[str, Any]],
    source: Dict[str, Any],
    target: Dict[str, Any],
    relation_type: str,
    reason: str,
    confidence: float = 0.7,
) -> None:
    relations.append({
        "relation_id": stable_id(
            "REL4",
            source["entity_id"],
            relation_type,
            target["entity_id"],
            reason,
        ),
        "source_entity_id": source["entity_id"],
        "target_entity_id": target["entity_id"],
        "relation_type": relation_type,
        "reason": reason,
        "confidence": confidence,
    })


def ro_name(ro: Dict[str, Any], index: int) -> str:
    return str(
        ro.get("name")
        or ro.get("title")
        or ro.get("id")
        or ro.get("research_object_id")
        or ro.get("object_id")
        or f"research_object_{index}"
    )


def has_any(blob: str, needles: List[str]) -> bool:
    return any(n in blob for n in needles)


def extract_entities_for_ro(ro: Dict[str, Any], index: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    blob = text_blob(ro)
    runtime = detect_runtime(ro)
    framework = detect_framework_origin(ro, runtime)
    base = ro_name(ro, index)

    entities: List[Dict[str, Any]] = []
    relations: List[Dict[str, Any]] = []

    runtime_entity = make_entity(
        ro, index, "RuntimeArtifactEntity",
        f"{base}:runtime:{runtime}",
        runtime,
        framework,
        [{"kind": "runtime_detection", "value": runtime}],
        confidence=0.75,
    )
    entities.append(runtime_entity)

    root = runtime_entity

    # Entrypoint
    if has_any(blob, ["activity", "intent-filter", "deeplink", "deep link", "route", "receiver", "service", "exported", "scheme", "host"]):
        e = make_entity(
            ro, index, "EntrypointEntity",
            f"{base}:entrypoint",
            runtime,
            framework,
            [{"kind": "entrypoint_signal", "value": "manifest_or_route_or_intent"}],
            confidence=0.75,
        )
        entities.append(e)
        add_relation(relations, root, e, "declares", "runtime artifact declares an entrypoint")

    # Bridge
    if has_any(blob, ["javascriptinterface", "reactmethod", "methodchannel", "bridge", "rnbridge", "flutterchannel", "capacitor", "cordova", "plugin"]):
        e = make_entity(
            ro, index, "BridgeEntity",
            f"{base}:bridge",
            runtime,
            framework,
            [{"kind": "bridge_signal", "value": "framework_or_native_bridge"}],
            confidence=0.8,
        )
        entities.append(e)
        add_relation(relations, root, e, "exposes_bridge", "runtime artifact exposes framework/native bridge")

    # Sink
    if has_any(blob, ["webview", "loadurl", "shouldoverrideurlloading", "evaluatejavascript", "addjavascriptinterface", "openfile", "exec", "query", "request", "socket", "http"]):
        e = make_entity(
            ro, index, "SinkEntity",
            f"{base}:sink",
            runtime,
            framework,
            [{"kind": "sink_signal", "value": "sensitive_operation_or_execution_point"}],
            confidence=0.78,
        )
        entities.append(e)
        add_relation(relations, root, e, "contains_sink", "runtime artifact contains or references a sink")

    # Assets
    assets = infer_related_assets(ro)
    for asset in assets:
        e = make_entity(
            ro, index, "AssetEntity",
            f"{base}:asset:{asset}",
            runtime,
            framework,
            [{"kind": "asset_signal", "value": asset}],
            confidence=0.72,
        )
        entities.append(e)
        add_relation(relations, root, e, "touches_asset", "runtime artifact touches asset")

    # Capabilities
    caps = infer_capabilities(ro)
    for cap in caps:
        e = make_entity(
            ro, index, "CapabilityEntity",
            f"{base}:capability:{cap}",
            runtime,
            framework,
            [{"kind": "capability_signal", "value": cap}],
            confidence=0.7,
        )
        e["inferred_capabilities"] = [cap]
        entities.append(e)
        add_relation(relations, root, e, "has_capability", "capability inferred from research object")

    # Trust boundaries
    boundaries = infer_trust_boundaries(ro)
    for boundary in boundaries:
        e = make_entity(
            ro, index, "TrustBoundaryEntity",
            f"{base}:boundary:{boundary}",
            runtime,
            framework,
            [{"kind": "trust_boundary_signal", "value": boundary}],
            confidence=0.7,
        )
        e["trust_boundaries"] = [boundary]
        entities.append(e)
        add_relation(relations, root, e, "crosses_boundary", "trust boundary inferred from research object")

    # Security controls / counter-evidence placeholders
    if has_any(blob, ["permission", "signature", "exported=false", "allowlist", "whitelist", "validate", "sanitize", "origin", "csrf", "auth"]):
        e = make_entity(
            ro, index, "SecurityControlEntity",
            f"{base}:security_control",
            runtime,
            framework,
            [{"kind": "control_signal", "value": "possible_security_control_or_constraint"}],
            confidence=0.55,
        )
        e["uncertainty_reasons"] = ["control_detected_but_not_validated"]
        entities.append(e)
        add_relation(relations, root, e, "may_be_constrained_by", "possible security control detected")

    # Propagation entity when there is boundary + sink/capability
    has_boundary = any(x["entity_type"] == "TrustBoundaryEntity" for x in entities)
    has_sink = any(x["entity_type"] == "SinkEntity" for x in entities)
    has_cap = any(x["entity_type"] == "CapabilityEntity" for x in entities)

    if has_boundary and (has_sink or has_cap):
        e = make_entity(
            ro, index, "PropagationEntity",
            f"{base}:propagation",
            runtime,
            framework,
            [{"kind": "propagation_inference", "value": "boundary_to_capability_or_sink_candidate"}],
            confidence=0.62,
        )
        e["uncertainty_reasons"] = ["propagation_is_inferred_not_proven"]
        entities.append(e)
        add_relation(relations, root, e, "suggests_propagation", "boundary and sink/capability co-occur")

    # Internal relations between extracted concepts
    by_type = {}
    for e in entities:
        by_type.setdefault(e["entity_type"], []).append(e)

    for b in by_type.get("BridgeEntity", []):
        for s in by_type.get("SinkEntity", []):
            add_relation(relations, b, s, "may_reach", "bridge and sink co-occur in same research object", 0.55)

    # Selective causal relations.
    # Evita prodotto cartesiano boundary x capability.
    causal_boundary_capability_rules = {
        "web_content_to_native": [
            "web_content_execution",
            "native_bridge_invocation",
            "network_access",
            "credential_or_token_handling",
        ],
        "framework_bridge_to_native": [
            "native_bridge_invocation",
            "local_file_access",
            "network_access",
            "credential_or_token_handling",
            "persistent_storage",
        ],
        "content_uri_boundary": [
            "local_file_access",
            "persistent_storage",
            "inter_process_communication",
        ],
        "external_app_to_app": [
            "inter_process_communication",
            "local_file_access",
            "credential_or_token_handling",
        ],
        "network_boundary": [
            "network_access",
            "credential_or_token_handling",
        ],
    }

    for tb in by_type.get("TrustBoundaryEntity", []):
        tb_values = tb.get("trust_boundaries", [])
        for cap in by_type.get("CapabilityEntity", []):
            cap_values = cap.get("inferred_capabilities", [])
            matched = False

            for tbv in tb_values:
                allowed_caps = causal_boundary_capability_rules.get(tbv, [])
                if any(cv in allowed_caps for cv in cap_values):
                    matched = True

            if matched:
                add_relation(
                    relations,
                    tb,
                    cap,
                    "enables_candidate_capability",
                    "boundary capability relation matches causal rule",
                    0.66,
                )

    causal_capability_sink_rules = {
        "web_content_execution": ["webview_load"],
        "native_bridge_invocation": ["webview_load", "file_open_or_share", "network_request"],
        "local_file_access": ["file_open_or_share"],
        "persistent_storage": ["database_query"],
        "network_access": ["network_request", "webview_load"],
        "credential_or_token_handling": ["network_request", "webview_load", "database_query"],
        "inter_process_communication": ["file_open_or_share", "webview_load"],
    }

    sink_values = infer_related_sinks(ro)

    for cap in by_type.get("CapabilityEntity", []):
        cap_values = cap.get("inferred_capabilities", [])
        for s in by_type.get("SinkEntity", []):
            matched = False

            for cv in cap_values:
                allowed_sinks = causal_capability_sink_rules.get(cv, [])
                if any(sv in allowed_sinks for sv in sink_values):
                    matched = True

            if matched:
                add_relation(
                    relations,
                    cap,
                    s,
                    "may_drive_sink",
                    "capability sink relation matches causal rule",
                    0.64,
                )

    return entities, relations


def dedupe_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = {}
    for e in entities:
        seen[e["entity_id"]] = e
    return list(seen.values())


def dedupe_relations(relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = {}
    for r in relations:
        seen[r["relation_id"]] = r
    return list(seen.values())


def build_graph(input_path: Path) -> Dict[str, Any]:
    data = load_json(input_path)
    ros = [x for x in as_list(data) if isinstance(x, dict)]

    entities: List[Dict[str, Any]] = []
    relations: List[Dict[str, Any]] = []

    for i, ro in enumerate(ros):
        es, rs = extract_entities_for_ro(ro, i)
        entities.extend(es)
        relations.extend(rs)

    entities = dedupe_entities(entities)
    relations = dedupe_relations(relations)

    by_type: Dict[str, int] = {}
    by_runtime: Dict[str, int] = {}
    by_relation: Dict[str, int] = {}

    for e in entities:
        by_type[e["entity_type"]] = by_type.get(e["entity_type"], 0) + 1
        by_runtime[e["source_runtime"]] = by_runtime.get(e["source_runtime"], 0) + 1

    for r in relations:
        by_relation[r["relation_type"]] = by_relation.get(r["relation_type"], 0) + 1

    return {
        "schema": "semantic_entity_graph_v4",
        "candidate_only": True,
        "finding_allowed": False,
        "input": str(input_path),
        "summary": {
            "research_objects": len(ros),
            "entities": len(entities),
            "relations": len(relations),
            "entities_per_research_object": round(len(entities) / max(len(ros), 1), 2),
            "relations_per_research_object": round(len(relations) / max(len(ros), 1), 2),
            "by_type": by_type,
            "by_runtime": by_runtime,
            "by_relation": by_relation,
        },
        "entities": entities,
        "relations": relations,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 -m core.semantic_entity_graph_extractor_v4 <merged_research_objects.json> <semantic_entity_graph_v4.json>")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2])

    graph = build_graph(inp)
    save_json(out, graph)

    print(json.dumps(graph["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
