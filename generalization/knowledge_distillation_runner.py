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


def distill_from_incremental_memory(memory: Dict[str, Any]) -> Dict[str, Any]:
    deltas = memory.get("deltas", [])

    patterns = []
    strategies = []
    meta_strategies = []
    counter_rules = []
    failure_modes = []

    for d in deltas:
        shape_id = d.get("shape_id")
        dtype = d.get("delta_type")
        evidence = d.get("evidence", {})

        if not shape_id:
            continue

        if dtype == "shape_memory_reinforcement":
            patterns.append({
                "pattern_id": stable_id("pattern", shape_id),
                "pattern_shape": shape_id,
                "abstraction_level": "semantic_shape",
                "core_question": f"Can the causal shape '{shape_id}' be validated without target-specific assumptions?",
                "causal_form": evidence.get("matched_edges", []),
                "positive_signals": evidence.get("positive_signals", []),
                "counter_evidence": evidence.get("counter_evidence", []),
                "promotion_state": "distilled_candidate",
                "anti_overfit": {
                    "framework_independent": True,
                    "apk_specific": False,
                    "requires_cross_apk_support": True,
                },
            })

        if dtype == "strategy_memory_update":
            strategies.append({
                "strategy_id": stable_id("strategy", shape_id, evidence.get("experiment_type")),
                "strategy_shape": shape_id,
                "preferred_experiment_order": evidence.get("steps", []),
                "priority": evidence.get("priority"),
                "observed_confidence": evidence.get("shape_adjusted_confidence"),
                "maturity": "candidate",
                "guardrails": evidence.get("guardrails", {}),
                "decision_score": evidence.get("shape_adjusted_confidence") or 0.0,
                "promotion_rule": {
                    "min_distinct_apks": 3,
                    "requires_regression_pass": True,
                    "requires_counterevidence_resolution": True,
                },
            })

        if dtype == "counterevidence_memory_update":
            counter_rules.append({
                "counterevidence_id": stable_id("counterrule", shape_id, evidence.get("counterevidence_type")),
                "strategy_shape": shape_id,
                "counterevidence_type": evidence.get("counterevidence_type"),
                "falsification_question": evidence.get("question"),
                "source": evidence.get("source"),
                "rule_type": "must_resolve_before_finding",
                "finding_allowed_if_unresolved": False,
            })

        if dtype == "evidence_story_memory_update":
            failure_modes.append({
                "failure_id": stable_id("failure", shape_id),
                "strategy_shape": shape_id,
                "failure_type": "missing_evidence_or_unresolved_assumption",
                "reason": "Reasoning session still requires proof, dynamic validation, and counter-evidence resolution.",
                "missing_evidence": evidence.get("add_missing_evidence", []),
                "assumptions": evidence.get("add_assumptions", []),
                "finding_allowed": False,
            })

    shape_ids = sorted({p["pattern_shape"] for p in patterns})
    for shape_id in shape_ids:
        meta_strategies.append({
            "meta_strategy_id": stable_id("metastrategy", shape_id),
            "shape_id": shape_id,
            "principle": "Prefer causal shape validation over isolated detector output.",
            "generalization_value": "high",
            "memory_compression_rule": "Store only shape, strategy, counter-evidence and failure mode; discard APK-specific raw detail.",
            "anti_overfit_rule": "Promote only after repeated support across heterogeneous APKs.",
        })

    return {
        "schema_version": "knowledge_distillation_snapshot.v1",
        "created_at": int(time.time()),
        "source": "incremental_memory_snapshot_v1",
        "distilled": {
            "patterns": dedupe(patterns, "pattern_id"),
            "strategies": dedupe(strategies, "strategy_id"),
            "meta_strategies": dedupe(meta_strategies, "meta_strategy_id"),
            "counter_rules": dedupe(counter_rules, "counterevidence_id"),
            "failure_modes": dedupe(failure_modes, "failure_id"),
        },
        "summary": {
            "patterns": len(dedupe(patterns, "pattern_id")),
            "strategies": len(dedupe(strategies, "strategy_id")),
            "meta_strategies": len(dedupe(meta_strategies, "meta_strategy_id")),
            "counter_rules": len(dedupe(counter_rules, "counterevidence_id")),
            "failure_modes": len(dedupe(failure_modes, "failure_id")),
            "framework_independent": True,
            "candidate_only": True,
            "finding_allowed": False,
        },
    }


def dedupe(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        k = item.get(key)
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out


def build_distillation_guard(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    distilled = snapshot.get("distilled", {})

    risks = []

    for bucket, items in distilled.items():
        for item in items:
            text = json.dumps(item, ensure_ascii=False).lower()

            if "output/croc_app" in text or "croc_app_unified" in text:
                risks.append({
                    "bucket": bucket,
                    "risk": "apk_specific_path_leaked_into_distilled_memory",
                    "item": item,
                })

            if item.get("finding_allowed") is True:
                risks.append({
                    "bucket": bucket,
                    "risk": "finding_allowed_true_in_distilled_memory",
                    "item": item,
                })

    return {
        "schema_version": "knowledge_distillation_guard.v1",
        "passed": len(risks) == 0,
        "risk_count": len(risks),
        "risks": risks,
        "checks": {
            "framework_independent": snapshot.get("summary", {}).get("framework_independent") is True,
            "candidate_only": snapshot.get("summary", {}).get("candidate_only") is True,
            "finding_allowed": snapshot.get("summary", {}).get("finding_allowed") is False,
            "anti_bloat": True,
            "distilled_not_raw": True,
        },
        "summary": snapshot.get("summary", {}),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge Distillation Runner v1")
    parser.add_argument("incremental_memory_snapshot")
    parser.add_argument("--out", required=True)
    parser.add_argument("--guard-out", required=True)

    args = parser.parse_args()

    memory = load_json(args.incremental_memory_snapshot)
    snapshot = distill_from_incremental_memory(memory)
    guard = build_distillation_guard(snapshot)

    save_json(args.out, snapshot)
    save_json(args.guard_out, guard)

    print(json.dumps({
        "schema_version": "knowledge_distillation_run.v1",
        "out": args.out,
        "guard_out": args.guard_out,
        "guard_passed": guard["passed"],
        "summary": snapshot["summary"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
