#!/usr/bin/env python3
from __future__ import annotations
import json, time, hashlib
from pathlib import Path

def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def eid(*x):
    return hashlib.sha256("|".join(map(str,x)).encode()).hexdigest()[:16]

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--closure", required=True)
    ap.add_argument("--memory", default="output/generalization/research_episode_memory_v1.json")
    ap.add_argument("--out", default="output/generalization/research_episode_memory_v1.json")
    args=ap.parse_args()

    closure=load(args.closure)
    mem=load(args.memory) or {
        "schema_version":"research_episode_memory.v1",
        "episodes":[],
        "indexes":{"by_shape":{}, "by_decision":{}, "by_training_status":{}}
    }

    ep={
        "episode_id":"episode-"+eid(closure.get("package"), closure.get("primary_shape"), closure.get("created_at")),
        "created_at":int(time.time()),
        "package":closure.get("package"),
        "target":closure.get("target"),
        "primary_shape":closure.get("primary_shape"),
        "top_component":closure.get("top_component"),
        "schemes_tested":closure.get("schemes_tested",[]),
        "decision":closure.get("decision",{}),
        "confirmed":closure.get("what_agent_found",{}).get("confirmed",[]),
        "not_confirmed":closure.get("what_agent_found",{}).get("not_confirmed",[]),
        "next_best_experiments":closure.get("next_best_experiments",[]),
        "learning_value":closure.get("learning_value",{}),
        "candidate_only":True,
        "finding_allowed":False
    }

    existing={e["episode_id"] for e in mem.get("episodes",[])}
    if ep["episode_id"] not in existing:
        mem["episodes"].append(ep)

    mem["indexes"]={"by_shape":{}, "by_decision":{}, "by_training_status":{}}
    for e in mem["episodes"]:
        shape=e.get("primary_shape") or "unknown"
        decision=e.get("decision",{}).get("state","unknown")
        status=e.get("learning_value",{}).get("training_status","unknown")
        mem["indexes"]["by_shape"].setdefault(shape,[]).append(e["episode_id"])
        mem["indexes"]["by_decision"].setdefault(decision,[]).append(e["episode_id"])
        mem["indexes"]["by_training_status"].setdefault(status,[]).append(e["episode_id"])

    mem["last_update_summary"]={
        "episodes":len(mem["episodes"]),
        "shapes":len(mem["indexes"]["by_shape"]),
        "candidate_only":True,
        "finding_allowed":False
    }

    save(args.out, mem)
    print(json.dumps(mem["last_update_summary"], indent=2))

if __name__=="__main__":
    main()
