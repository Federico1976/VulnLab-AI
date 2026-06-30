#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run_cmd(cmd: List[str], cwd: Path) -> Dict[str, Any]:
    started = time.time()
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=None,
        )
        return {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "duration_sec": round(time.time() - started, 2),
            "stdout_tail": p.stdout[-4000:],
            "stderr_tail": p.stderr[-4000:],
            "cmd": cmd,
        }
    except Exception as e:
        return {
            "ok": False,
            "returncode": -1,
            "duration_sec": round(time.time() - started, 2),
            "error": repr(e),
            "cmd": cmd,
        }


def valid_prepared_items(manifest: List[Dict[str, Any]], limit: int | None = None) -> List[Dict[str, Any]]:
    items = [m for m in manifest if m.get("status") == "prepared" and m.get("apk") and m.get("output_dir")]
    return items[:limit] if limit else items


def run_pipeline_for_item(repo: Path, item: Dict[str, Any]) -> Dict[str, Any]:
    apk = item["apk"]
    out_dir = item["output_dir"]

    cmd = [
        sys.executable,
        "-m",
        "pipelines.run_universal_apk_hunt",
        apk,
        out_dir,
    ]

    result = run_cmd(cmd, cwd=repo)

    return {
        "stage": "universal_apk_hunt",
        "package": item.get("package"),
        "apk": apk,
        "output_dir": out_dir,
        **result,
    }


def run_training(repo: Path, output_dirs: List[str], cognitive_graph: str, out_report: str) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "generalization.campaign_training_runner",
        "--apk-output-dirs",
        *output_dirs,
        "--cognitive-graph",
        cognitive_graph,
        "--out",
        out_report,
    ]

    return {
        "stage": "campaign_training_runner",
        **run_cmd(cmd, cwd=repo),
    }


def run_policy_for_outputs(repo: Path, output_dirs: List[str], external_knowledge: str, budget: float = 10.0) -> List[Dict[str, Any]]:
    results = []

    for out_dir in output_dirs:
        base = Path(out_dir)
        reasoning_session = base / "generalization" / "reasoning_session_v2.json"
        policy_out = base / "generalization" / "policy_engine_v1.json"

        if not reasoning_session.exists():
            results.append({
                "output_dir": out_dir,
                "ok": False,
                "reason": "missing_reasoning_session_v2",
            })
            continue

        cmd = [
            sys.executable,
            "-m",
            "generalization.universal_investigation_policy_engine",
            str(reasoning_session),
            "--memory",
            "output/generalization/incremental_memory_snapshot_v1.json",
            "--external-knowledge",
            external_knowledge,
            "--budget",
            str(budget),
            "--out",
            str(policy_out),
        ]

        run = run_cmd(cmd, cwd=repo)
        policy = load_json(policy_out)

        results.append({
            "output_dir": out_dir,
            "policy_out": str(policy_out),
            "ok": run.get("ok"),
            "run": run,
            "top_candidate_shape": policy.get("summary", {}).get("top_candidate_shape"),
            "top_policy_score": policy.get("summary", {}).get("top_policy_score"),
            "next_best_experiment": policy.get("summary", {}).get("next_best_experiment"),
        })

    return results



