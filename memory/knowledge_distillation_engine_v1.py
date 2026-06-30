from __future__ import annotations

import json
import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List


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


def distill_pattern(strategy: Dict[str, Any], calibration: Dict[str, Any]) -> Dict[str, Any]:
    shape = strategy.get("strategy_shape")
    maturity = strategy.get("maturity")
    priority = calibration.get("priority")
    confidence = calibration.get("calibrated_confidence")

    return {
        "pattern_id": stable_id("PATTERN1", shape),
        "compression_level": "pattern",
        "pattern_shape": shape,
        "candidate_only": True,
        "finding_allowed": False,
        "maturity": maturity,
        "priority": priority,
        "calibrated_confidence": confidence,
        "core_question": core_question(shape),
        "causal_form": causal_form(shape),
        "preferred_experiment_order": strategy.get("preferred_experiment_order", []),
        "counterevidence_to_seek": strategy.get("counterevidence_to_seek", []),
        "avoid_when": strategy.get("avoid_when", []),
        "training_needs": strategy.get("training_needs", []),
        "source_strategy_id": strategy.get("strategy_id"),
    }


def core_question(shape: str) -> str:
    if shape == "bridge_to_webview_sink":
        return "Can framework/native bridge-controlled behavior reach a WebView or web-content sink?"

    if shape == "entrypoint_to_content_uri_asset":
        return "Can an entrypoint cross a content URI or file asset boundary at runtime?"

    if shape == "bridge_to_file_asset":
        return "Can bridge-controlled behavior reach file-backed assets or file sinks?"

    return "Can the candidate semantic story be reached and validated at runtime?"


def causal_form(shape: str) -> List[str]:
    if shape == "bridge_to_webview_sink":
        return [
            "BridgeEntity",
            "TrustBoundaryEntity",
            "CapabilityEntity",
            "PropagationEntity",
            "SinkEntity",
            "SecurityControlEntity",
        ]

    if shape == "entrypoint_to_content_uri_asset":
        return [
            "EntrypointEntity",
            "TrustBoundaryEntity",
            "AssetEntity",
            "CapabilityEntity",
            "PropagationEntity",
            "SecurityControlEntity",
        ]

    if shape == "bridge_to_file_asset":
        return [
            "BridgeEntity",
            "AssetEntity",
            "CapabilityEntity",
            "PropagationEntity",
            "SinkEntity",
            "SecurityControlEntity",
        ]

    return [
        "RuntimeArtifactEntity",
        "CapabilityEntity",
        "TrustBoundaryEntity",
        "SinkEntity",
    ]


def distill_strategy(patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    families: Dict[str, List[Dict[str, Any]]] = {}

    for p in patterns:
        shape = p.get("pattern_shape", "")
        if "bridge" in shape:
            family = "bridge_boundary_sink_strategy"
        elif "entrypoint" in shape or "content_uri" in shape:
            family = "entrypoint_asset_boundary_strategy"
        else:
            family = "generic_runtime_validation_strategy"

        families.setdefault(family, []).append(p)

    strategies = []

    for family, ps in families.items():
        strategies.append({
            "strategy_id": stable_id("KSTRAT1", family),
            "compression_level": "strategy",
            "strategy_family": family,
            "candidate_only": True,
            "finding_allowed": False,
            "patterns": [p["pattern_id"] for p in ps],
            "pattern_shapes": [p["pattern_shape"] for p in ps],
            "default_reasoning_order": [
                "confirm_runtime_reachability",
                "seek_counterevidence",
                "test_security_controls",
                "trace_source_to_sink",
                "only_then_escalate_to_proof_evaluation",
            ],
            "common_counterevidence": sorted(set(
                ce
                for p in ps
                for ce in p.get("counterevidence_to_seek", [])
            )),
            "training_needs": sorted(set(
                tn
                for p in ps
                for tn in p.get("training_needs", [])
            )),
        })

    return strategies


def distill_meta_strategy(strategies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "meta_strategy_id": "META1-candidate-causal-validation",
            "compression_level": "meta_strategy",
            "candidate_only": True,
            "finding_allowed": False,
            "name": "candidate_causal_validation_before_claim",
            "applies_to_strategy_families": [s["strategy_family"] for s in strategies],
            "principles": [
                "static evidence creates candidate stories, not findings",
                "runtime reachability is the first hard gate",
                "counterevidence must be actively searched",
                "security controls are path breakers until proven otherwise",
                "proof evaluation is required before reportability",
            ],
            "default_guardrails": {
                "candidate_only": True,
                "finding_allowed": False,
                "requires_dynamic_validation": True,
            },
        }
    ]


def build_distillation(strategy_v3: Dict[str, Any], calibration: Dict[str, Any]) -> Dict[str, Any]:
    cal_map = {
        c.get("strategy_id"): c
        for c in calibration.get("calibrated_strategies", [])
    }

    patterns = []

    for profile in strategy_v3.get("decision_profiles", []):
        cal = cal_map.get(profile.get("strategy_id"), {})
        patterns.append(distill_pattern(profile, cal))

    strategies = distill_strategy(patterns)
    meta = distill_meta_strategy(strategies)

    return {
        "schema": "knowledge_distillation_engine_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "compress strategy memory and calibration into pattern, strategy and meta-strategy knowledge",
        "summary": {
            "input_decision_profiles": len(strategy_v3.get("decision_profiles", [])),
            "distilled_patterns": len(patterns),
            "distilled_strategies": len(strategies),
            "meta_strategies": len(meta),
        },
        "patterns": patterns,
        "strategies": strategies,
        "meta_strategies": meta,
    }


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: python3 -m memory.knowledge_distillation_engine_v1 <strategy_memory_v3.json> <confidence_calibration_v1.json> <knowledge_distillation_v1.json>")
        sys.exit(1)

    strategy_v3 = load_json(Path(sys.argv[1]))
    calibration = load_json(Path(sys.argv[2]))
    out = Path(sys.argv[3])

    result = build_distillation(strategy_v3, calibration)
    save_json(out, result)

    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
