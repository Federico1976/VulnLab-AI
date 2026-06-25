import json
import re
import sys
from pathlib import Path

SINK_PATTERNS = [
    "loadUrl(",
    "evaluateJavascript(",
    "addJavascriptInterface(",
    "startActivity(",
    "startActivityForResult(",
    "putExtra(",
    "setData(",
    "setAction(",
    "parseUri(",
    "File(",
    "FileInputStream(",
    "FileOutputStream(",
    "openFileInput(",
    "openFileOutput(",
    "getContentResolver(",
    ".query(",
    ".insert(",
    ".update(",
    ".delete(",
    "HttpURLConnection",
    "OkHttpClient",
    "Retrofit",
    "Cipher.getInstance(",
]

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def extract_method_name(signature):
    m = re.search(r"\s([A-Za-z0-9_$]+)\s*\(", signature)
    return m.group(1) if m else ""

def extract_body_from_file(file_path, method_name, line):
    p = Path(file_path)
    if not p.exists():
        return ""

    src = p.read_text(encoding="utf-8", errors="ignore")
    lines = src.splitlines()

    start_idx = max(0, int(line or 1) - 20)
    search = "\n".join(lines[start_idx:])

    idx = search.find(method_name + "(")
    if idx == -1:
        return ""

    brace = search.find("{", idx)
    if brace == -1:
        return ""

    depth = 0
    for i in range(brace, len(search)):
        if search[i] == "{":
            depth += 1
        elif search[i] == "}":
            depth -= 1
            if depth == 0:
                return search[brace:i + 1]

    return search[brace:brace + 5000]

def body_lines(body):
    return body.splitlines()

def find_sink_lines(body):
    results = []
    for idx, line in enumerate(body_lines(body), 1):
        for pat in SINK_PATTERNS:
            if pat in line:
                results.append({
                    "line_in_method": idx,
                    "pattern": pat,
                    "code": line.strip()
                })
    return results

def find_param_usage(body, arg_names):
    usage = {}
    for arg in arg_names:
        if not arg:
            continue
        hits = []
        for idx, line in enumerate(body_lines(body), 1):
            if re.search(rf"\b{re.escape(arg)}\b", line):
                hits.append({
                    "line_in_method": idx,
                    "code": line.strip()
                })
        usage[arg] = hits
    return usage

def find_local_calls(body):
    calls = []
    for idx, line in enumerate(body_lines(body), 1):
        stripped = line.strip()

        if stripped.startswith(("if ", "for ", "while ", "switch ", "catch ")):
            continue

        found = re.findall(r"\b([A-Za-z_][A-Za-z0-9_$]*)\s*\(", stripped)
        for fn in found:
            if fn in {
                "if", "for", "while", "switch", "catch", "return",
                "new", "super", "this"
            }:
                continue
            calls.append({
                "line_in_method": idx,
                "call": fn,
                "code": stripped
            })
    return calls

def confidence_score(param_usage, sink_lines, local_calls):
    score = 0.0

    if sink_lines:
        score += 0.35

    if any(len(v) > 0 for v in param_usage.values()):
        score += 0.30

    joined_sink = " ".join(x["code"] for x in sink_lines)
    for arg, hits in param_usage.items():
        if arg and arg in joined_sink:
            score += 0.25
            break

    if local_calls:
        score += 0.10

    return round(min(score, 1.0), 2)

def build_path(candidate):
    enrich = candidate.get("rn_enrichment", {})
    signature = candidate.get("signature", "")
    method_name = enrich.get("method_name") or extract_method_name(signature)

    body = extract_body_from_file(
        candidate.get("file", ""),
        method_name,
        candidate.get("line")
    )

    arg_names = enrich.get("argument_names", [])
    param_usage = find_param_usage(body, arg_names) if body else {}
    sink_lines = find_sink_lines(body) if body else []
    local_calls = find_local_calls(body) if body else []

    candidate["execution_path"] = {
        "source": {
            "type": "ReactMethod",
            "class": candidate.get("class"),
            "method": method_name,
            "signature": signature,
            "arguments": enrich.get("argument_types", []),
            "argument_names": arg_names,
        },
        "body_extracted": bool(body),
        "source_argument_usage": param_usage,
        "sink_lines": sink_lines,
        "local_calls": local_calls[:80],
        "path_confidence": confidence_score(param_usage, sink_lines, local_calls),
        "needs_joern_dataflow": True,
    }

    return candidate

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m path_builder.rn_execution_path_builder <input_queue.json> <output.json>")
        sys.exit(1)

    candidates = read_json(sys.argv[1])
    enriched = [build_path(c) for c in candidates]
    write_json(sys.argv[2], enriched)

    print(f"[+] Candidates: {len(enriched)}")
    print(f"[+] Written: {sys.argv[2]}")

    for i, c in enumerate(enriched[:20], 1):
        ep = c["execution_path"]
        print(
            f"{i:02d}. conf={ep['path_confidence']} "
            f"class={c.get('class')} "
            f"sig={c.get('signature')} "
            f"sinks={len(ep['sink_lines'])} "
            f"calls={len(ep['local_calls'])}"
        )

if __name__ == "__main__":
    main()