def run_local_planner_and_proof_graph(repo: Path, output_dirs: List[str], director_out: str | None = None) -> List[Dict[str, Any]]:
    results = []

    for out_dir in output_dirs:
        base = Path(out_dir)
        gen = base / "generalization"
        phase_b = base / "phase_b"

        policy = gen / "policy_engine_v1.json"
        reasoning = gen / "reasoning_session_v2.json"
        research_objects = phase_b / "merged_research_objects.json"
        local_plan = gen / "local_investigation_plan_v1.json"
        proof_graph = gen / "evidence_proof_graph_v1.json"

        if not policy.exists() or not reasoning.exists() or not research_objects.exists():
            results.append({
                "output_dir": out_dir,
                "ok": False,
                "reason": "missing_policy_reasoning_or_research_objects",
            })
            continue

        director_arg = director_out if director_out else str(policy)

        lp_run = run_cmd([
            sys.executable,
            "-m",
            "generalization.local_investigation_planner",
            "--policy", str(policy),
            "--director", director_arg,
            "--research-objects", str(research_objects),
            "--max-plans", "5",
            "--out", str(local_plan),
        ], cwd=repo)

        epg_run = run_cmd([
            sys.executable,
            "-m",
            "generalization.evidence_proof_graph",
            "--local-plan", str(local_plan),
            "--reasoning", str(reasoning),
            "--policy", str(policy),
            "--out", str(proof_graph),
        ], cwd=repo)

        epg = load_json(proof_graph)

        results.append({
            "output_dir": out_dir,
            "ok": lp_run.get("ok") and epg_run.get("ok"),
            "local_plan": str(local_plan),
            "proof_graph": str(proof_graph),
            "top_component": epg.get("summary", {}).get("top_component"),
            "top_proof_score": epg.get("summary", {}).get("top_proof_score"),
            "top_disclosure_readiness": epg.get("summary", {}).get("top_disclosure_readiness"),
            "finding_allowed": epg.get("summary", {}).get("finding_allowed"),
        })

    return results


def run_distillation(repo: Path, out_snapshot: str, out_guard: str) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "generalization.knowledge_distillation_runner",
        "output/generalization/incremental_memory_snapshot_v1.json",
        "--out",
        out_snapshot,
        "--guard-out",
        out_guard,
    ]

    return {
        "stage": "knowledge_distillation_runner",
        **run_cmd(cmd, cwd=repo),
    }


