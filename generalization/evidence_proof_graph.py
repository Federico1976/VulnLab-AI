#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def eid(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


STATUS_WEIGHT = {
    "confirmed": 1.0,
    "supported_static": 0.78,
    "supported_semantic": 0.62,
    "runtime_needed": 0.45,
    "unknown": 0.25,
    "contradicted": 0.0,
}


def infer_node_status(stage: str, evidence_needed: str, plan: Dict[str, Any]) -> str:
    stage = (stage or "").lower()
    ev = (evidence_needed or "").lower()

    if stage == "entrypoint":
        if plan.get("component") and plan.get("actions"):
            return "supported_static"
        return "unknown"

    if stage == "source":
        if any(x in ev for x in ["attacker-controlled", "intent", "query", "text"]):
            return "supported_semantic"
        return "unknown"

    if stage in ("normalization", "propagation"):
        return "runtime_needed"

    if stage == "sink":
        return "runtime_needed"

    if stage == "counter-evidence":
        return "unknown"

    return "supported_semantic"


def missing_for_status(status: str, stage: str) -> List[str]:
    if status == "confirmed":
        return []

    if status == "supported_static":
        return ["runtime_confirmation", "source_to_sink_trace"]

    if status == "supported_semantic":
        return ["static_callgraph_or_trace", "runtime_confirmation"]

    if status == "runtime_needed":
        return ["dynamic_validation", "trace_observation", "counterevidence_resolution"]

    if status == "unknown":
        return ["evidence_collection_required"]

    if status == "contradicted":
        return ["hypothesis_rejected_or_needs_revision"]

    return ["evidence_collection_required"]


def confidence_for_status(status: str, plan_probability: float, order: int) -> float:
    base = STATUS_WEIGHT.get(status, 0.25)
    decay = max(0.0, 1.0 - ((order - 1) * 0.06))
    return round(min(max(base * plan_probability * decay, 0.0), 1.0), 3)


def counter_evidence_for_stage(stage: str) -> List[Dict[str, Any]]:
    stage = (stage or "").lower()
    counters = []

    if stage == "entrypoint":
        counters.append({
            "type": "not_exported_or_permission_guarded",
            "severity": "high",
            "proof_required": "verify exported state, permission and caller reachability",
            "expected_information_gain": 0.20,
        })

    if stage == "source":
        counters.append({
            "type": "input_not_attacker_controlled",
            "severity": "high",
            "proof_required": "verify external caller controls URI/text/query/extra",
            "expected_information_gain": 0.25,
        })

    if stage == "normalization":
        counters.append({
            "type": "scheme_or_domain_restricted",
            "severity": "medium",
            "proof_required": "verify allowlist, canonicalization and parser behavior",
            "expected_information_gain": 0.18,
        })

    if stage == "propagation":
        counters.append({
            "type": "flow_break_or_safe_router",
            "severity": "high",
            "proof_required": "verify route does not reach sensitive sink",
            "expected_information_gain": 0.22,
        })

    if stage == "sink":
        counters.append({
            "type": "sink_unreachable_or_safely_wrapped",
            "severity": "high",
            "proof_required": "confirm actual sink behavior with static and dynamic evidence",
            "expected_information_gain": 0.25,
        })

    if stage == "counter-evidence":
        counters.append({
            "type": "unresolved_guard_or_sanitizer",
            "severity": "critical",
            "proof_required": "resolve all guards before disclosure readiness",
            "expected_information_gain": 0.30,
        })

    return counters


