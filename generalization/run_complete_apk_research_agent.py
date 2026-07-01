#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from generalization.ollama_llm_reasoner import run_ollama_llm_reasoning
from generalization.evidence_fusion_engine import build_evidence_story


def sh(cmd: str) -> dict:
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "ok": r.returncode == 0,
        "returncode": r.returncode,
        "stdout": r.stdout[-6000:],
        "stderr": r.stderr[-6000:],
    }


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description="Complete APK Research Agent v1")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--cognitive-graph", default="output/universal_cognitive_graph_v2.json")
    ap.add_argument("--external-knowledge", default="output/generalization/external_knowledge_distilled_v1.json")
    ap.add_argument("--campaign-name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--run-dynamic-probes", action="store_true")
    ap.add_argument("--package", default="")
    args = ap.parse_args()

    started = time.time()
    steps = []
    episode_updates = []
    closure_reports = []

    orch_out = f"output/generalization/{args.campaign_name}_orchestrated_report.json"

    steps.append(sh(
        f"PYTHONPATH=$PWD python3 -m generalization.campaign_orchestrator_v1 "
        f"--manifest {args.manifest} "
        f"--cognitive-graph {args.cognitive_graph} "
        f"--campaign-name {args.campaign_name} "
        f"--limit {args.limit} "
        f"--external-knowledge {args.external_knowledge} "
        f"--policy-budget 10 "
        f"--out {orch_out}"
    ))

    manifest = load(args.manifest)
    prepared = [x for x in manifest if x.get("status") == "prepared"]

    for item in prepared[:args.limit]:
        out_dir = Path(item["output_dir"])
        gen = out_dir / "generalization"
        gen.mkdir(parents=True, exist_ok=True)

        proof_candidates = [
            gen / "evidence_proof_graph_v1.json",
            out_dir / "evidence_proof_graph_v1.json",
        ]
        proof = next((x for x in proof_candidates if x.exists()), proof_candidates[0])

        runtime_candidates = [
            out_dir / "runtime_evidence_normalized_v1.json",
            gen / "runtime_evidence_normalized_v1.json",
        ]
        runtime = next((x for x in runtime_candidates if x.exists()), runtime_candidates[0])

        closure = out_dir / "research_closure_report_v1.json"

        if proof.exists() and runtime.exists() and not closure.exists():
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.opera_research_closure_report "
                f"--proof {proof} "
                f"--runtime {runtime} "
                f"--out {closure}"
            ))

        source_to_sink = out_dir / "source_to_sink_paths_v1.json"
        local_plan = gen / "local_investigation_plan_v1.json"
        research_objects = out_dir / "phase_b" / "merged_research_objects.json"

        if local_plan.exists() and research_objects.exists():
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.source_to_sink_causal_path_resolver "
                f"--local-plan {local_plan} "
                f"--research-objects {research_objects} "
                f"--out {source_to_sink}"
            ))

        source_to_sink_plan = out_dir / "runtime_source_to_sink_plan_v1.json"
        source_to_sink_results = out_dir / "source_to_sink_probe_results_v1.json"
        source_to_sink_interpretation = out_dir / "source_to_sink_probe_interpretation_v1.json"

        static_trace = out_dir / "static_trace_v1.json"
        code_dir = out_dir / "code" / "decompiled" / "sources"

        if source_to_sink.exists() and code_dir.exists():
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.static_trace_resolver "
                f"--paths {source_to_sink} "
                f"--code-dir {code_dir} "
                f"--out {static_trace}"
            ))

        if source_to_sink.exists() and args.package:
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.runtime_source_to_sink_instrumentation_planner "
                f"--paths {source_to_sink} "
                f"--package {args.package} "
                f"--out {source_to_sink_plan}"
            ))

        if args.run_dynamic_probes and source_to_sink_plan.exists() and args.package:
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.runtime_source_to_sink_probe_executor "
                f"--plan {source_to_sink_plan} "
                f"--package {args.package} "
                f"--out {source_to_sink_results}"
            ))

            if source_to_sink_results.exists():
                steps.append(sh(
                    f"PYTHONPATH=$PWD python3 -m generalization.source_to_sink_probe_interpreter "
                    f"--results {source_to_sink_results} "
                    f"--package {args.package} "
                    f"--out {source_to_sink_interpretation}"
                ))

        llm_trace_review = out_dir / "llm_trace_reviewer_v1.json"
        causal_graph = out_dir / "universal_causal_graph_v1.json"

        if static_trace.exists():
            probe_arg = f"--probe-interpretation {source_to_sink_interpretation}" if source_to_sink_interpretation.exists() else ""
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.universal_causal_graph_builder "
                f"--static-trace {static_trace} "
                f"{probe_arg} "
                f"--out {causal_graph}"
            ))

        if static_trace.exists() and args.package:
            probe_arg = f"--probe-interpretation {source_to_sink_interpretation}" if source_to_sink_interpretation.exists() else ""
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.llm_trace_reviewer "
                f"--static-trace {static_trace} "
                f"{probe_arg} "
                f"--target '{item.get('target', 'APK Target')}' "
                f"--package {args.package} "
                f"--out {llm_trace_review}"
            ))

        causal_llm_packet = out_dir / "causal_graph_llm_packet_v1.json"

        if causal_graph.exists():
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.causal_graph_llm_packet "
                f"--causal-graph {causal_graph} "
                f"--llm-review {llm_trace_review} "
                f"--target '{item.get('target', 'APK Target')}' "
                f"--package {args.package or item.get('package', '')} "
                f"--out {causal_llm_packet}"
            ))

        ollama_reasoning = out_dir / "ollama_llm_reasoning_v1.json"

        if causal_llm_packet.exists():
            try:
                llm_out = run_ollama_llm_reasoning(
                    packet_path=str(causal_llm_packet),
                    output_path=str(ollama_reasoning),
                )
                steps.append({
                    "cmd": "internal:run_ollama_llm_reasoning",
                    "ok": True,
                    "returncode": 0,
                    "stdout": json.dumps({
                        "out": str(ollama_reasoning),
                        "backend": llm_out.get("backend"),
                        "reasoning_mode": llm_out.get("reasoning_mode"),
                        "fallback_used": llm_out.get("fallback_used"),
                        "finding_allowed": llm_out.get("finding_allowed"),
                        "candidate_only": llm_out.get("candidate_only"),
                        "next_best_experiment": llm_out.get("next_best_experiment"),
                    }, indent=2, ensure_ascii=False),
                    "stderr": ""
                })
            except Exception as e:
                fallback = {
                    "schema": "ollama_llm_reasoning_v1",
                    "backend": "runner_safe_fallback",
                    "reasoning_mode": "safe_fallback",
                    "fallback_used": True,
                    "error": str(e),
                    "finding_allowed": False,
                    "candidate_only": True,
                    "report_allowed": False,
                    "next_best_experiment": {
                        "step": "method_level_trace_review",
                        "target": None,
                        "why": "Runner-level fallback after Ollama reasoning exception."
                    },
                    "missing_proof": [
                        "runtime_marker_propagation",
                        "ordered_source_to_sink_chain",
                        "sanitizer_decision",
                        "impact_proof"
                    ],
                    "counter_evidence": [
                        "no confirmed runtime propagation",
                        "no concrete exploitability proof"
                    ]
                }
                save(ollama_reasoning, fallback)
                steps.append({
                    "cmd": "internal:run_ollama_llm_reasoning",
                    "ok": False,
                    "returncode": 1,
                    "stdout": json.dumps({"out": str(ollama_reasoning)}, indent=2),
                    "stderr": str(e)
                })

        if closure.exists():
            closure_reports.append(str(closure))

        episode = out_dir / "research_episode_memory_v1.json"
        if closure.exists():
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.research_episode_memory_writer "
                f"--closure {closure} "
                f"--out {episode}"
            ))

        evidence_story = out_dir / "evidence_story_v1.json"
        try:
            story = build_evidence_story(args.manifest)
            save(evidence_story, story)
            steps.append({
                "cmd": "internal:build_evidence_story",
                "ok": True,
                "returncode": 0,
                "stdout": json.dumps({
                    "out": str(evidence_story),
                    "entry_component": story.get("entry_component"),
                    "primary_causal_state": story.get("primary_causal_state"),
                    "primary_causal_score": story.get("primary_causal_score"),
                    "evidence_strength": story.get("evidence_strength"),
                    "candidate_only": story.get("candidate_only"),
                    "finding_allowed": story.get("finding_allowed"),
                    "next_best_experiment": story.get("next_best_experiment"),
                }, indent=2, ensure_ascii=False),
                "stderr": ""
            })
        except Exception as e:
            steps.append({
                "cmd": "internal:build_evidence_story",
                "ok": False,
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            })

        if episode.exists():
            episode_updates.append(str(episode))

    final = {
        "schema": "complete_apk_research_agent_v1",
        "campaign": args.campaign_name,
        "manifest": args.manifest,
        "limit": args.limit,
        "duration_seconds": round(time.time() - started, 2),
        "guardrails": {
            "candidate_only_default": True,
            "finding_allowed_requires_concrete_proof": True,
            "dynamic_probes_require_explicit_flag": True,
        },
        "steps": steps,
        "closure_reports": closure_reports,
        "episode_updates": episode_updates,
    }

    save(args.out, final)
    print(json.dumps(final, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
