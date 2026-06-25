#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def safe_name(s):
    return str(s or "unknown").replace("/", "_").replace(".", "_").replace("$", "_")


def build_card(f, idx):
    lines = []
    lines.append(f"# WebView Candidate {idx}")
    lines.append("")
    lines.append("**Status:** candidate evidence only. Not a confirmed vulnerability.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Package:** `{f.get('package')}`")
    lines.append(f"- **File:** `{f.get('file')}`")
    lines.append(f"- **Candidate score:** `{f.get('candidate_score')}`")
    lines.append(f"- **Priority:** `{f.get('priority')}`")
    lines.append("")
    lines.append("## Risk reasons")
    lines.append("")
    for r in f.get("risk_reasons", []):
        lines.append(f"- `{r}`")
    lines.append("")
    lines.append("## Evidence lines")
    lines.append("")
    for h in f.get("hits", [])[:60]:
        lines.append(f"- L{h.get('line')}: `{h.get('code')}`")
    lines.append("")
    lines.append("## Impact hypothesis")
    lines.append("")
    lines.append(f.get("impact_hypothesis", ""))
    lines.append("")
    lines.append("## Required next analysis")
    lines.append("")
    for x in f.get("required_next_analysis", []):
        lines.append(f"- {x}")
    lines.append("")
    lines.append("## Dynamic validation plan")
    lines.append("")
    lines.append("1. Launch normal app flow and capture baseline logs.")
    lines.append("2. Hook WebView.loadUrl/evaluateJavascript/addJavascriptInterface with Frida to log arguments.")
    lines.append("3. Trigger known deeplink routes from deeplink_manifest cards using benign payloads.")
    lines.append("4. Confirm whether untrusted input reaches WebView sinks.")
    lines.append("5. Promote only with reproducible runtime evidence and meaningful impact.")
    lines.append("")
    lines.append("## Guardrail")
    lines.append("")
    lines.append(f.get("validation_guardrail", "Do not report without validation."))
    lines.append("")
    lines.append("`candidate_not_confirmed`")
    lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m reports.webview_investigation_cards <webview_candidates.json> <out_dir>")
        sys.exit(1)

    items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    index = []
    for i, f in enumerate(items, 1):
        name = safe_name(Path(f.get("file", "unknown")).name)
        out = out_dir / f"{i:03d}_{name}.md"
        out.write_text(build_card(f, i), encoding="utf-8")
        index.append({
            "rank": i,
            "file": f.get("file"),
            "score": f.get("candidate_score"),
            "priority": f.get("priority"),
            "card": str(out)
        })

    (out_dir / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "README.md").write_text(
        "# WebView Static Investigation Cards\n\n"
        "Candidate-only WebView static surfaces. No item is a confirmed vulnerability without source trace and dynamic validation.\n\n"
        f"- Total candidates: {len(items)}\n",
        encoding="utf-8"
    )

    print(f"[+] Cards written: {len(index)}")
    print(f"[+] Output dir: {out_dir}")
    for x in index[:10]:
        print(f"- {x['score']} {x['priority']} {x['card']}")


if __name__ == "__main__":
    main()
