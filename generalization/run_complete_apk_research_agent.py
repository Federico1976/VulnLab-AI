#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path

def sh(cmd):
    r=subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return {"cmd":cmd,"ok":r.returncode==0,"stdout":r.stdout[-6000:],"stderr":r.stderr[-6000:]}

def load(p):
    p=Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d,indent=2,ensure_ascii=False))

def main():
    import argparse
    ap=argparse.ArgumentParser(description="Complete APK Research Agent v1")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--cognitive-graph", default="output/universal_cognitive_graph_v2.json")
    ap.add_argument("--external-knowledge", default="output/generalization/external_knowledge_distilled_v1.json")
    ap.add_argument("--campaign-name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--run-dynamic-probes", action="store_true")
    ap.add_argument("--package", default="")
    args=ap.parse_args()

    started=time.time()

    orch_out=f"output/generalization/{args.campaign_name}_orchestrated_report.json"

    steps=[]

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

    orch=load(orch_out)
    manifest=load(args.manifest)
    prepared=[x for x in manifest if x.get("status")=="prepared"]

    episode_updates=[]
    closure_reports=[]

    for item in prepared[:args.limit]:
        out_dir=Path(item["output_dir"])
        gen=out_dir/"generalization"

        proof_candidates = [
            gen/"evidence_proof_graph_v1.json",
            out_dir/"evidence_proof_graph_v1.json",
        ]
        proof = next((x for x in proof_candidates if x.exists()), proof_candidates[0])

        runtime_candidates = [
            out_dir/"runtime_evidence_normalized_v1.json",
            gen/"runtime_evidence_normalized_v1.json",
            Path("output/bugbounty/opera_android/opera_runtime_evidence_normalized_v1.json"),
        ]
        runtime = next((x for x in runtime_candidates if x.exists()), runtime_candidates[0])

        closure_candidates = [
            out_dir/"research_closure_report_v1.json",
            gen/"research_closure_report_v1.json",
            Path("output/bugbounty/opera_android/opera_research_closure_report_v1.json"),
        ]
        closure = next((x for x in closure_candidates if x.exists()), closure_candidates[0])

        # Generic closure is created only if normalized runtime exists.
        # If not, preserve non-reportable candidate state.
        if proof.exists() and runtime.exists() and not closure.exists():
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.opera_research_closure_report "
                f"--proof {proof} "
                f"--runtime {runtime} "
                f"--out {closure}"
            ))

        source_to_sink = out_dir/"source_to_sink_paths_v1.json"
        local_plan = gen/"local_investigation_plan_v1.json"
        research_objects = out_dir/"phase_b"/"merged_research_objects.json"

        if local_plan.exists() and research_objects.exists():
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.source_to_sink_causal_path_resolver "
                f"--local-plan {local_plan} "
                f"--research-objects {research_objects} "
                f"--out {source_to_sink}"
            ))

        source_to_sink_plan = out_dir/"runtime_source_to_sink_plan_v1.json"
        source_to_sink_results = out_dir/"source_to_sink_probe_results_v1.json"
        source_to_sink_interpretation = out_dir/"source_to_sink_probe_interpretation_v1.json"

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

        if closure.exists():
            closure_reports.append(str(closure))
            steps.append(sh(
                f"PYTHONPATH=$PWD python3 -m generalization.research_episode_memory_writer "
                f"--closure {closure} "
                f"--memory output/generalization/research_episode_memory_v1.json "
                f"--out output/generalization/research_episode_memory_v1.json"
            ))
            episode_updates.append(str(closure))

    final={
        "schema_version":"complete_apk_research_agent_run.v1",
        "created_at":int(time.time()),
        "campaign_name":args.campaign_name,
        "manifest":args.manifest,
        "orchestrator_report":orch_out,
        "summary":{
            "apk_count":len(prepared[:args.limit]),
            "orchestrator_ok":steps[0]["ok"] if steps else False,
            "pipeline_completed":orch.get("summary",{}).get("pipeline_completed"),
            "training_completed":orch.get("summary",{}).get("training_completed"),
            "policy_completed":orch.get("summary",{}).get("policy_completed"),
            "proof_graph_completed":orch.get("summary",{}).get("proof_graph_completed"),
            "closure_reports":len(closure_reports),
            "episode_updates":len(episode_updates),
            "dynamic_source_to_sink_enabled":args.run_dynamic_probes,
            "candidate_only":True,
            "finding_allowed":False,
            "elapsed_sec":round(time.time()-started,2)
        },
        "steps":steps,
        "closure_reports":closure_reports,
        "episode_updates":episode_updates,
        "orchestrator_summary":orch.get("summary",{})
    }

    save(args.out, final)
    print(json.dumps(final["summary"],indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
