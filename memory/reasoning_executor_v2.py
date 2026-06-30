from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from memory.reasoning_executor_v1 import (
    load_json,
    save_json,
    build_reasoning_session,
)


def load_optional_json(path: str | Path | None) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)



def build_primary_shape_decision(shape_context: Dict[str, Any]) -> Dict[str, Any]:
    primary = shape_context.get("primary_shape") or {}
    primary_shape_id = primary.get("shape_id")
    recommended_next_step = primary.get("recommended_next_step")

    shape_delta = 0.0
    for adj in shape_context.get("confidence_adjustments", []):
        shape_delta += float(adj.get("confidence_delta") or 0.0)

    return {
        "candidate_shape": primary_shape_id,
        "decision_origin": "semantic_shape_matcher_v1",
        "pattern_match": {
            "matched": True,
            "pattern_id": primary_shape_id,
            "core_question": f"Can the causal investigative shape '{primary_shape_id}' be validated?",
            "causal_form": primary.get("matched_edges", []),
        },
        "strategy_selection": {
            "selected": True,
            "strategy_id": f"shape_strategy::{primary_shape_id}",
            "maturity": "generalization_phase_v1",
            "decision_score": primary.get("confidence_delta"),
            "use_when": ["semantic_shape_matcher_primary_shape"],
            "avoid_when": primary.get("counter_evidence", []),
        },
        "counterevidence_selection": [
            {
                "counterevidence_id": f"shape-counter-{ce}",
                "type": ce,
                "question": f"Verify whether shape counter-evidence '{ce}' invalidates the candidate causal path.",
                "source": "semantic_shape_matcher.v1",
            }
            for ce in primary.get("counter_evidence", [])
        ],
        "failure_prediction": [
            {
                "failure_id": f"shape-failure-{ce}",
                "failure_type": ce,
                "reason": f"Primary shape has unresolved counter-evidence: {ce}",
            }
            for ce in primary.get("counter_evidence", [])
        ],
        "confidence_calibration": {
            "available": True,
            "calibrated_confidence": round(min(max(0.35 + shape_delta, 0.0), 1.0), 3),
            "shape_adjusted_confidence": round(min(max(0.35 + shape_delta, 0.0), 1.0), 3),
            "priority": "high" if primary.get("match_strength") == "strong" else "medium",
            "reasoning": {
                "source": "semantic_shape_matcher.v1",
                "match_strength": primary.get("match_strength"),
                "confidence_delta": shape_delta,
                "positive_signals": primary.get("positive_signals", []),
                "counter_evidence": primary.get("counter_evidence", []),
            },
            "shape_confidence_adjustments": shape_context.get("confidence_adjustments", []),
        },
        "local_graph_evidence": {
            "matched_nodes": primary.get("matched_nodes", []),
            "matched_edges": primary.get("matched_edges", []),
            "missing_nodes": primary.get("missing_nodes", []),
            "missing_edges": primary.get("missing_edges", []),
            "positive_signals": primary.get("positive_signals", []),
            "counter_evidence": primary.get("counter_evidence", []),
        },
        "experiment_planning": {
            "experiment_type": "shape_guided_validation",
            "priority": "high" if primary.get("match_strength") == "strong" else "medium",
            "steps": [
                recommended_next_step,
                "resolve_shape_counter_evidence",
                "prove_reachability_against_manifest_and_runtime",
                "prove_source_to_sink_control",
                "produce_candidate_only_validation_result",
            ],
            "shape_proof_priorities": shape_context.get("proof_priorities", []),
            "guardrails": {
                "candidate_only": True,
                "finding_allowed": False,
                "requires_dynamic_validation": True,
            },
        },
        "evidence_story_update": {
            "add_missing_evidence": [
                "runtime_reachability_not_confirmed",
                "source_to_sink_runtime_flow_not_confirmed",
                "counter_evidence_not_resolved",
            ],
            "add_assumptions": [
                "semantic shape match is candidate evidence only",
                "primary shape must be validated before disclosure readiness",
            ],
            "shape_guided_updates": [
                {
                    "primary_shape_id": primary_shape_id,
                    "recommended_next_step": recommended_next_step,
                    "finding_allowed": False,
                    "reason": "Primary semantic shape injected as reasoning driver.",
                }
            ],
            "finding_allowed": False,
        },
        "shape_match_alignment": {
            "is_primary_shape": True,
            "primary_shape_id": primary_shape_id,
            "recommended_next_step": recommended_next_step,
        },
    }

