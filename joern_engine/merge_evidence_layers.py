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


def key(x):
    return (
        x.get("class"),
        x.get("method") or x.get("rn_enrichment", {}).get("method_name"),
        x.get("signature"),
        x.get("line"),
    )


def has_source_text_fallback(x):
    st = x.get("source_text_fallback")
    return isinstance(st, dict) and st.get("status") == "source_text_fallback"


def has_reconstructed_flow(x):
    fr = x.get("flow_reconstruction")
    return isinstance(fr, dict) and int(fr.get("sink_count") or 0) > 0


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m joern_engine.merge_evidence_layers <base_evidence.json> <fallback_flow.json> <out.json>")
        sys.exit(1)

    base_path, fallback_path, out_path = map(Path, sys.argv[1:])

    base = load_json(base_path)
    fallback = load_json(fallback_path)

    fb = {key(x): x for x in fallback}
    merged = []

    for item in base:
        k = key(item)
        f = fb.get(k)

        current_status = item.get("joern_evidence", {}).get("status") or item.get("joern_evidence_status")

        if f:
            item["source_text_fallback"] = f.get("source_text_fallback")
            item["flow_reconstruction"] = f.get("flow_reconstruction")

        if current_status == "cpg_local_proven":
            final_status = "cpg_local_proven"
            item["joern_evidence"]["status"] = "cpg_local_proven"

        elif f and has_source_text_fallback(f) and has_reconstructed_flow(f):
            final_status = "source_text_fallback"
            item.setdefault("joern_evidence", {})
            item["joern_evidence"]["status"] = "source_text_fallback"
            item["joern_evidence"]["reachableByFlows"] = "not_applicable_source_text_fallback"

        else:
            final_status = "no_joern_evidence"
            item.setdefault("joern_evidence", {})
            item["joern_evidence"]["status"] = "no_joern_evidence"

        item["joern_evidence_status"] = final_status
        item["evidence_status"] = final_status
        merged.append(item)

    dump_json(merged, out_path)

    cc = Counter(x.get("joern_evidence_status") for x in merged)
    print(f"[+] base={len(base)} fallback={len(fallback)} merged={len(merged)}")
    print(f"[+] distribution={dict(cc)}")
    print(f"[+] written {out_path}")


if __name__ == "__main__":
    main()
