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


def build_decision_profile(strategy: Dict[str, Any], quality: Dict[str, Any]) -> Dict[str, Any]:
    shape = strategy.get("strategy_shape")
    learning = strategy.get("learning", {})
    times_seen = learning.get("times_seen", 0)
    variants = strategy.get("variants", [])

    maturity = quality.get("maturity", "unknown")
    score = quality.get("score", 0.0)
    warnings = quality.get("warnings", [])

    use_when = [
        f"semantic_shape_matches:{shape}",
        "candidate_only=true",
        "finding_allowed=false",
        "dynamic_validation_not_performed",
    ]

    avoid_when = [
        "target_scope_not_authorized",
        "runtime_testing_would_exceed_safe_mode",
        "story_lacks_sink_or_boundary",
    ]

    if shape == "bridge_to_webview_sink":
        use_when += [
            "bridge_entity_present",
            "webview_or_web_content_sink_present",
            "bridge_to_sink_relation_candidate_present",
        ]
        avoid_when += [
            "bridge_is_internal_only_and_unreachable",
            "webview_sink_not_present",
        ]

    elif shape == "entrypoint_to_content_uri_asset":
        use_when += [
            "entrypoint_entity_present",
            "content_uri_or_file_asset_present",
            "content_uri_boundary_present",
        ]
        avoid_when += [
            "provider_not_exported_or_not_reachable",
            "asset_is_not_sensitive_or_not_accessible",
        ]

    elif shape == "bridge_to_file_asset":
        use_when += [
            "bridge_entity_present",
            "file_asset_present",
            "candidate_file_access_capability_present",
        ]
        avoid_when += [
            "bridge_has_no_file_access_path",
            "file_asset_is_app_private_and_unreachable",
        ]

    training_needs = []

    if times_seen < 10:
        training_needs.append("collect_more_cases_for_strategy_shape")

    if "high_variant_diversity" in warnings:
        training_needs.append("distill_variants_into_substrategies")

    if maturity != "mature":
        training_needs.append("increase_validation_outcome_coverage")

    return {
        "strategy_id": strategy.get("strategy_id"),
        "strategy_name": strategy.get("strategy_name"),
        "strategy_shape": shape,
        "decision_score": score,
        "maturity": maturity,
        "times_seen": times_seen,
        "variants": len(variants),
        "use_when": use_when,
        "avoid_when": avoid_when,
        "preferred_experiment_order": strategy.get("best_experiment_order", []),
        "counterevidence_to_seek": strategy.get("counter_evidence_patterns", []),
        "training_needs": training_needs,
        "warnings": warnings,
    }


def build_v3(memory_v2: Dict[str, Any], quality_v2: Dict[str, Any]) -> Dict[str, Any]:
    qmap = {
        q.get("strategy_id"): q
        for q in quality_v2.get("evaluations", [])
    }

    profiles = []

    for strategy in memory_v2.get("strategies", []):
        q = qmap.get(strategy.get("strategy_id"), {})
        profiles.append(build_decision_profile(strategy, q))

    by_maturity: Dict[str, int] = {}
    by_shape: Dict[str, int] = {}

    for p in profiles:
        by_maturity[p["maturity"]] = by_maturity.get(p["maturity"], 0) + 1
        by_shape[p["strategy_shape"]] = by_shape.get(p["strategy_shape"], 0) + 1

    return {
        "schema": "research_strategy_memory_v3",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "decision-ready strategy memory: when to use, avoid, train, and seek counterevidence",
        "summary": {
            "strategies": len(profiles),
            "by_maturity": by_maturity,
            "by_shape": by_shape,
        },
        "decision_profiles": profiles,
    }


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: python3 -m memory.research_strategy_memory_v3 <research_strategy_memory_v2.json> <research_strategy_quality_v2.json> <research_strategy_memory_v3.json>")
        sys.exit(1)

    memory_v2 = load_json(Path(sys.argv[1]))
    quality_v2 = load_json(Path(sys.argv[2]))
    out = Path(sys.argv[3])

    result = build_v3(memory_v2, quality_v2)
    save_json(out, result)

    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
