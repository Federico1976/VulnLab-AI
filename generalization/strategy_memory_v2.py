#!/usr/bin/env python3
"""
Strategy Memory v2.

Input:
- distilled_pattern_memory_v1.json

Output:
- strategy_memory_v2.json

Purpose:
- Convert distilled pattern clusters into reusable investigation strategies.
- No findings.
- No CVE-specific logic.
- No target-specific detectors.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def norm(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    value = str(value).strip()
    return value if value else "unknown"


def stable_id(*parts: Any) -> str:
    raw = "|".join(norm(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def strategy_family_for_cluster(cluster: Dict[str, Any]) -> str:
    pattern_type = cluster.get("pattern_type")

    if pattern_type in {"counter_evidence_or_blocker", "hypothesis_invalidation_signal"}:
        return "counter_evidence_first"
    if pattern_type == "missing_proof_frequency":
        return "proof_gap_closure"
    if pattern_type == "next_best_experiment_expected_information_gain":
        return "eig_driven_experiment_selection"
    if pattern_type == "proof_mode_tendency":
        return "proof_mode_guided_validation"
    if pattern_type == "strategy_validation_pair":
        return "strategy_validation_pair_reuse"
    if pattern_type == "source_sink_evidence_strength":
        return "source_sink_strengthening"
    if pattern_type == "causal_state_evolution":
        return "causal_state_disambiguation"

    return "general_investigation_strategy"


def recommended_action_for_strategy(strategy_family: str) -> str:
    mapping = {
        "counter_evidence_first": "Resolve recurring blockers before escalating confidence.",
        "proof_gap_closure": "Select experiments that close the most frequent missing proof.",
        "eig_driven_experiment_selection": "Rank experiments by expected information gain and proof-gap closure.",
        "proof_mode_guided_validation": "Choose static, runtime or causal validation according to proof mode.",
        "strategy_validation_pair_reuse": "Reuse validation families proven useful for this abstract shape.",
        "source_sink_strengthening": "Strengthen ordered source-to-sink evidence before reporting.",
        "causal_state_disambiguation": "Convert causal plausibility into reproducible evidence or counter-evidence.",
        "general_investigation_strategy": "Use only as weak triage guidance.",
    }
    return mapping.get(strategy_family, mapping["general_investigation_strategy"])


def build_strategy(cluster: Dict[str, Any]) -> Dict[str, Any]:
    family = strategy_family_for_cluster(cluster)

    score = 0.0
    score += num(cluster.get("distilled_pattern_score")) * 0.45
    score += min(num(cluster.get("support_count")), 20.0) / 20.0 * 0.20
    score += min(num(cluster.get("apk_diversity")), 10.0) / 10.0 * 0.15
    score += num(cluster.get("avg_expected_information_gain")) * 0.20
    score = round(min(score, 1.0), 4)

    return {
        "strategy_id": "strategy_" + stable_id(
            family,
            cluster.get("pattern_type"),
            cluster.get("abstract_shape"),
            cluster.get("framework"),
            cluster.get("proof_mode"),
            cluster.get("validation_family"),
            cluster.get("common_missing_proofs"),
            cluster.get("common_counter_evidence"),
            cluster.get("common_next_best_experiments"),
        ),
        "strategy_family": family,
        "abstract_shape": norm(cluster.get("abstract_shape")),
        "framework": norm(cluster.get("framework")),
        "proof_mode": norm(cluster.get("proof_mode")),
        "validation_family": norm(cluster.get("validation_family")),
        "source_cluster_id": cluster.get("cluster_id"),
        "support_count": cluster.get("support_count"),
        "apk_diversity": cluster.get("apk_diversity"),
        "strategy_reliability_score": score,
        "avg_expected_information_gain": cluster.get("avg_expected_information_gain"),
        "common_missing_proofs": cluster.get("common_missing_proofs", []),
        "common_counter_evidence": cluster.get("common_counter_evidence", []),
        "common_next_best_experiments": cluster.get("common_next_best_experiments", []),
        "recommended_action": recommended_action_for_strategy(family),
        "guardrail_rule": (
            "This strategy may prioritize experiments, but cannot produce findings, "
            "reports, CVE claims or target-specific detectors."
        ),
    }


def build_strategy_memory(distilled_memory: Dict[str, Any]) -> Dict[str, Any]:
    clusters = distilled_memory.get("distilled_clusters", []) or []
    strategies = [build_strategy(c) for c in clusters]

    strategies = sorted(
        strategies,
        key=lambda s: (
            -float(s.get("strategy_reliability_score") or 0),
            -int(s.get("support_count") or 0),
            s.get("strategy_id"),
        ),
    )

    return {
        "schema": "strategy_memory_v2",
        "generated_at": now_iso(),
        "source_schema": distilled_memory.get("schema"),
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
            "target_specific_detectors_allowed": False,
            "learns_findings": False,
            "learns_cves": False,
        },
        "stats": {
            "source_cluster_count": len(clusters),
            "strategy_count": len(strategies),
        },
        "strategies": strategies,
    }


def run(input_distilled: Path, out: Path) -> Dict[str, Any]:
    distilled = load_json(input_distilled)
    strategy_memory = build_strategy_memory(distilled)
    save_json(out, strategy_memory)
    return strategy_memory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--distilled", default="output/distilled_pattern_memory_v1.json")
    parser.add_argument("--out", default="output/strategy_memory_v2.json")
    args = parser.parse_args()

    result = run(Path(args.distilled), Path(args.out))

    print(json.dumps({
        "ok": True,
        "out": args.out,
        "stats": result.get("stats"),
        "guardrails": result.get("guardrails"),
    }, indent=2))


if __name__ == "__main__":
    main()
