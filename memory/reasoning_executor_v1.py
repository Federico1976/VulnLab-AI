from __future__ import annotations

import json
import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{h}"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def graph_shape(semantic_graph: Dict[str, Any]) -> Dict[str, Any]:
    summary = semantic_graph.get("summary", {})
    by_type = summary.get("by_type", {})
    by_relation = summary.get("by_relation", {})
    by_runtime = summary.get("by_runtime", {})

    bridge = by_type.get("BridgeEntity", 0)
    sink = by_type.get("SinkEntity", 0)
    asset = by_type.get("AssetEntity", 0)
    entrypoint = by_type.get("EntrypointEntity", 0)

    may_reach = by_relation.get("may_reach", 0)
    touches_asset = by_relation.get("touches_asset", 0)
    contains_sink = by_relation.get("contains_sink", 0)

    candidate_shapes = []
    shape_scores = {}

    # Shape 1: bridge -> webview/sink
    bridge_sink_score = (
        min(bridge / 10.0, 1.0) * 0.35
        + min(sink / 10.0, 1.0) * 0.25
        + min(may_reach / 10.0, 1.0) * 0.40
    )
    shape_scores["bridge_to_webview_sink"] = round(bridge_sink_score, 2)

    if bridge_sink_score >= 0.35:
        candidate_shapes.append("bridge_to_webview_sink")

    # Shape 2: entrypoint -> content uri/file asset
    entry_asset_score = (
        min(entrypoint / 10.0, 1.0) * 0.35
        + min(asset / 20.0, 1.0) * 0.25
        + min(touches_asset / 20.0, 1.0) * 0.40
    )
    shape_scores["entrypoint_to_content_uri_asset"] = round(entry_asset_score, 2)

    if entry_asset_score >= 0.45:
        candidate_shapes.append("entrypoint_to_content_uri_asset")

    # Shape 3: bridge -> file asset
    bridge_file_score = (
        min(bridge / 10.0, 1.0) * 0.40
        + min(asset / 20.0, 1.0) * 0.35
        + min(contains_sink / 20.0, 1.0) * 0.25
    )
    shape_scores["bridge_to_file_asset"] = round(bridge_file_score, 2)

    if bridge_file_score >= 0.55:
        candidate_shapes.append("bridge_to_file_asset")

    if not candidate_shapes and sink > 0:
        candidate_shapes.append("generic_sink_reachability")
        shape_scores["generic_sink_reachability"] = 0.3

    return {
        "by_type": by_type,
        "by_relation": by_relation,
        "by_runtime": by_runtime,
        "candidate_shapes": candidate_shapes,
        "shape_scores": shape_scores,
    }

def index_nodes(cognitive_graph: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    idx: Dict[str, List[Dict[str, Any]]] = {}
    for n in cognitive_graph.get("nodes", []):
        idx.setdefault(n.get("node_type", "unknown"), []).append(n)
    return idx


def find_strategy(nodes_by_type: Dict[str, List[Dict[str, Any]]], shape: str) -> Dict[str, Any] | None:
    for n in nodes_by_type.get("ResearchStrategy", []):
        if n.get("data", {}).get("strategy_shape") == shape:
            return n
    return None


def find_confidence(nodes_by_type: Dict[str, List[Dict[str, Any]]], shape: str) -> Dict[str, Any] | None:
    for n in nodes_by_type.get("ConfidenceCalibration", []):
        if n.get("data", {}).get("strategy_shape") == shape:
            return n
    return None


def find_counterevidence(nodes_by_type: Dict[str, List[Dict[str, Any]]], shape: str) -> List[Dict[str, Any]]:
    return [
        n for n in nodes_by_type.get("CounterEvidencePattern", [])
        if n.get("data", {}).get("strategy_shape") == shape
    ]


def find_failures(nodes_by_type: Dict[str, List[Dict[str, Any]]], shape: str) -> List[Dict[str, Any]]:
    return [
        n for n in nodes_by_type.get("FailurePattern", [])
        if n.get("data", {}).get("strategy_shape") == shape
    ]


def find_pattern(nodes_by_type: Dict[str, List[Dict[str, Any]]], shape: str) -> Dict[str, Any] | None:
    for n in nodes_by_type.get("DistilledPattern", []):
        if n.get("data", {}).get("pattern_shape") == shape:
            return n
    return None


def build_experiment_plan(strategy: Dict[str, Any] | None, confidence: Dict[str, Any] | None) -> Dict[str, Any]:
    if not strategy:
        return {
            "experiment_type": "manual_review_required",
            "priority": "low",
            "steps": [
                "inspect_semantic_graph",
                "identify_candidate_shape",
                "build_candidate_validation_plan",
            ],
        }

    data = strategy.get("data", {})
    conf = confidence.get("data", {}) if confidence else {}

    return {
        "experiment_type": "runtime_reachability_probe",
        "priority": conf.get("priority", "medium"),
        "calibrated_confidence": conf.get("calibrated_confidence"),
        "steps": data.get("preferred_experiment_order", []),
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "requires_dynamic_validation": True,
        },
    }


