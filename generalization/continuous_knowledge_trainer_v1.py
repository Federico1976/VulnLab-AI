#!/usr/bin/env python3
"""
Continuous Knowledge Trainer v1.

Purpose:
- Distill reusable investigative knowledge from APK evidence stories.
- Learn abstract strategies, not vulnerabilities.
- Never emit findings.
- Never create target-specific detectors.

Input:
- evidence_story_v1.json
- research_closure_report_v1.json
- research_episode_memory_v1.json

Output:
- knowledge_pattern_memory_v1.json
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


MEMORY_VERSION = "knowledge_pattern_memory_v1"


EVIDENCE_STORY_NAMES = [
    "semantic_story_v1.json",
    "evidence_story_v1.json",
    "phase_b/evidence_story_v1.json",
    "generalization/evidence_story_v1.json",
    "intelligence/evidence_story_v1.json",
]

CLOSURE_REPORT_NAMES = [
    "research_closure_report_v1.json",
    "phase_b/research_closure_report_v1.json",
    "generalization/research_closure_report_v1.json",
    "intelligence/research_closure_report_v1.json",
]

EPISODE_MEMORY_NAMES = [
    "research_episode_memory_v1.json",
    "phase_b/research_episode_memory_v1.json",
    "generalization/research_episode_memory_v1.json",
    "intelligence/research_episode_memory_v1.json",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def normalize(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    text = str(value).strip()
    return text if text else "unknown"


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def stable_id(*parts: Any) -> str:
    raw = "|".join(normalize(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def episode_id_for(apk_name: str, evidence_story_path: Path) -> str:
    return "episode_" + stable_id(apk_name, str(evidence_story_path))


def upsert_episode(memory: Dict[str, Any], episode_record: Dict[str, Any]) -> None:
    episodes = memory.setdefault("episodes", [])
    eid = episode_record["episode_id"]

    for idx, existing in enumerate(episodes):
        if existing.get("episode_id") == eid:
            original_first_seen = existing.get("first_seen_at") or existing.get("trained_at")
            merged = dict(existing)
            merged.update(episode_record)
            merged["first_seen_at"] = original_first_seen or episode_record["trained_at"]
            merged["last_seen_at"] = episode_record["trained_at"]
            merged["training_runs"] = int(existing.get("training_runs", 1)) + 1
            episodes[idx] = merged
            return

    episode_record["first_seen_at"] = episode_record["trained_at"]
    episode_record["last_seen_at"] = episode_record["trained_at"]
    episode_record["training_runs"] = 1
    episodes.append(episode_record)


def confidence_bucket(value: Any) -> str:
    try:
        v = float(value)
    except Exception:
        return "unknown"

    if v >= 0.80:
        return "high"
    if v >= 0.55:
        return "medium"
    if v > 0:
        return "low"
    return "unknown"


def numeric_or_none(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def find_first_json(base_dir: Path, candidates: List[str]) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
    for rel in candidates:
        p = base_dir / rel
        data = load_json(p)
        if data is not None:
            return p, data

    hits = sorted(base_dir.rglob("*.json"))
    lowered = {name.lower() for name in candidates}

    for p in hits:
        if p.name.lower() in lowered:
            data = load_json(p)
            if data is not None:
                return p, data

    return None, None


def resolve_episode_inputs(apk_output_dir: Path) -> Dict[str, Any]:
    story_path, story = find_first_json(apk_output_dir, EVIDENCE_STORY_NAMES)
    closure_path, closure = find_first_json(apk_output_dir, CLOSURE_REPORT_NAMES)
    episode_path, episode = find_first_json(apk_output_dir, EPISODE_MEMORY_NAMES)

    if story is None or story_path is None:
        raise FileNotFoundError(
            "No evidence_story_v1.json found under "
            f"{apk_output_dir}. Run find output command to locate generated story."
        )

    return {
        "story_path": story_path,
        "story": story,
        "closure_path": closure_path,
        "closure": closure,
        "episode_path": episode_path,
        "episode": episode,
    }


def init_memory() -> Dict[str, Any]:
    return {
        "version": MEMORY_VERSION,
        "generated_at": now_iso(),
        "purpose": "abstract_investigation_strategy_memory",
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
            "target_specific_detectors_allowed": False,
            "learns_findings": False,
            "learns_cves": False,
        },
        "patterns": {},
        "episodes": [],
        "stats": {
            "episode_count": 0,
            "pattern_count": 0,
        },
    }



def collect_runtime_hints(apk_output_dir: Path, story: Dict[str, Any], episode: Optional[Dict[str, Any]]) -> str:
    hints = []

    for obj in [story, episode or {}]:
        for key in [
            "framework",
            "runtime",
            "runtime_family",
            "framework_family",
            "technology",
            "stack",
            "platform_hints",
            "semantic_objects",
            "research_objects",
            "entrypoint",
            "static_trace",
            "source_to_sink",
        ]:
            if key in obj:
                hints.append(normalize(obj.get(key)))

    for name in [
        "runtime_understanding.json",
        "semantic_objects.json",
        "research_objects.json",
        "phase_b/runtime_understanding.json",
        "phase_b/semantic_objects.json",
        "phase_b/research_objects.json",
    ]:
        data = load_json(apk_output_dir / name)
        if data:
            hints.append(normalize(data))

    hints.append(apk_output_dir.name)
    return " ".join(hints).lower()


def infer_framework(apk_output_dir: Path, story: Dict[str, Any], episode: Optional[Dict[str, Any]]) -> str:
    explicit = (
        story.get("framework")
        or story.get("runtime")
        or story.get("runtime_family")
        or story.get("framework_family")
        or (episode or {}).get("framework")
        or (episode or {}).get("runtime")
    )

    if explicit and normalize(explicit) != "unknown":
        return normalize(explicit)

    hints = collect_runtime_hints(apk_output_dir, story, episode)

    framework_rules = [
        ("react_native", ["reactnative", "react native", "rnfs", "com.facebook.react", "hermes", "catalystinstance"]),
        ("flutter", ["flutter", "dart", "io.flutter", "libflutter.so", "flutteractivity"]),
        ("hybrid_webview", ["webview", "loadurl", "javascriptinterface", "shouldoverrideurlloading"]),
        ("cordova", ["cordova", "phonegap", "org.apache.cordova"]),
        ("xamarin", ["xamarin", "mono.android", "assemblies.blob"]),
        ("unity", ["unity", "libunity.so", "unityplayeractivity"]),
        ("native_android", ["android.app.activity", "androidx.", "kotlin.", "java.", "intent-filter"]),
    ]

    matched = []
    for framework, needles in framework_rules:
        score = sum(1 for n in needles if n in hints)
        if score:
            matched.append((score, framework))

    if not matched:
        return "unknown"

    matched.sort(reverse=True)
    return matched[0][1]


def extract_features(
    apk_output_dir: Path,
    story: Dict[str, Any],
    closure: Optional[Dict[str, Any]],
    episode: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    source_to_sink = (
        story.get("source_to_sink_state")
        or story.get("source_to_sink")
        or story.get("flow_state")
        or {}
    )

    causal_graph = story.get("causal_graph") or story.get("evidence_causal_graph") or {}

    blockers = []
    blockers.extend(as_list(story.get("blockers")))
    blockers.extend(as_list(story.get("missing_blockers")))
    if closure:
        blockers.extend(as_list(closure.get("blockers")))

    counter_evidence = []
    counter_evidence.extend(as_list(story.get("counter_evidence")))
    if closure:
        counter_evidence.extend(as_list(closure.get("counter_evidence")))

    missing_proof = (
        story.get("missing_proof")
        or story.get("proof_gap")
        or story.get("missing_evidence")
        or (closure or {}).get("missing_proof")
        or "unknown"
    )

    next_best_experiment = (
        story.get("next_best_experiment")
        or story.get("recommended_next_experiment")
        or (closure or {}).get("next_best_experiment")
        or (episode or {}).get("next_best_experiment")
        or "unknown"
    )

    learning_value = (
        story.get("learning_value")
        or (episode or {}).get("learning_value")
        or (closure or {}).get("learning_value")
    )

    semantic_contract = story.get("semantic_contract") or {}
    learning_fields = story.get("learning_fields") or {}

    return {
        "apk_name": normalize(
            story.get("apk_name")
            or story.get("target")
            or story.get("package")
            or (episode or {}).get("apk_name")
            or apk_output_dir.name
        ),
        "framework": normalize(
            semantic_contract.get("framework_family")
            or infer_framework(apk_output_dir, story, episode)
        ),
        "abstract_shape": normalize(
            semantic_contract.get("semantic_shape")
            or story.get("primary_shape")
            or story.get("shape")
            or story.get("category")
            or story.get("hypothesis_shape")
            or "unknown"
        ),
        "entrypoint": normalize(story.get("entrypoint")),
        "source_to_sink_state": normalize(learning_fields.get("source_to_sink_state") or source_to_sink),
        "static_trace_state": normalize(story.get("static_trace_state") or story.get("static_trace")),
        "runtime_plan_state": normalize(story.get("runtime_plan_state") or story.get("runtime_plan")),
        "runtime_probe_state": normalize(learning_fields.get("runtime_probe_state") or story.get("runtime_probe_state")),
        "causal_state": normalize(causal_graph.get("state") if isinstance(causal_graph, dict) else causal_graph),
        "missing_proof": normalize(learning_fields.get("missing_proof") or missing_proof),
        "next_best_experiment": normalize(learning_fields.get("next_best_experiment") or next_best_experiment),
        "learning_value": learning_fields.get("learning_value") or semantic_contract.get("expected_information_gain") or learning_value,
        "expected_information_gain": learning_fields.get("expected_information_gain") or semantic_contract.get("expected_information_gain"),
        "proof_mode": normalize(learning_fields.get("proof_mode") or semantic_contract.get("proof_mode")),
        "strategy_family": normalize(learning_fields.get("strategy_family") or semantic_contract.get("strategy_family")),
        "validation_family": normalize(learning_fields.get("validation_family") or semantic_contract.get("validation_family")),
        "contract_quality": normalize(learning_fields.get("contract_quality") or semantic_contract.get("contract_quality")),
        "blockers": [normalize(x) for x in (as_list(learning_fields.get("blockers")) or blockers)],
        "counter_evidence": [normalize(x) for x in (as_list(learning_fields.get("counter_evidence")) or counter_evidence)],
    }


def distill_patterns(features: Dict[str, Any]) -> List[Dict[str, Any]]:
    apk = features["apk_name"]
    framework = features["framework"]
    shape = features["abstract_shape"]

    patterns: List[Dict[str, Any]] = []

    patterns.append({
        "pattern_id": "kp_source_sink_strength_" + stable_id(shape, features["source_to_sink_state"], features["runtime_probe_state"]),
        "pattern_type": "source_sink_evidence_strength",
        "abstract_shape": shape,
        "framework": framework,
        "source_to_sink_state": features["source_to_sink_state"],
        "runtime_probe_state": features["runtime_probe_state"],
        "evidence_strength_hint": confidence_bucket(features["learning_value"]),
        "observed_in_apks": [apk],
        "learning_value_samples": [features["learning_value"]],
        "learned_strategy": "Escalate only when source-to-sink state, entrypoint plausibility, static trace and runtime probe are mutually consistent.",
    })

    patterns.append({
        "pattern_id": "kp_missing_proof_frequency_" + stable_id(shape, framework, features["missing_proof"]),
        "pattern_type": "missing_proof_frequency",
        "abstract_shape": shape,
        "framework": framework,
        "missing_proof": features["missing_proof"],
        "observed_in_apks": [apk],
        "learning_value_samples": [features["learning_value"]],
        "validation_strategy": "Prioritize proof-gap-closing experiments before confidence escalation.",
    })

    patterns.append({
        "pattern_id": "kp_next_experiment_eig_" + stable_id(shape, framework, features["next_best_experiment"], features["missing_proof"]),
        "pattern_type": "next_best_experiment_expected_information_gain",
        "abstract_shape": shape,
        "framework": framework,
        "next_best_experiment": features["next_best_experiment"],
        "missing_proof": features["missing_proof"],
        "expected_information_gain_hint": confidence_bucket(features["learning_value"]),
        "observed_in_apks": [apk],
        "learning_value_samples": [features["learning_value"]],
        "ranking_rule": "Rank higher when the experiment can transform candidate-only evidence into concrete proof or decisive counter-evidence.",
    })

    patterns.append({
        "pattern_id": "kp_framework_strategy_" + stable_id(framework, shape),
        "pattern_type": "framework_investigation_strategy",
        "framework": framework,
        "abstract_shape": shape,
        "observed_in_apks": [apk],
        "learning_value_samples": [features["learning_value"]],
        "strategy_rule": "Use framework/runtime only to select investigation strategy, never to create target-specific detectors.",
    })

    patterns.append({
        "pattern_id": "kp_causal_evolution_" + stable_id(shape, features["causal_state"], features["runtime_probe_state"]),
        "pattern_type": "causal_state_evolution",
        "abstract_shape": shape,
        "framework": framework,
        "causal_state": features["causal_state"],
        "runtime_probe_state": features["runtime_probe_state"],
        "observed_in_apks": [apk],
        "learning_value_samples": [features["learning_value"]],
        "proof_mode_hint": "Prefer experiments that convert causal plausibility into reproducible runtime evidence.",
    })

    patterns.append({
        "pattern_id": "kp_proof_mode_" + stable_id(shape, framework, features["proof_mode"]),
        "pattern_type": "proof_mode_tendency",
        "abstract_shape": shape,
        "framework": framework,
        "proof_mode": features["proof_mode"],
        "validation_family": features["validation_family"],
        "learning_value_samples": [features["expected_information_gain"] or features["learning_value"]],
        "observed_in_apks": [apk],
        "proof_rule": "Use proof mode to decide whether the next experiment should seek static trace, runtime evidence or causal disambiguation.",
    })

    patterns.append({
        "pattern_id": "kp_strategy_validation_pair_" + stable_id(shape, framework, features["strategy_family"], features["validation_family"]),
        "pattern_type": "strategy_validation_pair",
        "abstract_shape": shape,
        "framework": framework,
        "strategy_family": features["strategy_family"],
        "validation_family": features["validation_family"],
        "contract_quality": features["contract_quality"],
        "learning_value_samples": [features["expected_information_gain"] or features["learning_value"]],
        "observed_in_apks": [apk],
        "strategy_rule": "Prefer strategy/validation pairs that repeatedly reduce proof gaps without escalating candidate-only evidence into findings.",
    })

    for blocker in sorted(set(features["blockers"])):
        patterns.append({
            "pattern_id": "kp_blocker_" + stable_id(shape, framework, blocker),
            "pattern_type": "counter_evidence_or_blocker",
            "abstract_shape": shape,
            "framework": framework,
            "counter_evidence": blocker,
            "observed_in_apks": [apk],
            "learning_value_samples": [features["learning_value"]],
            "research_effect": "Treat as confidence limiter until resolved by static proof, runtime validation or reproducible trace.",
        })

    for ce in sorted(set(features["counter_evidence"])):
        patterns.append({
            "pattern_id": "kp_hypothesis_invalidation_" + stable_id(shape, framework, ce),
            "pattern_type": "hypothesis_invalidation_signal",
            "abstract_shape": shape,
            "framework": framework,
            "counter_evidence": ce,
            "observed_in_apks": [apk],
            "learning_value_samples": [features["learning_value"]],
            "research_effect": "Use as hypothesis invalidation signal before proof escalation or disclosure reporting.",
        })

    return patterns


def update_pattern_support_metrics(pattern: Dict[str, Any]) -> None:
    observed_apks = sorted(set(pattern.get("observed_in_apks", [])))
    frameworks = sorted(set(
        normalize(pattern.get("framework"))
        for _ in [1]
        if normalize(pattern.get("framework")) != "unknown"
    ))

    samples = [
        numeric_or_none(x)
        for x in pattern.get("learning_value_samples", [])
        if numeric_or_none(x) is not None
    ]

    avg_eig = round(sum(samples) / len(samples), 4) if samples else None

    support_count = int(pattern.get("support_count", 0))
    apk_diversity = len(observed_apks)
    framework_diversity = len(frameworks)

    reliability = 0.0
    reliability += min(support_count, 10) * 0.05
    reliability += min(apk_diversity, 5) * 0.08
    reliability += min(framework_diversity, 3) * 0.06
    if avg_eig is not None:
        reliability += min(max(avg_eig, 0.0), 1.0) * 0.30
    reliability = round(min(reliability, 1.0), 4)

    pattern["support_metrics"] = {
        "apk_diversity": apk_diversity,
        "framework_diversity": framework_diversity,
        "avg_expected_information_gain": avg_eig,
        "pattern_reliability_score": reliability,
    }


def merge_pattern(memory: Dict[str, Any], pattern: Dict[str, Any]) -> None:
    patterns = memory.setdefault("patterns", {})
    pid = pattern["pattern_id"]

    if pid not in patterns:
        pattern["support_count"] = 1
        pattern["first_seen_at"] = now_iso()
        pattern["last_seen_at"] = now_iso()
        update_pattern_support_metrics(pattern)
        patterns[pid] = pattern
        return

    existing = patterns[pid]
    existing["support_count"] = int(existing.get("support_count", 0)) + 1
    existing["last_seen_at"] = now_iso()

    observed = set(existing.get("observed_in_apks", []))
    observed.update(pattern.get("observed_in_apks", []))
    existing["observed_in_apks"] = sorted(observed)

    samples = existing.setdefault("learning_value_samples", [])
    samples.extend(pattern.get("learning_value_samples", []))

    update_pattern_support_metrics(existing)


def compute_global_support_metrics(memory: Dict[str, Any]) -> Dict[str, Any]:
    patterns = memory.get("patterns", {})
    episodes = memory.get("episodes", [])

    apk_names = sorted(set(e.get("apk_name") for e in episodes if e.get("apk_name")))
    frameworks = sorted(set(
        e.get("framework")
        for e in episodes
        if e.get("framework") and e.get("framework") != "unknown"
    ))

    missing_counts: Dict[str, int] = {}
    counter_counts: Dict[str, int] = {}

    for pattern in patterns.values():
        mp = pattern.get("missing_proof")
        if mp and mp != "unknown":
            missing_counts[mp] = missing_counts.get(mp, 0) + int(pattern.get("support_count", 1))

        ce = pattern.get("counter_evidence")
        if ce and ce != "unknown":
            counter_counts[ce] = counter_counts.get(ce, 0) + int(pattern.get("support_count", 1))

    def top_item(counts: Dict[str, int]) -> Optional[Dict[str, Any]]:
        if not counts:
            return None
        key, count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        return {"value": key, "count": count}

    reliability_scores = [
        p.get("support_metrics", {}).get("pattern_reliability_score")
        for p in patterns.values()
        if isinstance(p.get("support_metrics", {}).get("pattern_reliability_score"), (int, float))
    ]

    return {
        "apk_diversity": len(apk_names),
        "framework_diversity": len(frameworks),
        "most_common_missing_proof": top_item(missing_counts),
        "most_common_counter_evidence": top_item(counter_counts),
        "avg_pattern_reliability_score": round(sum(reliability_scores) / len(reliability_scores), 4)
        if reliability_scores else None,
    }


def train_from_apk_output(apk_output_dir: Path, memory_path: Path) -> Dict[str, Any]:
    resolved = resolve_episode_inputs(apk_output_dir)

    story = resolved["story"]
    closure = resolved["closure"]
    episode = resolved["episode"]

    memory = load_json(memory_path) if memory_path.exists() else None
    if not memory:
        memory = init_memory()

    features = extract_features(apk_output_dir, story, closure, episode)
    patterns = distill_patterns(features)

    for pattern in patterns:
        merge_pattern(memory, pattern)

    trained_at = now_iso()
    episode_record = {
        "episode_id": episode_id_for(features["apk_name"], resolved["story_path"]),
        "apk_name": features["apk_name"],
        "output_dir": str(apk_output_dir),
        "trained_at": trained_at,
        "evidence_story": str(resolved["story_path"]),
        "closure_report": str(resolved["closure_path"]) if resolved["closure_path"] else None,
        "episode_memory": str(resolved["episode_path"]) if resolved["episode_path"] else None,
        "distilled_pattern_count": len(patterns),
        "abstract_shape": features["abstract_shape"],
        "framework": features["framework"],
        "missing_proof": features["missing_proof"],
        "next_best_experiment": features["next_best_experiment"],
        "proof_mode": features["proof_mode"],
        "strategy_family": features["strategy_family"],
        "validation_family": features["validation_family"],
        "contract_quality": features["contract_quality"],
        "expected_information_gain": features["expected_information_gain"],
        "candidate_only": True,
        "finding_allowed": False,
        "report_allowed": False,
    }
    upsert_episode(memory, episode_record)

    memory["generated_at"] = now_iso()
    memory["stats"] = {
        "episode_count": len(memory.get("episodes", [])),
        "pattern_count": len(memory.get("patterns", {})),
    }
    memory["support_metrics"] = compute_global_support_metrics(memory)

    write_json(memory_path, memory)
    return memory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk_output_dir")
    parser.add_argument("--memory", default="output/knowledge_pattern_memory_v1.json")
    args = parser.parse_args()

    memory = train_from_apk_output(
        apk_output_dir=Path(args.apk_output_dir),
        memory_path=Path(args.memory),
    )

    print(json.dumps({
        "ok": True,
        "memory": args.memory,
        "episode_count": memory["stats"]["episode_count"],
        "pattern_count": memory["stats"]["pattern_count"],
        "guardrails": memory["guardrails"],
    }, indent=2))


if __name__ == "__main__":
    main()
