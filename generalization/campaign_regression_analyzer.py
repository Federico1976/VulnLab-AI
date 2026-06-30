#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load(path):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("campaign_report")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    report = load(args.campaign_report)
    summary = report.get("summary", {})
    dist = summary.get("primary_shape_distribution", {})
    total = summary.get("training_completed") or summary.get("total_apks") or 0

    risks = []

    for shape, count in dist.items():
        ratio = count / total if total else 0
        if ratio >= 0.70:
            risks.append({
                "risk": "shape_overdominance",
                "shape_id": shape,
                "count": count,
                "total": total,
                "ratio": round(ratio, 3),
                "impact": "possible overmatch or weak discriminative ranking",
                "recommended_fix": "increase negative evidence weight and require stronger shape-specific positive signals"
            })

    avg_conf = summary.get("avg_shape_adjusted_confidence") or 0
    if avg_conf > 0.80:
        risks.append({
            "risk": "confidence_too_high_for_smoke_campaign",
            "avg_shape_adjusted_confidence": avg_conf,
            "impact": "possible overconfidence before dynamic validation",
            "recommended_fix": "cap static-only shape confidence before proof validation"
        })

    result = {
        "schema_version": "campaign_regression_analysis.v1",
        "passed": len(risks) == 0,
        "risk_count": len(risks),
        "risks": risks,
        "summary": summary,
        "freeze_readiness": {
            "ready_for_30_apk_campaign": summary.get("ready_for_next_campaign_scale") is True,
            "requires_shape_calibration_before_freeze": len(risks) > 0,
            "candidate_only_preserved": summary.get("all_candidate_only") is True,
            "finding_block_preserved": summary.get("no_findings_allowed") is True,
        }
    }

    save(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
