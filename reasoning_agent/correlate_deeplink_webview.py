#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def is_noise_webview_candidate(wv):
    f = str(wv.get("file", ""))
    if f.endswith("/R.java") or "/R$" in f:
        return True
    if "/okhttp3/" in f:
        return True
    return False


def score_pair(dl, wv):
    if is_noise_webview_candidate(wv):
        return 0, "weak_or_no_correlation", ["noise_candidate_excluded"]

    score = 0
    reasons = []

    if dl.get("ownership") == "first_party_or_app_code":
        score += 25
        reasons.append("first_party_deeplink")

    if wv.get("ownership") == "first_party_or_app_code":
        score += 25
        reasons.append("first_party_webview")

    if dl.get("priority") == "high_candidate_priority":
        score += 20
        reasons.append("high_priority_deeplink")

    if wv.get("priority") == "high_candidate_priority":
        score += 20
        reasons.append("high_priority_webview")

    dl_text = " ".join([
        str(dl.get("component_name", "")),
        " ".join(dl.get("schemes", [])),
        " ".join(dl.get("hosts", [])),
        " ".join(dl.get("paths", [])),
    ]).lower()

    wv_text = " ".join([
        str(wv.get("file", "")),
        " ".join(wv.get("risk_reasons", [])),
        " ".join(h.get("code", "") for h in wv.get("hits", [])),
    ]).lower()

    if "auth" in dl_text and ("auth" in wv_text or "oauth" in dl_text):
        score += 10
        reasons.append("auth_flow_overlap")

    if "http" in dl_text or "https" in dl_text or "wienapp" in dl_text:
        score += 10
        reasons.append("url_or_custom_scheme_input_surface")

    if "loadurl" in wv_text or "loadurl(" in wv_text:
        score += 15
        reasons.append("webview_loadurl_sink")

    if "javascript" in wv_text:
        score += 10
        reasons.append("javascript_related_webview_behavior")

    score = max(0, min(100, score))

    # Conservative rule:
    # high correlation requires both surfaces to be first-party.
    if score >= 80 and dl.get("ownership") == "first_party_or_app_code" and wv.get("ownership") == "first_party_or_app_code":
        priority = "high_correlation_candidate"
    elif score >= 55:
        priority = "medium_correlation_candidate"
    elif score >= 30:
        priority = "low_correlation_candidate"
    else:
        priority = "weak_or_no_correlation"

    return score, priority, reasons


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m reasoning_agent.correlate_deeplink_webview <deeplink_candidates.json> <webview_candidates.json> <out.json>")
        sys.exit(1)

    deeplinks = load(sys.argv[1])
    webviews = load(sys.argv[2])

    out = []
    idx = 1

    for dl in deeplinks:
        for wv in webviews:
            score, priority, reasons = score_pair(dl, wv)

            if score < 55:
                continue

            out.append({
                "id": f"APK-CORR-DEEPLINK-WEBVIEW-{idx:03d}",
                "title": "Deeplink to WebView correlation candidate",
                "status": "candidate_not_confirmed",
                "correlation_type": "deeplink_to_webview",
                "correlation_score": score,
                "correlation_priority": priority,
                "correlation_reasons": reasons,
                "deeplink": {
                    "component": dl.get("component_name"),
                    "priority": dl.get("priority"),
                    "ownership": dl.get("ownership"),
                    "schemes": dl.get("schemes"),
                    "hosts": dl.get("hosts"),
                    "paths": dl.get("paths")
                },
                "webview": {
                    "file": wv.get("file"),
                    "priority": wv.get("priority"),
                    "ownership": wv.get("ownership"),
                    "risk_reasons": wv.get("risk_reasons"),
                    "top_hits": wv.get("hits", [])[:20]
                },
                "impact_hypothesis": "A first-party exported deeplink or app link may route attacker-controlled URL/navigation state toward a WebView load path. This is only a correlation candidate until source routing and runtime validation prove reachability.",
                "required_next_analysis": [
                    "Resolve deeplink routing code for the component.",
                    "Trace Intent data / Uri path / query parameters into navigation handlers.",
                    "Check whether the WebView Activity receives URL or route state from deeplink handling.",
                    "Hook Activity.onCreate/onNewIntent and WebView.loadUrl with Frida on the rooted device.",
                    "Use benign payloads only and confirm actual runtime route before any report."
                ],
                "guardrail": "Do not call this a vulnerability without confirmed source-to-sink reachability and dynamic validation."
            })
            idx += 1

    out = sorted(out, key=lambda x: x["correlation_score"], reverse=True)
    dump(sys.argv[3], out)

    print(f"[+] written {sys.argv[3]}")
    print(f"[+] correlations={len(out)}")
    for x in out[:10]:
        print(f"- {x['correlation_score']} {x['correlation_priority']} {x['deeplink']['component']} -> {Path(x['webview']['file']).name}")


if __name__ == "__main__":
    main()
