#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, time
from pathlib import Path

def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def sh(cmd, timeout=25):
    r=subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout)
    return {"cmd":cmd,"returncode":r.returncode,"ok":r.returncode==0,"stdout":r.stdout[-5000:],"stderr":r.stderr[-5000:]}

def state():
    return {
        "resumed": sh("adb shell dumpsys activity activities | grep -E 'mResumedActivity|ResumedActivity|topResumedActivity' | tail -10"),
        "focus": sh("adb shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp' | tail -10"),
    }

def main():
    import argparse
    ap=argparse.ArgumentParser(description="Runtime Source-to-Sink Probe Executor v1")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sleep", type=float, default=2.0)
    args=ap.parse_args()

    plan=load(args.plan)
    results=[]

    for p in plan.get("plans", []):
        for probe in p.get("safe_probes", []):
            cmd=probe.get("command")
            if not cmd:
                continue

            sh("adb logcat -c")
            before=state()
            run=sh(cmd)
            time.sleep(args.sleep)
            after=state()

            log=sh(
                "adb logcat -d -t 500 | grep -iE "
                f"'{args.package}|vulnlab-safe-marker|deeplink|oauth|webview|loadurl|redirect|authorization|navigation|router|intent|uri|url|blocked|denied|exception|security' "
                "| tail -200"
            )

            combined=(json.dumps(after)+log.get("stdout","")).lower()
            marker_seen="vulnlab-safe-marker" in combined
            sink_words=[w for w in ["webview","loadurl","oauth","redirect","authorization","router","navigation"] if w in combined]

            if marker_seen and sink_words:
                state_class="marker_reached_sink_related_runtime"
                delta=0.18
            elif marker_seen:
                state_class="marker_reached_runtime"
                delta=0.10
            elif sink_words:
                state_class="sink_runtime_seen_without_marker"
                delta=0.04
            elif run["ok"]:
                state_class="probe_executed_no_marker_observed"
                delta=0.0
            else:
                state_class="probe_failed"
                delta=-0.08

            results.append({
                "entry_component":p.get("entry_component"),
                "path_score":p.get("path_score"),
                "probe_type":probe.get("probe_type"),
                "command":cmd,
                "before":before,
                "after":after,
                "run":run,
                "filtered_log":log,
                "interpretation":{
                    "state":state_class,
                    "marker_seen":marker_seen,
                    "sink_words_seen":sink_words,
                    "confidence_delta":delta,
                    "candidate_only":True,
                    "finding_allowed":False
                }
            })

    summary={
        "probes_executed":len(results),
        "marker_reached_sink_related_runtime":sum(1 for r in results if r["interpretation"]["state"]=="marker_reached_sink_related_runtime"),
        "marker_reached_runtime":sum(1 for r in results if r["interpretation"]["state"]=="marker_reached_runtime"),
        "sink_runtime_seen_without_marker":sum(1 for r in results if r["interpretation"]["state"]=="sink_runtime_seen_without_marker"),
        "probe_failed":sum(1 for r in results if r["interpretation"]["state"]=="probe_failed"),
        "confidence_delta_total":round(sum(r["interpretation"]["confidence_delta"] for r in results),3),
        "candidate_only":True,
        "finding_allowed":False,
        "next_step":"interpret_source_to_sink_probe_results"
    }

    out={"schema_version":"runtime_source_to_sink_probe_executor.v1","created_at":int(time.time()),"summary":summary,"results":results}
    save(args.out,out)
    print(json.dumps(summary, indent=2))

if __name__=="__main__":
    main()
