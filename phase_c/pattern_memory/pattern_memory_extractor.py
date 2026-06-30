import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_id(value: str) -> str:
    value = (value or "unknown").lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value.upper() or "UNKNOWN"


def as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def collect_unique(items: List[Any]) -> List[Any]:
    seen = set()
    out = []
    for item in items:
        if isinstance(item, dict):
            key = json.dumps(item, sort_keys=True, ensure_ascii=False)
        else:
            key = str(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def case_signature(case: Dict[str, Any]) -> str:
    identity = case.get("identity", {})
    causal = case.get("causal_shape", {})

    family = identity.get("vulnerability_family", "unknown")
    trust_boundary = causal.get("trust_boundary", {}).get("boundary_type", "unknown")
    sensitive_operation = causal.get("sensitive_operation", {}).get("type", "unknown")
    security_effect = causal.get("security_effect", {}).get("type", "unknown")
    exploit_primitive = causal.get("exploit_primitive", {}).get("type", "unknown")

    parts = [
        normalize_id(family),
        normalize_id(trust_boundary),
        normalize_id(sensitive_operation),
        normalize_id(security_effect),
        normalize_id(exploit_primitive)
    ]

    return "__".join(parts)


def extract_pattern_from_cases(signature: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    families = []
    titles = []
    root_causes = []
    faulty_assumptions = []
    trust_boundaries = []
    entrypoints = []
    sensitive_operations = []
    security_effects = []
    exploit_primitives = []
    common_counterevidence = []
    counter_signals = []
    strategy_hints = []
    investigation_heuristics = []
    dynamic_validation_methods = []
    disallowed_claims = []

    for case in cases:
        identity = case.get("identity", {})
        affected = case.get("affected_context", {})
        causal = case.get("causal_shape", {})
        evidence = case.get("evidence_model", {})
        counter = case.get("counterevidence_model", {})
        learning = case.get("learning_model", {})

        families.append(identity.get("vulnerability_family"))
        titles.append(identity.get("title"))

        root_causes.append(learning.get("root_cause"))
        faulty_assumptions.append(learning.get("faulty_assumption"))

        trust_boundaries.append(causal.get("trust_boundary", {}).get("boundary_type"))
        sensitive_operations.append(causal.get("sensitive_operation", {}).get("type"))
        security_effects.append(causal.get("security_effect", {}).get("type"))
        exploit_primitives.append(causal.get("exploit_primitive", {}).get("type"))

        entrypoints.extend(as_list(affected.get("entrypoint_type")))

        common_counterevidence.extend(as_list(counter.get("common_false_positives")))
        counter_signals.extend(as_list(counter.get("counter_signals")))
        strategy_hints.extend(as_list(learning.get("strategy_hints")))
        investigation_heuristics.extend(as_list(learning.get("investigation_heuristics")))

        for item in evidence.get("dynamic_evidence_required", []):
            method = item.get("validation_method")
            if method:
                dynamic_validation_methods.append(method)

        disallowed_claims.extend(as_list(evidence.get("disallowed_claims")))

    main_family = collect_unique(families)[0] if collect_unique(families) else "unknown"
    pattern_id = "PM-" + normalize_id(str(main_family))

    return {
        "schema": "vulnlab.pattern_memory.v1",
        "pattern_id": pattern_id,
        "signature": signature,
        "case_count": len(cases),
        "case_titles": collect_unique([x for x in titles if x]),
        "families": collect_unique([x for x in families if x]),
        "causal_memory": {
            "root_cause_patterns": collect_unique([x for x in root_causes if x]),
            "faulty_assumptions": collect_unique([x for x in faulty_assumptions if x]),
            "trust_boundaries": collect_unique([x for x in trust_boundaries if x]),
            "entrypoints": collect_unique([x for x in entrypoints if x]),
            "sensitive_operations": collect_unique([x for x in sensitive_operations if x]),
            "security_effects": collect_unique([x for x in security_effects if x]),
            "exploit_primitives": collect_unique([x for x in exploit_primitives if x])
        },
        "counterevidence_memory": {
            "common_false_positives": collect_unique([x for x in common_counterevidence if x]),
            "counter_signals": collect_unique([x for x in counter_signals if x])
        },
        "strategy_memory": {
            "investigation_heuristics": collect_unique([x for x in investigation_heuristics if x]),
            "strategy_hints": collect_unique([x for x in strategy_hints if x]),
            "dynamic_validation_methods": collect_unique([x for x in dynamic_validation_methods if x])
        },
        "guardrail": {
            "candidate_only": True,
            "finding_allowed": False,
            "requires_dynamic_validation": True,
            "do_not_infer_vulnerability_from_pattern_match": True
        },
        "disallowed_claims": collect_unique(disallowed_claims)
    }


def extract_pattern_memory(seed_cases_dir: Path) -> Dict[str, Any]:
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for path in sorted(seed_cases_dir.glob("*.json")):
        case = load_json(path)
        sig = case_signature(case)
        groups.setdefault(sig, []).append(case)

    patterns = [
        extract_pattern_from_cases(signature, cases)
        for signature, cases in sorted(groups.items())
    ]

    return {
        "status": "ok",
        "schema": "vulnlab.pattern_memory_store.v1",
        "summary": {
            "cases_consumed": sum(len(v) for v in groups.values()),
            "patterns": len(patterns),
            "deduplicated_groups": sum(1 for v in groups.values() if len(v) > 1),
            "finding_allowed": False,
            "requires_dynamic_validation": True
        },
        "patterns": patterns
    }


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python3 -m phase_c.pattern_memory.pattern_memory_extractor "
            "<knowledge_memory_cases_dir> <output_json>"
        )

    seed_cases_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])
    output_json.parent.mkdir(parents=True, exist_ok=True)

    result = extract_pattern_memory(seed_cases_dir)

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