def summarize(pipeline_results: List[Dict[str, Any]], training_report: Dict[str, Any], distillation_guard: Dict[str, Any]) -> Dict[str, Any]:
    completed_pipeline = [r for r in pipeline_results if r.get("ok")]
    failed_pipeline = [r for r in pipeline_results if not r.get("ok")]

    training_summary = training_report.get("summary", {}) if isinstance(training_report, dict) else {}

    return {
        "total_apks": len(pipeline_results),
        "pipeline_completed": len(completed_pipeline),
        "pipeline_failed": len(failed_pipeline),
        "training_completed": training_summary.get("completed", 0),
        "training_skipped": training_summary.get("skipped", 0),
        "avg_precision_proxy": training_summary.get("avg_precision_proxy"),
        "avg_shape_adjusted_confidence": training_summary.get("avg_shape_adjusted_confidence"),
        "distinct_primary_shapes": training_summary.get("distinct_primary_shapes"),
        "primary_shape_distribution": training_summary.get("primary_shape_distribution", {}),
        "all_candidate_only": training_summary.get("all_candidate_only"),
        "no_findings_allowed": training_summary.get("no_findings_allowed"),
        "all_memory_guards_passed": training_summary.get("all_memory_guards_passed"),
        "distillation_guard_passed": distillation_guard.get("passed") if isinstance(distillation_guard, dict) else None,
        "ready_for_next_campaign_scale": (
            len(completed_pipeline) > 0
            and training_summary.get("all_candidate_only") is True
            and training_summary.get("no_findings_allowed") is True
            and training_summary.get("all_memory_guards_passed") is True
            and distillation_guard.get("passed") is True
        ),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Campaign Orchestrator v1")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--cognitive-graph", required=True)
    parser.add_argument("--campaign-name", default="smoke10")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", required=True)
    parser.add_argument("--external-knowledge", default="output/generalization/external_knowledge_distilled_v1.json")
    parser.add_argument("--policy-budget", type=float, default=10.0)

    args = parser.parse_args()

    repo = Path.cwd()
    manifest = load_json(args.manifest)
    items = valid_prepared_items(manifest, args.limit)

    campaign_dir = Path("output/generalization") / args.campaign_name
    campaign_dir.mkdir(parents=True, exist_ok=True)

    pipeline_results = []

    for item in items:
        print(f"[+] A+B+C pipeline: {item.get('package')} -> {item.get('output_dir')}")
        result = run_pipeline_for_item(repo, item)
        pipeline_results.append(result)

        save_json(campaign_dir / "pipeline_progress.json", pipeline_results)

        if not result.get("ok"):
            print(f"[!] failed: {item.get('package')} returncode={result.get('returncode')}")
        else:
            print(f"[+] completed: {item.get('package')} in {result.get('duration_sec')}s")

    successful_output_dirs = [
        r["output_dir"]
        for r in pipeline_results
        if r.get("ok") and r.get("output_dir")
    ]

    training_report_path = str(campaign_dir / "campaign_training_report.json")
    distillation_snapshot_path = str(campaign_dir / "knowledge_distillation_snapshot.json")
    distillation_guard_path = str(campaign_dir / "knowledge_distillation_guard.json")

    print("[+] running campaign training")
    training_run = run_training(repo, successful_output_dirs, args.cognitive_graph, training_report_path) if successful_output_dirs else {
        "stage": "campaign_training_runner",
        "ok": False,
        "reason": "no_successful_pipeline_outputs",
    }

    print("[+] running policy engine per APK")
    policy_results = run_policy_for_outputs(
        repo,
        successful_output_dirs,
        args.external_knowledge,
        args.policy_budget,
    )

    print("[+] running local investigation planner + evidence proof graph")
    proof_graph_results = run_local_planner_and_proof_graph(repo, successful_output_dirs)

    print("[+] running knowledge distillation")
    distillation_run = run_distillation(repo, distillation_snapshot_path, distillation_guard_path)

    training_report = load_json(training_report_path)
    distillation_guard = load_json(distillation_guard_path)

    final_report = {
        "schema_version": "campaign_orchestrator_report.v1",
        "campaign_name": args.campaign_name,
        "created_at": int(time.time()),
        "manifest": args.manifest,
        "cognitive_graph": args.cognitive_graph,
        "items_requested": len(items),
        "pipeline_results": pipeline_results,
        "training_run": training_run,
        "policy_results": policy_results,
        "proof_graph_results": proof_graph_results,
        "distillation_run": distillation_run,
        "training_report_path": training_report_path,
        "distillation_snapshot_path": distillation_snapshot_path,
        "distillation_guard_path": distillation_guard_path,
        "summary": summarize(pipeline_results, training_report, distillation_guard),
    }

    policy_ok = [p for p in policy_results if p.get("ok")]
    final_report["summary"]["policy_completed"] = len(policy_ok)
    final_report["summary"]["policy_failed"] = len(policy_results) - len(policy_ok)
    final_report["summary"]["avg_policy_score"] = round(
        sum((p.get("top_policy_score") or 0.0) for p in policy_ok) / len(policy_ok),
        3
    ) if policy_ok else 0.0
    final_report["summary"]["top_next_best_experiments"] = [
        {
            "output_dir": p.get("output_dir"),
            "shape": p.get("top_candidate_shape"),
            "policy_score": p.get("top_policy_score"),
            "next_best_experiment": p.get("next_best_experiment"),
        }
        for p in policy_ok[:10]
    ]

    proof_ok = [p for p in proof_graph_results if p.get("ok")]
    final_report["summary"]["proof_graph_completed"] = len(proof_ok)
    final_report["summary"]["proof_graph_failed"] = len(proof_graph_results) - len(proof_ok)
    final_report["summary"]["avg_proof_score"] = round(
        sum((p.get("top_proof_score") or 0.0) for p in proof_ok) / len(proof_ok),
        3
    ) if proof_ok else 0.0
    final_report["summary"]["avg_disclosure_readiness"] = round(
        sum((p.get("top_disclosure_readiness") or 0.0) for p in proof_ok) / len(proof_ok),
        3
    ) if proof_ok else 0.0

    save_json(args.out, final_report)

    print(json.dumps(final_report["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
