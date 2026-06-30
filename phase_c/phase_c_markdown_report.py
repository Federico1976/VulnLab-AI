import json
import sys
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def family_questions(family):
    if "fileprovider" in family:
        return [
            "Is the provider exported or externally grantable?",
            "Which provider paths are declared and how broad are they?",
            "Can an external caller obtain or use a content URI?",
            "Are paths canonicalized before file access?",
            "Are sensitive internal files excluded from exposed paths?",
            "Can negative tests prove traversal-like or out-of-scope paths are rejected?"
        ]

    if "deeplink" in family or "webview" in family:
        return [
            "Can an external caller trigger the observed entrypoint?",
            "Which URI parts are attacker-controlled at runtime?",
            "Does attacker-controlled URI data reach WebView.loadUrl or equivalent sink?",
            "Is there a strict scheme/host/path allowlist before the sink?",
            "Is the WebView code first-party reachable or only plugin/library scaffolding?",
            "Can negative tests prove that untrusted hosts are rejected?"
        ]

    if "js_bridge" in family or "origin_confusion" in family:
        return [
            "Can untrusted web content reach the WebView context?",
            "Is a JavaScript bridge exposed to that content?",
            "Are origin checks enforced before native bridge invocation?",
            "Is bridge availability limited to trusted pages only?",
            "Can negative tests prove untrusted origins cannot invoke native capability?"
        ]

    if "token" in family or "storage" in family:
        return [
            "Which sensitive values are stored locally?",
            "Where are tokens, credentials, or secrets persisted?",
            "Are logs, backups, exported files, or shared storage involved?",
            "Can another app or local attacker access the data?",
            "Can negative tests prove secrets are absent from insecure locations?"
        ]

    if "exported_component" in family or "intent" in family:
        return [
            "Which exported component receives attacker-controlled input?",
            "Which intent actions, extras, or data fields are controllable?",
            "Does the component perform sensitive or privileged behavior?",
            "Are permission checks or caller identity checks enforced?",
            "Can negative tests prove unauthorized callers are rejected?"
        ]

    return [
        "What attacker-controlled source exists?",
        "What trust boundary is crossed?",
        "What sensitive operation may be reached?",
        "What validation or permission check may break the path?",
        "What counterevidence would downgrade this to signal-only?"
    ]


def family_dynamic_validation(family):
    if "fileprovider" in family:
        return [
            {
                "goal": "Confirm provider reachability",
                "method": "safe content URI access test using benign in-scope paths",
                "success_signal": "provider responds only for intended share/cache paths"
            },
            {
                "goal": "Check path scoping",
                "method": "attempt benign out-of-scope and traversal-like URI variants",
                "success_signal": "out-of-scope paths are rejected before file read"
            },
            {
                "goal": "Confirm no sensitive file exposure",
                "method": "verify readable files are non-sensitive and intentionally shared",
                "success_signal": "no private database, token, config, or internal file is exposed"
            }
        ]

    if "deeplink" in family or "webview" in family:
        return [
            {
                "goal": "Confirm external trigger reachability",
                "method": "safe adb intent trigger using benign controlled URI",
                "success_signal": "target component receives the intent"
            },
            {
                "goal": "Observe sink argument",
                "method": "instrument or hook WebView.loadUrl/evaluateJavascript equivalent",
                "success_signal": "controlled URI appears at the sink"
            },
            {
                "goal": "Check validation boundary",
                "method": "try trusted and untrusted benign hosts and compare behavior",
                "success_signal": "untrusted host is blocked before sensitive sink"
            }
        ]

    if "js_bridge" in family or "origin_confusion" in family:
        return [
            {
                "goal": "Confirm bridge exposure",
                "method": "load trusted and untrusted benign pages and enumerate bridge availability",
                "success_signal": "bridge is unavailable to untrusted origins"
            },
            {
                "goal": "Observe native bridge invocation boundary",
                "method": "instrument bridge methods and origin decision logic",
                "success_signal": "native methods are reachable only after trusted-origin validation"
            },
            {
                "goal": "Run negative origin tests",
                "method": "attempt benign calls from untrusted local/test origins",
                "success_signal": "calls are blocked before native capability"
            }
        ]

    if "token" in family or "storage" in family:
        return [
            {
                "goal": "Check insecure storage",
                "method": "inspect app-private, shared, backup, and log locations for benign token-like values",
                "success_signal": "sensitive values are absent or encrypted with appropriate controls"
            },
            {
                "goal": "Check log exposure",
                "method": "exercise login/session-like flows and inspect logcat for token-like data",
                "success_signal": "no secrets are logged"
            },
            {
                "goal": "Check backup/export exposure",
                "method": "verify backup/export settings and exported artifacts",
                "success_signal": "secrets are excluded from backups and exported files"
            }
        ]

    if "exported_component" in family or "intent" in family:
        return [
            {
                "goal": "Confirm unauthorized caller behavior",
                "method": "send safe crafted intents from adb without privileged identity",
                "success_signal": "component rejects unauthorized caller or ignores sensitive action"
            },
            {
                "goal": "Observe sensitive operation",
                "method": "instrument target action path and permission/caller checks",
                "success_signal": "sensitive operation requires explicit authorization"
            },
            {
                "goal": "Run negative permission tests",
                "method": "try benign inputs without expected permission or caller identity",
                "success_signal": "unauthorized paths are blocked"
            }
        ]

    return [
        {
            "goal": "Confirm runtime reachability",
            "method": "safe dynamic trigger",
            "success_signal": "reachable path is observed"
        },
        {
            "goal": "Search for counterevidence",
            "method": "inspect validation, permissions, and runtime guards",
            "success_signal": "guards are identified and evaluated"
        }
    ]


