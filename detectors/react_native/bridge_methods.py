import json
import re
from pathlib import Path

RISKY_KEYWORDS = [
    "url", "uri", "token", "auth", "cookie", "secret", "key",
    "file", "path", "bluetooth", "ble", "intent", "webview",
    "open", "start", "exec", "command", "encrypt", "decrypt"
]

def analyze(output_dir: str) -> dict:
    root = Path(output_dir) / "code/decompiled/sources"
    findings = []

    for path in root.rglob("*.java"):
        text = path.read_text(errors="ignore")
        if "@ReactMethod" not in text:
            continue

        lines = text.splitlines()
        package = ""
        m = re.search(r"package\s+([\w.]+);", text)
        if m:
            package = m.group(1)

        cls = path.stem
        full_class = f"{package}.{cls}" if package else cls

        for i, line in enumerate(lines):
            if "@ReactMethod" not in line:
                continue

            window = "\n".join(lines[i:i+20])
            sig = ""
            for j in range(i+1, min(i+8, len(lines))):
                if re.search(r"\bpublic\b|\bprivate\b|\bprotected\b", lines[j]):
                    sig = lines[j].strip()
                    break

            body_window = "\n".join(lines[i:min(i+80, len(lines))])
            risky = [k for k in RISKY_KEYWORDS if k.lower() in body_window.lower() or k.lower() in sig.lower()]

            findings.append({
                "id": "APK-RN-BRIDGE-METHOD-001",
                "title": "React Native exposed native method",
                "category": "react_native_bridge",
                "severity": "medium" if risky else "info",
                "confidence": "medium",
                "class": full_class,
                "file": str(path),
                "line": i + 1,
                "signature": sig,
                "risky_keywords": risky,
                "evidence": body_window[:4000],
                "risk": "Native method exposed to JavaScript bridge. Risk depends on JS controllability and sensitive operations performed.",
                "next_tests": [
                    "Identify JS call sites for the native module name.",
                    "Check whether arguments originate from deeplinks, remote config, WebView, push notifications, or untrusted content.",
                    "Trace arguments into sensitive sinks such as WebView, file, crypto, IPC, BLE, intents, or network."
                ]
            })

    out = Path(output_dir) / "react_native_bridge_methods.json"
    out.write_text(json.dumps({"findings": findings}, indent=2, ensure_ascii=False))
    return {"findings": findings}

if __name__ == "__main__":
    import sys
    print(json.dumps(analyze(sys.argv[1]), indent=2, ensure_ascii=False))
