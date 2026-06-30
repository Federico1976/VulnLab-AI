#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


NVD_CVE_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OSV_API = "https://api.osv.dev/v1/query"
ANDROID_BULLETIN_OVERVIEW = "https://source.android.com/docs/security/bulletin"


ANDROID_KEYWORDS = [
    "android",
    "webview",
    "intent",
    "content provider",
    "fileprovider",
    "ipc",
    "binder",
    "exported",
    "permission",
    "path traversal",
    "uri",
    "deeplink",
    "privilege escalation",
    "information disclosure",
]


def fetch_json(url: str, headers: Dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "VulnLab-AI/Generalization"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "VulnLab-AI/Generalization"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", errors="replace")


def collect_nvd_android(keyword: str = "android", results: int = 40) -> List[Dict[str, Any]]:
    qs = urllib.parse.urlencode({
        "keywordSearch": keyword,
        "resultsPerPage": results,
    })
    data = fetch_json(f"{NVD_CVE_API}?{qs}")

    out = []
    for item in data.get("vulnerabilities", []):
        cve = item.get("cve", {})
        cve_id = cve.get("id")
        descs = cve.get("descriptions", [])
        description = ""
        for d in descs:
            if d.get("lang") == "en":
                description = d.get("value", "")
                break

        metrics = cve.get("metrics", {})
        refs = cve.get("references", {}).get("referenceData", [])

        text = f"{cve_id} {description}".lower()
        if not any(k in text for k in ANDROID_KEYWORDS):
            continue

        out.append({
            "source": "nvd",
            "source_type": "cve",
            "id": cve_id,
            "published": cve.get("published"),
            "lastModified": cve.get("lastModified"),
            "description": description,
            "metrics": metrics,
            "references": refs[:5],
            "raw_shape_hints": infer_shape_hints(description),
        })

    return out


def collect_osv_android_packages() -> List[Dict[str, Any]]:
    # OSV is mainly package/version oriented. This collector seeds Android-relevant ecosystems conservatively.
    seeds = [
        {"package": {"name": "android", "ecosystem": "Android"}},
    ]

    out = []
    for seed in seeds:
        try:
            body = json.dumps(seed).encode()
            req = urllib.request.Request(
                OSV_API,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "VulnLab-AI/Generalization",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))

            for vuln in data.get("vulns", []):
                summary = vuln.get("summary") or vuln.get("details") or ""
                out.append({
                    "source": "osv",
                    "source_type": "osv_vulnerability",
                    "id": vuln.get("id"),
                    "summary": summary,
                    "details": vuln.get("details"),
                    "aliases": vuln.get("aliases", []),
                    "modified": vuln.get("modified"),
                    "published": vuln.get("published"),
                    "raw_shape_hints": infer_shape_hints(summary + " " + (vuln.get("details") or "")),
                })
        except Exception as e:
            out.append({
                "source": "osv",
                "source_type": "collector_error",
                "error": repr(e),
                "seed": seed,
            })

    return out


def collect_android_bulletin_links(limit: int = 24) -> List[Dict[str, Any]]:
    html = fetch_text(ANDROID_BULLETIN_OVERVIEW)

    links = []
    for m in re.finditer(r'href="([^"]*?/docs/security/bulletin/\d{4}/\d{4}-\d{2}-\d{2})"', html):
        href = m.group(1)
        if href.startswith("http"):
            url = href
        else:
            url = "https://source.android.com" + href

        if url not in [x.get("url") for x in links]:
            links.append({"url": url})

    links = links[:limit]

    out = []
    for item in links:
        url = item["url"]
        try:
            page = fetch_text(url)
            cves = sorted(set(re.findall(r"CVE-\d{4}-\d{4,7}", page)))
            text_lower = page.lower()

            out.append({
                "source": "android_security_bulletin",
                "source_type": "bulletin",
                "url": url,
                "cves": cves[:100],
                "cve_count": len(cves),
                "raw_shape_hints": infer_shape_hints(text_lower),
            })
        except Exception as e:
            out.append({
                "source": "android_security_bulletin",
                "source_type": "collector_error",
                "url": url,
                "error": repr(e),
            })

    return out