def apply_shape_context(session: Dict[str, Any], shape_context: Dict[str, Any]) -> Dict[str, Any]:
    if not shape_context or not shape_context.get("has_shape_context"):
        session["shape_guided_reasoning"] = {
            "enabled": False,
            "reason": "no_shape_context_available",
        }
        return session

    primary = shape_context.get("primary_shape") or {}
    primary_shape_id = primary.get("shape_id")
    recommended_next_step = primary.get("recommended_next_step")

    session["schema"] = "reasoning_session_v2"
    session["shape_guided_reasoning"] = {
        "enabled": True,
        "source_schema": shape_context.get("schema_version"),
        "primary_shape_id": primary_shape_id,
        "primary_shape": primary,
        "reasoning_bias": shape_context.get("reasoning_bias", []),
        "proof_priorities": shape_context.get("proof_priorities", []),
        "confidence_adjustments": shape_context.get("confidence_adjustments", []),
        "alternative_shapes": shape_context.get("alternative_shapes", []),
    }

    session.setdefault("summary", {})
    session["summary"]["shape_guided"] = True
    session["summary"]["primary_shape_id"] = primary_shape_id
    session["summary"]["primary_recommended_next_step"] = recommended_next_step

    decisions = session.get("decisions", [])

    if primary_shape_id and not any(d.get("candidate_shape") == primary_shape_id for d in decisions):
        decisions.insert(0, build_primary_shape_decision(shape_context))

    enriched: List[Dict[str, Any]] = []

    for d in decisions:
        candidate = d.get("candidate_shape")

        d["shape_match_alignment"] = {
            "is_primary_shape": candidate == primary_shape_id,
            "primary_shape_id": primary_shape_id,
            "recommended_next_step": recommended_next_step,
        }

        d.setdefault("experiment_planning", {})
        steps = d["experiment_planning"].get("steps") or []

        if recommended_next_step and recommended_next_step not in steps:
            d["experiment_planning"]["steps"] = [recommended_next_step] + steps

        d["experiment_planning"]["shape_proof_priorities"] = shape_context.get("proof_priorities", [])

        d.setdefault("confidence_calibration", {})
        d["confidence_calibration"]["shape_confidence_adjustments"] = shape_context.get("confidence_adjustments", [])

        current_conf = d["confidence_calibration"].get("calibrated_confidence")
        shape_delta = 0.0
        for adj in shape_context.get("confidence_adjustments", []):
            shape_delta += float(adj.get("confidence_delta") or 0.0)

        if isinstance(current_conf, (int, float)):
            d["confidence_calibration"]["shape_adjusted_confidence"] = round(
                min(max(current_conf + shape_delta, 0.0), 1.0), 3
            )
        else:
            d["confidence_calibration"]["shape_adjusted_confidence"] = round(
                min(max(0.35 + shape_delta, 0.0), 1.0), 3
            )

        d.setdefault("counterevidence_selection", [])
        for ce in primary.get("counter_evidence", []):
            d["counterevidence_selection"].insert(0, {
                "counterevidence_id": f"shape-counter-{ce}",
                "type": ce,
                "question": f"Verify whether shape counter-evidence '{ce}' invalidates external reachability or exploitability.",
                "source": "semantic_shape_matcher.v1",
            })

        d.setdefault("evidence_story_update", {})
        d["evidence_story_update"].setdefault("shape_guided_updates", [])
        d["evidence_story_update"]["shape_guided_updates"].append({
            "primary_shape_id": primary_shape_id,
            "recommended_next_step": recommended_next_step,
            "finding_allowed": False,
            "reason": "Shape match supports candidate reasoning only; proof and dynamic validation still required.",
        })

        enriched.append(d)

    enriched.sort(
        key=lambda x: (
            x.get("shape_match_alignment", {}).get("is_primary_shape") is True,
            x.get("confidence_calibration", {}).get("shape_adjusted_confidence") or 0,
        ),
        reverse=True,
    )

    session["decisions"] = enriched

    if enriched:
        session["summary"]["top_candidate_shape"] = enriched[0].get("candidate_shape")
        session["summary"]["top_shape_adjusted_confidence"] = enriched[0].get("confidence_calibration", {}).get("shape_adjusted_confidence")

    return session


def main() -> None:
    if len(sys.argv) not in (4, 5):
        print(
            "Usage: python3 -m memory.reasoning_executor_v2 "
            "<semantic_entity_graph_v4.json> "
            "<universal_cognitive_graph_v1.json> "
            "<reasoning_session_v2.json> "
            "[reasoning_shape_context_v1.json]"
        )
        sys.exit(1)

    semantic_graph = load_json(Path(sys.argv[1]))
    cognitive_graph = load_json(Path(sys.argv[2]))
    out = Path(sys.argv[3])
    shape_context = load_optional_json(sys.argv[4]) if len(sys.argv) == 5 else {}

    session = build_reasoning_session(semantic_graph, cognitive_graph)
    session = apply_shape_context(session, shape_context)

    save_json(out, session)
    print(json.dumps(session.get("summary", {}), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
