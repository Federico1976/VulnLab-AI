import json
import sys
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def uniq(items):
    out, seen = [], set()
    for x in items:
        k = json.dumps(x, sort_keys=True) if isinstance(x, dict) else str(x)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def strategy_from_pattern(pm):
    causal = pm.get("causal_memory", {})
    counter = pm.get("counterevidence_memory", {})
    strategy = pm.get("strategy_memory", {})

    pattern_id = pm.get("pattern_id")
    family = pm.get("families", ["unknown"])[0]

    return {
        "schema": "vulnlab.research_strategy.v1",
        "strategy_id": "RS-" + pattern_id.replace("PM-", ""),
        "derived_from_pattern": pattern_id,
        "family": family,
        "case_count": pm.get("case_count", 0),
        "investigation_goal": "Validate whether an observed APK pattern represents a real security-relevant trust-boundary failure.",
        "reasoning_sequence": [
            "Identify externally or attacker-controllable entrypoint",
            "Map attacker-controlled input shape",
            "Confirm trust boundary crossed",
            "Identify sensitive operation or security effect",
            "Search for validators, permissions, allowlists, canonicalization, or origin checks",
            "Collect counterevidence before increasing confidence",
            "Design safe dynamic validation",
            "Do not claim vulnerability without runtime evidence"
        ],
        "focus_points": {
            "trust_boundaries": causal.get("trust_boundaries", []),
            "entrypoints": causal.get("entrypoints", []),
            "sensitive_operations": causal.get("sensitive_operations", []),
            "security_effects": causal.get("security_effects", []),
            "exploit_primitives": causal.get("exploit_primitives", [])
        },
        "counterevidence_first": {
            "common_false_positives": counter.get("common_false_positives", []),
            "counter_signals": counter.get("counter_signals", [])
        },
        "dynamic_validation_methods": strategy.get("dynamic_validation_methods", []),
        "heuristics": uniq(strategy.get("investigation_heuristics", []) + strategy.get("strategy_hints", [])),
        "claim_guardrail": {
            "finding_allowed": False,
            "max_claim_without_dynamic_validation": "candidate_evidence_or_causal_static_evidence",
            "requires_dynamic_validation": True,
            "requires_counterevidence_review": True
        }
    }


def build(pattern_memory_path):
    pm_doc = load_json(pattern_memory_path)
    strategies = [strategy_from_pattern(pm) for pm in pm_doc.get("patterns", [])]

    return {
        "status": "ok",
        "schema": "vulnlab.research_strategy_memory_store.v1",
        "summary": {
            "strategies": len(strategies),
            "patterns_consumed": len(pm_doc.get("patterns", [])),
            "finding_allowed": False,
            "requires_dynamic_validation": True
        },
        "strategies": strategies
    }


def main():
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python3 -m phase_c.research_strategy_memory.strategy_memory_builder "
            "<pattern_memory_json> <output_json>"
        )

    result = build(Path(sys.argv[1]))
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(result, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    print(json.dumps({
        "status": result["status"],
        "schema": result["schema"],
        "summary": result["summary"],
        "output": str(out)
    }, indent=2))


if __name__ == "__main__":
    main()
