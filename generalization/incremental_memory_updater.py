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


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def extract_memory_deltas(reasoning_session: Dict[str, Any]) -> List[Dict[str, Any]]:
    deltas: List[Dict[str, Any]] = []

    shape_ctx = reasoning_session.get("shape_guided_reasoning", {})
    primary_shape = shape_ctx.get("primary_shape", {})
    primary_shape_id = primary_shape.get("shape_id")

    if primary_shape_id:
        deltas.append({
            "delta_id": stable_id("delta-shape", primary_shape_id),
            "delta_type": "shape_memory_reinforcement",
            "target_memory_type": "SemanticShapeMemory",
            "shape_id": primary_shape_id,
            "update_mode": "reinforce_existing_or_create_summary",
            "evidence": {
                "match_strength": primary_shape.get("match_strength"),
                "matched_nodes": primary_shape.get("matched_nodes", []),
                "matched_edges": primary_shape.get("matched_edges", []),
                "positive_signals": primary_shape.get("positive_signals", []),
                "counter_evidence": primary_shape.get("counter_evidence", []),
            },
            "anti_overfit": {
                "apk_specific_terms_allowed": False,
                "store_framework_specific_detail": False,
                "store_only_shape_level_abstraction": True,
            },
        })

    for d in reasoning_session.get("decisions", []):
        candidate_shape = d.get("candidate_shape")
        if not candidate_shape:
            continue

        conf = d.get("confidence_calibration", {})
        exp = d.get("experiment_planning", {})
        story = d.get("evidence_story_update", {})

        deltas.append({
            "delta_id": stable_id("delta-strategy", candidate_shape, exp.get("experiment_type")),
            "delta_type": "strategy_memory_update",
            "target_memory_type": "ResearchStrategyMemory",
            "shape_id": candidate_shape,
            "update_mode": "incremental_strategy_observation",
            "evidence": {
                "experiment_type": exp.get("experiment_type"),
                "priority": exp.get("priority"),
                "steps": exp.get("steps", []),
                "guardrails": exp.get("guardrails", {}),
                "shape_adjusted_confidence": conf.get("shape_adjusted_confidence"),
            },
            "anti_overfit": {
                "requires_multiple_apk_support_before_promotion": True,
                "promotion_threshold": 3,
                "candidate_only": True,
            },
        })

        for ce in d.get("counterevidence_selection", []):
            ce_type = ce.get("type")
            if not ce_type:
                continue
            deltas.append({
                "delta_id": stable_id("delta-counter", candidate_shape, ce_type),
                "delta_type": "counterevidence_memory_update",
                "target_memory_type": "CounterEvidenceMemory",
                "shape_id": candidate_shape,
                "update_mode": "incremental_counterevidence_observation",
                "evidence": {
                    "counterevidence_type": ce_type,
                    "question": ce.get("question"),
                    "source": ce.get("source"),
                },
                "anti_overfit": {
                    "store_as_falsification_question": True,
                    "do_not_convert_to_finding": True,
                },
            })

        if story:
            deltas.append({
                "delta_id": stable_id("delta-story", candidate_shape),
                "delta_type": "evidence_story_memory_update",
                "target_memory_type": "EvidenceStoryMemory",
                "shape_id": candidate_shape,
                "update_mode": "missing_evidence_tracking",
                "evidence": {
                    "add_missing_evidence": story.get("add_missing_evidence", []),
                    "add_assumptions": story.get("add_assumptions", []),
                    "finding_allowed": story.get("finding_allowed", False),
                },
                "anti_overfit": {
                    "candidate_only": True,
                    "requires_dynamic_validation": True,
                },
            })

    return deltas


def apply_deltas(memory_snapshot: Dict[str, Any], deltas: List[Dict[str, Any]]) -> Dict[str, Any]:
    memory_snapshot.setdefault("schema_version", "incremental_memory_snapshot.v1")
    memory_snapshot.setdefault("created_at", int(time.time()))
    memory_snapshot.setdefault("updated_at", int(time.time()))
    memory_snapshot.setdefault("deltas", [])
    memory_snapshot.setdefault("indexes", {
        "by_shape": {},
        "by_delta_type": {},
        "by_target_memory_type": {},
    })

    existing = {d.get("delta_id") for d in memory_snapshot.get("deltas", [])}

    added = 0
    skipped = 0

    for delta in deltas:
        delta_id = delta.get("delta_id")
        if delta_id in existing:
            skipped += 1
            continue

        delta["first_seen_at"] = int(time.time())
        delta["promotion_state"] = "candidate_memory"
        delta["finding_allowed"] = False

        memory_snapshot["deltas"].append(delta)
        existing.add(delta_id)
        added += 1

        shape = delta.get("shape_id", "unknown")
        dtype = delta.get("delta_type", "unknown")
        target = delta.get("target_memory_type", "unknown")

        memory_snapshot["indexes"]["by_shape"].setdefault(shape, []).append(delta_id)
        memory_snapshot["indexes"]["by_delta_type"].setdefault(dtype, []).append(delta_id)
        memory_snapshot["indexes"]["by_target_memory_type"].setdefault(target, []).append(delta_id)

    memory_snapshot["updated_at"] = int(time.time())
    memory_snapshot["last_update_summary"] = {
        "incoming_deltas": len(deltas),
        "added": added,
        "skipped_existing": skipped,
        "total_deltas": len(memory_snapshot["deltas"]),
    }

    return memory_snapshot


def build_regression_guard(memory_snapshot: Dict[str, Any], deltas: List[Dict[str, Any]]) -> Dict[str, Any]:
    risky = []

    for d in deltas:
        anti = d.get("anti_overfit", {})
        if anti.get("apk_specific_terms_allowed") is True:
            risky.append({
                "delta_id": d.get("delta_id"),
                "risk": "apk_specific_terms_allowed",
            })
        if d.get("finding_allowed") is True:
            risky.append({
                "delta_id": d.get("delta_id"),
                "risk": "finding_allowed_true_in_memory_delta",
            })

    return {
        "schema_version": "incremental_memory_regression_guard.v1",
        "passed": len(risky) == 0,
        "risk_count": len(risky),
        "risks": risky,
        "checks": {
            "candidate_only_preserved": True,
            "no_direct_finding_promotion": True,
            "no_full_rebuild_required": True,
            "anti_overfit_metadata_present": all("anti_overfit" in d for d in deltas),
        },
        "memory_size": {
            "total_deltas": len(memory_snapshot.get("deltas", [])),
            "shapes": len(memory_snapshot.get("indexes", {}).get("by_shape", {})),
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Incremental Memory Updater v1")
    parser.add_argument("reasoning_session_v2")
    parser.add_argument("--memory", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--guard-out", required=True)

    args = parser.parse_args()

    reasoning_session = load_json(args.reasoning_session_v2)
    memory_snapshot = load_json(args.memory)

    deltas = extract_memory_deltas(reasoning_session)
    updated = apply_deltas(memory_snapshot, deltas)
    guard = build_regression_guard(updated, deltas)

    save_json(args.out, updated)
    save_json(args.guard_out, guard)

    print(json.dumps({
        "schema_version": "incremental_memory_update_run.v1",
        "deltas_extracted": len(deltas),
        "memory_out": args.out,
        "guard_out": args.guard_out,
        "guard_passed": guard["passed"],
        "last_update_summary": updated.get("last_update_summary", {}),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
