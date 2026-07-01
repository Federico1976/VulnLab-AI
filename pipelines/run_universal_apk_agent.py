#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sh(cmd: str) -> dict:
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "ok": r.returncode == 0,
        "returncode": r.returncode,
        "stdout": r.stdout[-8000:],
        "stderr": r.stderr[-8000:],
    }


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def infer_name(apk_input: Path) -> str:
    name = apk_input.name[:-4] if apk_input.name.endswith(".apk") else apk_input.name
    return name.replace(" ", "_").replace("-", "_").lower()


def build_manifest(path: Path, apk_input: Path, output_dir: Path, name: str, package: str) -> None:
    save_json(path, [{
        "app": name,
        "name": name.lower().replace(" ", "_"),
        "package": package,
        "status": "prepared",
        "apk_path": str(apk_input),
        "apk_dir": str(apk_input if apk_input.is_dir() else apk_input.parent),
        "output_dir": str(output_dir),
        "scope": "authorized_or_open_source_security_research",
        "platform": "android",
        "agent_version": "2.0",
        "candidate_only": True,
        "finding_allowed": False,
        "report_allowed": False
    }])


def summarize(output_dir: Path, readiness_path: Path) -> dict:
    semantic = load_json(output_dir / "semantic_story_v1.json")
    hyp = load_json(output_dir / "hypothesis_priorities_v1.json")
    plan = load_json(output_dir / "universal_investigation_plan_v2.json")
    decision = load_json(output_dir / "reasoning_executor_decision_v1.json")
    readiness = load_json(readiness_path)

    top = (hyp.get("ranked_hypotheses") or [{}])[0]
    best = decision.get("current_best_action") or {}

    return {
        "apk_name": semantic.get("apk_name") or output_dir.name,
        "semantic_contract": semantic.get("semantic_contract"),
        "top_hypothesis": {
            "name": top.get("hypothesis_name"),
            "family": top.get("strategy_family"),
            "score": top.get("priority_score")
        },
        "best_action": {
            "experiment_id": best.get("experiment_id"),
            "role": best.get("experiment_role"),
            "decision_score": best.get("decision_score"),
            "expected_information_gain": best.get("expected_information_gain"),
            "estimated_cost": best.get("estimated_cost"),
            "finding_allowed": best.get("finding_allowed")
        },
        "plan_steps": [
            {
                "order": s.get("order"),
                "experiment_id": s.get("experiment_id"),
                "role": s.get("experiment_role"),
                "uncertainty_reduction": s.get("uncertainty_reduction_score"),
                "finding_allowed": s.get("finding_allowed")
            }
            for s in (plan.get("ordered_plan") or [])[:8]
        ],
        "readiness": readiness.get("summary"),
        "guardrails": decision.get("guardrails") or readiness.get("guardrails")
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="VulnLab-AI 2.0 Universal APK Agent")
    ap.add_argument("apk_input")
    ap.add_argument("output_dir")
    ap.add_argument("--name", default="")
    ap.add_argument("--package", default="")
    ap.add_argument("--campaign-name", default="")
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--run-dynamic-probes", action="store_true")
    ap.add_argument("--continue-on-hunt-failure", action="store_true", default=True)
    args = ap.parse_args()

    started = time.time()
    apk_input = Path(args.apk_input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    name = args.name or infer_name(apk_input)
    campaign = args.campaign_name or f"{name}_v2_universal"

    manifest = output_dir / "universal_agent_manifest_v2.json"
    complete_out = output_dir / "complete_agent_v2_result.json"
    readiness_out = output_dir / "phase_c_readiness_v1.json"
    final_out = output_dir / "universal_agent_final_summary_v2.json"

    steps = []

    hunt = sh(f"PYTHONPATH=$PWD python3 -m pipelines.run_universal_apk_hunt {apk_input} {output_dir}")
    steps.append(hunt)

    build_manifest(manifest, apk_input, output_dir, name, args.package)

    dynamic = " --run-dynamic-probes" if args.run_dynamic_probes else ""

    if hunt["ok"] or args.continue_on_hunt_failure:
        steps.append(sh(
            f"PYTHONPATH=$PWD python3 -m generalization.run_complete_apk_research_agent "
            f"--manifest {manifest} "
            f"--campaign-name {campaign} "
            f"--out {complete_out} "
            f"--limit {args.limit} "
            f"--package '{args.package}'"
            f"{dynamic}"
        ))

        steps.append(sh(
            f"PYTHONPATH=$PWD python3 -m generalization.phase_c_readiness_evaluator_v1 "
            f"{output_dir} --out {readiness_out}"
        ))

    final = {
        "schema": "universal_apk_agent_v2",
        "generated_at": now_iso(),
        "duration_seconds": round(time.time() - started, 2),
        "apk_input": str(apk_input),
        "output_dir": str(output_dir),
        "manifest": str(manifest),
        "complete_agent_result": str(complete_out),
        "readiness_report": str(readiness_out),
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
            "target_specific_detectors_allowed": False,
            "learns_findings": False,
            "learns_cves": False
        },
        "steps": steps,
        "agent_summary": summarize(output_dir, readiness_out)
    }

    save_json(final_out, final)

    print(json.dumps({
        "ok": all(s["ok"] for s in steps),
        "out": str(final_out),
        "summary": final["agent_summary"],
        "failed_steps": [
            {
                "cmd": s["cmd"],
                "returncode": s["returncode"],
                "stderr": s["stderr"][-1500:]
            }
            for s in steps if not s["ok"]
        ],
        "guardrails": final["guardrails"]
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
