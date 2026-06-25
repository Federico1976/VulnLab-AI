import json
import sys
from pathlib import Path

SENSITIVE_JOERN_SINK_TERMS = [
    "new File(",
    "File(",
    "Uri.parse(",
    "putExtra(",
    "setData(",
    "setAction(",
    "startActivity(",
    "startActivityForResult(",
    "loadUrl(",
    "evaluateJavascript(",
    "addJavascriptInterface(",
    "getContentResolver(",
    ".query(",
    ".insert(",
    ".update(",
    ".delete(",
    "Cipher.getInstance(",
    "MessageDigest.getInstance(",
    "HttpURLConnection",
    "OkHttpClient",
    "openConnection(",
]

LOW_SIGNAL_JOERN_TERMS = [
    "sendEvent(",
    "MimeTypeMap",
    "getMimeTypeFromExtension",
    "getFileExtensionFromUrl",
    "toLowerCase(",
]


def is_sensitive_joern_sink(code: str) -> bool:
    code = code or ""

    if any(t in code for t in LOW_SIGNAL_JOERN_TERMS):
        return False

    return any(t in code for t in SENSITIVE_JOERN_SINK_TERMS)


def classify_candidate(c):
    jl = c.get("joern_local_path", {})
    methods = jl.get("methods", [])

    local_flows = []
    seen = set()

    for m in methods:
        local = m.get("local_path_reconstruction", {})
        for f in local.get("flow_candidates", []):
            sink = f.get("sink", {}) or {}

            if not is_sensitive_joern_sink(sink.get("code", "")):
                continue

            source_calls = []

            for sc in f.get("contributing_source_calls", []):
                sc_code = sc.get("code", "")
                sink_code = sink.get("code", "")

                # Do not treat the sink call itself as a source call.
                if sc_code and sc_code != sink_code:
                    source_calls.append(sc)

            key = (
                m.get("full_name"),
                sink.get("code"),
                tuple(sorted(f.get("contributing_params", []))),
                tuple(sc.get("code", "") for sc in source_calls),
            )

            if key in seen:
                continue

            seen.add(key)

            local_flows.append({
                "method": m.get("full_name"),
                "file": m.get("file"),
                "line": m.get("line"),
                "confidence": f.get("confidence"),
                "sink": sink,
                "contributing_params": f.get("contributing_params", []),
                "contributing_source_calls": source_calls,
            })

    status = "no_joern_evidence"
    confidence = 0.0

    if local_flows:
        status = "cpg_local_proven"
        confidence = max(float(f.get("confidence") or 0.0) for f in local_flows)

    c["joern_evidence"] = {
        "status": status,
        "confidence": confidence,
        "method_count": jl.get("method_count", 0),
        "local_flow_count": len(local_flows),
        "local_flows": local_flows,
        "reachable_by_flows": {
            "status": "attempted_no_path",
            "note": "Joern resolved source and sink nodes, but reachableByFlows did not emit a path for this decompiled Android pattern.",
        },
        "decision": (
            "Use as strong CPG-backed local evidence, but require dynamic or cross-method validation before calling vulnerability."
            if local_flows else
            "Insufficient Joern evidence."
        ),
    }

    return c


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m joern_engine.joern_evidence_integrator <joern_local_paths.json> <out.json>")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2])

    data = json.loads(inp.read_text(encoding="utf-8"))
    enriched = [classify_candidate(c) for c in data]

    out.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[+] Input: {len(data)}")
    print(f"[+] Written: {out}")

    summary = {}
    for c in enriched:
        s = c["joern_evidence"]["status"]
        summary[s] = summary.get(s, 0) + 1

    print("[+] Joern evidence summary:")
    for k, v in sorted(summary.items()):
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
