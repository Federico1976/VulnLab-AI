#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def clean_filename(s):
    return (
        str(s or "unknown")
        .replace(".", "_")
        .replace("/", "_")
        .replace("$", "_")
        .replace(":", "_")
    )


def build_card(f, idx):
    lines = []

    lines.append(f"# Deeplink Candidate {idx}: {f.get('component_name')}")
    lines.append("")
    lines.append("**Status:** candidate evidence only. Not a confirmed vulnerability.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Package:** `{f.get('package')}`")
    lines.append(f"- **Component:** `{f.get('component_name')}`")
    lines.append(f"- **Component type:** `{f.get('component_type')}`")
    lines.append(f"- **Ownership:** `{f.get('ownership')}`")
    lines.append(f"- **Exported:** `{f.get('exported')}`")
    lines.append(f"- **Permission:** `{f.get('permission')}`")
    lines.append(f"- **Candidate score:** `{f.get('candidate_score')}`")
    lines.append(f"- **Priority:** `{f.get('priority')}`")
    lines.append("")

    lines.append("## Intent filter evidence")
    lines.append("")
    lines.append(f"- **Actions:** `{', '.join(f.get('actions', []))}`")
    lines.append(f"- **Categories:** `{', '.join(f.get('categories', []))}`")
    lines.append(f"- **Schemes:** `{', '.join(f.get('schemes', []))}`")
    lines.append(f"- **Hosts:** `{', '.join(f.get('hosts', []))}`")
    lines.append(f"- **Paths:** `{', '.join(f.get('paths', []))}`")
    lines.append("")

    lines.append("## Risk reasons")
    lines.append("")
    for r in f.get("risk_reasons", []):
        lines.append(f"- `{r}`")
    lines.append("")

    lines.append("## Impact hypothesis")
    lines.append("")
    lines.append(f.get("impact_hypothesis", ""))
    lines.append("")

    lines.append("## Required next analysis")
    lines.append("")
    for step in f.get("required_next_analysis", []):
        lines.append(f"- {step}")
    lines.append("")

    lines.append("## Dynamic validation plan")
    lines.append("")
    lines.append("Use only benign payloads on the authorized target.")
    lines.append("")
    lines.append("1. Launch the activity normally and capture baseline logs.")
    lines.append("2. Trigger each declared scheme/host/path with `adb shell am start -a android.intent.action.VIEW -d <url>`.")
    lines.append("3. Observe whether the route changes authenticated state, opens WebView, invokes OAuth, loads remote content, or reaches file/IPC/native sinks.")
    lines.append("4. Hook the component with Frida only to log received Intent data/extras and internal route decisions.")
    lines.append("5. Promote only if runtime evidence proves attacker-controlled input reaches a meaningful sink.")
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
        print("Usage: python3 -m reports.deeplink_investigation_cards <deeplink_candidates.json> <out_dir>")
        sys.exit(1)

    items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    index = []
    for i, f in enumerate(items, 1):
        name = clean_filename(f.get("component_name"))
        out = out_dir / f"{i:03d}_{name}.md"
        out.write_text(build_card(f, i), encoding="utf-8")
        index.append({
            "rank": i,
            "component": f.get("component_name"),
            "priority": f.get("priority"),
            "score": f.get("candidate_score"),
            "ownership": f.get("ownership"),
            "card": str(out)
        })

    (out_dir / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    readme = out_dir / "README.md"
    readme.write_text(
        "# Deeplink Manifest Investigation Cards\n\n"
        "Candidate-only manifest/deeplink surfaces. No item is a confirmed vulnerability without source trace and dynamic validation.\n\n"
        f"- Total candidates: {len(items)}\n"
        f"- Cards: {len(index)}\n\n",
        encoding="utf-8"
    )

    print(f"[+] Cards written: {len(index)}")
    print(f"[+] Output dir: {out_dir}")
    for x in index[:10]:
        print(f"- {x['score']} {x['priority']} {x['ownership']} {x['card']}")


if __name__ == "__main__":
    main()
