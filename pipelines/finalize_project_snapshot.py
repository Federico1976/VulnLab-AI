#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

def load(p):
    p = Path(p)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

matrix = load("output/universal_coverage_matrix.json")

snapshot = {
    "project": "VulnLab-AI – Universal Android APK Hunting Agent",
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "mission": "Universal defensive APK hunting agent for responsible disclosure; candidate evidence only; no vulnerability claim without reachability and dynamic validation.",
    "completed_layers": [
        "Confidence Engine",
        "Evidence Graph v2",
        "Universal Coverage Matrix",
        "Reasoning API v1"
    ],
    "coverage_summary": matrix.get("summary", {}),
    "targets": matrix.get("rows", []),
    "next_phase": {
        "name": "Semantic Bridge Expansion",
        "bridges": [
            "RN Bridge → Semantic Story",
            "WebView/DeepLink → Semantic Story",
            "Activity/Intent Router → Semantic Story"
        ],
        "goal": "Promote non-Flutter APKs from raw_signals_only to causal evidence stories ready for reachability."
    }
}

out = Path("output/final_project_snapshot.json")
out.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

print(json.dumps({
    "completed_layers": snapshot["completed_layers"],
    "coverage_summary": snapshot["coverage_summary"],
    "next_phase": snapshot["next_phase"]
}, indent=2))
print(f"[+] wrote {out}")
