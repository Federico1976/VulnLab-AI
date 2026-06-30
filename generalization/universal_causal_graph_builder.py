#!/usr/bin/env python3
from __future__ import annotations
import json, time, hashlib
from pathlib import Path
from typing import Any, Dict, List

SOURCE_TERMS = ["getIntent", "getData", "getDataString", "getExtras", "onCreate", "onNewIntent"]
ROUTER_TERMS = ["deeplink", "router", "navigation", "destination", "route", "Uri.parse", "getQueryParameter"]
TRANSFORM_TERMS = ["setData", "putExtra", "normalize", "parse", "toString", "builder", "appendQueryParameter"]
SINK_TERMS = ["startActivity", "loadUrl", "evaluateJavascript", "addJavascriptInterface", "Authorization", "OAuth", "FileProvider", "content://", "openFile"]
COUNTER_TERMS = ["allowlist", "whitelist", "host", "scheme", "validate", "verify", "sanitize", "nonce", "state", "not_exported", "permission"]

def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() and p.is_file() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def sid(*x):
    return hashlib.sha256("|".join(map(str,x)).encode()).hexdigest()[:16]

def node(kind, label, **kw):
    nid=f"{kind}-{sid(label, kw.get('file',''), kw.get('term',''))}"
    return {"id":nid, "kind":kind, "label":label, **kw}

def edge(src, dst, kind, **kw):
    return {"id":f"edge-{sid(src,dst,kind)}", "source":src, "target":dst, "kind":kind, **kw}

def hits_to_nodes(trace: Dict[str,Any]) -> Dict[str,List[Dict[str,Any]]]:
    groups={"source":[], "router":[], "transform":[], "sink":[], "counter_evidence":[]}
    entry=trace.get("entry_component") or "unknown_entry"

    for h in trace.get("source_hits", []):
        groups["source"].append(node("source", h.get("term"), file=h.get("file"), entry_component=entry))

    for h in trace.get("sink_hits", []):
        term=h.get("term") or ""
        f=h.get("file")
        if term in ROUTER_TERMS:
            groups["router"].append(node("router", term, file=f, entry_component=entry))
        elif term in TRANSFORM_TERMS:
            groups["transform"].append(node("transform", term, file=f, entry_component=entry))
        elif term in SINK_TERMS:
            groups["sink"].append(node("sink", term, file=f, entry_component=entry))

    # infer counter-evidence from files when possible
    for f in trace.get("candidate_files", [])[:8]:
        try:
            text=Path(f).read_text(errors="ignore")
        except Exception:
            text=""
        low=text.lower()
        for term in COUNTER_TERMS:
            if term.lower() in low:
                groups["counter_evidence"].append(node("counter_evidence", term, file=f, entry_component=entry))

    return groups

def build_subgraph(trace):
    entry_label=trace.get("entry_component") or "unknown_entry"
    entry=node("entrypoint", entry_label, entry_component=entry_label)
    groups=hits_to_nodes(trace)

    nodes=[entry]
    edges=[]
    for kind in ["source","router","transform","sink","counter_evidence"]:
        # de-dupe
        seen=set()
        clean=[]
        for n in groups[kind]:
            if n["id"] not in seen:
                clean.append(n); seen.add(n["id"])
        groups[kind]=clean
        nodes.extend(clean)

    def connect_many(srcs, dsts, kind):
        for a in srcs:
            for b in dsts:
                edges.append(edge(a["id"], b["id"], kind, confidence="inferred_static", candidate_only=True))

    connect_many([entry], groups["source"], "reads")
    connect_many(groups["source"], groups["router"], "routes_or_parses")
    connect_many(groups["router"] or groups["source"], groups["transform"], "transforms_or_forwards")
    connect_many(groups["transform"] or groups["router"] or groups["source"], groups["sink"], "reaches_candidate_sink")
    connect_many(groups["counter_evidence"], groups["sink"] or groups["router"] or groups["source"], "may_guard_or_sanitize")

    source_count=len(groups["source"])
    sink_count=len(groups["sink"])
    router_count=len(groups["router"])
    transform_count=len(groups["transform"])
    counter_count=len(groups["counter_evidence"])

    if source_count and sink_count and (router_count or transform_count):
        state="candidate_causal_path"
        score=0.72
    elif source_count and sink_count:
        state="source_sink_same_surface_needs_causal_edge"
        score=0.55
    elif source_count:
        state="source_only"
        score=0.3
    else:
        state="weak_or_unknown"

        score=0.1

    score=max(0.0, min(1.0, score - min(counter_count,3)*0.04))

    return {
        "entry_component": entry_label,
        "causal_state": state,
        "causal_score": round(score,3),
        "nodes": nodes,
        "edges": edges,
        "missing_edges": [
            "runtime marker propagation",
            "ordered method-level call chain",
            "sanitizer decision",
            "impact proof"
        ],
        "candidate_only": True,
        "finding_allowed": False
    }

def main():
    import argparse
    ap=argparse.ArgumentParser(description="Universal Causal Graph Builder v1")
    ap.add_argument("--static-trace", required=True)
    ap.add_argument("--probe-interpretation", default="")
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    static=load(args.static_trace)
    probes=load(args.probe_interpretation) if args.probe_interpretation else {}

    subgraphs=[build_subgraph(t) for t in static.get("traces", [])]
    subgraphs.sort(key=lambda x:x["causal_score"], reverse=True)

    all_nodes={}
    all_edges={}
    for sg in subgraphs:
        for n in sg["nodes"]:
            all_nodes[n["id"]]=n
        for e in sg["edges"]:
            all_edges[e["id"]]=e

    out={
        "schema_version":"universal_causal_graph.v1",
        "created_at":int(time.time()),
        "source_static_trace":args.static_trace,
        "source_probe_interpretation":args.probe_interpretation or None,
        "summary":{
            "subgraphs":len(subgraphs),
            "nodes":len(all_nodes),
            "edges":len(all_edges),
            "top_entry_component":subgraphs[0]["entry_component"] if subgraphs else None,
            "top_causal_state":subgraphs[0]["causal_state"] if subgraphs else None,
            "top_causal_score":subgraphs[0]["causal_score"] if subgraphs else 0,
            "probe_research_state":probes.get("summary",{}).get("research_state"),
            "candidate_only":True,
            "finding_allowed":False,
            "next_step":"feed_universal_causal_graph_to_source_to_sink_resolver_and_llm_reviewer"
        },
        "nodes":list(all_nodes.values()),
        "edges":list(all_edges.values()),
        "subgraphs":subgraphs
    }

    save(args.out,out)
    print(json.dumps(out["summary"], indent=2))

if __name__=="__main__":
    main()
