#!/usr/bin/env python3
import json, sys, hashlib
from pathlib import Path

def load(p):
    p=Path(p)
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except Exception: return {}

def save(p,d):
    Path(p).write_text(json.dumps(d,indent=2,ensure_ascii=False))

def key(x):
    return hashlib.sha1(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()[:16]

def uniq(items, fields):
    out=[]; seen=set()
    for x in items:
        if not isinstance(x,dict): continue
        k="|".join(str(x.get(f,"")) for f in fields) or key(x)
        if k not in seen:
            seen.add(k); out.append(x)
    return out

def main():
    if len(sys.argv)!=3:
        print("Usage: python3 -m phase_b.freeze.dedup_prioritizer <phase_b_brain_dir> <out.json>")
        sys.exit(1)

    d=Path(sys.argv[1])
    report={
        "schema":"vulnlab.freeze.dedup_prioritization.v1",
        "phase_b_brain_dir":str(d),
        "artifacts":{}
    }

    specs={
        "semantic_capabilities.json":("capabilities",["research_object_id","name","type"]),
        "capability_graphs.json":("graphs",["research_object_id","capability_id"]),
        "security_effects.json":("effects",["research_object_id","capability_id","type"]),
        "evidence_models.json":("evidence_models",["research_object_id","type"]),
        "unknown_resolution_tasks.json":("tasks",["research_object_id","task_type","question","proof_requirement"]),
        "dynamic_validation_plans.json":("plans",["research_object_id","source"]),
        "learning_memory.json":("memories",["research_object_id","memory_type","decision_v4","task_type"]),
        "research_strategy_memory.json":("strategies",["research_object_id","strategy_type"])
    }

    for fname,(listkey,fields) in specs.items():
        p=d/fname
        data=load(p)
        items=data.get(listkey) if isinstance(data,dict) else []
        if not isinstance(items,list): items=[]
        deduped=uniq(items,fields)
        report["artifacts"][fname]={
            "list_key":listkey,
            "before":len(items),
            "after":len(deduped),
            "removed":len(items)-len(deduped)
        }

        data[listkey]=deduped
        data.setdefault("freeze_dedup_summary",report["artifacts"][fname])
        save(p,data)

    save(sys.argv[2],report)
    print(json.dumps({"status":"ok","output":sys.argv[2],"artifacts":report["artifacts"]},indent=2))

if __name__=="__main__":
    main()
