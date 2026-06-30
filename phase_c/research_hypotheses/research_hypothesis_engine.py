import json
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def hypothesis_for_pattern(pattern: Dict[str, Any]) -> Dict[str, Any]:
    shape = pattern.get("observed_shape", {})
    family = shape.get("investigation_family", "unknown")
    tags = set(shape.get("surface_tags", []))
    trust_boundary = shape.get("trust_boundary", "unknown")
    security_effect = shape.get("security_effect", "unknown")

    base = {
        "schema": "vulnlab.research_hypothesis.v1",
        "source_pattern_id": pattern.get("pattern_id"),
        "observed_shape": shape,
        "claim_guardrail": {
            "finding_allowed": False,
            "max_claim": "research_hypothesis_until_dynamic_validation"
        },
        "hypothesis_family": family,
        "trust_boundary_under_test": trust_boundary,
        "security_effect_under_test": security_effect,
        "status": "hypothesis_only"
    }

    if family == "deeplink_to_webview" or ("deeplink" in tags and "webview" in tags):
        base.update({
            "hypothesis": (
                "External URI routing may reach a WebView navigation context. "
                "If attacker-controlled URI parts cross into WebView sinks without strict origin validation, "
                "the app may expose attacker-controlled navigation behavior."
            ),
            "architectural_assumptions_to_challenge": [
                "Only trusted callers can invoke this route",
                "Deep link URI parts are validated before navigation",
                "WebView sinks are not reachable from external input",
                "Plugin WebView code is not exposed through first-party routing",
                "Untrusted hosts are rejected before sensitive operations"
            ],
            "benign_explanations": [
                "The deep link only opens trusted internal routes",
                "The WebView code is plugin scaffolding and not reachable",
                "The URI is parsed but not passed to WebView sinks",
                "A strict allowlist blocks untrusted scheme/host/path values"
            ],
            "research_questions": [
                "Can an external app invoke the route?",
                "Which URI fields are attacker-controlled at runtime?",
                "Does controlled data reach WebView.loadUrl or equivalent?",
                "Where is scheme/host/path validation enforced?",
                "Is the sink first-party reachable or library-only?",
                "What counterevidence would downgrade this to signal-only?"
            ],
            "dynamic_validation_goals": [
                "Trigger entrypoint safely with benign controlled URI",
                "Observe whether controlled URI reaches WebView sink",
                "Test trusted vs untrusted host behavior",
                "Confirm whether validation blocks before sink"
            ],
            "priority": "high"
        })
    elif family == "fileprovider_exposure" or "fileprovider" in tags:
        base.update({
            "hypothesis": (
                "The APK exposes a FileProvider-related surface. "
                "If external content URI access can reach sensitive paths without proper path scoping, "
                "there may be a file exposure or URI grant issue."
            ),
            "architectural_assumptions_to_challenge": [
                "Provider paths are strictly scoped",
                "URI grants cannot expose sensitive internal files",
                "External callers cannot select arbitrary files",
                "Canonicalization prevents traversal-like behavior"
            ],
            "benign_explanations": [
                "Provider exposes only cache/share directories",
                "No exported provider is reachable by attacker",
                "Manifest grants are restricted",
                "Paths are static and non-sensitive"
            ],
            "research_questions": [
                "Is the provider exported or grantable?",
                "Which paths are declared?",
                "Can an external caller obtain a content URI?",
                "Are paths canonicalized and scoped?",
                "What files are actually readable?"
            ],
            "dynamic_validation_goals": [
                "Enumerate declared provider paths safely",
                "Attempt benign URI access within allowed scope",
                "Verify traversal-like inputs are rejected",
                "Confirm no sensitive path exposure"
            ],
            "priority": "medium"
        })
    else:
        base.update({
            "hypothesis": (
                "The APK exposes an Android security-relevant surface, but the observed pattern "
                "is not yet specific enough to map to a known high-confidence family."
            ),
            "architectural_assumptions_to_challenge": [
                "The observed surface is externally reachable",
                "Attacker-controlled input crosses a trust boundary",
                "A sensitive operation is reachable",
                "Missing validation is security-relevant"
            ],
            "benign_explanations": [
                "The surface is internal only",
                "No attacker-controlled data reaches sensitive operations",
                "Validation or permissions block the path"
            ],
            "research_questions": [
                "What is the attacker-controlled source?",
                "What is the sink?",
                "Which trust boundary is crossed?",
                "What evidence is missing?"
            ],
            "dynamic_validation_goals": [
                "Confirm runtime reachability",
                "Observe source-to-sink behavior",
                "Search for counterevidence"
            ],
            "priority": "low"
        })

    return base


def build_hypotheses(patterns_doc: Dict[str, Any]) -> Dict[str, Any]:
    patterns = patterns_doc.get("patterns", [])
    hypotheses = [hypothesis_for_pattern(p) for p in patterns]

    summary = {
        "hypotheses": len(hypotheses),
        "by_priority": {},
        "by_family": {}
    }

    for h in hypotheses:
        pr = h.get("priority", "unknown")
        fam = h.get("hypothesis_family", "unknown")
        summary["by_priority"][pr] = summary["by_priority"].get(pr, 0) + 1
        summary["by_family"][fam] = summary["by_family"].get(fam, 0) + 1

    return {
        "status": "ok",
        "schema": "vulnlab.research_hypotheses.v1",
        "summary": summary,
        "hypotheses": hypotheses,
        "guardrail": {
            "candidate_only": True,
            "finding_allowed": False,
            "requires_dynamic_validation": True,
            "llm_required": False,
            "model_independent": True
        }
    }


def main() -> None:
    import sys

    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python3 -m phase_c.research_hypotheses.research_hypothesis_engine "
            "<observed_patterns_json> <output_json>"
        )

    patterns_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = build_hypotheses(load_json(patterns_path))

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(json.dumps({
        "status": result["status"],
        "schema": result["schema"],
        "summary": result["summary"],
        "guardrail": result["guardrail"],
        "output": str(output_path)
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
