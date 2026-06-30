#!/usr/bin/env python3
from __future__ import annotations
import json, re, time
from pathlib import Path

SINK_TERMS = [
    "loadUrl", "evaluateJavascript", "addJavascriptInterface",
    "startActivity", "setData", "Uri.parse",
    "Intent", "Authorization", "Bearer", "OAuth", "redirect",
    "FileProvider", "content://", "openFile", "getQueryParameter"
]

SOURCE_TERMS = [
    "getIntent", "getData", "getDataString", "getExtras",
    "onCreate", "onNewIntent", "Intent.ACTION_VIEW"
]

def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def grep_file(path):
    try:
        return Path(path).read_text(errors="ignore")
    except Exception:
        return ""

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--paths", required=True)
    ap.add_argument("--code-dir", required=True)
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    paths=load(args.paths).get("resolved_paths", [])
    code_dir=Path(args.code_dir)

    traces=[]

    for p in paths:
        comp=(p.get("entry_component") or "").split(".")[-1]
        if not comp:
            continue

        candidate_files=[]
        for f in code_dir.rglob("*.java"):
            if comp in f.name or comp.lower() in str(f).lower():
                candidate_files.append(f)

        source_hits=[]
        sink_hits=[]

        for f in candidate_files[:20]:
            text=grep_file(f)
            for term in SOURCE_TERMS:
                if term in text:
                    source_hits.append({"file":str(f), "term":term})
            for term in SINK_TERMS:
                if term in text:
                    sink_hits.append({"file":str(f), "term":term})

        if source_hits and sink_hits:
            state="static_source_and_sink_terms_in_entry_surface"
            score=0.65
            next_step="manual_or_llm_assisted_trace_review"
        elif source_hits:
            state="static_source_seen_sink_not_local"
            score=0.45
            next_step="expand_trace_to_called_classes"
        elif sink_hits:
            state="static_sink_seen_source_not_local"
            score=0.35
            next_step="resolve_entrypoint_reachability_to_sink_class"
        else:
            state="static_trace_not_found"
            score=0.0
            next_step="deprioritize_or_use_cpg_trace"

        traces.append({
            "entry_component":p.get("entry_component"),
            "causal_state":p.get("causal_state"),
            "path_score":p.get("path_score"),
            "candidate_files":[str(x) for x in candidate_files[:20]],
            "source_hits":source_hits[:30],
            "sink_hits":sink_hits[:30],
            "static_trace_state":state,
            "static_trace_score":score,
            "next_step":next_step,
            "candidate_only":True,
            "finding_allowed":False
        })

    traces.sort(key=lambda x:(x["static_trace_score"], x["path_score"]), reverse=True)

    out={
        "schema_version":"static_trace_resolver.v1",
        "created_at":int(time.time()),
        "summary":{
            "entries_analyzed":len(traces),
            "top_entry_component":traces[0]["entry_component"] if traces else None,
            "top_static_trace_state":traces[0]["static_trace_state"] if traces else None,
            "top_static_trace_score":traces[0]["static_trace_score"] if traces else 0,
            "candidate_only":True,
            "finding_allowed":False,
            "next_step":traces[0]["next_step"] if traces else "no_trace"
        },
        "traces":traces
    }

    save(args.out,out)
    print(json.dumps(out["summary"], indent=2))

if __name__=="__main__":
    main()
