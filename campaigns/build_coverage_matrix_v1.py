#!/usr/bin/env python3
import json
from pathlib import Path

APKS = [
    ("Next Player", "output/campaign_single_01_nextplayer"),
    ("ServeIt", "output/campaign_single_02_serveit"),
    ("WebView Kiosk", "output/campaign_single_03_webviewkiosk"),
    ("LessPass", "output/campaign_single_04_lesspass"),
    ("openDSP-4x4", "output/campaign_single_05_opendsp"),
]

PARADIGMS = [
    "kotlin",
    "jetpack_compose",
    "react_native",
    "flutter",
    "webview",
    "deeplink",
    "fileprovider",
    "cordova",
    "xamarin",
    "unity",
    "kmp",
    "jni",
    "capacitor"
]

def load(p):
    p = Path(p)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

rows = []

for name, out in APKS:
    char = load(Path(out) / "apk_characterization.json")
    factory = load(Path(out) / "phase_b/research_object_factory_report.json")
    freeze = load(Path(out) / "phase_b_brain/phase_ab_freeze_report.json")
    s = freeze.get("summary", {})

    features = char.get("detected_features") or char.get("features") or {}
    recommended = char.get("recommended_pipelines") or char.get("recommended") or []

    builders = {
        b.get("builder"): b
        for b in factory.get("builders", [])
        if isinstance(b, dict)
    }

    rows.append({
        "apk": name,
        "package": char.get("package"),
        "label": char.get("label"),
        "features": list(features.keys()) if isinstance(features, dict) else features,
        "recommended_pipelines": recommended,
        "factory_declarative": factory.get("schema") == "vulnlab_ai.research_object_builder_factory.v2_declarative",
        "builders_ok": factory.get("summary", {}).get("builders_ok"),
        "research_objects_declared": factory.get("summary", {}).get("research_objects_declared"),
        "semantic_entities": s.get("semantic_entities"),
        "capability_graphs": s.get("capability_graphs"),
        "security_effects": s.get("security_effects"),
        "evidence_models": s.get("evidence_models"),
        "proof_evaluations": s.get("proof_evaluations"),
        "causal_ready": s.get("causal_ready_for_dynamic_validation"),
        "unknown_tasks": s.get("unknown_resolution_tasks"),
        "dynamic_plans": s.get("dynamic_validation_plans"),
        "freeze_ready": freeze.get("freeze_ready"),
        "finding_allowed": freeze.get("guardrail", {}).get("finding_allowed"),
        "builder_coverage": builders,
    })

paradigm_matrix = []

for p in PARADIGMS:
    detected = []
    builder_present = False
    builder_used = False

    for row in rows:
        feats = row.get("features") or []
        recs = row.get("recommended_pipelines") or []
        builders = row.get("builder_coverage") or {}

        if p in feats or any(p in str(x) for x in recs):
            detected.append(row["apk"])

        for bname, b in builders.items():
            if p in str(bname):
                builder_present = True
                if b.get("status") == "ok" and (b.get("count") or 0) > 0:
                    builder_used = True

    paradigm_matrix.append({
        "paradigm": p,
        "detected_in": detected,
        "detected_count": len(detected),
        "builder_present_or_registered": builder_present,
        "builder_used": builder_used,
        "status": (
            "covered"
            if builder_used
            else "detected_no_builder_or_not_exercised"
            if detected
            else "not_seen_in_campaign"
        )
    })

out = {
    "schema": "vulnlab.coverage_matrix.v1",
    "apk_count": len(rows),
    "all_freeze_ready": all(r.get("freeze_ready") for r in rows),
    "candidate_only_guardrail": all(r.get("finding_allowed") is False for r in rows),
    "rows": rows,
    "paradigm_matrix": paradigm_matrix,
}

Path("output/coverage_matrix_v1.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(json.dumps({
    "status": "ok",
    "output": "output/coverage_matrix_v1.json",
    "apk_count": len(rows),
    "all_freeze_ready": out["all_freeze_ready"],
    "candidate_only_guardrail": out["candidate_only_guardrail"]
}, indent=2))