def infer_shape_hints(text: str) -> List[str]:
    t = text.lower()
    hints = []

    if any(x in t for x in ["intent", "deeplink", "deep link", "exported"]):
        hints.append("external_entry_to_sensitive_sink")

    if any(x in t for x in ["content provider", "fileprovider", "uri", "path traversal", "file access"]):
        hints.append("untrusted_uri_to_file_access")

    if any(x in t for x in ["webview", "loadurl", "javascript"]):
        hints.append("webview_external_input_to_load")

    if any(x in t for x in ["ipc", "binder", "permission", "privilege escalation", "elevation of privilege"]):
        hints.append("ipc_boundary_to_privileged_action")

    if not hints:
        hints.append("generic_sink_reachability")

    return sorted(set(hints))


def distill_sources(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    patterns: Dict[str, Dict[str, Any]] = {}
    strategies: Dict[str, Dict[str, Any]] = {}

    for item in items:
        for shape in item.get("raw_shape_hints", []):
            patterns.setdefault(shape, {
                "pattern_id": f"external_knowledge_pattern::{shape}",
                "pattern_shape": shape,
                "source_count": 0,
                "sources": [],
                "promotion_state": "external_distilled_candidate",
                "framework_independent": True,
                "finding_allowed": False,
            })

            patterns[shape]["source_count"] += 1
            patterns[shape]["sources"].append({
                "source": item.get("source"),
                "source_type": item.get("source_type"),
                "id": item.get("id"),
                "url": item.get("url"),
            })

            strategies.setdefault(shape, {
                "strategy_id": f"external_knowledge_strategy::{shape}",
                "strategy_shape": shape,
                "preferred_experiment_order": preferred_steps_for_shape(shape),
                "maturity": "external_candidate",
                "finding_allowed": False,
                "requires_local_apk_evidence": True,
                "requires_dynamic_validation": True,
            })

    return {
        "schema_version": "external_knowledge_distillation.v1",
        "created_at": int(time.time()),
        "summary": {
            "raw_items": len(items),
            "patterns": len(patterns),
            "strategies": len(strategies),
            "finding_allowed": False,
            "framework_independent": True,
        },
        "patterns": list(patterns.values()),
        "strategies": list(strategies.values()),
    }


def preferred_steps_for_shape(shape: str) -> List[str]:
    mapping = {
        "external_entry_to_sensitive_sink": [
            "prove_external_reachability",
            "prove_source_control",
            "prove_sensitive_sink_effect",
            "resolve_counter_evidence",
        ],
        "untrusted_uri_to_file_access": [
            "prove_uri_or_path_control",
            "prove_file_boundary_crossing",
            "prove_canonicalization_absence_or_bypass",
            "resolve_permission_controls",
        ],
        "webview_external_input_to_load": [
            "prove_external_navigation_control",
            "prove_url_load_sink",
            "prove_domain_or_scheme_filter_gap",
            "resolve_webview_counter_evidence",
        ],
        "ipc_boundary_to_privileged_action": [
            "prove_caller_control_and_privilege_gap",
            "prove_binder_or_component_reachability",
            "prove_privileged_action",
            "resolve_permission_counter_evidence",
        ],
    }
    return mapping.get(shape, [
        "inspect_semantic_graph",
        "identify_candidate_shape",
        "build_candidate_validation_plan",
    ])


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Knowledge Ingestion Source Collector v1")
    ap.add_argument("--out-raw", required=True)
    ap.add_argument("--out-distilled", required=True)
    ap.add_argument("--nvd-keyword", default="android")
    ap.add_argument("--nvd-results", type=int, default=40)
    ap.add_argument("--android-bulletins", type=int, default=12)
    args = ap.parse_args()

    raw_items: List[Dict[str, Any]] = []

    try:
        raw_items.extend(collect_nvd_android(args.nvd_keyword, args.nvd_results))
    except Exception as e:
        raw_items.append({"source": "nvd", "source_type": "collector_error", "error": repr(e)})

    raw_items.extend(collect_osv_android_packages())

    try:
        raw_items.extend(collect_android_bulletin_links(args.android_bulletins))
    except Exception as e:
        raw_items.append({"source": "android_security_bulletin", "source_type": "collector_error", "error": repr(e)})

    distilled = distill_sources(raw_items)

    Path(args.out_raw).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_raw).write_text(json.dumps(raw_items, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(args.out_distilled).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_distilled).write_text(json.dumps(distilled, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "raw_items": len(raw_items),
        "distilled_summary": distilled["summary"],
        "out_raw": args.out_raw,
        "out_distilled": args.out_distilled,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
