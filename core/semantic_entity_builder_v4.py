from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

from core.semantic_entities_v4 import UniversalEntity, stable_id


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def as_list(obj: Any) -> List[Any]:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("research_objects", "objects", "items", "results"):
            if isinstance(obj.get(key), list):
                return obj[key]
        return [obj]
    return []


def text_blob(ro: Dict[str, Any]) -> str:
    return json.dumps(ro, ensure_ascii=False).lower()


def detect_runtime(ro: Dict[str, Any]) -> str:
    blob = text_blob(ro)

    if "flutter" in blob or "dart" in blob:
        return "flutter"
    if "react native" in blob or "reactnative" in blob or "rnbridge" in blob:
        return "react_native"
    if "ionic" in blob or "cordova" in blob or "capacitor" in blob:
        return "ionic"
    if "webview" in blob:
        return "hybrid_webview"
    if "xamarin" in blob:
        return "xamarin"
    if "compose" in blob or "jetpack" in blob:
        return "android_compose"
    if "intent" in blob or "activity" in blob or "provider" in blob or "service" in blob:
        return "android_native"

    return "unknown"


def detect_framework_origin(ro: Dict[str, Any], runtime: str) -> str:
    blob = text_blob(ro)

    markers = [
        "flutter",
        "dart",
        "react_native",
        "reactnative",
        "rn",
        "ionic",
        "cordova",
        "capacitor",
        "webview",
        "compose",
        "fileprovider",
        "contentprovider",
        "deeplink",
        "intent",
        "httpserver",
        "ktor",
        "okhttp",
    ]

    found = [m for m in markers if m in blob]
    if found:
        return ",".join(sorted(set(found))[:5])

    return runtime


def infer_entity_type(ro: Dict[str, Any]) -> str:
    blob = text_blob(ro)

    # Ordine intenzionale:
    # prima i concetti più specifici, poi gli entrypoint generici.

    if any(x in blob for x in [
        "javascriptinterface",
        "reactmethod",
        "methodchannel",
        "bridge",
        "rnbridge",
        "flutterchannel",
        "capacitor plugin",
        "cordova plugin",
    ]):
        return "BridgeEntity"

    if any(x in blob for x in [
        "webview",
        "loadurl",
        "shouldoverrideurlloading",
        "evaluatejavascript",
        "addjavascriptinterface",
    ]):
        return "SinkEntity"

    if any(x in blob for x in [
        "fileprovider",
        "contentprovider",
        "content://",
        "openfile",
        "asset",
        "res/raw",
        "external files",
        "cache",
    ]):
        return "AssetEntity"

    if any(x in blob for x in [
        "sharedpreferences",
        "sqlite",
        "database",
        "room",
        "datastore",
        "keystore",
        "storage",
    ]):
        return "StorageEntity"

    if any(x in blob for x in [
        "auth",
        "token",
        "jwt",
        "oauth",
        "login",
        "session",
        "credential",
    ]):
        return "AuthEntity"

    if any(x in blob for x in [
        "permission",
        "exported=true",
        "external",
        "ipc",
        "boundary",
        "untrusted",
    ]):
        return "TrustBoundaryEntity"

    if any(x in blob for x in [
        "activity",
        "intent-filter",
        "deeplink",
        "deep link",
        "route",
        "receiver",
        "service",
        "exported",
        "scheme",
        "host",
    ]):
        return "EntrypointEntity"

    if any(x in blob for x in [
        "sink",
        "exec",
        "write",
        "read",
        "query",
        "request",
        "network",
    ]):
        return "SinkEntity"

    return "RuntimeArtifactEntity"

def infer_capabilities(ro: Dict[str, Any]) -> List[str]:
    blob = text_blob(ro)
    caps = []

    checks = {
        "external_entrypoint": ["exported", "intent-filter", "deeplink", "scheme", "host"],
        "local_file_access": ["file", "path", "uri", "openfile", "content://"],
        "web_content_execution": ["webview", "javascript", "loadurl"],
        "native_bridge_invocation": ["bridge", "reactmethod", "methodchannel", "javascriptinterface"],
        "network_access": ["http", "https", "socket", "server", "okhttp"],
        "credential_or_token_handling": ["token", "jwt", "auth", "oauth", "credential"],
        "persistent_storage": ["sqlite", "sharedpreferences", "database", "cache"],
        "inter_process_communication": ["intent", "binder", "provider", "receiver", "service"],
    }

    for cap, needles in checks.items():
        if any(n in blob for n in needles):
            caps.append(cap)

    return sorted(set(caps))


