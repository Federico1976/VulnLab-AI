import json
import re
import sys
from pathlib import Path


def extract_method_name(signature):
    m = re.search(r"\s([A-Za-z0-9_$]+)\s*\(", signature or "")
    return m.group(1) if m else ""


def extract_method_slice(path, line, window=90):
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(0, int(line or 1) - 1)
    end = min(len(lines), start + window)

    depth = 0
    seen_open = False
    real_end = end

    for i in range(start, min(len(lines), start + 250)):
        depth += lines[i].count("{")
        if "{" in lines[i]:
            seen_open = True
        depth -= lines[i].count("}")
        if seen_open and depth <= 0 and i > start:
            real_end = i + 1
            break

    return [
        {"line": i + 1, "code": lines[i]}
        for i in range(start, real_end)
    ]


SENSITIVE_TERMS = [
    "new File(",
    "FileInputStream",
    "FileOutputStream",
    "RandomAccessFile",
    "MessageDigest",
    "Base64",
    "Uri.parse",
    "getContentResolver",
    ".query(",
    ".openInputStream(",
    ".openOutputStream(",
    "downloadFile",
    "uploadFiles",
    "HttpURLConnection",
]


def analyze_slice(candidate):
    file_path = candidate.get("file")
    line = candidate.get("line")
    signature = candidate.get("signature", "")
    method = extract_method_name(signature)

    if not file_path or not Path(file_path).exists():
        return None

    sl = extract_method_slice(file_path, line)

    sinks = []
    params = []

    sig_params = signature[signature.find("(")+1:signature.rfind(")")]
    for part in sig_params.split(","):
        part = part.strip()
        if not part:
            continue
        name = part.split()[-1]
        params.append(name)

    for row in sl:
        code = row["code"].strip()
        if any(t in code for t in SENSITIVE_TERMS):
            used = [p for p in params if re.search(rf"\b{re.escape(p)}\b", code)]
            sinks.append({
                "line": row["line"],
                "code": code,
                "params": used,
            })

    return {
        "status": "source_text_fallback",
        "method": method,
        "line": line,
        "file": file_path,
        "params": params,
        "sensitive_sink_count": len(sinks),
        "sensitive_sinks": sinks,
        "slice": sl[:120],
        "decision": "Source file parsed textually because Joern did not expose the expected method node. Treat as fallback evidence, not CPG proof.",
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m joern_engine.source_text_fallback <candidates.json> <out.json>")
        sys.exit(1)

    data = json.loads(Path(sys.argv[1]).read_text())
    out = []

    for c in data:
        r = analyze_slice(c)
        c["source_text_fallback"] = r
        out.append(c)

    Path(sys.argv[2]).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[+] written {sys.argv[2]}")


if __name__ == "__main__":
    main()
