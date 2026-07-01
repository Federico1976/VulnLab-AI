#!/usr/bin/env python3
"""
Pattern Distillation Engine v1.

Input:
- knowledge_pattern_memory_v1.json

Output:
- distilled_pattern_memory_v1.json

Purpose:
- Fuse repeated abstract investigative patterns into higher-level pattern clusters.
- No findings.
- No CVE-specific logic.
- No target-specific detectors.
"""

import argparse
import hashlib
import json
from collections import defaultdict
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


def numeric(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def cluster_key(pattern: Dict[str, Any]) -> str:
    return "|".join([
        norm(pattern.get("pattern_type")),
        norm(pattern.get("abstract_shape")),
        norm(pattern.get("framework")),
        norm(pattern.get("strategy_family")),
        norm(pattern.get("validation_family")),
        norm(pattern.get("proof_mode")),
    ])


def distill_cluster(patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
    first = patterns[0]

    apks = sorted(set(
        apk
        for p in patterns
        for apk in p.get("observed_in_apks", [])
    ))

    support_count = sum(int(p.get("support_count", 1)) for p in patterns)

    reliability_scores = [
        numeric(p.get("support_metrics", {}).get("pattern_reliability_score"))
        for p in patterns
    ]
    reliability_scores = [x for x in reliability_scores if x is not None]

    eig_scores = [
        numeric(p.get("support_metrics", {}).get("avg_expected_information_gain"))
        for p in patterns
    ]
    eig_scores = [x for x in eig_scores if x is not None]

    missing_proofs = defaultdict(int)
    counter_evidence = defaultdict(int)
    next_experiments = defaultdict(int)

    for p in patterns:
        weight = int(p.get("support_count", 1))

        if p.get("missing_proof") and p.get("missing_proof") != "unknown":
            missing_proofs[p["missing_proof"]] += weight

        if p.get("counter_evidence") and p.get("counter_evidence") != "unknown":
            counter_evidence[p["counter_evidence"]] += weight

        if p.get("next_best_experiment") and p.get("next_best_experiment") != "unknown":
            next_experiments[p["next_best_experiment"]] += weight

    def top_items(d: Dict[str, int], limit: int = 5) -> List[Dict[str, Any]]:
        return [
            {"value": k, "count": v}
            for k, v in sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        ]

    avg_reliability = round(sum(reliability_scores) / len(reliability_scores), 4) if reliability_scores else None
    avg_eig = round(sum(eig_scores) / len(eig_scores), 4) if eig_scores else None

    distilled_score = 0.0
    distilled_score += min(support_count, 20) * 0.025
    distilled_score += min(len(apks), 10) * 0.04
    if avg_reliability is not None:
        distilled_score += avg_reliability * 0.35
    if avg_eig is not None:
        distilled_score += avg_eig * 0.25
    distilled_score = round(min(distilled_score, 1.0), 4)

    return {
        "cluster_id": "dp_" + stable_id(cluster_key(first)),
        "pattern_type": norm(first.get("pattern_type")),
        "abstract_shape": norm(first.get("abstract_shape")),
        "framework": norm(first.get("framework")),
        "strategy_family": norm(first.get("strategy_family")),
        "validation_family": norm(first.get("validation_family")),
        "proof_mode": norm(first.get("proof_mode")),
        "member_pattern_ids": sorted(p.get("pattern_id") for p in patterns if p.get("pattern_id")),
        "support_count": support_count,
        "apk_diversity": len(apks),
        "observed_in_apks": apks,
        "avg_pattern_reliability_score": avg_reliability,
        "avg_expected_information_gain": avg_eig,
        "distilled_pattern_score": distilled_score,
        "common_missing_proofs": top_items(missing_proofs),
        "common_counter_evidence": top_items(counter_evidence),
        "common_next_best_experiments": top_items(next_experiments),
        "distilled_rule": (
            "Use this cluster as abstract investigation guidance only. "
            "It can prioritize proof experiments, but cannot declare findings."
        ),
    }


def distill_patterns(knowledge_memory: Dict[str, Any]) -> Dict[str, Any]:
    patterns = list((knowledge_memory.get("patterns") or {}).values())

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for pattern in patterns:
        grouped[cluster_key(pattern)].append(pattern)

    clusters = [
        distill_cluster(items)
        for _, items in sorted(grouped.items())
    ]

    clusters = sorted(
        clusters,
        key=lambda c: (
            -float(c.get("distilled_pattern_score") or 0),
            -int(c.get("support_count") or 0),
            c.get("cluster_id"),
        ),
    )

    return {
        "schema": "distilled_pattern_memory_v1",
        "generated_at": now_iso(),
        "source_memory_version": knowledge_memory.get("version"),
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
            "target_specific_detectors_allowed": False,
            "learns_findings": False,
            "learns_cves": False,
        },
        "stats": {
            "source_pattern_count": len(patterns),
            "cluster_count": len(clusters),
        },
        "source_support_metrics": knowledge_memory.get("support_metrics"),
        "distilled_clusters": clusters,
    }


def run(input_memory: Path, out: Path) -> Dict[str, Any]:
    knowledge = load_json(input_memory)
    distilled = distill_patterns(knowledge)
    save_json(out, distilled)
    return distilled


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory", default="output/knowledge_pattern_memory_v1.json")
    parser.add_argument("--out", default="output/distilled_pattern_memory_v1.json")
    args = parser.parse_args()

    result = run(Path(args.memory), Path(args.out))

    print(json.dumps({
        "ok": True,
        "out": args.out,
        "stats": result.get("stats"),
        "guardrails": result.get("guardrails"),
    }, indent=2))


if __name__ == "__main__":
    main()
