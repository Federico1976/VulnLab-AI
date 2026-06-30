from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def group_by_ro(graph: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    groups: Dict[int, Dict[str, Any]] = {}

    for e in graph.get("entities", []):
        ro_index = e.get("raw_ref", {}).get("ro_index")
        if ro_index is None:
            continue

        g = groups.setdefault(ro_index, {
            "entities": [],
            "relations": [],
            "by_type": {},
        })

        g["entities"].append(e)
        g["by_type"].setdefault(e.get("entity_type"), []).append(e)

    entity_to_ro = {}
    for ro_index, g in groups.items():
        for e in g["entities"]:
            entity_to_ro[e["entity_id"]] = ro_index

    for r in graph.get("relations", []):
        ro_index = entity_to_ro.get(r.get("source_entity_id"))
        if ro_index is not None and ro_index in groups:
            groups[ro_index]["relations"].append(r)

    return groups


def names(items: List[Dict[str, Any]], limit: int = 8) -> List[str]:
    return [str(x.get("name")) for x in items[:limit]]


def relation_count(relations: List[Dict[str, Any]], relation_type: str) -> int:
    return sum(1 for r in relations if r.get("relation_type") == relation_type)


def infer_uncertainty(by_type: Dict[str, List[Dict[str, Any]]], relations: List[Dict[str, Any]]) -> Dict[str, Any]:
    missing = []
    assumptions = []
    breakpoints = []

    # Guardrail fondamentale:
    # una storia causale statica non è mai "provata".
    missing.append("dynamic_validation_not_performed")
    missing.append("runtime_reachability_not_confirmed")
    missing.append("source_to_sink_runtime_flow_not_confirmed")

    assumptions.append("static semantic co-occurrence does not prove exploitability")
    assumptions.append("candidate story must remain separated from any target finding")

    if not by_type.get("EntrypointEntity"):
        missing.append("external_or_user_reachable_entrypoint_not_confirmed")
        assumptions.append("reachability may be internal only")

    if not by_type.get("SecurityControlEntity"):
        missing.append("security_controls_not_observed")
        assumptions.append("absence of observed controls does not mean absence of controls")
    else:
        missing.append("security_control_effectiveness_not_verified")
        breakpoints.append("possible_security_control_may_break_candidate_path")

    if not by_type.get("SinkEntity"):
        missing.append("concrete_sink_not_identified")
        breakpoints.append("no sink means no actionable validation path")

    if not by_type.get("TrustBoundaryEntity"):
        missing.append("trust_boundary_not_identified")
        breakpoints.append("no boundary means no meaningful security transition")

    if relation_count(relations, "may_drive_sink") == 0:
        missing.append("capability_to_sink_link_not_established")
        assumptions.append("capability and sink co-occurrence is not enough for reachability")

    if relation_count(relations, "may_reach") == 0 and by_type.get("BridgeEntity"):
        missing.append("bridge_to_sink_reachability_not_established")

    if relation_count(relations, "suggests_propagation") == 0:
        missing.append("propagation_path_not_established")

    # Calibrazione conservativa:
    # senza validazione dinamica, non scendiamo mai sotto medium.
    if len(missing) >= 7:
        level = "high"
    else:
        level = "medium"

    return {
        "missing_evidence": sorted(set(missing)),
        "assumptions": sorted(set(assumptions)),
        "breakpoints": sorted(set(breakpoints)),
        "uncertainty_level": level,
    }

def highest_value_experiment(by_type: Dict[str, List[Dict[str, Any]]], uncertainty: Dict[str, Any]) -> Dict[str, Any]:
    missing = set(uncertainty["missing_evidence"])

    if "runtime_reachability_not_confirmed" in missing:
        return {
            "experiment_type": "runtime_reachability_probe",
            "goal": "confirm whether the candidate chain is reachable at runtime from a realistic entry condition",
            "value": "highest",
            "safe_mode": True,
            "finding_allowed_after": False,
        }

    if "source_to_sink_runtime_flow_not_confirmed" in missing:
        return {
            "experiment_type": "source_to_sink_runtime_trace",
            "goal": "verify whether candidate-controlled input can reach the observed sink",
            "value": "highest",
            "safe_mode": True,
            "finding_allowed_after": False,
        }

    if "bridge_to_sink_reachability_not_established" in missing:
        return {
            "experiment_type": "bridge_to_sink_trace",
            "goal": "verify whether bridge-controlled data can reach the observed sink",
            "value": "highest",
            "safe_mode": True,
            "finding_allowed_after": False,
        }

    if "security_control_effectiveness_not_verified" in missing:
        return {
            "experiment_type": "control_effectiveness_check",
            "goal": "verify whether observed security controls block the candidate path",
            "value": "high",
            "safe_mode": True,
            "finding_allowed_after": False,
        }

    return {
        "experiment_type": "minimal_dynamic_validation_plan",
        "goal": "collect the smallest runtime evidence needed to reduce uncertainty",
        "value": "medium",
        "safe_mode": True,
        "finding_allowed_after": False,
    }

def build_story(ro_index: int, group: Dict[str, Any]) -> Dict[str, Any]:
    by_type = group["by_type"]
    relations = group["relations"]

    observations = []

    for t in [
        "RuntimeArtifactEntity",
        "EntrypointEntity",
        "BridgeEntity",
        "TrustBoundaryEntity",
        "CapabilityEntity",
        "AssetEntity",
        "SinkEntity",
        "SecurityControlEntity",
        "PropagationEntity",
    ]:
        if by_type.get(t):
            observations.append({
                "kind": "entity_observed",
                "entity_type": t,
                "count": len(by_type[t]),
                "examples": names(by_type[t], 5),
            })

    causal_edges = [
        r for r in relations
        if r.get("relation_type") in {
            "enables_candidate_capability",
            "may_drive_sink",
            "may_reach",
            "suggests_propagation",
        }
    ]

    inferences = []

    if by_type.get("TrustBoundaryEntity") and by_type.get("CapabilityEntity"):
        inferences.append("A trust boundary and one or more capabilities co-exist in the same research object.")

    if by_type.get("CapabilityEntity") and by_type.get("SinkEntity"):
        inferences.append("A candidate capability-to-sink story can be constructed, but remains unvalidated.")

    if by_type.get("BridgeEntity") and by_type.get("SinkEntity"):
        inferences.append("A framework/native bridge may interact with a sensitive sink.")

    if by_type.get("SecurityControlEntity"):
        inferences.append("Possible security controls are present and must be treated as candidate path breakers.")

    uncertainty = infer_uncertainty(by_type, relations)

    return {
        "evidence_story_id": f"EVSTORY4-{ro_index}",
        "research_object_index": ro_index,
        "candidate_only": True,
        "finding_allowed": False,
        "status": "candidate_causal_story",
        "observations": observations,
        "inferences": inferences,
        "counter_evidence": [],
        "assumptions": uncertainty["assumptions"],
        "breakpoints": uncertainty["breakpoints"],
        "missing_evidence": uncertainty["missing_evidence"],
        "uncertainty_level": uncertainty["uncertainty_level"],
        "causal_edges": causal_edges[:50],
        "highest_value_experiment": highest_value_experiment(by_type, uncertainty),
        "entity_counts": {k: len(v) for k, v in by_type.items()},
        "relation_counts": {
            "enables_candidate_capability": relation_count(relations, "enables_candidate_capability"),
            "may_drive_sink": relation_count(relations, "may_drive_sink"),
            "may_reach": relation_count(relations, "may_reach"),
            "suggests_propagation": relation_count(relations, "suggests_propagation"),
            "may_be_constrained_by": relation_count(relations, "may_be_constrained_by"),
        },
    }


def build_evidence_stories(graph: Dict[str, Any]) -> Dict[str, Any]:
    groups = group_by_ro(graph)
    stories = [build_story(i, groups[i]) for i in sorted(groups.keys())]

    by_uncertainty: Dict[str, int] = {}
    by_experiment: Dict[str, int] = {}

    for s in stories:
        by_uncertainty[s["uncertainty_level"]] = by_uncertainty.get(s["uncertainty_level"], 0) + 1
        et = s["highest_value_experiment"]["experiment_type"]
        by_experiment[et] = by_experiment.get(et, 0) + 1

    return {
        "schema": "evidence_story_v4",
        "candidate_only": True,
        "finding_allowed": False,
        "source_schema": graph.get("schema"),
        "summary": {
            "stories": len(stories),
            "by_uncertainty": by_uncertainty,
            "by_highest_value_experiment": by_experiment,
        },
        "stories": stories,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 -m core.evidence_story_builder_v4 <semantic_entity_graph_v4.json> <evidence_stories_v4.json>")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2])

    graph = load_json(inp)
    stories = build_evidence_stories(graph)
    save_json(out, stories)

    print(json.dumps(stories["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
