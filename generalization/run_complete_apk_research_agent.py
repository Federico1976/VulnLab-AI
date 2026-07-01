#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from generalization.ollama_llm_reasoner import run_ollama_llm_reasoning
from generalization.evidence_fusion_engine import build_evidence_story
from generalization.continuous_knowledge_trainer_v1 import train_from_apk_output
from generalization.semantic_story_normalizer_v1 import normalize_apk_output
from generalization.pattern_distillation_engine_v1 import run as run_pattern_distillation
from generalization.strategy_memory_v2 import run as run_strategy_memory
from generalization.hypothesis_prioritizer_v1 import run as run_hypothesis_prioritizer
from generalization.universal_investigation_planner_v2 import run as run_universal_investigation_planner
from generalization.reasoning_executor_v1 import run as run_reasoning_executor


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
    knowledge_memory_updates = []
    semantic_story_updates = []
    distilled_pattern_updates = []
    strategy_memory_updates = []
    hypothesis_priority_updates = []
    universal_plan_updates = []
    reasoning_executor_updates = []

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

        semantic_story = out_dir / "semantic_story_v1.json"
        try:
            story_norm = normalize_apk_output(out_dir, semantic_story)
            semantic_story_updates.append(str(semantic_story))
            steps.append({
                "cmd": "internal:semantic_story_normalizer_v1",
                "ok": True,
                "returncode": 0,
                "stdout": json.dumps({
                    "out": str(semantic_story),
                    "semantic_contract": story_norm.get("semantic_contract"),
                    "guardrails": story_norm.get("guardrails"),
                }, indent=2, ensure_ascii=False),
                "stderr": ""
            })
        except Exception as e:
            steps.append({
                "cmd": "internal:semantic_story_normalizer_v1",
                "ok": False,
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            })

        knowledge_memory = Path("output/knowledge_pattern_memory_v1.json")
        try:
            memory = train_from_apk_output(
                apk_output_dir=out_dir,
                memory_path=knowledge_memory,
            )
            knowledge_memory_updates.append(str(knowledge_memory))
            steps.append({
                "cmd": "internal:continuous_knowledge_trainer_v1",
                "ok": True,
                "returncode": 0,
                "stdout": json.dumps({
                    "memory": str(knowledge_memory),
                    "episode_count": memory.get("stats", {}).get("episode_count"),
                    "pattern_count": memory.get("stats", {}).get("pattern_count"),
                    "guardrails": memory.get("guardrails"),
                }, indent=2, ensure_ascii=False),
                "stderr": ""
            })
        except Exception as e:
            steps.append({
                "cmd": "internal:continuous_knowledge_trainer_v1",
                "ok": False,
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            })

        distilled_patterns = Path("output/distilled_pattern_memory_v1.json")
        try:
            distilled = run_pattern_distillation(
                input_memory=Path("output/knowledge_pattern_memory_v1.json"),
                out=distilled_patterns,
            )
            distilled_pattern_updates.append(str(distilled_patterns))
            steps.append({
                "cmd": "internal:pattern_distillation_engine_v1",
                "ok": True,
                "returncode": 0,
                "stdout": json.dumps({
                    "out": str(distilled_patterns),
                    "stats": distilled.get("stats"),
                    "guardrails": distilled.get("guardrails"),
                }, indent=2, ensure_ascii=False),
                "stderr": ""
            })
        except Exception as e:
            steps.append({
                "cmd": "internal:pattern_distillation_engine_v1",
                "ok": False,
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            })

        strategy_memory = Path("output/strategy_memory_v2.json")
        try:
            strategy = run_strategy_memory(
                input_distilled=Path("output/distilled_pattern_memory_v1.json"),
                out=strategy_memory,
            )
            strategy_memory_updates.append(str(strategy_memory))
            steps.append({
                "cmd": "internal:strategy_memory_v2",
                "ok": True,
                "returncode": 0,
                "stdout": json.dumps({
                    "out": str(strategy_memory),
                    "stats": strategy.get("stats"),
                    "guardrails": strategy.get("guardrails"),
                }, indent=2, ensure_ascii=False),
                "stderr": ""
            })
        except Exception as e:
            steps.append({
                "cmd": "internal:strategy_memory_v2",
                "ok": False,
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            })

        hypothesis_priorities = out_dir / "hypothesis_priorities_v1.json"
        try:
            hyp = run_hypothesis_prioritizer(
                semantic_story_path=out_dir / "semantic_story_v1.json",
                strategy_memory_path=Path("output/strategy_memory_v2.json"),
                out=hypothesis_priorities,
            )
            hypothesis_priority_updates.append(str(hypothesis_priorities))
            steps.append({
                "cmd": "internal:hypothesis_prioritizer_v1",
                "ok": True,
                "returncode": 0,
                "stdout": json.dumps({
                    "out": str(hypothesis_priorities),
                    "stats": hyp.get("stats"),
                    "top_hypothesis": hyp.get("ranked_hypotheses", [{}])[0].get("hypothesis_name"),
                    "guardrails": hyp.get("guardrails"),
                }, indent=2, ensure_ascii=False),
                "stderr": ""
            })
        except Exception as e:
            steps.append({
                "cmd": "internal:hypothesis_prioritizer_v1",
                "ok": False,
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            })

        universal_plan = out_dir / "universal_investigation_plan_v2.json"
        try:
            plan = run_universal_investigation_planner(
                hypothesis_priorities_path=out_dir / "hypothesis_priorities_v1.json",
                out=universal_plan,
                max_steps=8,
            )
            universal_plan_updates.append(str(universal_plan))
            steps.append({
                "cmd": "internal:universal_investigation_planner_v2",
                "ok": True,
                "returncode": 0,
                "stdout": json.dumps({
                    "out": str(universal_plan),
                    "stats": plan.get("stats"),
                    "top_step": plan.get("ordered_plan", [{}])[0].get("experiment_id"),
                    "guardrails": plan.get("guardrails"),
                }, indent=2, ensure_ascii=False),
                "stderr": ""
            })
        except Exception as e:
            steps.append({
                "cmd": "internal:universal_investigation_planner_v2",
                "ok": False,
                "returncode": 1,
                "stdout": "",
                "stderr": str(e)
            })

        reasoning_decision = out_dir / "reasoning_executor_decision_v1.json"
        try:
            decision = run_reasoning_executor(
                apk_output_dir=out_dir,
                out=reasoning_decision,
            )
            reasoning_executor_updates.append(str(reasoning_decision))
            steps.append({
                "cmd": "internal:reasoning_executor_v1",
                "ok": True,
                "returncode": 0,
                "stdout": json.dumps({
                    "out": str(reasoning_decision),
                    "current_best_action": decision.get("current_best_action"),
                    "guardrails": decision.get("guardrails"),
                }, indent=2, ensure_ascii=False),
                "stderr": ""
            })
        except Exception as e:
            steps.append({
                "cmd": "internal:reasoning_executor_v1",
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
        "knowledge_memory_updates": knowledge_memory_updates,
        "semantic_story_updates": semantic_story_updates,
        "distilled_pattern_updates": distilled_pattern_updates,
        "strategy_memory_updates": strategy_memory_updates,
        "hypothesis_priority_updates": hypothesis_priority_updates,
        "universal_plan_updates": universal_plan_updates,
        "reasoning_executor_updates": reasoning_executor_updates,
    }

    save(args.out, final)
    print(json.dumps(final, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
