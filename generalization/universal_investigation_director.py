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


def sid(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


DIRECTOR_WEIGHTS = {
    "policy_score": 0.30,
    "expected_information_gain": 0.25,
    "shape_diversity_gain": 0.15,
    "counterevidence_resolution_value": 0.15,
    "cost_efficiency": 0.10,
    "knowledge_promotion_value": 0.05,
}


def collect_policy_files(root_patterns: List[str]) -> List[Path]:
    files = []
    for pat in root_patterns:
        files.extend(Path(".").glob(pat))
    return sorted(set(files))


def infer_cost(experiment: Dict[str, Any]) -> float:
    step = str(experiment.get("step") or "")
    if "resolve_counter" in step:
        return 0.30
    if "reachability" in step:
        return 0.35
    if "privilege" in step:
        return 0.50
    if "navigation" in step:
        return 0.40
    if "path" in step or "file" in step:
        return 0.45
    return 0.35


def cost_efficiency(cost: float) -> float:
    return round(1.0 - min(max(cost, 0.0), 1.0), 3)


def load_policy_items(policy_files: List[Path]) -> List[Dict[str, Any]]:
    items = []

    for pf in policy_files:
        data = load_json(pf)
        summary = data.get("summary", {})
        ranked = data.get("ranked_decisions", [])

        if not ranked:
            continue

        top = ranked[0]
        exp = summary.get("next_best_experiment") or top.get("next_best_experiment") or {}
        shape = summary.get("top_candidate_shape") or top.get("candidate_shape")
        score = summary.get("top_policy_score") or top.get("policy", {}).get("policy_score") or 0.0

        items.append({
            "policy_file": str(pf),
            "apk_output_dir": str(pf.parent.parent),
            "shape": shape,
            "policy_score": float(score or 0.0),
            "next_best_experiment": exp,
            "finding_allowed": summary.get("finding_allowed", False),
            "raw_policy": data,
        })

    return items


def score_global_items(items: List[Dict[str, Any]], memory: Dict[str, Any], global_budget: float) -> List[Dict[str, Any]]:
    shape_counts: Dict[str, int] = {}
    for i in items:
        shape = i.get("shape") or "unknown"
        shape_counts[shape] = shape_counts.get(shape, 0) + 1

    memory_shapes = set((memory.get("indexes", {}).get("by_shape", {}) or {}).keys())

    scored = []

    for item in items:
        shape = item.get("shape") or "unknown"
        exp = item.get("next_best_experiment") or {}
        cost = infer_cost(exp)

        policy_score = item.get("policy_score", 0.0)

        # Favor experiments that resolve uncertainty and reduce campaign-level ambiguity.
        expected_information_gain = 0.35
        step = str(exp.get("step") or "")
        if "resolve_counter" in step:
            expected_information_gain += 0.25
        if "prove" in step:
            expected_information_gain += 0.20
        if shape not in memory_shapes:
            expected_information_gain += 0.15
        expected_information_gain = min(expected_information_gain, 1.0)

        # Favor less dominant shapes to avoid campaign monoculture.
        shape_diversity_gain = 1.0 / max(shape_counts.get(shape, 1), 1)
        shape_diversity_gain = min(shape_diversity_gain * 2.0, 1.0)

        counter_value = 0.75 if "resolve_counter" in step else 0.35
        promotion_value = 0.70 if shape not in memory_shapes else 0.35

        ce = cost_efficiency(cost)

        global_score = (
            policy_score * DIRECTOR_WEIGHTS["policy_score"]
            + expected_information_gain * DIRECTOR_WEIGHTS["expected_information_gain"]
            + shape_diversity_gain * DIRECTOR_WEIGHTS["shape_diversity_gain"]
            + counter_value * DIRECTOR_WEIGHTS["counterevidence_resolution_value"]
            + ce * DIRECTOR_WEIGHTS["cost_efficiency"]
            + promotion_value * DIRECTOR_WEIGHTS["knowledge_promotion_value"]
        )

        enriched = dict(item)
        enriched["director"] = {
            "global_score": round(global_score, 3),
            "components": {
                "policy_score": round(policy_score, 3),
                "expected_information_gain": round(expected_information_gain, 3),
                "shape_diversity_gain": round(shape_diversity_gain, 3),
                "counterevidence_resolution_value": round(counter_value, 3),
                "cost_efficiency": ce,
                "knowledge_promotion_value": round(promotion_value, 3),
            },
            "estimated_cost": cost,
            "weights": DIRECTOR_WEIGHTS,
        }
        enriched["scheduled_experiment"] = {
            "schedule_id": sid("campaign-exp", item.get("apk_output_dir"), shape, exp.get("step"), exp.get("target")),
            "apk_output_dir": item.get("apk_output_dir"),
            "shape": shape,
            "step": exp.get("step"),
            "target": exp.get("target"),
            "question": exp.get("question"),
            "why": exp.get("why"),
            "finding_allowed": False,
            "candidate_only": True,
        }

        scored.append(enriched)

    scored.sort(key=lambda x: x["director"]["global_score"], reverse=True)

    total_score = sum(x["director"]["global_score"] for x in scored) or 1.0
    for x in scored:
        x["global_budget_allocation"] = {
            "budget_units": round(global_budget * x["director"]["global_score"] / total_score, 3),
            "allocation_reason": "proportional_to_director_global_score",
        }

    return scored


def _to_scheduled(item: Dict[str, Any], rank: int) -> Dict[str, Any]:
    scheduled = dict(item["scheduled_experiment"])
    scheduled["director_global_score"] = item["director"]["global_score"]
    scheduled["budget_units"] = item.get("global_budget_allocation", {}).get("budget_units", 0.0)
    scheduled["estimated_cost"] = item.get("director", {}).get("estimated_cost", 0.35)
    scheduled["rank"] = rank
    return scheduled


def build_schedule(scored: List[Dict[str, Any]], max_experiments: int, global_budget: float) -> List[Dict[str, Any]]:
    selected = []
    used_budget = 0.0
    selected_ids = set()

    # First pass: guarantee at least one experiment per distinct shape when budget allows.
    best_by_shape: Dict[str, Dict[str, Any]] = {}
    for item in scored:
        shape = item.get("shape") or "unknown"
        if shape not in best_by_shape:
            best_by_shape[shape] = item

    for shape, item in sorted(
        best_by_shape.items(),
        key=lambda kv: kv[1]["director"]["global_score"],
        reverse=True,
    ):
        if len(selected) >= max_experiments:
            break

        cost = item.get("director", {}).get("estimated_cost", 0.35)
        sidv = item.get("scheduled_experiment", {}).get("schedule_id")

        if used_budget + cost > global_budget and selected:
            continue

        selected.append(_to_scheduled(item, len(selected) + 1))
        selected_ids.add(sidv)
        used_budget += cost

    # Second pass: fill remaining slots by global score.
    for item in scored:
        if len(selected) >= max_experiments:
            break

        sidv = item.get("scheduled_experiment", {}).get("schedule_id")
        if sidv in selected_ids:
            continue

        cost = item.get("director", {}).get("estimated_cost", 0.35)

        if used_budget + cost > global_budget and selected:
            continue

        selected.append(_to_scheduled(item, len(selected) + 1))
        selected_ids.add(sidv)
        used_budget += cost

    for idx, item in enumerate(selected):
        item["rank"] = idx + 1

    return selected


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Universal Investigation Director v1")
    ap.add_argument("--policy-glob", nargs="+", required=True)
    ap.add_argument("--memory", required=True)
    ap.add_argument("--global-budget", type=float, default=10.0)
    ap.add_argument("--max-experiments", type=int, default=10)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    memory = load_json(args.memory)
    policy_files = collect_policy_files(args.policy_glob)
    items = load_policy_items(policy_files)
    scored = score_global_items(items, memory, args.global_budget)
    schedule = build_schedule(scored, args.max_experiments, args.global_budget)

    shape_distribution: Dict[str, int] = {}
    for s in schedule:
        shape = s.get("shape") or "unknown"
        shape_distribution[shape] = shape_distribution.get(shape, 0) + 1

    result = {
        "schema_version": "universal_investigation_director.v1",
        "created_at": int(time.time()),
        "policy_files_seen": len(policy_files),
        "policy_items_loaded": len(items),
        "director_policy": {
            "purpose": "cross-APK investigation scheduling and metacognitive prioritization",
            "candidate_only": True,
            "finding_allowed": False,
            "global_budget": args.global_budget,
            "max_experiments": args.max_experiments,
            "weights": DIRECTOR_WEIGHTS,
        },
        "summary": {
            "ranked_items": len(scored),
            "scheduled_experiments": len(schedule),
            "top_global_shape": scored[0].get("shape") if scored else None,
            "top_global_score": scored[0].get("director", {}).get("global_score") if scored else None,
            "scheduled_shape_distribution": shape_distribution,
            "finding_allowed": False,
            "ready_for_30_apk_campaign": len(schedule) > 0,
        },
        "ranked_items": scored,
        "campaign_experiment_schedule": schedule,
    }

    save_json(args.out, result)
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
