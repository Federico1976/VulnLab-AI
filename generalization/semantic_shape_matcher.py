#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


ENTITY_ALIASES = {
    "entrypoint": {"entrypoint", "EntrypointEntity", "DeepLinkEntity", "ExportedComponentEntity", "IntentEntrypoint", "activity", "service", "receiver", "provider"},
    "source": {"source", "SourceEntity", "IntentSourceEntity", "UriSourceEntity", "BundleSourceEntity", "input", "uri", "intent"},
    "propagation": {"propagation", "PropagationEntity", "DataFlowEntity", "BridgeMethodEntity", "flow", "path", "edge"},
    "trust_boundary": {"trust_boundary", "TrustBoundaryEntity", "BoundaryCrossingEntity", "ipc", "external_boundary"},
    "sanitizer": {"sanitizer", "SanitizerEntity", "ValidationEntity", "validation", "allowlist"},
    "sink": {"sink", "SinkEntity", "SensitiveSinkEntity", "FileSinkEntity", "WebViewSinkEntity", "capability", "fileprovider", "webview"},
    "asset": {"asset", "AssetEntity", "ProtectedAssetEntity", "file", "storage", "secret"},
    "evidence": {"evidence", "ValidationEvidenceEntity", "EvidenceEntity"},
    "counter_evidence": {"counter_evidence", "CounterEvidenceEntity"},
}


DEFAULT_SHAPES = [
    {
        "shape_id": "external_entry_to_sensitive_sink",
        "title": "External entrypoint may influence sensitive sink",
        "required_nodes": ["entrypoint", "source", "propagation", "sink"],
        "required_edges": [["entrypoint", "source"], ["source", "propagation"], ["propagation", "sink"]],
        "positive_signals": ["external_reachable", "tainted_flow", "sink_sensitive"],
        "negative_signals": ["sanitized", "not_exported", "permission_protected", "unreachable"],
        "base_confidence_delta": 0.18,
        "recommended_next_step": "prove_reachability",
    },
    {
        "shape_id": "untrusted_uri_to_file_access",
        "title": "Untrusted URI/path may influence file access",
        "required_nodes": ["entrypoint", "source", "propagation", "sink", "asset"],
        "required_edges": [["entrypoint", "source"], ["source", "propagation"], ["propagation", "sink"], ["sink", "asset"]],
        "positive_signals": ["uri_controlled", "path_sensitive", "file_access"],
        "negative_signals": ["canonicalized", "allowlisted", "permission_protected", "unreachable"],
        "base_confidence_delta": 0.22,
        "recommended_next_step": "prove_path_control",
    },
    {
        "shape_id": "webview_external_input_to_load",
        "title": "External input may reach WebView loading/navigation sink",
        "required_nodes": ["entrypoint", "source", "propagation", "sink"],
        "required_edges": [["entrypoint", "source"], ["source", "propagation"], ["propagation", "sink"]],
        "positive_signals": ["webview", "load_url", "intent_controlled", "javascript_enabled"],
        "negative_signals": ["domain_allowlist", "scheme_restricted", "not_exported", "unreachable"],
        "base_confidence_delta": 0.20,
        "recommended_next_step": "prove_external_navigation_control",
    },
    {
        "shape_id": "ipc_boundary_to_privileged_action",
        "title": "IPC boundary may lead to privileged action",
        "required_nodes": ["entrypoint", "trust_boundary", "source", "propagation", "sink"],
        "required_edges": [["entrypoint", "trust_boundary"], ["trust_boundary", "source"], ["source", "propagation"], ["propagation", "sink"]],
        "positive_signals": ["ipc", "exported", "privileged_action", "permission_gap"],
        "negative_signals": ["signature_permission", "caller_verified", "not_exported", "unreachable"],
        "base_confidence_delta": 0.24,
        "recommended_next_step": "prove_caller_control_and_privilege_gap",
    },
]


@dataclass
class ShapeMatchResult:
    shape_id: str
    title: str
    match_strength: str
    matched_nodes: List[str]
    missing_nodes: List[str]
    matched_edges: List[List[str]]
    missing_edges: List[List[str]]
    positive_signals: List[str]
    counter_evidence: List[str]
    confidence_delta: float
    recommended_next_step: str
    reasoning: List[str]


