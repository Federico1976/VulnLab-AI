#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from generalization.output_layout_resolver import resolve_manifest


TARGETS = [
    {
        "name": "opera",
        "package": "com.opera.browser",
        "manifest": "output/bugbounty/opera_android/opera_android_manifest.json",
        "output_dir": "output/bugbounty_opera_android",
    },
    {
        "name": "skyscanner",
        "package": "net.skyscanner.android.main",
        "manifest": "output/bugbounty/skyscanner_android/skyscanner_android_manifest.json",
        "output_dir": "output/bugbounty_skyscanner_android",
    },
    {
        "name": "opsgenie",
        "package": "com.ifountain.opsgenie",
        "manifest": "output/bugbounty/opsgenie_android/opsgenie_android_manifest.json",
        "output_dir": "output/bugbounty_opsgenie_android",
    },
    {
        "name": "quizlet",
        "package": "com.quizlet.quizletandroid",
        "manifest": "output/bugbounty/quizlet_android/quizlet_android_manifest.json",
        "output_dir": "output/bugbounty_quizlet_android",
    },
    {
        "name": "trello",
        "package": "com.trello",
        "manifest": "output/bugbounty/trello_android/trello_android_manifest.json",
        "output_dir": "output/bugbounty_trello_android",
    },
]


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "ok": r.returncode == 0,
        "returncode": r.returncode,
        "stdout": r.stdout[-8000:],
        "stderr": r.stderr[-8000:],
    }


def artifact_exists(out_dir, name):
    return (Path(out_dir) / name).exists()


def summarize_target(t, report_path):
    out_dir = Path(t["output_dir"])

    layout = resolve_manifest(t["manifest"])
    layout_item = layout.get("items", [{}])[0] if layout.get("items") else {}
    artifacts = layout_item.get("artifacts", {})

    causal = load(artifacts.get("causal_graph"))
    llm = load(artifacts.get("ollama_reasoning"))
    packet = load(artifacts.get("causal_llm_packet"))
    sts = load(artifacts.get("source_to_sink_paths"))
    trace = load(artifacts.get("static_trace"))
    report = load(report_path)

    steps = report.get("steps", [])
    failed_steps = [
        {
            "cmd": s.get("cmd"),
            "returncode": s.get("returncode"),
            "stderr": s.get("stderr"),
        }
        for s in steps
        if not s.get("ok")
    ]

    top_candidate = packet.get("top_candidate", {})

    return {
        "name": t["name"],
        "package": t["package"],
        "manifest": t["manifest"],
        "output_dir": str(out_dir),
        "runner_report": str(report_path),
        "ok": len(failed_steps) == 0,
        "failed_steps": failed_steps,
        "artifacts": layout_item.get("artifact_presence", {}),
        "resolved_artifacts": artifacts,
        "top_entry_component": (
            top_candidate.get("entry_component")
            or causal.get("top_entry_component")
            or sts.get("top_entry_component")
            or trace.get("top_entry_component")
        ),
        "causal_state": top_candidate.get("causal_state") or causal.get("top_causal_state"),
        "causal_score": top_candidate.get("causal_score") or causal.get("top_causal_score"),
        "source_to_sink_state": sts.get("top_causal_state"),
        "static_trace_state": trace.get("top_static_trace_state"),
        "llm_backend": llm.get("backend"),
        "llm_reasoning_mode": llm.get("reasoning_mode"),
        "llm_fallback_used": llm.get("fallback_used"),
        "next_best_experiment": llm.get("next_best_experiment"),
        "missing_proof": llm.get("missing_proof"),
        "guardrails": {
            "candidate_only": llm.get("candidate_only", True),
            "finding_allowed": llm.get("finding_allowed", False),
            "report_allowed": llm.get("report_allowed", False),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Five Bug Bounty APK Regression Manager")
    ap.add_argument("--out", default="output/generalization/five_bounty_regression_matrix_v1.json")
    ap.add_argument("--skip-run", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    started = time.time()
    results = []
    commands = []

    for t in TARGETS[: args.limit]:
        manifest = Path(t["manifest"])
        report_path = Path(f"output/generalization/{t['name']}_complete_regression_report.json")

        if not manifest.exists():
            results.append({
                "name": t["name"],
                "package": t["package"],
                "ok": False,
                "error": f"missing manifest: {manifest}",
            })
            continue

        if not args.skip_run:
            cmd = (
                "PYTHONPATH=$PWD python3 -m generalization.run_complete_apk_research_agent "
                f"--manifest {manifest} "
                f"--campaign-name {t['name']}_complete_regression "
                f"--out {report_path} "
                f"--limit 1 "
                f"--package {t['package']}"
            )
            commands.append(sh(cmd))

        results.append(summarize_target(t, report_path))

    matrix = {
        "schema": "five_bounty_regression_matrix_v1",
        "duration_seconds": round(time.time() - started, 2),
        "targets_total": len(results),
        "targets_ok": sum(1 for r in results if r.get("ok")),
        "targets_failed": sum(1 for r in results if not r.get("ok")),
        "all_candidate_only": all(r.get("guardrails", {}).get("candidate_only") is True for r in results if "guardrails" in r),
        "no_findings_allowed": all(r.get("guardrails", {}).get("finding_allowed") is False for r in results if "guardrails" in r),
        "no_reports_allowed": all(r.get("guardrails", {}).get("report_allowed") is False for r in results if "guardrails" in r),
        "commands": commands,
        "results": results,
    }

    save(args.out, matrix)
    print(json.dumps(matrix, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