def reason_for_shape(
    semantic_shape: Dict[str, Any],
    nodes_by_type: Dict[str, List[Dict[str, Any]]],
    shape: str,
) -> Dict[str, Any]:
    strategy = find_strategy(nodes_by_type, shape)
    confidence = find_confidence(nodes_by_type, shape)
    counter = find_counterevidence(nodes_by_type, shape)
    failures = find_failures(nodes_by_type, shape)
    pattern = find_pattern(nodes_by_type, shape)

    strategy_data = strategy.get("data", {}) if strategy else {}
    confidence_data = confidence.get("data", {}) if confidence else {}
    pattern_data = pattern.get("data", {}) if pattern else {}

    return {
        "candidate_shape": shape,
        "pattern_match": {
            "matched": pattern is not None,
            "pattern_id": pattern_data.get("pattern_id"),
            "core_question": pattern_data.get("core_question"),
            "causal_form": pattern_data.get("causal_form", []),
        },
        "strategy_selection": {
            "selected": strategy is not None,
            "strategy_id": strategy_data.get("strategy_id"),
            "maturity": strategy_data.get("maturity"),
            "decision_score": strategy_data.get("decision_score"),
            "use_when": strategy_data.get("use_when", []),
            "avoid_when": strategy_data.get("avoid_when", []),
        },
        "counterevidence_selection": [
            {
                "counterevidence_id": c.get("data", {}).get("counterevidence_id"),
                "type": c.get("data", {}).get("counterevidence_type"),
                "question": c.get("data", {}).get("falsification_question"),
            }
            for c in counter
        ],
        "failure_prediction": [
            {
                "failure_id": f.get("data", {}).get("failure_id"),
                "failure_type": f.get("data", {}).get("failure_type"),
                "reason": f.get("data", {}).get("reason"),
            }
            for f in failures
        ],
        "confidence_calibration": {
            "available": confidence is not None,
            "calibrated_confidence": confidence_data.get("calibrated_confidence"),
            "priority": confidence_data.get("priority"),
            "reasoning": confidence_data.get("reasoning", {}),
        },
        "local_graph_evidence": {
            "by_type": semantic_shape.get("by_type", {}),
            "by_relation": semantic_shape.get("by_relation", {}),
            "by_runtime": semantic_shape.get("by_runtime", {}),
        },
        "experiment_planning": build_experiment_plan(strategy, confidence),
        "evidence_story_update": {
            "add_missing_evidence": [
                "runtime_reachability_not_confirmed",
                "source_to_sink_runtime_flow_not_confirmed",
                "security_control_effectiveness_not_verified",
            ],
            "add_assumptions": [
                "static semantic graph supports only candidate causal reasoning",
                "no finding can be claimed before dynamic validation and proof evaluation",
            ],
            "finding_allowed": False,
        },
    }


def build_reasoning_session(semantic_graph: Dict[str, Any], cognitive_graph: Dict[str, Any]) -> Dict[str, Any]:
    shape = graph_shape(semantic_graph)
    nodes_by_type = index_nodes(cognitive_graph)

    decisions = [
        reason_for_shape(shape, nodes_by_type, candidate_shape)
        for candidate_shape in shape["candidate_shapes"]
    ]

    decisions = sorted(
        decisions,
        key=lambda d: d.get("confidence_calibration", {}).get("calibrated_confidence") or 0,
        reverse=True,
    )

    return {
        "schema": "reasoning_session_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "online reasoning session over semantic graph and universal cognitive graph",
        "summary": {
            "candidate_shapes": shape["candidate_shapes"],
            "decisions": len(decisions),
            "top_priority": decisions[0]["confidence_calibration"].get("priority") if decisions else "none",
            "top_shape": decisions[0]["candidate_shape"] if decisions else "none",
        },
        "input_semantic_shape": shape,
        "decisions": decisions,
        "global_guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "no_vulnerability_claim_without_dynamic_validation": True,
            "separate_historical_pattern_from_target_finding": True,
        },
    }


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: python3 -m memory.reasoning_executor_v1 <semantic_entity_graph_v4.json> <universal_cognitive_graph_v1.json> <reasoning_session_v1.json>")
        sys.exit(1)

    semantic_graph = load_json(Path(sys.argv[1]))
    cognitive_graph = load_json(Path(sys.argv[2]))
    out = Path(sys.argv[3])

    session = build_reasoning_session(semantic_graph, cognitive_graph)
    save_json(out, session)

    print(json.dumps(session["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
