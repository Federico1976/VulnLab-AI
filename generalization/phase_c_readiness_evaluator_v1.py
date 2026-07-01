#!/usr/bin/env python3
"""
Phase C Readiness Evaluator v1.

Verifica se il cervello cognitivo APK Agent è pronto per campagna pratica.
Non produce finding.
Non produce report disclosure.
Valida solo completezza, guardrail, coerenza e readiness.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


REQUIRED_APK_ARTIFACTS = [
    "evidence_story_v1.json",
    "semantic_story_v1.json",
    "hypothesis_priorities_v1.json",
    "universal_investigation_plan_v2.json",
    "reasoning_executor_decision_v1.json",
]

REQUIRED_GLOBAL_ARTIFACTS = [
    "output/knowledge_pattern_memory_v1.json",
    "output/distilled_pattern_memory_v1.json",
    "output/strategy_memory_v2.json",
]

FORBIDDEN_TRUE_FLAGS = [
    "finding_allowed",
    "report_allowed",
    "target_specific_detectors_allowed",
    "learns_findings",
    "learns_cves",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def guardrails_ok(data: Dict[str, Any]) -> bool:
    g = data.get("guardrails") or {}

    candidate_only = g.get("candidate_only")
    if candidate_only is None:
        candidate_only = data.get("candidate_only")

    if candidate_only is not True:
        return False

    for key in FORBIDDEN_TRUE_FLAGS:
        value = g.get(key)
        if value is None:
            value = data.get(key)
        if value is True:
            return False

    return True


def evaluate_apk_dir(apk_dir: Path) -> Dict[str, Any]:
    artifact_status = {}
    guardrail_status = {}
    schemas = {}

    for rel in REQUIRED_APK_ARTIFACTS:
        p = apk_dir / rel
        data = load_json(p)
        artifact_status[rel] = data is not None
        if data:
            guardrail_status[rel] = guardrails_ok(data)
            schemas[rel] = data.get("schema")
        else:
            guardrail_status[rel] = False
            schemas[rel] = None

    decision = load_json(apk_dir / "reasoning_executor_decision_v1.json") or {}
    action = decision.get("current_best_action") or {}

    plan = load_json(apk_dir / "universal_investigation_plan_v2.json") or {}
    plan_steps = plan.get("ordered_plan") or []

    hypotheses = load_json(apk_dir / "hypothesis_priorities_v1.json") or {}
    ranked = hypotheses.get("ranked_hypotheses") or []

    checks = {
        "all_required_artifacts_present": all(artifact_status.values()),
        "all_guardrails_valid": all(guardrail_status.values()),
        "reasoning_executor_selected_action": bool(action.get("experiment_id")),
        "planner_has_steps": len(plan_steps) > 0,
        "hypotheses_ranked": len(ranked) > 0,
        "current_action_is_not_finding": action.get("finding_allowed") is False,
    }

    score = sum(1 for v in checks.values() if v) / len(checks)

    return {
        "apk_dir": str(apk_dir),
        "artifact_status": artifact_status,
        "guardrail_status": guardrail_status,
        "schemas": schemas,
        "checks": checks,
        "readiness_score": round(score, 4),
        "current_best_action": action,
        "ready_for_practical_campaign": score >= 1.0,
    }


def evaluate_global() -> Dict[str, Any]:
    artifact_status = {}
    guardrail_status = {}
    stats = {}

    for rel in REQUIRED_GLOBAL_ARTIFACTS:
        p = Path(rel)
        data = load_json(p)
        artifact_status[rel] = data is not None
        guardrail_status[rel] = guardrails_ok(data) if data else False
        stats[rel] = data.get("stats") if data else None

    checks = {
        "all_global_artifacts_present": all(artifact_status.values()),
        "all_global_guardrails_valid": all(guardrail_status.values()),
        "knowledge_memory_has_patterns": bool((load_json(Path("output/knowledge_pattern_memory_v1.json")) or {}).get("patterns")),
        "distilled_memory_has_clusters": bool((load_json(Path("output/distilled_pattern_memory_v1.json")) or {}).get("distilled_clusters")),
        "strategy_memory_has_strategies": bool((load_json(Path("output/strategy_memory_v2.json")) or {}).get("strategies")),
    }

    score = sum(1 for v in checks.values() if v) / len(checks)

    return {
        "artifact_status": artifact_status,
        "guardrail_status": guardrail_status,
        "stats": stats,
        "checks": checks,
        "readiness_score": round(score, 4),
        "ready": score >= 1.0,
    }


def run(apk_dirs: List[Path], out: Path) -> Dict[str, Any]:
    apk_results = [evaluate_apk_dir(d) for d in apk_dirs]
    global_result = evaluate_global()

    all_ready = global_result["ready"] and all(x["ready_for_practical_campaign"] for x in apk_results)

    result = {
        "schema": "phase_c_readiness_evaluator_v1",
        "generated_at": now_iso(),
        "purpose": "final_phase_c_cognitive_readiness_gate",
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
            "target_specific_detectors_allowed": False,
            "learns_findings": False,
            "learns_cves": False,
        },
        "global_readiness": global_result,
        "apk_readiness": apk_results,
        "summary": {
            "apk_count": len(apk_results),
            "ready_apk_count": sum(1 for x in apk_results if x["ready_for_practical_campaign"]),
            "all_ready_for_heterogeneous_apk_campaign": all_ready,
        },
    }

    save_json(out, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk_dirs", nargs="+")
    parser.add_argument("--out", default="output/phase_c_readiness_report_v1.json")
    args = parser.parse_args()

    result = run([Path(x) for x in args.apk_dirs], Path(args.out))

    print(json.dumps({
        "ok": True,
        "out": args.out,
        "summary": result.get("summary"),
        "guardrails": result.get("guardrails"),
    }, indent=2))


if __name__ == "__main__":
    main()