def _stable_id(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _load_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _canonical_type(raw_type: Optional[str]) -> Optional[str]:
    if not raw_type:
        return None
    rt = str(raw_type).strip()
    rtl = rt.lower()
    for canonical, aliases in ENTITY_ALIASES.items():
        lowered = {a.lower() for a in aliases}
        if rtl in lowered:
            return canonical
    if "entry" in rtl or "deeplink" in rtl or "exported" in rtl or "activity" in rtl:
        return "entrypoint"
    if "source" in rtl or "intent" in rtl or "uri" in rtl or "input" in rtl:
        return "source"
    if "flow" in rtl or "propagation" in rtl or "bridge" in rtl or "path" in rtl:
        return "propagation"
    if "boundary" in rtl or "ipc" in rtl:
        return "trust_boundary"
    if "sanitize" in rtl or "validation" in rtl or "allowlist" in rtl:
        return "sanitizer"
    if "sink" in rtl or "webview" in rtl or "fileprovider" in rtl or "capability" in rtl:
        return "sink"
    if "asset" in rtl or "file" in rtl or "storage" in rtl:
        return "asset"
    return rtl


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _looks_like_entity(d: Dict[str, Any]) -> bool:
    keys = {str(k).lower() for k in d.keys()}
    entity_keys = {
        "entity_type", "semantic_type", "type", "kind", "category",
        "capability_type", "object_type", "node_type", "role"
    }
    semantic_markers = {
        "entrypoint", "source", "sink", "asset", "evidence", "confidence",
        "component", "method", "class", "flow", "capability", "reachability"
    }
    return bool(keys & entity_keys) or len(keys & semantic_markers) >= 2


def _infer_entity_type(d: Dict[str, Any]) -> str:
    raw = (
        d.get("entity_type")
        or d.get("semantic_type")
        or d.get("type")
        or d.get("kind")
        or d.get("category")
        or d.get("capability_type")
        or d.get("object_type")
        or d.get("node_type")
        or d.get("role")
    )
    canonical = _canonical_type(raw)
    if canonical:
        return canonical

    text = json.dumps(d, default=str).lower()

    if any(x in text for x in ["deeplink", "intent-filter", "exported", "activity", "receiver", "service", "provider"]):
        return "entrypoint"
    if any(x in text for x in ["getintent", "extras", "bundle", "uri", "content://", "file://", "input"]):
        return "source"
    if any(x in text for x in ["dataflow", "taint", "propagation", "bridge", "next_hop", "call_chain"]):
        return "propagation"
    if any(x in text for x in ["webview", "loadurl", "load_url", "openfile", "query", "insert", "delete", "sink"]):
        return "sink"
    if any(x in text for x in ["fileprovider", "paths.xml", "external-path", "cache-path", "files-path", "storage"]):
        return "asset"
    if any(x in text for x in ["permission", "ipc", "trust_boundary", "boundary"]):
        return "trust_boundary"
    if any(x in text for x in ["sanitize", "canonical", "allowlist", "validation"]):
        return "sanitizer"

    return "unknown"


def _extract_entities(blob: Any) -> List[Dict[str, Any]]:
    if blob is None:
        return []

    entities: List[Dict[str, Any]] = []

    preferred_keys = [
        "entities", "semantic_entities", "nodes", "research_objects",
        "objects", "capabilities", "findings", "candidates",
        "observed_patterns", "patterns", "hypotheses"
    ]

    roots: List[Any] = []
    if isinstance(blob, list):
        roots.append(blob)
    elif isinstance(blob, dict):
        for k in preferred_keys:
            if isinstance(blob.get(k), list):
                roots.append(blob[k])
        if not roots:
            roots.append(blob)

    for root in roots:
        for d in _walk(root):
            if not isinstance(d, dict) or not _looks_like_entity(d):
                continue

            canonical = _infer_entity_type(d)
            if canonical == "unknown":
                continue

            entity_id = str(
                d.get("id")
                or d.get("entity_id")
                or d.get("object_id")
                or d.get("finding_id")
                or d.get("name")
                or d.get("title")
                or d.get("method")
                or d.get("class")
                or _stable_id(d)
            )

            entities.append({
                "id": entity_id,
                "canonical_type": canonical,
                "data": d,
            })

    seen = set()
    deduped = []
    for e in entities:
        key = (e["id"], e["canonical_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    return deduped


def _extract_edges(blob: Any, entities: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    edges: Set[Tuple[str, str]] = set()

    for d in _walk(blob):
        if not isinstance(d, dict):
            continue

        src = d.get("source") or d.get("from") or d.get("src") or d.get("source_entity")
        dst = d.get("target") or d.get("to") or d.get("dst") or d.get("sink") or d.get("target_entity")

        if src and dst:
            edges.add((str(src), str(dst)))

    by_type: Dict[str, List[str]] = {}
    for e in entities:
        by_type.setdefault(e["canonical_type"], []).append(e["id"])

    inferred_type_edges = [
        ("entrypoint", "source"),
        ("source", "propagation"),
        ("propagation", "sink"),
        ("entrypoint", "trust_boundary"),
        ("trust_boundary", "source"),
        ("sink", "asset"),
        ("sanitizer", "propagation"),
    ]

    for a, b in inferred_type_edges:
        if by_type.get(a) and by_type.get(b):
            edges.add((a, b))

    return sorted(edges)


def _collect_signals(blobs: List[Any]) -> Set[str]:
    text = " ".join(json.dumps(b, default=str).lower() for b in blobs if b is not None)
    maps = {
        "external_reachable": ["external_reachable", "exported", "deeplink", "intent-filter"],
        "tainted_flow": ["taint", "dataflow", "source_to_sink", "flow", "propagation"],
        "sink_sensitive": ["sink", "sensitive", "privileged", "capability"],
        "uri_controlled": ["uri", "path", "content://", "file://"],
        "path_sensitive": ["path traversal", "canonical", "filepath", "filename", "external-path"],
        "file_access": ["fileprovider", "openfile", "readfile", "writefile", "file access", "paths.xml"],
        "webview": ["webview"],
        "load_url": ["loadurl", "load_url", "shouldoverrideurlloading"],
        "intent_controlled": ["intent", "bundle", "extras"],
        "javascript_enabled": ["javascriptenabled", "setjavascriptenabled"],
        "ipc": ["binder", "service", "receiver", "provider", "ipc"],
        "exported": ["exported", "intent-filter"],
        "privileged_action": ["privileged", "permission", "account", "token", "credential"],
        "permission_gap": ["permission_gap", "missing permission", "no permission"],
        "sanitized": ["sanitized", "validated", "escaped"],
        "not_exported": ["not_exported", "exported=false", '"exported": false'],
        "permission_protected": ["permission_protected", "signature permission", "requires permission"],
        "unreachable": ["unreachable", "not reachable", 'externally_reachable": false'],
        "canonicalized": ["canonicalized", "getcanonicalpath"],
        "allowlisted": ["allowlist", "whitelist"],
        "domain_allowlist": ["domain allowlist", "host allowlist"],
        "scheme_restricted": ["scheme restricted", "https only"],
        "signature_permission": ["signature_permission", "protectionlevel=signature"],
        "caller_verified": ["caller verified", "checkcallingpermission", "getcallinguid"],
    }

    found = set()
    for sig, needles in maps.items():
        if any(n in text for n in needles):
            found.add(sig)
    return found


def _score_shape(shape: Dict[str, Any], node_types: Set[str], type_edges: Set[Tuple[str, str]], signals: Set[str]) -> ShapeMatchResult:
    required_nodes = shape["required_nodes"]
    required_edges = [tuple(e) for e in shape["required_edges"]]

    matched_nodes = [n for n in required_nodes if n in node_types]
    missing_nodes = [n for n in required_nodes if n not in node_types]

    matched_edges = [list(e) for e in required_edges if e in type_edges]
    missing_edges = [list(e) for e in required_edges if e not in type_edges]

    positive = [s for s in shape.get("positive_signals", []) if s in signals]
    negative = [s for s in shape.get("negative_signals", []) if s in signals]

    node_ratio = len(matched_nodes) / max(len(required_nodes), 1)
    edge_ratio = len(matched_edges) / max(len(required_edges), 1)
    pos_bonus = min(len(positive) * 0.06, 0.24)
    neg_penalty = min(len(negative) * 0.08, 0.32)

    raw_score = (node_ratio * 0.45) + (edge_ratio * 0.45) + pos_bonus - neg_penalty

    specificity = shape.get("specificity_requirements") or {}
    if specificity:
        must_include = specificity.get("must_include_one_of", [])
        min_pos = specificity.get("minimum_specific_positive_signals", 0)
        has_required_specific_signal = any(sig in positive for sig in must_include)
        enough_positive_signals = len(positive) >= min_pos

        if not has_required_specific_signal:
            raw_score -= 0.22
            negative.append("missing_shape_specific_signal")

        if not enough_positive_signals:
            raw_score -= 0.14
            negative.append("insufficient_shape_specificity")

    if raw_score >= 0.82 and not missing_edges:
        strength = "strong"
    elif raw_score >= 0.58:
        strength = "medium"
    elif raw_score >= 0.35:
        strength = "weak"
    else:
        strength = "none"

    confidence_delta = 0.0 if strength == "none" else round(shape.get("base_confidence_delta", 0.12) * raw_score, 3)

    return ShapeMatchResult(
        shape_id=shape["shape_id"],
        title=shape["title"],
        match_strength=strength,
        matched_nodes=matched_nodes,
        missing_nodes=missing_nodes,
        matched_edges=matched_edges,
        missing_edges=[list(e) for e in missing_edges],
        positive_signals=positive,
        counter_evidence=negative,
        confidence_delta=confidence_delta,
        recommended_next_step=shape.get("recommended_next_step", "continue_investigation"),
        reasoning=[
            f"node_ratio={node_ratio:.2f}",
            f"edge_ratio={edge_ratio:.2f}",
            f"positive_signals={len(positive)}",
            f"counter_evidence={len(negative)}",
            f"raw_score={raw_score:.2f}",
        ],
    )


def match_semantic_shapes(semantic_graph: Any, evidence_graph: Any = None, research_objects: Any = None, pattern_memory: Any = None) -> Dict[str, Any]:
    blobs = [semantic_graph, evidence_graph, research_objects, pattern_memory]

    entities: List[Dict[str, Any]] = []
    for b in blobs:
        entities.extend(_extract_entities(b))

    node_types = {e["canonical_type"] for e in entities if e["canonical_type"] != "unknown"}

    all_edges: Set[Tuple[str, str]] = set()
    for b in blobs:
        for src, dst in _extract_edges(b, entities):
            src_c = _canonical_type(src) or src
            dst_c = _canonical_type(dst) or dst
            all_edges.add((src_c, dst_c))

    signals = _collect_signals(blobs)

    results = [_score_shape(shape, node_types, all_edges, signals) for shape in DEFAULT_SHAPES]

    ranked = sorted(
        [asdict(r) for r in results if r.match_strength != "none"],
        key=lambda r: (
            {"strong": 3, "medium": 2, "weak": 1}.get(r["match_strength"], 0),
            len(r["positive_signals"]) - len(r["counter_evidence"]),
            r["confidence_delta"],
            -len(r["missing_edges"]),
            -len(r["missing_nodes"]),
        ),
        reverse=True,
    )

    for idx, r in enumerate(ranked):
        r["rank"] = idx + 1
        r["primary_shape"] = idx == 0
        r["decision_use"] = "primary_reasoning_driver" if idx == 0 else "supporting_or_alternative_shape"

    return {
        "schema_version": "semantic_shape_matcher.v1",
        "summary": {
            "entities_seen": len(entities),
            "node_types_seen": sorted(node_types),
            "type_edges_seen": [list(e) for e in sorted(all_edges)],
            "signals_seen": sorted(signals),
            "matches": len(ranked),
            "strong_matches": sum(1 for r in ranked if r["match_strength"] == "strong"),
            "medium_matches": sum(1 for r in ranked if r["match_strength"] == "medium"),
            "weak_matches": sum(1 for r in ranked if r["match_strength"] == "weak"),
            "primary_shape_id": ranked[0]["shape_id"] if ranked else None,
            "primary_recommended_next_step": ranked[0]["recommended_next_step"] if ranked else None,
        },
        "matches": ranked,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Semantic Shape Matcher v1")
    parser.add_argument("semantic_graph")
    parser.add_argument("--evidence-graph", default=None)
    parser.add_argument("--research-objects", default=None)
    parser.add_argument("--pattern-memory", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    result = match_semantic_shapes(
        semantic_graph=_load_json(args.semantic_graph),
        evidence_graph=_load_json(args.evidence_graph) if args.evidence_graph else None,
        research_objects=_load_json(args.research_objects) if args.research_objects else None,
        pattern_memory=_load_json(args.pattern_memory) if args.pattern_memory else None,
    )

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
