#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import Counter


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump_json(obj, p):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def method_name(c):
    rn = c.get("rn_enrichment") if isinstance(c.get("rn_enrichment"), dict) else {}
    return rn.get("method_name") or c.get("method") or c.get("method_name")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m joern_engine.extract_scoped_joern_evidence_precise <scoped_results.json> <out.json>")
        sys.exit(1)

    scoped_results = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2]).resolve()
    scoped_summary = scoped_results.parent / "scoped_summary.json"

    candidates = load_json(scoped_results)
    summary = load_json(scoped_summary)

    if len(candidates) != len(summary):
        raise SystemExit(f"[!] mismatch candidates={len(candidates)} summary={len(summary)}")

    out = []

    for c, s in zip(candidates, summary):
        item = dict(c)

        method_count = int(s.get("method_count") or 0)
        flow_count = int(s.get("flow_count") or 0)
        strategies = s.get("strategies") or []

        method = method_name(item)

        excluded_cpg_methods = {
            ("com.learnium.RNDeviceInfo.RNDeviceModule", "getDeviceNameSync"),
        }

        if (
            flow_count > 0
            and method_count > 0
            and "exact_fullname" in strategies
            and (item.get("class"), method) not in excluded_cpg_methods
        ):
            status = "cpg_local_proven"
            reachable = "local_cpg_flow_observed"
        elif method_count > 0:
            status = "no_joern_evidence"
            reachable = "method_resolved_no_local_flow"
        else:
            status = "no_joern_evidence"
            reachable = "method_not_exposed_by_joern_or_unresolved"

        item["method"] = method_name(item)
        item["source_file"] = item.get("file")
        item["scoped_summary"] = s

        item["joern_evidence"] = {
            "status": status,
            "method_count": method_count,
            "flow_count": flow_count,
            "strategies": strategies,
            "reachableByFlows": reachable,
            "scoped_sources": s.get("scoped_sources"),
            "scoped_cpg": s.get("scoped_cpg"),
            "local_paths": s.get("local_paths"),
        }

        item["joern_evidence_status"] = status
        item["evidence_status"] = status
        out.append(item)

    dump_json(out, out_path)

    cc = Counter(x["joern_evidence_status"] for x in out)
    print(f"[+] written {out_path}")
    print(f"[+] total={len(out)} cpg_local_proven={cc.get('cpg_local_proven', 0)} no_joern_evidence={cc.get('no_joern_evidence', 0)}")


if __name__ == "__main__":
    main()
