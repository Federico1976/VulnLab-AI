import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List


SINK_PATTERNS = {
    "webview": [
        "loadUrl(",
        "evaluateJavascript(",
        "addJavascriptInterface(",
        "WebView",
    ],
    "intent": [
        "new Intent(",
        "Intent(",
        ".putExtra(",
        ".setData(",
        ".setAction(",
        ".parseUri(",
    ],
    "activity_launch": [
        "startActivity(",
        "startActivityForResult(",
    ],
    "broadcast": [
        "sendBroadcast(",
        "sendOrderedBroadcast(",
    ],
    "service": [
        "startService(",
        "bindService(",
    ],
    "file": [
        "File(",
        "FileInputStream(",
        "FileOutputStream(",
        "openFileInput(",
        "openFileOutput(",
        "delete(",
    ],
    "content_resolver": [
        "getContentResolver(",
        ".query(",
        ".insert(",
        ".update(",
        ".delete(",
        "ContentResolver",
    ],
    "crypto": [
        "Cipher.getInstance(",
        "MessageDigest.getInstance(",
        "Mac.getInstance(",
        "KeyStore",
        "SecretKeySpec",
    ],
    "network": [
        "HttpURLConnection",
        "OkHttpClient",
        "Retrofit",
        ".openConnection(",
        "Socket(",
    ],
    "reflection": [
        "Class.forName(",
        "getDeclaredMethod(",
        "getMethod(",
        ".invoke(",
    ],
    "dynamic_code": [
        "DexClassLoader",
        "PathClassLoader",
        "loadClass(",
    ],
    "command_execution": [
        "Runtime.getRuntime().exec(",
        "ProcessBuilder(",
    ],
    "bluetooth": [
        "BluetoothAdapter",
        "BluetoothDevice",
        "BluetoothGatt",
        "connectGatt(",
    ],
    "nfc": [
        "NfcAdapter",
        "NdefMessage",
        "Tag",
    ],
}


CONTROLLED_ARG_TYPES = [
    "String",
    "ReadableMap",
    "ReadableArray",
    "Callback",
    "Promise",
    "Boolean",
    "Integer",
    "Double",
    "int",
    "boolean",
]


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_method_name(signature: str) -> str:
    m = re.search(r"\s([A-Za-z0-9_$]+)\s*\(", signature)
    if not m:
        return ""
    return m.group(1)


def extract_arguments(signature: str) -> List[Dict[str, str]]:
    m = re.search(r"\((.*)\)", signature)
    if not m:
        return []

    raw_args = m.group(1).strip()
    if not raw_args:
        return []

    args = []
    for part in raw_args.split(","):
        part = part.strip()
        pieces = part.split()
        if len(pieces) >= 2:
            arg_type = pieces[-2]
            arg_name = pieces[-1]
            args.append({"type": arg_type, "name": arg_name})
    return args


def extract_method_body(source: str, signature: str, line: int = None) -> str:
    method_name = extract_method_name(signature)
    if not method_name:
        return ""

    search_area = source

    if line and line > 0:
        lines = source.splitlines()
        start = max(0, line - 20)
        search_area = "\n".join(lines[start:])

    idx = search_area.find(method_name + "(")
    if idx == -1:
        idx = search_area.find(signature.strip())

    if idx == -1:
        return ""

    brace_start = search_area.find("{", idx)
    if brace_start == -1:
        return ""

    depth = 0
    for i in range(brace_start, len(search_area)):
        if search_area[i] == "{":
            depth += 1
        elif search_area[i] == "}":
            depth -= 1
            if depth == 0:
                return search_area[brace_start:i + 1]

    return search_area[brace_start:brace_start + 4000]


def detect_sinks(body: str) -> Dict[str, Any]:
    sink_hits = []

    for sink_type, patterns in SINK_PATTERNS.items():
        for pattern in patterns:
            if pattern in body:
                sink_hits.append({
                    "type": sink_type,
                    "pattern": pattern,
                })

    unique_types = sorted(set(hit["type"] for hit in sink_hits))

    return {
        "sink_count": len(sink_hits),
        "sink_types": unique_types,
        "sink_hits": sink_hits,
    }


def enrich_finding(finding: Dict[str, Any]) -> Dict[str, Any]:
    file_path = Path(finding.get("file", ""))
    signature = finding.get("signature", "")
    line = finding.get("line")

    args = extract_arguments(signature)

    finding["rn_enrichment"] = {
        "method_name": extract_method_name(signature),
        "argument_count": len(args),
        "argument_types": [a["type"] for a in args],
        "argument_names": [a["name"] for a in args],
        "js_controllable_args": [
            a for a in args if a["type"] in CONTROLLED_ARG_TYPES
        ],
        "body_extracted": False,
        "sink_count": 0,
        "sink_types": [],
        "sink_hits": [],
    }

    if not file_path.exists():
        finding["rn_enrichment"]["error"] = f"source file not found: {file_path}"
        return finding

    source = file_path.read_text(encoding="utf-8", errors="ignore")
    body = extract_method_body(source, signature, line)

    if not body:
        finding["rn_enrichment"]["error"] = "method body not extracted"
        return finding

    sinks = detect_sinks(body)

    finding["rn_enrichment"]["body_extracted"] = True
    finding["rn_enrichment"]["body_preview"] = body[:1200]
    finding["rn_enrichment"].update(sinks)

    return finding


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m enrichment.rn_bridge_enricher <input.json> <output.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    findings = read_json(input_path)

    if isinstance(findings, dict) and "findings" in findings:
        findings = findings["findings"]

    enriched = [enrich_finding(f) for f in findings]

    write_json(output_path, enriched)

    with_sinks = [f for f in enriched if f["rn_enrichment"]["sink_count"] > 0]

    print(f"[+] Loaded findings: {len(enriched)}")
    print(f"[+] Findings with local sinks: {len(with_sinks)}")
    print(f"[+] Written: {output_path}")

    sink_summary = {}
    for f in with_sinks:
        for sink_type in f["rn_enrichment"]["sink_types"]:
            sink_summary[sink_type] = sink_summary.get(sink_type, 0) + 1

    print("[+] Sink type summary:")
    for k, v in sorted(sink_summary.items(), key=lambda x: x[1], reverse=True):
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
