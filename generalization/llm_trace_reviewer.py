#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path

def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def summarize_trace(t):
    source_terms=[x.get("term") for x in t.get("source_hits",[])]
    sink_terms=[x.get("term") for x in t.get("sink_hits",[])]
    entry=t.get("entry_component")

    risk_tags=[]
    if "getData" in source_terms or "getIntent" in source_terms:
        risk_tags.append("external_intent_input")
    if "getQueryParameter" in sink_terms:
        risk_tags.append("uri_parameter_parsing")
    if "Uri.parse" in sink_terms or "setData" in sink_terms:
        risk_tags.append("uri_reconstruction_or_forwarding")
    if "startActivity" in sink_terms:
        risk_tags.append("intent_forwarding")
    if "OAuth" in sink_terms:
        risk_tags.append("oauth_flow")
    if "Authorization" in sink_terms or "Bearer" in sink_terms:
        risk_tags.append("auth_token_surface")
    if "FileProvider" in sink_terms or "content://" in sink_terms:
        risk_tags.append("file_or_content_surface")
    if "loadUrl" in sink_terms or "addJavascriptInterface" in sink_terms:
        risk_tags.append("webview_surface")

    if {"external_intent_input","uri_parameter_parsing","uri_reconstruction_or_forwarding"} & set(risk_tags):
        triage="needs_human_or_llm_trace_review"
    else:
        triage="low_static_specificity"

    return {
        "entry_component":entry,
        "static_trace_state":t.get("static_trace_state"),
        "static_trace_score":t.get("static_trace_score"),
        "risk_tags":risk_tags,
        "source_terms":sorted(set(source_terms)),
        "sink_terms":sorted(set(sink_terms)),
        "candidate_files":t.get("candidate_files",[])[:8],
        "triage":triage,
        "review_questions":[
            "Does external Intent data influence URI parameters, redirect targets, or OAuth state?",
            "Is attacker-controlled input forwarded via startActivity, setData, Uri.parse, or WebView load?",
            "Are allowlists, host checks, scheme checks, state/nonce validation, or auth guards present?",
            "Can the route affect account/session state, token handling, file/content access, or privileged navigation?",
            "What exact proof is still missing before this could become a reportable finding?"
        ],
        "llm_guardrails":{
            "finding_allowed":False,
            "candidate_only":True,
            "llm_must_not_claim_vulnerability":True,
            "llm_output_allowed":["triage","missing_evidence","next_experiments","code_review_questions","report_outline_if_validated"]
        }
    }

def main():
    import argparse
    ap=argparse.ArgumentParser(description="LLM Trace Reviewer v1")
    ap.add_argument("--static-trace", required=True)
    ap.add_argument("--probe-interpretation", default="")
    ap.add_argument("--target", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    trace=load(args.static_trace)
    probes=load(args.probe_interpretation) if args.probe_interpretation else {}

    trace_reviews=[summarize_trace(t) for t in trace.get("traces",[])]
    trace_reviews.sort(key=lambda x:(x["static_trace_score"], len(x["risk_tags"])), reverse=True)

    prompt={
        "role":"LLM Trace Reviewer",
        "instruction":"Review structured APK security evidence. Do not invent findings. Do not claim vulnerability. Produce triage, missing evidence, counter-evidence, and next proof experiments only.",
        "target":args.target,
        "package":args.package,
        "candidate_only":True,
        "finding_allowed":False,
        "evidence_inputs":{
            "static_trace_summary":trace.get("summary",{}),
            "probe_interpretation_summary":probes.get("summary",{}),
            "top_trace_reviews":trace_reviews[:5]
        },
        "required_output_schema":{
            "triage_state":"string",
            "most_promising_paths":"array",
            "counter_evidence":"array",
            "missing_evidence":"array",
            "next_experiments":"array",
            "finding_allowed":"must_be_false"
        }
    }

    out={
        "schema_version":"llm_trace_reviewer.v1",
        "created_at":int(time.time()),
        "summary":{
            "target":args.target,
            "package":args.package,
            "traces_reviewed":len(trace_reviews),
            "top_entry_component":trace_reviews[0]["entry_component"] if trace_reviews else None,
            "top_risk_tags":trace_reviews[0]["risk_tags"] if trace_reviews else [],
            "candidate_only":True,
            "finding_allowed":False,
            "ready_for_llm_review":len(trace_reviews)>0
        },
        "trace_reviews":trace_reviews,
        "llm_prompt_packet":prompt
    }

    save(args.out,out)
    print(json.dumps(out["summary"], indent=2))

if __name__=="__main__":
    main()
