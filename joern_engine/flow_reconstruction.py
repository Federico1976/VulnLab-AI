import json
import re
import sys
from pathlib import Path


ASSIGN_RE = re.compile(r'^\s*(?:(?:final\s+)?[\w<>\[\].?,]+\s+)?([A-Za-z_$][\w$]*)\s*=\s*(.+?);?\s*$')


SENSITIVE_TERMS = [
    "new File(",
    "FileInputStream",
    "FileOutputStream",
    "RandomAccessFile",
    "MessageDigest",
    "Base64.decode",
    "Uri.parse",
    "putExtra(",
    "setData(",
    "setAction(",
    "startActivity(",
    "startActivityForResult(",
    "loadUrl(",
    "evaluateJavascript(",
    "addJavascriptInterface(",
    "getContentResolver",
    ".query(",
    ".insert(",
    ".update(",
    ".delete(",
    ".openInputStream(",
    ".openOutputStream(",
    "HttpURLConnection",
    "openConnection(",
]


LOW_SIGNAL_TERMS = [
    "sendEvent(",
    "promise.resolve(",
    "promise.reject(",
]


def param_names_from_signature(signature: str):
    params = []
    if "(" not in signature or ")" not in signature:
        return params
    raw = signature[signature.find("(")+1:signature.rfind(")")]
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        name = part.split()[-1].replace("...", "")
        params.append(name)
    return params


def is_sensitive(code: str):
    code = code or ""
    if any(x in code for x in LOW_SIGNAL_TERMS):
        return False
    return any(x in code for x in SENSITIVE_TERMS)


def identifiers(code: str):
    return set(re.findall(r'\b[A-Za-z_$][\w$]*\b', code or ""))


def build_local_flow(slice_lines, params):
    taint = {p: [{"kind": "param", "name": p}] for p in params}
    assignments = []
    sinks = []

    for row in slice_lines:
        line_no = row.get("line")
        code = (row.get("code") or "").strip()

        if not code:
            continue

        m = ASSIGN_RE.match(code)
        if m:
            lhs, rhs = m.group(1), m.group(2)
            used = identifiers(rhs)
            sources = []

            for name, trace in taint.items():
                if name in used:
                    sources.extend(trace)

            if sources:
                taint[lhs] = sources + [{
                    "kind": "assignment",
                    "line": line_no,
                    "lhs": lhs,
                    "rhs": rhs,
                    "code": code,
                }]
                assignments.append({
                    "line": line_no,
                    "lhs": lhs,
                    "rhs": rhs,
                    "source_params": sorted({x.get("name") for x in sources if x.get("kind") == "param"}),
                    "code": code,
                })

        if is_sensitive(code):
            used = identifiers(code)
            source_params = []
            source_vars = []
            trace = []

            for name, t in taint.items():
                if name in used:
                    source_vars.append(name)
                    trace.extend(t)
                    for x in t:
                        if x.get("kind") == "param":
                            source_params.append(x.get("name"))

            direct_params = [p for p in params if re.search(rf'\b{re.escape(p)}\b', code)]
            source_params.extend(direct_params)

            if source_params or source_vars:
                sinks.append({
                    "line": line_no,
                    "code": code,
                    "source_params": sorted(set(source_params)),
                    "source_vars": sorted(set(source_vars)),
                    "trace": trace[-12:],
                    "confidence": 0.9 if trace else 0.7,
                })

    return {
        "params": params,
        "assignments": assignments,
        "sinks": sinks,
        "sink_count": len(sinks),
    }


def from_source_text_fallback(candidate):
    st = candidate.get("source_text_fallback")
    if not st:
        return None
    return build_local_flow(st.get("slice", []), st.get("params", []))


def from_joern_local_path(candidate):
    # Joern local path already has sink lines, but not full assignment propagation.
    # Keep this hook for future CPG AST slices.
    return None


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m joern_engine.flow_reconstruction <input.json> <out.json>")
        sys.exit(1)

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = []

    for c in data:
        flow = from_source_text_fallback(c)
        if not flow:
            flow = from_joern_local_path(c)

        c["flow_reconstruction"] = flow
        out.append(c)

    Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    total = len(out)
    with_flow = len([x for x in out if x.get("flow_reconstruction") and x["flow_reconstruction"].get("sink_count", 0) > 0])
    print(f"[+] Input: {total}")
    print(f"[+] With reconstructed flows: {with_flow}")
    print(f"[+] Written: {sys.argv[2]}")


if __name__ == "__main__":
    main()
