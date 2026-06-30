#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, time
from pathlib import Path

def load(p):
    p=Path(p)
    return json.loads(p.read_text()) if p.exists() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False))

def run(cmd):
    t=time.time()
    r=subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=20)
    return {
        "command": cmd,
        "returncode": r.returncode,
        "stdout": r.stdout[-4000:],
        "stderr": r.stderr[-4000:],
        "duration_sec": round(time.time()-t, 2),
        "executed": True,
        "success": r.returncode == 0
    }

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--proof-graph", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=6)
    args=ap.parse_args()

    g=load(args.proof_graph)
    validations=g["proof_graphs"][0].get("validation_evidence", [])[:args.limit]
    results=[]

    subprocess.run("adb logcat -c", shell=True)

    for v in validations:
        cmd=v.get("command","")
        if not cmd or cmd.strip().startswith("#"):
            continue

        res=run(cmd)
        time.sleep(2)
        log=subprocess.run(
            "adb logcat -d -t 300 | grep -iE 'opera|activity|intent|url|navigation|chromium|webview|denied|blocked|exception|security' | tail -120",
            shell=True, text=True, capture_output=True
        )

        results.append({
            "validation_id": v.get("validation_id"),
            "validates_node": v.get("validates_node"),
            "validates_edge": v.get("validates_edge"),
            "expected_confidence_gain": v.get("expected_confidence_gain"),
            "runtime_result": res,
            "log_observation": log.stdout[-6000:],
            "interpretation": {
                "component_launch_observed": res["success"],
                "needs_manual_ui_observation": True,
                "finding_allowed": False,
                "candidate_only": True
            }
        })

    out={
        "schema_version":"dynamic_validation_result_collector.v1",
        "created_at": int(time.time()),
        "source_proof_graph": args.proof_graph,
        "summary":{
            "validations_requested": len(validations),
            "validations_executed": len(results),
            "successful_commands": sum(1 for r in results if r["runtime_result"]["success"]),
            "candidate_only": True,
            "finding_allowed": False
        },
        "results": results
    }
    save(args.out,out)
    print(json.dumps(out["summary"], indent=2))

if __name__=="__main__":
    main()
