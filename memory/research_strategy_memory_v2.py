from __future__ import annotations

import json
import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{h}"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def text(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False).lower()


def load_story_index(plan_path: Path) -> Dict[str, Dict[str, Any]]:
    story_path = plan_path.with_name("evidence_stories_v4.json")
    if not story_path.exists():
        return {}

    doc = load_json(story_path)
    return {
        s.get("evidence_story_id"): s
        for s in doc.get("stories", [])
        if s.get("evidence_story_id")
    }


def infer_strategy_shape(plan: Dict[str, Any], story: Optional[Dict[str, Any]]) -> str:
    combined = text({
        "plan": plan,
        "story": story or {},
    })

    entity_counts = {}
    if story:
        entity_counts = story.get("entity_counts", {})

    has_bridge = entity_counts.get("BridgeEntity", 0) > 0 or "bridge" in combined
    has_webview = "webview" in combined or "web_content_to_native" in combined
    has_file = (
        "fileprovider" in combined
        or "content_uri" in combined
        or "filesystem_or_content_uri" in combined
        or "file_open" in combined
    )
    has_network = "network" in combined or "http" in combined or "socket" in combined
    has_auth = "credential" in combined or "token" in combined or "auth" in combined or "jwt" in combined
    has_storage = "storage" in combined or "database" in combined or "sqlite" in combined or "sharedpreferences" in combined
    has_entry = entity_counts.get("EntrypointEntity", 0) > 0
    has_sink = entity_counts.get("SinkEntity", 0) > 0

    if has_bridge and has_webview:
        return "bridge_to_webview_sink"

    if has_bridge and has_file:
        return "bridge_to_file_asset"

    if has_file and has_entry:
        return "entrypoint_to_content_uri_asset"

    if has_webview:
        return "webview_sink_reachability"

    if has_storage:
        return "persistent_storage_flow"

    if has_auth and has_network:
        return "credential_network_flow"

    if has_auth:
        return "credential_or_token_flow"

    if has_network:
        return "network_reachability_flow"

    if has_sink:
        return "generic_sink_reachability"

    return "generic_candidate_reachability"


def extract_strategy_from_plan(plan: Dict[str, Any], story: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    exp_type = plan.get("experiment_type", "unknown")
    missing = plan.get("missing_evidence", [])
    breakpoints = plan.get("breakpoints", [])
    uncertainty = plan.get("uncertainty_level", "unknown")
    shape = infer_strategy_shape(plan, story)

    story_counts = story.get("entity_counts", {}) if story else {}
    relation_counts = story.get("relation_counts", {}) if story else {}

    strategy_name = f"{shape}:{exp_type}:{uncertainty}"

    # ID canonico: non include missing_evidence o breakpoints.
    # Questi restano come varianti interne della strategia.
    strategy_id = stable_id("RSM2", strategy_name)

    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "strategy_shape": shape,
        "candidate_only": True,
        "finding_allowed": False,
        "applies_when": {
            "strategy_shape": shape,
            "experiment_type": exp_type,
            "uncertainty_level": uncertainty,
            "missing_evidence": missing,
            "breakpoints": breakpoints,
            "entity_shape": story_counts,
            "relation_shape": relation_counts,
        },
        "best_experiment_order": [
            step.get("action") for step in plan.get("steps", [])
        ],
        "high_value_experiments": [
            exp_type
        ],
        "low_value_experiments": [],
        "false_positive_patterns": [],
        "confirmed_disclosure_patterns": [],
        "counter_evidence_patterns": [
            "candidate path is not reachable",
            "security control blocks the path",
            "runtime behavior contradicts static story",
        ],
        "learning": {
            "times_seen": 1,
            "successful_validations": 0,
            "rejected_candidates": 0,
            "unknown_outcomes": 1,
        },
        "variants": [
            {
                "missing_evidence": missing,
                "breakpoints": breakpoints,
                "entity_shape": story_counts,
                "relation_shape": relation_counts,
                "times_seen": 1,
            }
        ],
        "compression_level": "strategy",
        "source": {
            "source_plan_id": plan.get("validation_plan_id"),
            "source_story_id": plan.get("source_evidence_story_id"),
        },
    }


def merge_strategy(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    e = existing.setdefault("learning", {})
    n = new.get("learning", {})

    e["times_seen"] = e.get("times_seen", 0) + n.get("times_seen", 0)
    e["successful_validations"] = e.get("successful_validations", 0) + n.get("successful_validations", 0)
    e["rejected_candidates"] = e.get("rejected_candidates", 0) + n.get("rejected_candidates", 0)
    e["unknown_outcomes"] = e.get("unknown_outcomes", 0) + n.get("unknown_outcomes", 0)

    for key in [
        "high_value_experiments",
        "low_value_experiments",
        "false_positive_patterns",
        "confirmed_disclosure_patterns",
        "counter_evidence_patterns",
        "best_experiment_order",
    ]:
        merged = list(dict.fromkeys(existing.get(key, []) + new.get(key, [])))
        existing[key] = merged

    # Merge varianti equivalenti mantenendo la diversità strutturale.
    existing_variants = existing.setdefault("variants", [])
    new_variants = new.get("variants", [])

    for nv in new_variants:
        matched = False
        for ev in existing_variants:
            if (
                ev.get("missing_evidence") == nv.get("missing_evidence")
                and ev.get("breakpoints") == nv.get("breakpoints")
                and ev.get("entity_shape") == nv.get("entity_shape")
                and ev.get("relation_shape") == nv.get("relation_shape")
            ):
                ev["times_seen"] = ev.get("times_seen", 0) + nv.get("times_seen", 1)
                matched = True
                break

        if not matched:
            existing_variants.append(nv)

    return existing


def build_strategy_memory(plan_paths: List[Path]) -> Dict[str, Any]:
    strategies: Dict[str, Dict[str, Any]] = {}
    total_plans = 0

    for plan_path in plan_paths:
        doc = load_json(plan_path)
        story_index = load_story_index(plan_path)

        for plan in doc.get("plans", []):
            total_plans += 1
            story = story_index.get(plan.get("source_evidence_story_id"))

            s = extract_strategy_from_plan(plan, story)
            sid = s["strategy_id"]

            if sid in strategies:
                strategies[sid] = merge_strategy(strategies[sid], s)
            else:
                strategies[sid] = s

    strategy_list = sorted(
        strategies.values(),
        key=lambda x: x.get("learning", {}).get("times_seen", 0),
        reverse=True,
    )

    by_shape: Dict[str, int] = {}
    for s in strategy_list:
        shape = s.get("strategy_shape", "unknown")
        by_shape[shape] = by_shape.get(shape, 0) + s.get("learning", {}).get("times_seen", 0)

    return {
        "schema": "research_strategy_memory_v2",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "compress repeated evidence stories and validation plans into reusable investigative strategies",
        "summary": {
            "source_plans": total_plans,
            "strategies": len(strategy_list),
            "compression_ratio": round(total_plans / max(len(strategy_list), 1), 2),
            "by_strategy_shape": by_shape,
        },
        "strategies": strategy_list,
    }


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python3 -m memory.research_strategy_memory_v2 <output_memory.json> <dynamic_validation_plans_v4.json> [...]")
        sys.exit(1)

    out = Path(sys.argv[1])
    inputs = [Path(x) for x in sys.argv[2:]]

    memory = build_strategy_memory(inputs)
    save_json(out, memory)

    print(json.dumps(memory["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
