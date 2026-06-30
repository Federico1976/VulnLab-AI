#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def select_primary_shape(shape_matches: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    matches = shape_matches.get("matches", []) if isinstance(shape_matches, dict) else []
    for m in matches:
        if m.get("primary_shape") is True:
            return m
    return matches[0] if matches else None


def build_reasoning_shape_context(shape_matches: Dict[str, Any]) -> Dict[str, Any]:
    primary = select_primary_shape(shape_matches)

    if not primary:
        return {
            "schema_version": "reasoning_shape_context.v1",
            "has_shape_context": False,
            "primary_shape": None,
            "reasoning_bias": [],
            "proof_priorities": [],
            "confidence_adjustments": [],
            "alternative_shapes": [],
        }

    alternatives = [
        m for m in shape_matches.get("matches", [])
        if m.get("shape_id") != primary.get("shape_id")
    ]

    reasoning_bias = [
        {
            "type": "shape_first_reasoning",
            "message": "Prioritize causal investigative shape over isolated entity count.",
        },
        {
            "type": "primary_shape",
            "shape_id": primary.get("shape_id"),
            "match_strength": primary.get("match_strength"),
            "recommended_next_step": primary.get("recommended_next_step"),
        },
    ]

    proof_priorities = []

    if primary.get("missing_edges"):
        proof_priorities.append({
            "priority": "prove_missing_edges",
            "missing_edges": primary.get("missing_edges", []),
        })

    if primary.get("counter_evidence"):
        proof_priorities.append({
            "priority": "resolve_counter_evidence",
            "counter_evidence": primary.get("counter_evidence", []),
        })

    proof_priorities.append({
        "priority": "execute_recommended_next_step",
        "step": primary.get("recommended_next_step"),
    })

    confidence_adjustments = [{
        "source": "semantic_shape_matcher.v1",
        "shape_id": primary.get("shape_id"),
        "confidence_delta": primary.get("confidence_delta", 0.0),
        "reason": "Primary investigative shape matched.",
    }]

    return {
        "schema_version": "reasoning_shape_context.v1",
        "has_shape_context": True,
        "primary_shape": primary,
        "reasoning_bias": reasoning_bias,
        "proof_priorities": proof_priorities,
        "confidence_adjustments": confidence_adjustments,
        "alternative_shapes": alternatives[:5],
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Bridge Semantic Shape Matcher output into Reasoning Executor context")
    parser.add_argument("shape_matches")
    parser.add_argument("--out", required=True)

    args = parser.parse_args()

    shape_matches = load_json(args.shape_matches)
    context = build_reasoning_shape_context(shape_matches or {})

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "written": str(out),
        "has_shape_context": context["has_shape_context"],
        "primary_shape_id": context["primary_shape"]["shape_id"] if context["primary_shape"] else None,
        "recommended_next_step": context["primary_shape"]["recommended_next_step"] if context["primary_shape"] else None,
    }, indent=2))


if __name__ == "__main__":
    main()
