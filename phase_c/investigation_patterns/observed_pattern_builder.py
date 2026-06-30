import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "objects", "evidence_models", "effects", "evaluations"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


def normalize_text(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, str):
        return value.strip() or "unknown"
    return str(value)


def infer_surface_tags(model: Dict[str, Any]) -> List[str]:
    raw = json.dumps(model, ensure_ascii=False).lower()
    tags = []

    checks = {
        "deeplink": ["deeplink", "deep_link", "custom_scheme", "intent_data_uri", "scheme"],
        "webview": ["webview", "loadurl", "evaluatejavascript", "addjavascriptinterface"],
        "fileprovider": ["fileprovider", "content_uri", "file_provider"],
        "flutter": ["flutter", "dart", "plugin_channel"],
        "kotlin_compose": ["compose", "kotlin"],
        "exported_component": ["exported", "externally_reachable"],
        "receiver": ["receiver", "broadcast"],
        "service": ["service"],
        "activity": ["activity"]
    }

    for tag, needles in checks.items():
        if any(n in raw for n in needles):
            tags.append(tag)

    return sorted(set(tags))


def infer_trust_boundary(tags: List[str]) -> str:
    if "deeplink" in tags or "exported_component" in tags:
        if "webview" in tags:
            return "external_app_to_app_internal_to_webview"
        return "external_app_to_app_internal"
    if "webview" in tags:
        return "web_content_to_native_or_app_context"
    if "fileprovider" in tags:
        return "content_uri_to_filesystem"
    return "unknown"


def infer_security_effect(tags: List[str]) -> str:
    if "deeplink" in tags and "webview" in tags:
        return "attacker_controlled_navigation_candidate"
    if "webview" in tags:
        return "webview_sensitive_operation_candidate"
    if "fileprovider" in tags:
        return "file_exposure_or_uri_grant_candidate"
    if "exported_component" in tags:
        return "external_component_invocation_candidate"
    return "unknown_security_effect_candidate"


def infer_investigation_family(tags: List[str]) -> str:
    if "deeplink" in tags and "webview" in tags:
        return "deeplink_to_webview"
    if "fileprovider" in tags:
        return "fileprovider_exposure"
    if "webview" in tags:
        return "webview_surface"
    if "exported_component" in tags:
        return "exported_component_surface"
    return "generic_android_surface"


def build_observed_patterns(phase_b_brain_dir: Path) -> Dict[str, Any]:
    evidence_models = as_list(load_json(phase_b_brain_dir / "evidence_models.json", []))
    causal_reachability = as_list(load_json(phase_b_brain_dir / "causal_reachability_v2.json", []))
    security_effects = as_list(load_json(phase_b_brain_dir / "security_effects_aggregated.json", []))
    proof_evaluations = as_list(load_json(phase_b_brain_dir / "proof_evaluations.json", []))
    dynamic_plans = as_list(load_json(phase_b_brain_dir / "dynamic_validation_plans.json", []))

    patterns = []

    for idx, model in enumerate(evidence_models, start=1):
        tags = infer_surface_tags(model)
        family = infer_investigation_family(tags)
        trust_boundary = infer_trust_boundary(tags)
        security_effect = infer_security_effect(tags)

        pattern = {
            "schema": "vulnlab.observed_investigation_pattern.v1",
            "pattern_id": f"OIP-{idx:04d}",
            "source": {
                "phase_b_brain_dir": str(phase_b_brain_dir),
                "evidence_model_index": idx - 1
            },
            "observed_shape": {
                "investigation_family": family,
                "surface_tags": tags,
                "trust_boundary": trust_boundary,
                "security_effect": security_effect
            },
            "phase_ab_links": {
                "has_evidence_model": True,
                "has_causal_reachability": bool(causal_reachability),
                "has_security_effects": bool(security_effects),
                "has_proof_evaluations": bool(proof_evaluations),
                "has_dynamic_validation_plans": bool(dynamic_plans)
            },
            "claim_guardrail": {
                "max_claim_without_dynamic_validation": "candidate_evidence",
                "finding_allowed": False
            },
            "reasoning_state": {
                "status": "observed_pattern_only",
                "ready_for_knowledge_matching": True,
                "requires_dynamic_validation_before_finding": True
            },
            "raw_evidence_model": model
        }

        patterns.append(pattern)

    summary = {
        "patterns": len(patterns),
        "families": {},
        "surface_tags": {}
    }

    for p in patterns:
        fam = p["observed_shape"]["investigation_family"]
        summary["families"][fam] = summary["families"].get(fam, 0) + 1
        for tag in p["observed_shape"]["surface_tags"]:
            summary["surface_tags"][tag] = summary["surface_tags"].get(tag, 0) + 1

    return {
        "status": "ok",
        "schema": "vulnlab.observed_investigation_patterns.v1",
        "summary": summary,
        "patterns": patterns
    }


def main() -> None:
    import sys

    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python3 -m phase_c.investigation_patterns.observed_pattern_builder "
            "<phase_b_brain_dir> <output_json>"
        )

    phase_b_brain_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])
    output_json.parent.mkdir(parents=True, exist_ok=True)

    result = build_observed_patterns(phase_b_brain_dir)

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(json.dumps({
        "status": result["status"],
        "schema": result["schema"],
        "summary": result["summary"],
        "output": str(output_json)
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