def build_nodes(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    probability = float(plan.get("success_probability") or 0.35)
    nodes = []

    for item in plan.get("ordered_call_chain_hypothesis", []):
        order = int(item.get("order") or len(nodes) + 1)
        stage = item.get("stage")
        node = item.get("node")
        evidence_needed = item.get("evidence_needed")

        status = infer_node_status(stage, evidence_needed, plan)
        confidence = confidence_for_status(status, probability, order)

        nodes.append({
            "node_id": eid("proof-node", plan.get("plan_id"), order, stage, node),
            "order": order,
            "semantic_role": stage,
            "label": node,
            "confidence": confidence,
            "proof_state": status,
            "required_evidence": [evidence_needed] if evidence_needed else [],
            "existing_evidence": infer_existing_evidence(stage, plan),
            "missing_evidence": missing_for_status(status, stage),
            "counter_evidence": counter_evidence_for_stage(stage),
            "validation_state": "not_validated_runtime" if status in ("runtime_needed", "supported_semantic", "supported_static") else "unknown",
        })

    return nodes


def infer_existing_evidence(stage: str, plan: Dict[str, Any]) -> List[str]:
    stage = (stage or "").lower()
    out = []

    if stage == "entrypoint":
        if plan.get("component"):
            out.append("component_identified")
        if plan.get("actions"):
            out.append("intent_actions_present")
        if "component_exported_true" in plan.get("risk_reasons", []):
            out.append("exported_component_signal")
        if "has_intent_filter" in plan.get("risk_reasons", []):
            out.append("intent_filter_signal")

    if stage == "source":
        if plan.get("actions"):
            out.append("source_action_signal")
        if plan.get("schemes"):
            out.append("uri_scheme_surface")

    if stage == "normalization":
        if plan.get("schemes"):
            out.append("scheme_set_available")
        if plan.get("hosts"):
            out.append("host_scope_available")
        if plan.get("paths"):
            out.append("path_scope_available")

    if stage == "propagation":
        out.append("semantic_shape_requires_propagation")

    if stage == "sink":
        out.append("semantic_shape_sink_hypothesis")

    return out


def build_edges(nodes: List[Dict[str, Any]], plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    edges = []

    for a, b in zip(nodes, nodes[1:]):
        source_state = a.get("proof_state")
        target_state = b.get("proof_state")
        conf = round((a.get("confidence", 0.0) + b.get("confidence", 0.0)) / 2, 3)

        if "runtime_needed" in (source_state, target_state):
            proof_status = "runtime_needed"
        elif "unknown" in (source_state, target_state):
            proof_status = "unknown"
        else:
            proof_status = "candidate"

        counters = []
        counters.extend(a.get("counter_evidence", []))
        counters.extend(b.get("counter_evidence", []))

        edges.append({
            "edge_id": eid("proof-edge", a.get("node_id"), b.get("node_id")),
            "from_node": a.get("node_id"),
            "to_node": b.get("node_id"),
            "from_label": a.get("label"),
            "to_label": b.get("label"),
            "relationship": f"{a.get('semantic_role')} -> {b.get('semantic_role')}",
            "confidence": conf,
            "proof_type": "semantic_static_candidate",
            "proof_state": proof_status,
            "counter_evidence": counters[:4],
            "missing_evidence": list(dict.fromkeys(a.get("missing_evidence", []) + b.get("missing_evidence", []))),
        })

    return edges


def link_validation(commands: List[str], nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    validations = []

    runtime_edges = [e for e in edges if e.get("proof_state") in ("runtime_needed", "unknown", "candidate")]
    runtime_nodes = [n for n in nodes if n.get("proof_state") in ("runtime_needed", "supported_semantic", "supported_static", "unknown")]

    for idx, cmd in enumerate(commands):
        edge = runtime_edges[min(idx, len(runtime_edges) - 1)] if runtime_edges else None
        node = runtime_nodes[min(idx, len(runtime_nodes) - 1)] if runtime_nodes else None

        validations.append({
            "validation_id": eid("validation", idx, cmd),
            "command": cmd,
            "validates_node": node.get("node_id") if node else None,
            "validates_edge": edge.get("edge_id") if edge else None,
            "expected_confidence_gain": round(0.08 + min(idx, 4) * 0.02, 3),
            "validation_type": "safe_dynamic_probe",
            "success_observation": [
                "component launches or rejects deterministically",
                "input is accepted, normalized, or blocked",
                "navigation/load behavior is observed safely",
                "logs or UI confirm whether route reaches sink",
            ],
            "failure_observation": [
                "activity not exported or not reachable",
                "input ignored",
                "scheme blocked",
                "navigation sink not reached",
            ],
        })

    return validations


def compute_proof_score(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not nodes:
        return {
            "proof_score": 0.0,
            "disclosure_readiness": 0,
            "finding_allowed": False,
            "reason": "no proof nodes",
        }

    node_score = sum(n.get("confidence", 0.0) for n in nodes) / len(nodes)
    edge_score = sum(e.get("confidence", 0.0) for e in edges) / len(edges) if edges else 0.0

    unresolved_counter = sum(len(n.get("counter_evidence", [])) for n in nodes)
    runtime_needed = sum(1 for n in nodes if n.get("proof_state") == "runtime_needed")
    unknown = sum(1 for n in nodes if n.get("proof_state") == "unknown")

    penalty = min((unresolved_counter * 0.025) + (runtime_needed * 0.06) + (unknown * 0.07), 0.55)
    proof_score = max(((node_score * 0.55) + (edge_score * 0.45)) - penalty, 0.0)

    readiness = int(round(proof_score * 100))

    return {
        "proof_score": round(proof_score, 3),
        "disclosure_readiness": readiness,
        "finding_allowed": False,
        "reason": "candidate proof graph only; dynamic validation and counter-evidence resolution required",
        "metrics": {
            "avg_node_confidence": round(node_score, 3),
            "avg_edge_confidence": round(edge_score, 3),
            "unresolved_counter_evidence": unresolved_counter,
            "runtime_needed_nodes": runtime_needed,
            "unknown_nodes": unknown,
        },
    }


def build_graph(local_plan: Dict[str, Any], reasoning: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    selected = local_plan.get("selected_plans", [])
    graphs = []

    for rank, plan in enumerate(selected, start=1):
        nodes = build_nodes(plan)
        edges = build_edges(nodes, plan)
        validations = link_validation(plan.get("safe_dynamic_probe_commands", []), nodes, edges)
        score = compute_proof_score(nodes, edges)

        graphs.append({
            "proof_graph_id": eid("proof-graph", plan.get("plan_id")),
            "rank": rank,
            "plan_id": plan.get("plan_id"),
            "target_shape": plan.get("target_shape"),
            "component": plan.get("component"),
            "success_probability": plan.get("success_probability"),
            "proof_score": score,
            "evidence_nodes": nodes,
            "evidence_edges": edges,
            "validation_evidence": validations,
            "next_highest_information_gain": select_next_information_gain(nodes, edges, validations),
            "finding_policy": {
                "candidate_only": True,
                "finding_allowed": False,
                "requires_dynamic_validation": True,
                "requires_counterevidence_resolution": True,
            },
        })

    return {
        "schema_version": "evidence_proof_graph.v1",
        "created_at": int(time.time()),
        "source": {
            "local_plan_schema": local_plan.get("schema_version"),
            "reasoning_schema": reasoning.get("schema"),
            "policy_schema": policy.get("schema_version"),
        },
        "summary": {
            "proof_graphs": len(graphs),
            "top_component": graphs[0].get("component") if graphs else None,
            "top_shape": graphs[0].get("target_shape") if graphs else None,
            "top_proof_score": graphs[0].get("proof_score", {}).get("proof_score") if graphs else None,
            "top_disclosure_readiness": graphs[0].get("proof_score", {}).get("disclosure_readiness") if graphs else 0,
            "candidate_only": True,
            "finding_allowed": False,
        },
        "proof_graphs": graphs,
    }


def select_next_information_gain(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], validations: List[Dict[str, Any]]) -> Dict[str, Any]:
    if validations:
        return {
            "type": "validation",
            "target": validations[0].get("validates_edge") or validations[0].get("validates_node"),
            "action": validations[0].get("command"),
            "expected_confidence_gain": validations[0].get("expected_confidence_gain"),
            "reason": "dynamic validation can confirm or reject the highest-priority uncertain edge",
        }

    runtime_edges = [e for e in edges if e.get("proof_state") in ("runtime_needed", "unknown")]
    if runtime_edges:
        e = runtime_edges[0]
        return {
            "type": "edge_proof",
            "target": e.get("edge_id"),
            "action": "collect static trace or runtime trace for edge",
            "expected_confidence_gain": 0.12,
            "reason": "edge is unresolved and blocks proof completeness",
        }

    unknown_nodes = [n for n in nodes if n.get("proof_state") == "unknown"]
    if unknown_nodes:
        n = unknown_nodes[0]
        return {
            "type": "node_proof",
            "target": n.get("node_id"),
            "action": "collect missing evidence for node",
            "expected_confidence_gain": 0.10,
            "reason": "node uncertainty blocks proof completeness",
        }

    return {
        "type": "none",
        "target": None,
        "action": "manual review",
        "expected_confidence_gain": 0.0,
        "reason": "no automated validation available",
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Evidence Proof Graph v1")
    ap.add_argument("--local-plan", required=True)
    ap.add_argument("--reasoning", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    local_plan = load_json(args.local_plan)
    reasoning = load_json(args.reasoning)
    policy = load_json(args.policy)

    graph = build_graph(local_plan, reasoning, policy)
    save_json(args.out, graph)

    print(json.dumps(graph["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