def why_interesting_text(family):
    if "fileprovider" in family:
        return (
            "The APK exposes FileProvider/content-URI-shaped patterns. This is not a finding; "
            "it is a candidate investigation focused on provider reachability, path scoping, URI grants, "
            "and counterevidence against unintended file exposure."
        )

    if "deeplink" in family or "webview" in family:
        return (
            "The APK exposes DeepLink-to-WebView-shaped patterns. This is not a finding; "
            "it is a candidate investigation focused on external routing, controlled URI propagation, "
            "WebView sink reachability, and origin validation."
        )

    if "js_bridge" in family or "origin_confusion" in family:
        return (
            "The APK exposes WebView JavaScript bridge/origin-boundary-shaped patterns. This is not a finding; "
            "it is a candidate investigation focused on bridge exposure, origin validation, and native capability boundaries."
        )

    if "token" in family or "storage" in family:
        return (
            "The APK exposes token/storage-shaped patterns. This is not a finding; "
            "it is a candidate investigation focused on sensitive data persistence, logs, backups, and local exposure."
        )

    if "exported_component" in family or "intent" in family:
        return (
            "The APK exposes exported-component/intent-shaped patterns. This is not a finding; "
            "it is a candidate investigation focused on caller controllability, permissions, and privileged behavior."
        )

    return (
        "The APK exposes Android security-relevant patterns. This is not a finding; "
        "it is a candidate investigation requiring causal and dynamic validation."
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: python3 -m phase_c.phase_c_markdown_report <phase_c_dir> <output_md>")

    phase_c_dir = Path(sys.argv[1])
    output_md = Path(sys.argv[2])

    summary = load_json(phase_c_dir / "phase_c_summary.json")
    hypotheses = load_json(phase_c_dir / "research_hypotheses.json")
    reasoning = load_json(phase_c_dir / "investigation_reasoning_plan.json")

    lines = []
    lines.append("# VulnLab-AI Phase C Report")
    lines.append("")
    lines.append("## Architecture")
    lines.append("")
    lines.append(f"- Mode: `{summary['architecture']['mode']}`")
    lines.append(f"- Model independent: `{summary['architecture']['model_independent']}`")
    lines.append(f"- LLM required: `{summary['architecture']['llm_required']}`")
    lines.append(f"- Candidate-only guardrail: `{summary['architecture']['candidate_only_guardrail']}`")
    lines.append(f"- Finding allowed: `{summary['architecture']['finding_allowed']}`")
    lines.append("")
    lines.append("## Cognitive Pipeline")
    lines.append("")
    for step in summary["pipeline"]:
        lines.append(f"- {step}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Observed patterns: `{summary['summary']['observed_patterns']['patterns']}`")
    lines.append(f"- Research hypotheses: `{summary['summary']['research_hypotheses']['hypotheses']}`")
    lines.append(f"- Strong knowledge matches: `{summary['summary']['knowledge_matches']['strong_matches']}`")
    lines.append(f"- Medium knowledge matches: `{summary['summary']['knowledge_matches'].get('medium_matches', 0)}`")
    lines.append(f"- Weak knowledge matches: `{summary['summary']['knowledge_matches']['weak_matches']}`")
    lines.append(f"- Finding allowed: `{summary['summary']['finding_allowed']}`")
    lines.append(f"- Requires dynamic validation: `{summary['summary']['requires_dynamic_validation']}`")
    lines.append("")
    lines.append("## Hypothesis Distribution")
    lines.append("")
    for k, v in hypotheses["summary"]["by_family"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("## Investigation Plans")
    lines.append("")

    if not reasoning.get("plans"):
        lines.append("No strong or medium investigation plans generated.")
    else:
        for plan in reasoning["plans"]:
            family = plan.get("case_id", "").lower()
            if "fileprovider" in family:
                family_key = "fileprovider_exposure"
            elif "deeplink" in family or "webview" in family:
                family_key = "deeplink_to_webview"
            elif "bridge" in family:
                family_key = "webview_js_bridge_origin_confusion"
            elif "token" in family or "storage" in family:
                family_key = "token_storage_exposure"
            elif "intent" in family or "exported" in family:
                family_key = "exported_component_intent_injection"
            else:
                family_key = family

            lines.append(f"### {plan['case_id']}")
            lines.append("")
            lines.append(f"**Title:** {plan['case_title']}")
            lines.append("")
            lines.append(f"**Matched patterns:** `{plan['matched_pattern_count']}`")
            lines.append("")
            lines.append(f"**Investigation status:** `{plan.get('investigation_status', 'candidate_investigation')}`")
            lines.append("")
            lines.append("**Why interesting:**")
            lines.append("")
            lines.append(why_interesting_text(family_key))
            lines.append("")
            lines.append("**Current claim limit:**")
            lines.append("")
            lines.append(f"`{plan['candidate_scope']['max_current_claim']}`")
            lines.append("")
            lines.append("**Do not claim:**")
            lines.append("")
            for dc in plan.get("do_not_claim", []):
                lines.append(f"- {dc.get('claim')}: {dc.get('reason')}")
            lines.append("")
            lines.append("**Research questions:**")
            lines.append("")
            for q in family_questions(family_key):
                lines.append(f"- {q}")
            lines.append("")
            lines.append("**Recommended dynamic validation:**")
            lines.append("")
            for dv in family_dynamic_validation(family_key):
                lines.append(f"- Goal: {dv['goal']}")
                lines.append(f"  - Method: {dv['method']}")
                lines.append(f"  - Success signal: {dv['success_signal']}")
            lines.append("")

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "output": str(output_md)
    }, indent=2))


if __name__ == "__main__":
    main()
