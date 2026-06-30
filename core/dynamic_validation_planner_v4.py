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


def build_plan(story: Dict[str, Any]) -> Dict[str, Any]:
    exp = story.get("highest_value_experiment", {})
    exp_type = exp.get("experiment_type", "minimal_dynamic_validation_plan")

    steps = []

    if exp_type == "runtime_reachability_probe":
        steps = [
            {
                "step": 1,
                "action": "identify_runtime_entry_condition",
                "goal": "map the candidate story to a realistic runtime trigger",
                "expected_output": "entry condition candidate",
                "safe": True,
            },
            {
                "step": 2,
                "action": "instrument_or_log_reachability",
                "goal": "observe whether the candidate path is reached during normal app execution",
                "expected_output": "reachability observed or not observed",
                "safe": True,
            },
            {
                "step": 3,
                "action": "check_security_control_breakpoints",
                "goal": "verify whether observed controls stop the candidate path",
                "expected_output": "control blocks, allows, or unknown",
                "safe": True,
            },
        ]

    elif exp_type == "source_to_sink_runtime_trace":
        steps = [
            {
                "step": 1,
                "action": "define_candidate_source",
                "goal": "identify candidate-controlled or semi-controlled input",
                "expected_output": "source candidate",
                "safe": True,
            },
            {
                "step": 2,
                "action": "trace_source_to_sink",
                "goal": "observe whether source data reaches the sink",
                "expected_output": "flow confirmed, blocked, or not observed",
                "safe": True,
            },
        ]

    elif exp_type == "control_effectiveness_check":
        steps = [
            {
                "step": 1,
                "action": "enumerate_observed_controls",
                "goal": "list candidate controls affecting the story",
                "expected_output": "control list",
                "safe": True,
            },
            {
                "step": 2,
                "action": "test_control_effectiveness",
                "goal": "verify whether controls break the path",
                "expected_output": "effective, ineffective, or unknown",
                "safe": True,
            },
        ]

    else:
        steps = [
            {
                "step": 1,
                "action": "collect_minimal_runtime_evidence",
                "goal": "reduce uncertainty without claiming a vulnerability",
                "expected_output": "runtime observation",
                "safe": True,
            }
        ]

    return {
        "validation_plan_id": story["evidence_story_id"].replace("EVSTORY4", "DVPLAN4"),
        "source_evidence_story_id": story["evidence_story_id"],
        "candidate_only": True,
        "finding_allowed": False,
        "status": "planned_candidate_validation",
        "priority": exp.get("value", "medium"),
        "experiment_type": exp_type,
        "goal": exp.get("goal"),
        "uncertainty_level": story.get("uncertainty_level"),
        "missing_evidence": story.get("missing_evidence", []),
        "breakpoints": story.get("breakpoints", []),
        "steps": steps,
        "success_criteria": [
            "runtime reachability is observed without unsafe actions",
            "security controls are characterized",
            "source-to-sink relation is confirmed, blocked, or rejected",
        ],
        "stop_conditions": [
            "candidate path is not reachable",
            "security control blocks the path",
            "runtime behavior contradicts static story",
            "test would exceed authorized defensive scope",
        ],
        "post_validation_rule": "even if successful, finding_allowed remains false until explicit proof evaluation confirms reportability",
    }


def build_plans(stories_doc: Dict[str, Any]) -> Dict[str, Any]:
    stories = stories_doc.get("stories", [])
    plans = [build_plan(s) for s in stories]

    by_type: Dict[str, int] = {}
    by_uncertainty: Dict[str, int] = {}

    for p in plans:
        by_type[p["experiment_type"]] = by_type.get(p["experiment_type"], 0) + 1
        by_uncertainty[p["uncertainty_level"]] = by_uncertainty.get(p["uncertainty_level"], 0) + 1

    return {
        "schema": "dynamic_validation_plans_v4",
        "candidate_only": True,
        "finding_allowed": False,
        "source_schema": stories_doc.get("schema"),
        "summary": {
            "plans": len(plans),
            "by_experiment_type": by_type,
            "by_uncertainty": by_uncertainty,
        },
        "plans": plans,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 -m core.dynamic_validation_planner_v4 <evidence_stories_v4.json> <dynamic_validation_plans_v4.json>")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2])

    stories = load_json(inp)
    plans = build_plans(stories)
    save_json(out, plans)

    print(json.dumps(plans["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
