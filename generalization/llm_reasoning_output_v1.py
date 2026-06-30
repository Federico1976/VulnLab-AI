#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path

def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() and p.is_file() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    import argparse
    ap=argparse.ArgumentParser(description="LLM Reasoning Output v1 - guarded local reviewer")
    ap.add_argument("--packet", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    packet=load(args.packet)
    top=packet.get("top_candidate",{})
    missing=top.get("missing_edges",[])
    node_kinds=set(top.get("node_kinds",[]))
    edge_kinds=set(top.get("edge_kinds",[]))

    counter=[]
    if "counter_evidence" in node_kinds:
        counter.append("Identify whether guard/sanitizer nodes are real validation, allowlist, state/nonce, scheme/host check, or only weak keyword evidence.")
    if "may_guard_or_sanitize" in edge_kinds:
        counter.append("Resolve may_guard_or_sanitize edge before increasing confidence.")

    if "runtime marker propagation" in missing:
        next_exp={
            "goal":"Prove whether attacker-controlled URI marker reaches OAuth/router/sink code path.",
            "safe_command_or_static_task":"Perform method-level trace review from getIntent/getData/getQueryParameter to Uri.parse/setData/startActivity/OAuth handler; then repeat benign marker probe only on the confirmed route.",
            "expected_information_gain":"high",
            "why_this_before_other_tests":"It directly resolves the largest uncertainty: source-to-sink propagation. Without this, runtime activity transitions remain candidate-only."
        }
    else:
        next_exp={
            "goal":"Resolve the highest-confidence missing causal edge.",
            "safe_command_or_static_task":"Inspect ordered method-level call chain and sanitizer decisions for the top causal subgraph.",
            "expected_information_gain":"medium",
            "why_this_before_other_tests":"It reduces false positives before further dynamic probing."
        }

    out={
        "schema_version":"llm_reasoning_output.v1",
        "created_at":int(time.time()),
        "source_packet":args.packet,
        "triage_state":"candidate_needs_trace",
        "most_promising_path":top.get("entry_component"),
        "counter_evidence_to_resolve":counter,
        "missing_proof":missing,
        "next_best_experiment":next_exp,
        "finding_allowed":False,
        "candidate_only":True,
        "llm_guardrail_result":{
            "no_vulnerability_claimed":True,
            "no_report_generated":True,
            "next_step_only":True
        }
    }

    save(args.out,out)
    print(json.dumps({
        "triage_state":out["triage_state"],
        "most_promising_path":out["most_promising_path"],
        "next_best_experiment":out["next_best_experiment"],
        "finding_allowed":False
    }, indent=2))

if __name__=="__main__":
    main()