def infer_trust_boundaries(ro: Dict[str, Any]) -> List[str]:
    blob = text_blob(ro)
    boundaries = []

    if any(x in blob for x in ["exported", "intent-filter", "deeplink", "scheme"]):
        boundaries.append("external_app_to_app")
    if "webview" in blob:
        boundaries.append("web_content_to_native")
    if any(x in blob for x in ["bridge", "reactmethod", "methodchannel", "javascriptinterface"]):
        boundaries.append("framework_bridge_to_native")
    if any(x in blob for x in ["content://", "fileprovider", "contentprovider"]):
        boundaries.append("content_uri_boundary")
    if any(x in blob for x in ["http", "socket", "server"]):
        boundaries.append("network_boundary")

    return sorted(set(boundaries))


def infer_related_assets(ro: Dict[str, Any]) -> List[str]:
    blob = text_blob(ro)
    assets = []

    if "file" in blob or "content://" in blob:
        assets.append("filesystem_or_content_uri")
    if "token" in blob or "jwt" in blob or "credential" in blob:
        assets.append("credential_material")
    if "database" in blob or "sqlite" in blob:
        assets.append("local_database")
    if "webview" in blob:
        assets.append("webview_state")
    if "cache" in blob:
        assets.append("local_cache")

    return sorted(set(assets))


def infer_related_sinks(ro: Dict[str, Any]) -> List[str]:
    blob = text_blob(ro)
    sinks = []

    if "loadurl" in blob or "webview" in blob:
        sinks.append("webview_load")
    if "openfile" in blob or "fileprovider" in blob:
        sinks.append("file_open_or_share")
    if "exec" in blob:
        sinks.append("command_execution")
    if "sqlite" in blob or "query" in blob:
        sinks.append("database_query")
    if "http" in blob or "socket" in blob:
        sinks.append("network_request")

    return sorted(set(sinks))


def confidence_for(ro: Dict[str, Any], caps: List[str], boundaries: List[str]) -> float:
    score = 0.25

    if caps:
        score += 0.25
    if boundaries:
        score += 0.25
    if ro.get("evidence") or ro.get("observations") or ro.get("source_artifacts"):
        score += 0.15
    if ro.get("confidence"):
        score += 0.10

    return min(round(score, 2), 0.95)


def uncertainty_reasons(ro: Dict[str, Any], caps: List[str], boundaries: List[str]) -> List[str]:
    reasons = []

    if not caps:
        reasons.append("no_capability_inferred")
    if not boundaries:
        reasons.append("no_trust_boundary_inferred")
    if not (ro.get("evidence") or ro.get("observations") or ro.get("source_artifacts")):
        reasons.append("limited_source_evidence")
    if not ro.get("dynamic_validation"):
        reasons.append("no_dynamic_validation")

    return reasons


def build_entity(ro: Dict[str, Any], index: int) -> UniversalEntity:
    runtime = detect_runtime(ro)
    framework = detect_framework_origin(ro, runtime)
    entity_type = infer_entity_type(ro)

    name = (
        ro.get("name")
        or ro.get("title")
        or ro.get("id")
        or ro.get("research_object_id")
        or ro.get("object_id")
        or f"research_object_{index}"
    )

    caps = infer_capabilities(ro)
    boundaries = infer_trust_boundaries(ro)

    entity_id = stable_id(
        "UE4",
        entity_type,
        name,
        runtime,
        framework,
        ro.get("class"),
        ro.get("method"),
        ro.get("component"),
    )

    obs = []
    if ro.get("observations"):
        obs = ro.get("observations")
    elif ro.get("evidence"):
        obs = [{"kind": "evidence_reference", "value": ro.get("evidence")}]
    else:
        obs = [{"kind": "raw_research_object", "value": name}]

    return UniversalEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=str(name),
        source_runtime=runtime,
        framework_origin=framework,
        observations=obs if isinstance(obs, list) else [obs],
        inferred_capabilities=caps,
        trust_boundaries=boundaries,
        related_assets=infer_related_assets(ro),
        related_sinks=infer_related_sinks(ro),
        confidence=confidence_for(ro, caps, boundaries),
        uncertainty_reasons=uncertainty_reasons(ro, caps, boundaries),
        counter_evidence=[],
        source_artifacts=[{"kind": "research_object", "index": index}],
        raw=ro,
    )


def build_entities(input_path: Path) -> Dict[str, Any]:
    data = load_json(input_path)
    ros = [x for x in as_list(data) if isinstance(x, dict)]

    entities = [build_entity(ro, i).to_dict() for i, ro in enumerate(ros)]

    summary = {
        "input": str(input_path),
        "research_objects": len(ros),
        "entities": len(entities),
        "by_type": {},
        "by_runtime": {},
    }

    for e in entities:
        summary["by_type"][e["entity_type"]] = summary["by_type"].get(e["entity_type"], 0) + 1
        summary["by_runtime"][e["source_runtime"]] = summary["by_runtime"].get(e["source_runtime"], 0) + 1

    return {
        "schema": "semantic_entities_v4",
        "candidate_only": True,
        "finding_allowed": False,
        "summary": summary,
        "entities": entities,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 -m core.semantic_entity_builder_v4 <research_objects.json> <output.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    result = build_entities(input_path)
    save_json(output_path, result)

    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
