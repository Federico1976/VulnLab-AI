import json
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def unique(items: List[Any]) -> List[Any]:
    seen = set()
    out = []
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, dict) else str(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def build_reasoning_plan(matches_doc: Dict[str, Any]) -> Dict[str, Any]:
    matches = matches_doc.get("matches", [])

    selected = [
        m for m in matches
        if m.get("best_match")
        and m["best_match"].get("match_level") in {
            "strong_investigative_match",
            "medium_investigative_match"
        }
    ]

    grouped: Dict[str, Dict[str, Any]] = {}

    for m in selected:
        bm = m["best_match"]
        case_id = bm["case_id"]

        if case_id not in grouped:
            grouped[case_id] = {
                "case_id": case_id,
                "case_title": bm.get("case_title"),
                "matched_patterns": [],
                "reasons": [],
                "strategy_hints": [],
                "evidence_gaps": [],
                "disallowed_claims": []
            }

        grouped[case_id]["matched_patterns"].append({
            "pattern_id": m.get("pattern_id"),
            "observed_shape": m.get("observed_shape"),
            "score": bm.get("score"),
            "match_level": bm.get("match_level")
        })

        grouped[case_id]["reasons"].extend(bm.get("reasons", []))
        grouped[case_id]["strategy_hints"].extend(bm.get("strategy_hints", []))
        grouped[case_id]["evidence_gaps"].extend(bm.get("evidence_gaps", []))
        grouped[case_id]["disallowed_claims"].extend(bm.get("disallowed_claims", []))

    plans = []

    for case_id, group in grouped.items():
        group["reasons"] = sorted(set(group["reasons"]))
        group["strategy_hints"] = sorted(set(group["strategy_hints"]))
        group["evidence_gaps"] = unique(group["evidence_gaps"])
        group["disallowed_claims"] = unique(group["disallowed_claims"])

        plan = {
            "case_id": group["case_id"],
            "case_title": group["case_title"],
            "investigation_status": (
                "strong_knowledge_guided_candidate_investigation"
                if any(x["match_level"] == "strong_investigative_match" for x in group["matched_patterns"])
                else "medium_knowledge_guided_candidate_investigation"
            ),
            "matched_pattern_count": len(group["matched_patterns"]),
            "why_interesting": {
                "summary": (
                    "The APK exposes observed investigation patterns that strongly resemble "
                    "a known DeepLink-to-WebView vulnerability shape. This is not a finding; "
                    "it is a knowledge-guided candidate investigation."
                ),
                "match_reasons": group["reasons"]
            },
            "candidate_scope": {
                "max_current_claim": "candidate_evidence_or_causal_static_evidence",
                "finding_allowed": False,
                "requires_dynamic_validation": True
            },
            "do_not_claim": group["disallowed_claims"],
            "investigation_questions": [
                "Can an external caller trigger the observed entrypoint?",
                "Which URI parts are attacker-controlled at runtime?",
                "Does attacker-controlled URI data reach WebView.loadUrl or equivalent sink?",
                "Is there a strict scheme/host/path allowlist before the sink?",
                "Is the WebView code first-party reachable or only plugin/library scaffolding?",
                "Can negative tests prove that untrusted hosts are rejected?"
            ],
            "recommended_dynamic_validation": [
                {
                    "goal": "Confirm external trigger reachability",
                    "method": "safe adb intent trigger using benign controlled URI",
                    "success_signal": "target component receives the intent"
                },
                {
                    "goal": "Observe sink argument",
                    "method": "instrument or hook WebView.loadUrl/evaluateJavascript equivalent",
                    "success_signal": "controlled URI appears at the sink"
                },
                {
                    "goal": "Check validation boundary",
                    "method": "try trusted and untrusted benign hosts and compare behavior",
                    "success_signal": "untrusted host is blocked before sensitive sink"
                }
            ],
            "strategy_hints": group["strategy_hints"],
            "evidence_gaps": group["evidence_gaps"],
            "matched_patterns": group["matched_patterns"]
        }

        plans.append(plan)

    return {
        "status": "ok",
        "schema": "vulnlab.investigation_reasoning_plan.v1",
        "summary": {
            "investigation_groups": len(plans),
            "patterns_consumed": len(selected),
            "strong_patterns_consumed": sum(
                1 for m in selected
                if m["best_match"].get("match_level") == "strong_investigative_match"
            ),
            "medium_patterns_consumed": sum(
                1 for m in selected
                if m["best_match"].get("match_level") == "medium_investigative_match"
            ),
            "finding_allowed": False,
            "requires_dynamic_validation": True
        },
        "plans": plans
    }


def main() -> None:
    import sys

    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python3 -m phase_c.investigation_patterns.investigation_reasoning_planner "
            "<vulnerability_case_matches_json> <output_json>"
        )

    matches_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = build_reasoning_plan(load_json(matches_path))

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(json.dumps({
        "status": result["status"],
        "schema": result["schema"],
        "summary": result["summary"],
        "output": str(output_path)
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
