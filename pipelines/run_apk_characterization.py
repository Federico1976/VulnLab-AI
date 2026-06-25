#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path
from collections import Counter


def run(cmd, cwd):
    print(f"\n[+] RUN: {' '.join(map(str, cmd))}")
    subprocess.run([str(x) for x in cmd], cwd=cwd, check=True)


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main():
    if len(sys.argv) != 3:
        print("Usage: PYTHONPATH=$PWD python3 -m pipelines.run_apk_characterization <apk> <out_dir>")
        sys.exit(1)

    repo = Path.cwd()
    apk = Path(sys.argv[1]).resolve()
    out_dir = Path(sys.argv[2]).resolve()

    if not apk.exists():
        raise SystemExit(f"[!] APK not found: {apk}")

    out_dir.mkdir(parents=True, exist_ok=True)

    char_json = out_dir / "apk_characterization.json"
    deeplink_json = out_dir / "deeplink_manifest_candidates.json"
    deeplink_cards = out_dir / "investigation_cards" / "deeplink_manifest"
    webview_json = out_dir / "webview_static_candidates.json"
    webview_cards = out_dir / "investigation_cards" / "webview_static"
    deeplink_webview_corr = out_dir / "deeplink_webview_correlation.json"
    summary_json = out_dir / "universal_apk_summary.json"
    readme = out_dir / "README.md"

    print("[+] Universal APK characterization started")
    print(f"[+] APK:    {apk}")
    print(f"[+] Out:    {out_dir}")

    run([
        "python3", "-m", "core.apk_characterization_engine",
        apk,
        out_dir
    ], repo)

    if not char_json.exists():
        raise SystemExit(f"[!] Missing characterization output: {char_json}")

    characterization = load_json(char_json)
    recommended = characterization.get("recommended_pipelines", [])

    print("\n[+] Pipeline selector:")
    for r in recommended:
        print(f"  - {r}")

    produced = {
        "apk_characterization": str(char_json),
        "deeplink_manifest_candidates": None,
        "deeplink_cards": None,
        "webview_static_candidates": None,
        "webview_cards": None,
        "deeplink_webview_correlation": None
    }

    if "deeplink_manifest_hunt" in recommended:
        run([
            "python3", "-m", "detectors.deeplink_manifest_hunt",
            char_json,
            deeplink_json
        ], repo)

        if not deeplink_json.exists():
            raise SystemExit(f"[!] Missing deeplink candidates: {deeplink_json}")

        if deeplink_cards.exists():
            subprocess.run(["rm", "-rf", str(deeplink_cards)], check=True)

        run([
            "python3", "-m", "reports.deeplink_investigation_cards",
            deeplink_json,
            deeplink_cards
        ], repo)

        produced["deeplink_manifest_candidates"] = str(deeplink_json)
        produced["deeplink_cards"] = str(deeplink_cards)

    if "webview_hunt" in recommended:
        run([
            "python3", "-m", "detectors.webview_static_hunt",
            out_dir,
            char_json,
            webview_json
        ], repo)

        if webview_cards.exists():
            subprocess.run(["rm", "-rf", str(webview_cards)], check=True)

        run([
            "python3", "-m", "reports.webview_investigation_cards",
            webview_json,
            webview_cards
        ], repo)

        produced["webview_static_candidates"] = str(webview_json)
        produced["webview_cards"] = str(webview_cards)

    if deeplink_json.exists() and webview_json.exists():
        run([
            "python3", "-m", "reasoning_agent.correlate_deeplink_webview",
            deeplink_json,
            webview_json,
            deeplink_webview_corr
        ], repo)
        produced["deeplink_webview_correlation"] = str(deeplink_webview_corr)

    deeplink_items = load_json(deeplink_json) if deeplink_json.exists() else []
    webview_items = load_json(webview_json) if webview_json.exists() else []
    corr_items = load_json(deeplink_webview_corr) if deeplink_webview_corr.exists() else []
    deeplink_priority = Counter(x.get("priority") for x in deeplink_items)
    deeplink_ownership = Counter(x.get("ownership") for x in deeplink_items)
    webview_priority = Counter(x.get("priority") for x in webview_items)
    webview_ownership = Counter(x.get("ownership") for x in webview_items)
    corr_priority = Counter(x.get("correlation_priority") for x in corr_items)

    features = [
        k for k, v in characterization.get("features", {}).items()
        if isinstance(v, dict) and v.get("present")
    ]

    summary = {
        "schema": "vulnlab_ai.universal_apk_summary.v1",
        "apk": str(apk),
        "package": characterization.get("package_metadata", {}).get("package"),
        "label": characterization.get("package_metadata", {}).get("label"),
        "size_bytes": characterization.get("size_bytes"),
        "sha256": characterization.get("sha256"),
        "detected_features": features,
        "recommended_pipelines": recommended,
        "produced_artifacts": produced,
        "deeplink_manifest": {
            "total_candidates": len(deeplink_items),
            "priority_distribution": dict(deeplink_priority),
            "ownership_distribution": dict(deeplink_ownership)
        },
        "webview_static": {
            "total_candidates": len(webview_items),
            "priority_distribution": dict(webview_priority),
            "ownership_distribution": dict(webview_ownership)
        },
        "deeplink_webview_correlation": {
            "total_candidates": len(corr_items),
            "priority_distribution": dict(corr_priority)
        },
        "candidate_only_note": "No item is a confirmed vulnerability without source trace, reachability proof, and dynamic validation."
    }

    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    readme.write_text(
        "# Universal APK Characterization Summary\n\n"
        "Candidate-only analysis for responsible disclosure. No item is a confirmed vulnerability without validation.\n\n"
        f"- APK: `{apk}`\n"
        f"- Package: `{summary['package']}`\n"
        f"- Label: `{summary['label']}`\n"
        f"- Size bytes: `{summary['size_bytes']}`\n"
        f"- SHA256: `{summary['sha256']}`\n\n"
        "## Detected features\n\n"
        + "".join(f"- `{x}`\n" for x in features)
        + "\n## Recommended pipelines\n\n"
        + "".join(f"- `{x}`\n" for x in recommended)
        + "\n## Deeplink manifest hunt\n\n"
        f"- Total candidates: `{len(deeplink_items)}`\n"
        f"- Priority distribution: `{dict(deeplink_priority)}`\n"
        f"- Ownership distribution: `{dict(deeplink_ownership)}`\n\n"
        "## Artifacts\n\n"
        f"- Characterization: `{char_json}`\n"
        f"- Deeplink candidates: `{deeplink_json if deeplink_json.exists() else 'not_run'}`\n"
        f"- Deeplink cards: `{deeplink_cards if deeplink_cards.exists() else 'not_run'}`\n"
        f"- WebView candidates: `{webview_json if webview_json.exists() else 'not_run'}`\n"
        f"- WebView cards: `{webview_cards if webview_cards.exists() else 'not_run'}`\n"
        f"- Deeplink/WebView correlation: `{deeplink_webview_corr if deeplink_webview_corr.exists() else 'not_run'}`\n"
        f"- Summary JSON: `{summary_json}`\n",
        encoding="utf-8"
    )

    print("\n========== UNIVERSAL APK SUMMARY ==========")
    print(f"package:              {summary['package']}")
    print(f"label:                {summary['label']}")
    print(f"features:             {features}")
    print(f"recommended:          {recommended}")
    print(f"deeplink candidates:  {len(deeplink_items)}")
    print(f"deeplink priority:    {dict(deeplink_priority)}")
    print(f"deeplink ownership:   {dict(deeplink_ownership)}")
    print(f"webview candidates:   {len(webview_items)}")
    print(f"webview priority:     {dict(webview_priority)}")
    print(f"webview ownership:    {dict(webview_ownership)}")
    print(f"dl->webview corr:     {len(corr_items)}")
    print(f"corr priority:        {dict(corr_priority)}")
    print(f"summary:              {summary_json}")
    print(f"readme:               {readme}")
    print("===========================================")


if __name__ == "__main__":
    main()
