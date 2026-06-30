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
    ap=argparse.ArgumentParser(description="Causal Graph LLM Packet v1")
    ap.add_argument("--causal-graph", required=True)
    ap.add_argument("--llm-review", default="")
    ap.add_argument("--target", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    graph=load(args.causal_graph)
    review=load(args.llm_review) if args.llm_review else {}

    top=(graph.get("subgraphs") or [{}])[0]

    packet={
        "schema_version":"causal_graph_llm_packet.v1",
        "created_at":int(time.time()),
        "target":args.target,
        "package":args.package,
        "guardrails":{
            "candidate_only":True,
            "finding_allowed":False,
            "llm_must_not_claim_vulnerability":True,
            "llm_role":"reasoning_triage_next_experiment_only"
        },
        "causal_summary":graph.get("summary",{}),
        "top_candidate":{
            "entry_component":top.get("entry_component"),
            "causal_state":top.get("causal_state"),
            "causal_score":top.get("causal_score"),
            "missing_edges":top.get("missing_edges",[]),
            "node_kinds":sorted(set(n.get("kind") for n in top.get("nodes",[]))),
            "edge_kinds":sorted(set(e.get("kind") for e in top.get("edges",[])))
        },
        "evidence":{
            "top_nodes":top.get("nodes",[])[:40],
            "top_edges":top.get("edges",[])[:60],
            "llm_trace_review_summary":review.get("summary",{}),
            "trace_reviews":review.get("trace_reviews",[])[:5]
        },
        "required_llm_output":{
            "triage_state":"candidate_needs_trace | weak_candidate | strong_candidate_continue",
            "most_promising_path":"entrypoint/source/router/sink path",
            "counter_evidence_to_resolve":["list"],
            "missing_proof":["list"],
            "next_best_experiment":{
                "goal":"string",
                "safe_command_or_static_task":"string",
                "expected_information_gain":"low|medium|high",
                "why_this_before_other_tests":"string"
            },
            "finding_allowed":False
        },
        "prompt":"Review this structured causal graph. Do not invent facts. Do not claim a vulnerability. Choose the next proof step that maximizes information gain and reduces false positives."
    }

    save(args.out,packet)
    print(json.dumps({
        "ready_for_llm":True,
        "target":args.target,
        "top_entry_component":packet["top_candidate"]["entry_component"],
        "causal_state":packet["top_candidate"]["causal_state"],
        "causal_score":packet["top_candidate"]["causal_score"],
        "finding_allowed":False
    }, indent=2))

if __name__=="__main__":
    main()
