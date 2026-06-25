#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def is_third_party_component(name):
    prefixes = (
        "com.google.",
        "androidx.",
        "com.willowtreeapps.",
        "com.facebook.",
        "io.flutter.",
        "org.apache.",
    )
    return str(name or "").startswith(prefixes)


def risk_for_component(c):
    score = 0
    reasons = []

    if c.get("exported") is True:
        score += 30
        reasons.append("component_exported_true")

    if c.get("has_intent_filter"):
        score += 20
        reasons.append("has_intent_filter")

    actions = set(c.get("actions", []))
    categories = set(c.get("categories", []))
    data = c.get("data", [])

    if "android.intent.action.VIEW" in actions:
        score += 20
        reasons.append("view_action")

    if "android.intent.category.BROWSABLE" in categories:
        score += 20
        reasons.append("browsable_category")

    schemes = {x.get("scheme") for x in data if x.get("scheme")}
    hosts = {x.get("host") for x in data if x.get("host")}
    paths = {x.get("path") for x in data if x.get("path")}

    if "http" in schemes or "https" in schemes:
        score += 10
        reasons.append("http_https_applink")

    if "*" in hosts:
        score += 20
        reasons.append("wildcard_host")

    if paths:
        score += min(20, len(paths) * 2)
        reasons.append("multiple_deeplink_paths")

    if c.get("permission"):
        score -= 20
        reasons.append("protected_by_permission")

    if is_third_party_component(c.get("name")):
        score = min(score, 45)
        reasons.append("third_party_sdk_component_demoted")

    score = max(0, min(100, score))

    if score >= 75:
        severity = "high_candidate_priority"
    elif score >= 50:
        severity = "medium_candidate_priority"
    elif score >= 25:
        severity = "low_candidate_priority"
    else:
        severity = "informational"

    return score, severity, reasons


def build_findings(characterization):
    pkg = characterization.get("package_metadata", {}).get("package")
    label = characterization.get("package_metadata", {}).get("label")
    surfaces = characterization.get("manifest_surfaces", {})
    out = []

    for idx, c in enumerate(surfaces.get("exported_components", []), 1):
        data = c.get("data", [])
        schemes = sorted({x.get("scheme") for x in data if x.get("scheme")})
        hosts = sorted({x.get("host") for x in data if x.get("host")})
        paths = sorted({x.get("path") for x in data if x.get("path")})

        if not c.get("has_intent_filter") and c.get("type") != "activity":
            continue

        score, priority, reasons = risk_for_component(c)

        out.append({
            "id": f"APK-DEEPLINK-MANIFEST-{idx:03d}",
            "title": "Exported component or deeplink-capable manifest surface",
            "category": "deeplink_manifest",
            "status": "candidate_not_confirmed",
            "package": pkg,
            "app_label": label,
            "component_type": c.get("type"),
            "component_name": c.get("name"),
            "exported": c.get("exported"),
            "permission": c.get("permission"),
            "has_intent_filter": c.get("has_intent_filter"),
            "actions": sorted(set(c.get("actions", []))),
            "categories": sorted(set(c.get("categories", []))),
            "schemes": schemes,
            "hosts": hosts,
            "paths": paths,
            "candidate_score": score,
            "priority": priority,
            "ownership": "third_party_sdk" if is_third_party_component(c.get("name")) else "first_party_or_app_code",
            "risk_reasons": reasons,
            "impact_hypothesis": "External intent/deeplink surface may route untrusted input into app navigation or authentication flows. Impact depends on runtime routing, parameter handling, authentication state, and sink reachability.",
            "required_next_analysis": [
                "Resolve target Activity source code.",
                "Trace Intent data from getIntent()/NavDeepLink/AppLink handling.",
                "Identify parameters accepted by each scheme/host/path.",
                "Check whether route reaches WebView, OAuth, Firebase Auth, file, IPC, or privileged app state.",
                "Validate dynamically only with benign deeplink payloads on authorized target."
            ],
            "validation_guardrail": "Do not report as vulnerability without source trace and dynamic validation."
        })

    return sorted(out, key=lambda x: x["candidate_score"], reverse=True)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m detectors.deeplink_manifest_hunt <apk_characterization.json> <out.json>")
        sys.exit(1)

    characterization = load(sys.argv[1])
    findings = build_findings(characterization)
    dump(sys.argv[2], findings)

    print(f"[+] written {sys.argv[2]}")
    print(f"[+] findings={len(findings)}")
    for f in findings[:10]:
        print(f"- {f['candidate_score']} {f['priority']} {f['component_name']} schemes={f['schemes']} hosts={f['hosts']} paths={f['paths'][:5]}")


if __name__ == "__main__":
    main()
