from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def score_strategy(strategy: Dict[str, Any]) -> Dict[str, Any]:
    learning = strategy.get("learning", {})
    variants = strategy.get("variants", [])

    times_seen = learning.get("times_seen", 0)
    variant_count = len(variants)

    warnings: List[str] = []

    if times_seen < 5:
        warnings.append("low_experience")
    if variant_count > 12:
        warnings.append("high_variant_diversity")
    if not strategy.get("best_experiment_order"):
        warnings.append("missing_experiment_order")
    if not strategy.get("counter_evidence_patterns"):
        warnings.append("missing_counter_evidence_patterns")

    score = 1.0

    if "low_experience" in warnings:
        score -= 0.35
    if "high_variant_diversity" in warnings:
        score -= 0.15
    if "missing_experiment_order" in warnings:
        score -= 0.25
    if "missing_counter_evidence_patterns" in warnings:
        score -= 0.20

    score = max(round(score, 2), 0.0)

    if score >= 0.85:
        maturity = "mature"
    elif score >= 0.65:
        maturity = "usable"
    elif score >= 0.40:
        maturity = "needs_training"
    else:
        maturity = "immature"

    return {
        "strategy_id": strategy.get("strategy_id"),
        "strategy_name": strategy.get("strategy_name"),
        "strategy_shape": strategy.get("strategy_shape"),
        "times_seen": times_seen,
        "variants": variant_count,
        "score": score,
        "maturity": maturity,
        "warnings": warnings,
        "recommended_next_training": recommended_training(strategy, warnings),
    }


def recommended_training(strategy: Dict[str, Any], warnings: List[str]) -> List[str]:
    shape = strategy.get("strategy_shape")
    recs: List[str] = []

    if "low_experience" in warnings:
        recs.append(f"collect_more_examples_for_shape:{shape}")

    if "high_variant_diversity" in warnings:
        recs.append(f"distill_variants_into_substrategies:{shape}")

    if shape == "bridge_to_webview_sink":
        recs.append("train_bridge_to_sink_experiment_order")
        recs.append("collect_counterexamples_where_bridge_does_not_reach_webview")

    if shape == "entrypoint_to_content_uri_asset":
        recs.append("train_content_uri_boundary_validation")
        recs.append("collect_counterexamples_where_fileprovider_is_not_externally_reachable")

    if shape == "bridge_to_file_asset":
        recs.append("collect_more_bridge_to_file_asset_cases")

    return list(dict.fromkeys(recs))


def evaluate(memory: Dict[str, Any]) -> Dict[str, Any]:
    evaluations = [score_strategy(s) for s in memory.get("strategies", [])]

    by_maturity: Dict[str, int] = {}
    for e in evaluations:
        by_maturity[e["maturity"]] = by_maturity.get(e["maturity"], 0) + 1

    return {
        "schema": "research_strategy_quality_v2",
        "candidate_only": True,
        "finding_allowed": False,
        "source_schema": memory.get("schema"),
        "summary": {
            "strategies": len(evaluations),
            "by_maturity": by_maturity,
        },
        "evaluations": evaluations,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 -m memory.research_strategy_quality_v2 <research_strategy_memory_v2.json> <quality_report.json>")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2])

    memory = load_json(inp)
    report = evaluate(memory)
    save_json(out, report)

    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
