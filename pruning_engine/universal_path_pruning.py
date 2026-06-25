import json
import sys
from pathlib import Path


def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(errors="ignore"))
    except Exception:
        return default


def text_of(x):
    return json.dumps(x, ensure_ascii=False).lower()


def extract_corr_summary(corr):
    deeplink = corr.get("deeplink") or {}
    webview = corr.get("webview") or {}

    return {
        "deeplink_component": (
            deeplink.get("component_name")
            or deeplink.get("component")
            or deeplink.get("class")
            or deeplink.get("name")
        ),
        "deeplink_hosts": deeplink.get("hosts"),
        "deeplink_paths": deeplink.get("paths"),
        "webview_file": (
            webview.get("file")
            or webview.get("source_file")
            or webview.get("webview_file")
        ),
        "webview_priority": webview.get("priority"),
        "webview_ownership": webview.get("ownership"),
        "webview_reasons": webview.get("risk_reasons") or webview.get("reasons"),
    }


def classify_corr(corr, runtime_fp):
    t = text_of(corr)
    corr_summary = extract_corr_summary(corr)
    score = corr.get("correlation_score") or corr.get("score") or corr.get("candidate_score") or 0
    reasons = []
    demotions = []

    # Strong keep evidence
    if "reactnativecommunity/webview" in t or "rncwebview" in t:
        score += 30
        reasons.append("React Native WebView surface matches React Native runtime")

    if "ee.linktr.admin" in t or "admin/linktr/ee" in t:
        score += 25
        reasons.append("first-party package evidence")

    if "mainactivity" in t and runtime_fp.get("primary_runtime") == "react_native":
        score += 20
        reasons.append("React Native MainActivity is plausible app runtime entrypoint")

    if "deeplink" in t and ("webview" in t or "loadurl" in t):
        score += 5
        reasons.append("weak deeplink/webview semantic overlap")

    # Demotions for SDK-only/library/informational surfaces unless specific bridge/path evidence exists
    ownership = (corr_summary.get("webview_ownership") or "").lower()
    priority = (corr_summary.get("webview_priority") or "").lower()

    deeplink_component = (corr_summary.get("deeplink_component") or "").lower()

    non_activity_like = any(x in deeplink_component for x in [
        "receiver", "widgetprovider", "provider", "service"
    ])

    if non_activity_like:
        score -= 75
        demotions.append("entrypoint is receiver/widget/provider/service; requires explicit runtime handoff edge")

    config_like_activity = any(x in deeplink_component for x in [
        "config", "settings", "preference", "widget"
    ])

    if config_like_activity and "mainactivity" not in deeplink_component:
        score -= 55
        demotions.append("config/widget/settings Activity; requires explicit navigation edge")

    if "third_party" in ownership or "library" in ownership:
        score -= 55
        demotions.append("webview ownership is third_party_or_library; requires explicit call edge")

    if priority == "informational":
        score -= 45
        demotions.append("informational webview candidate; insufficient for strong reachability")

    third_party_markers = [
        "io/intercom", "com/braze", "com/amazon", "androidx/work",
        "com/google/firebase", "app/notifee", "datadog", "bugsnag"
    ]

    if any(m in t for m in third_party_markers):
        score -= 60
        demotions.append("third-party SDK surface; requires explicit app-to-SDK call edge")

    if "webview_static" in t and "mainactivity" in t and not any(x in t for x in ["rncwebview", "reactnativecommunity", "ee.linktr.admin"]):
        score -= 20
        demotions.append("broad MainActivity-to-WebView cartesian correlation")

    strong_evidence = any(
        r.startswith("React Native WebView surface")
        or r.startswith("first-party package evidence")
        for r in reasons
    )

    if score >= 130 and strong_evidence and not demotions and priority in {"high_candidate_priority", "medium_candidate_priority"}:
        decision = "keep_high"
        confidence = "high"
    elif score >= 100 and strong_evidence and priority != "informational":
        decision = "keep_medium"
        confidence = "medium"
    elif score >= 70:
        decision = "review_low"
        confidence = "low"
    else:
        decision = "prune"
        confidence = "low"

    return {
        "decision": decision,
        "pruned": decision == "prune",
        "pruned_score": score,
        "confidence": confidence,
        "keep_reasons": reasons,
        "demotions": demotions,
        "summary": corr_summary,
        "raw": corr,
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: PYTHONPATH=$PWD python3 -m pruning_engine.universal_path_pruning output/<target_dir>")
        sys.exit(1)

    target = Path(sys.argv[1])
    fp = load_json(target / "runtime_fingerprint_v2.json", {})
    corr = load_json(target / "deeplink_webview_correlation.json", [])

    if isinstance(corr, dict):
        corr = corr.get("correlations") or corr.get("items") or []

    pruned = [classify_corr(c, fp) for c in corr if isinstance(c, dict)]

    out = target / "universal_path_pruning.json"
    out.write_text(json.dumps(pruned, indent=2), encoding="utf-8")

    summary = {}
    for x in pruned:
        summary[x["decision"]] = summary.get(x["decision"], 0) + 1

    print("[+] Universal Path Pruning written:", out)
    print(json.dumps({
        "input_correlations": len(corr),
        "output_items": len(pruned),
        "summary": summary,
    }, indent=2))


if __name__ == "__main__":
    main()
