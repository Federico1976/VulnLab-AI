#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import defaultdict


SEVERITY_WEIGHT = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def aggregate_effects(objects):
    by_hyp = defaultdict(list)

    for obj in objects:
        by_hyp[obj["hypothesis_id"]].append(obj)

    aggregated = []

    for hyp_id, objs in by_hyp.items():
        effects_by_type = defaultdict(list)

        for obj in objs:
            for eff in obj.get("effects", []):
                effects_by_type[eff["effect_type"]].append({
                    "task_type": obj["task_type"],
                    "effect": eff,
                })

        hyp_effects = []

        for effect_type, items in effects_by_type.items():
            severity_floor = max(
                (i["effect"].get("severity_floor", "low") for i in items),
                key=lambda s: SEVERITY_WEIGHT.get(s, 0)
            )

            modifiers = sorted({
                m
                for i in items
                for m in i["effect"].get("modifiers", [])
            })

            proof_focus = []
            seen = set()
            for i in items:
                for p in i["effect"].get("proof_focus", []):
                    if p not in seen:
                        seen.add(p)
                        proof_focus.append(p)

            task_support = sorted({i["task_type"] for i in items})

            confidence = "high" if len(task_support) >= 2 else "medium"

            hyp_effects.append({
                "effect_type": effect_type,
                "status": "hypothesis_level_security_effect_candidate",
                "severity_floor": severity_floor,
                "confidence": confidence,
                "task_support_count": len(task_support),
                "supporting_task_types": task_support,
                "modifiers": modifiers,
                "proof_focus": proof_focus,
                "declares_vulnerability": False,
            })

        hyp_effects.sort(
            key=lambda e: (
                SEVERITY_WEIGHT.get(e["severity_floor"], 0),
                e["task_support_count"]
            ),
            reverse=True
        )

        aggregated.append({
            "hypothesis_id": hyp_id,
            "effect_count": len(hyp_effects),
            "effects": hyp_effects,
        })

    aggregated.sort(key=lambda h: h["effect_count"], reverse=True)
    return aggregated


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.security_effects.security_effect_aggregator <security_effects.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())
    objects = data.get("security_effect_objects", [])

    aggregated = aggregate_effects(objects)

    summary = {}
    for h in aggregated:
        for eff in h["effects"]:
            summary[eff["effect_type"]] = summary.get(eff["effect_type"], 0) + 1

    output = {
        "schema": "vulnlab.security_effects_aggregated.v1",
        "input_schema": data.get("schema"),
        "hypothesis_count": len(aggregated),
        "aggregated_effect_count": sum(h["effect_count"] for h in aggregated),
        "summary": summary,
        "hypotheses": aggregated,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "aggregated_effects_are_not_findings": True,
            "requires_proof_evaluator": True,
            "requires_dynamic_validation_for_disclosure": True,
        }
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "hypotheses": len(aggregated),
        "aggregated_effects": output["aggregated_effect_count"],
        "summary": summary,
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
