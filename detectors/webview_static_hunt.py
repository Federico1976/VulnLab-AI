#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


WEBVIEW_PATTERNS = [
    "WebView",
    "loadUrl(",
    "loadData(",
    "loadDataWithBaseURL(",
    "evaluateJavascript(",
    "addJavascriptInterface(",
    "setJavaScriptEnabled(true)",
    "setAllowFileAccess(true)",
    "setAllowContentAccess(true)",
    "setAllowUniversalAccessFromFileURLs(true)",
    "setAllowFileAccessFromFileURLs(true)",
    "shouldOverrideUrlLoading",
    "onReceivedSslError",
    "proceed()",
    "AwesomeWebView"
]

RISK_WEIGHTS = {
    "loadUrl(": 25,
    "evaluateJavascript(": 30,
    "addJavascriptInterface(": 40,
    "setJavaScriptEnabled(true)": 25,
    "setAllowFileAccess(true)": 20,
    "setAllowContentAccess(true)": 15,
    "setAllowUniversalAccessFromFileURLs(true)": 40,
    "setAllowFileAccessFromFileURLs(true)": 35,
    "onReceivedSslError": 25,
    "proceed()": 30,
    "AwesomeWebView": 20
}


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump_json(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_source_roots(target):
    roots = []
    for rel in [
        "code/decompiled/sources",
        "code/decompiled_tesla_only",
        "sources",
        "jadx_sources",
        "decompiled"
    ]:
        p = target / rel
        if p.exists():
            roots.append(p)
    return roots


def is_third_party_file(path):
    s = str(path)
    third_party = [
        "/com/google/",
        "/androidx/",
        "/okhttp3/",
        "/com/wuadam/",
        "/kotlin/",
        "/kotlinx/",
        "/com/facebook/",
        "/io/flutter/"
    ]
    return any(x in s for x in third_party)


def first_party_prefixes(characterization):
    prefixes = set()

    pkg = characterization.get("package_metadata", {}).get("package")
    if pkg:
        parts = pkg.split(".")
        prefixes.add("/" + "/".join(parts) + "/")
        if len(parts) >= 3:
            prefixes.add("/" + "/".join(reversed(parts[:3])) + "/")

    surfaces = characterization.get("manifest_surfaces", {})
    for group in ("activities", "services", "receivers", "providers"):
        for c in surfaces.get(group, []):
            name = c.get("name") or ""
            if name.startswith(("com.google.", "androidx.", "com.willowtreeapps.", "com.facebook.", "okhttp3.")):
                continue
            parts = name.split(".")
            if len(parts) >= 3:
                prefixes.add("/" + "/".join(parts[:3]) + "/")

    return sorted(prefixes, key=len, reverse=True)


def is_first_party_file(path, prefixes):
    s = str(path)
    return any(prefix in s for prefix in prefixes)


def scan_file(path, first_party_prefix_list=None):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    # Avoid generic false positives: proceed() alone is common in OkHttp/interceptor code.
    if "WebView" not in text and "webview" not in text.lower() and "AwesomeWebView" not in text:
        webview_context = False
    else:
        webview_context = True

    hits = []
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        for pat in WEBVIEW_PATTERNS:
            if pat in line:
                if pat == "proceed()" and not webview_context:
                    continue
                hits.append({
                    "line": i,
                    "pattern": pat,
                    "code": line.strip()
                })

    if not hits:
        return None

    score = 0
    reasons = []

    for h in hits:
        pat = h["pattern"]
        if pat in RISK_WEIGHTS:
            score += RISK_WEIGHTS[pat]
            reasons.append(pat)

    if "loadUrl(" in reasons and "setJavaScriptEnabled(true)" in reasons:
        score += 20
        reasons.append("loadUrl_with_javascript_enabled")

    if "addJavascriptInterface(" in reasons and "setJavaScriptEnabled(true)" in reasons:
        score += 25
        reasons.append("js_interface_with_javascript_enabled")

    if "onReceivedSslError" in reasons and "proceed()" in reasons:
        score += 30
        reasons.append("ssl_error_proceed_pattern")

    if is_third_party_file(path):
        ownership = "third_party_or_library"
    elif is_first_party_file(path, first_party_prefix_list or []):
        ownership = "first_party_or_app_code"
    else:
        ownership = "third_party_or_library"

    if ownership == "third_party_or_library":
        score = min(score, 45)
        reasons.append("third_party_or_library_demoted")

    score = max(0, min(100, score))

    if score >= 75:
        priority = "high_candidate_priority"
    elif score >= 45:
        priority = "medium_candidate_priority"
    elif score >= 20:
        priority = "low_candidate_priority"
    else:
        priority = "informational"

    return {
        "file": str(path),
        "score": score,
        "priority": priority,
        "ownership": ownership,
        "hits": hits,
        "risk_reasons": sorted(set(reasons))
    }


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m detectors.webview_static_hunt <target_dir> <apk_characterization.json> <out.json>")
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()
    characterization = load_json(sys.argv[2])
    out = Path(sys.argv[3])

    roots = find_source_roots(target)
    fp_prefixes = first_party_prefixes(characterization)

    print(f"[+] first_party_prefixes={fp_prefixes}")

    findings = []

    for root in roots:
        for ext in ("*.java", "*.kt"):
            for f in root.rglob(ext):
                r = scan_file(f, fp_prefixes)
                if not r:
                    continue

                findings.append({
                    "id": f"APK-WEBVIEW-STATIC-{len(findings)+1:03d}",
                    "title": "WebView-related static surface",
                    "category": "webview_static",
                    "status": "candidate_not_confirmed",
                    "package": characterization.get("package_metadata", {}).get("package"),
                    "app_label": characterization.get("package_metadata", {}).get("label"),
                    "file": r["file"],
                    "candidate_score": r["score"],
                    "priority": r["priority"],
                    "ownership": r.get("ownership"),
                    "hits": r["hits"],
                    "risk_reasons": r["risk_reasons"],
                    "impact_hypothesis": "WebView-related code may load or process URLs/content. Impact depends on whether input is attacker-controlled, whether JavaScript/file access is enabled, and whether sensitive bridges or auth flows are reachable.",
                    "required_next_analysis": [
                        "Identify whether URL/content originates from deeplink, OAuth callback, push, remote config, server response, or trusted constant.",
                        "Trace loadUrl/evaluateJavascript/addJavascriptInterface callsites.",
                        "Check WebSettings for JavaScript, file access, content access, mixed content, and universal file URL access.",
                        "Correlate with exported deeplink Activity and AuthActivity routes.",
                        "Validate dynamically with Frida logging before any security claim."
                    ],
                    "validation_guardrail": "Do not report as vulnerability without source trace, attacker-control proof, and dynamic validation."
                })

    findings = sorted(findings, key=lambda x: x["candidate_score"], reverse=True)
    dump_json(out, findings)

    print(f"[+] written {out}")
    print(f"[+] findings={len(findings)}")
    for f in findings[:10]:
        print(f"- {f['candidate_score']} {f['priority']} {f['file']} reasons={f['risk_reasons']}")


if __name__ == "__main__":
    main()
