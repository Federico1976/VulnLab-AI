#!/usr/bin/env python3
"""
Semantic Story Normalizer v1.

Input: APK output directory with evidence_story_v1.json and existing artifacts.
Output: semantic_story_v1.json

Purpose:
- Normalize Evidence Story into a stable cognitive contract.
- No findings.
- No CVE logic.
- No target-specific detector.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def norm(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    value = str(value).strip()
    return value if value else "unknown"


def text_blob(*items: Any) -> str:
    return " ".join(norm(x).lower() for x in items if x is not None)


def score_runtime(blob: str, needles: List[str]) -> int:
    return sum(blob.count(n) for n in needles)


def classify_runtime(blob: str) -> List[str]:
    """
    Classifica runtime in modo conservativo.

    Non deve trasformare keyword di librerie terze in framework primario.
    WebView/deeplink sono surface/strategy, non necessariamente framework app.
    """

    rules = {
        "react_native": [
            "com.facebook.react",
            "reactnativehost",
            "reactapplication",
            "catalystinstance",
            "hermesexecutor",
            "rnfs",
        ],
        "flutter": [
            "io.flutter.embedding",
            "flutteractivity",
            "flutterengine",
            "libflutter.so",
            "dart_executor",
        ],
        "cordova": [
            "org.apache.cordova.cordovaactivity",
            "cordovawebview",
            "cordova_plugin",
            "config.xml",
        ],
        "xamarin": [
            "mono.android",
            "xamarin.android",
            "assemblies.blob",
            "libmonodroid",
        ],
        "unity": [
            "com.unity3d.player.unityplayeractivity",
            "libunity.so",
            "unityplayer",
        ],
        "native_android": [
            "intent-filter",
            "androidx.",
            "kotlin.",
            "android.app.activity",
            "android.app.service",
            "android.content.broadcastreceiver",
        ],
    }

    scores = {
        runtime: score_runtime(blob, needles)
        for runtime, needles in rules.items()
    }

    selected = []

    for runtime in ["react_native", "flutter", "cordova", "xamarin", "unity"]:
        if scores.get(runtime, 0) >= 2:
            selected.append(runtime)

    if scores.get("native_android", 0) > 0 or not selected:
        selected.append("native_android")

    if any(x in blob for x in ["webview", "loadurl", "javascriptinterface", "shouldoverrideurlloading"]):
        selected.append("hybrid_webview")

    return sorted(set(selected)) or ["unknown"]


def primary_framework_family(runtimes: List[str]) -> str:
    priority = [
        "react_native",
        "flutter",
        "cordova",
        "xamarin",
        "unity",
        "native_android",
        "hybrid_webview",
    ]

    for item in priority:
        if item in runtimes:
            return item

    return "unknown"


def classify_semantic_shape(blob: str) -> str:
    has_deeplink = any(x in blob for x in ["deeplink", "intent-filter", "uri", "oauth", "redirect"])
    has_webview = any(x in blob for x in ["webview", "loadurl", "javascriptinterface"])
    has_fileprovider = any(x in blob for x in ["fileprovider", "content://", "provider"])
    has_compose = any(x in blob for x in ["compose", "androidx.compose"])

    if has_deeplink and has_webview:
        return "deeplink_to_webview_surface"
    if has_deeplink:
        return "deeplink_entrypoint_surface"
    if has_fileprovider:
        return "fileprovider_content_surface"
    if has_webview:
        return "webview_runtime_surface"
    if has_compose:
        return "kotlin_compose_navigation_surface"
    return "unknown"


def classify_strategy_family(blob: str) -> str:
    if any(x in blob for x in ["source_to_sink", "source-to-sink", "static_trace", "runtime_probe"]):
        return "source_to_sink_validation"
    if any(x in blob for x in ["deeplink", "intent-filter", "entrypoint"]):
        return "entrypoint_reachability"
    if any(x in blob for x in ["proof", "causal", "evidence_graph"]):
        return "causal_proof_building"
    return "unknown"


def classify_validation_family(blob: str) -> str:
    if any(x in blob for x in ["runtime_probe", "probe_results", "marker propagation"]):
        return "runtime_probe_validation"
    if any(x in blob for x in ["joern", "static_trace", "call chain"]):
        return "static_trace_validation"
    if any(x in blob for x in ["causal_graph", "proof_graph"]):
        return "causal_graph_validation"
    return "unknown"



def detect_artifact_signal(artifacts: Dict[str, Any], key: str) -> bool:
    value = artifacts.get(key)
    if value is None:
        return False
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return len(value) > 0
    return True


def infer_proof_mode(artifacts: Dict[str, Any], blob: str) -> str:
    has_static = (
        detect_artifact_signal(artifacts, "source_to_sink_paths")
        or "static_trace" in blob
        or "joern" in blob
        or "call chain" in blob
    )
    has_runtime = (
        detect_artifact_signal(artifacts, "runtime_probe_results")
        or "runtime_probe" in blob
        or "probe_results" in blob
        or "marker propagation" in blob
    )
    has_causal = (
        detect_artifact_signal(artifacts, "universal_causal_graph")
        or detect_artifact_signal(artifacts, "causal_reachability")
        or "causal" in blob
    )

    if has_static and has_runtime:
        return "static_and_runtime_artifacts_present_proof_gap_open"
    if has_runtime:
        return "runtime_artifacts_present_proof_gap_open"
    if has_static:
        return "static_trace_artifacts_present_proof_gap_open"
    if has_causal:
        return "causal_hypothesis_only"
    return "candidate_only_until_runtime_or_static_proof"


def infer_expected_information_gain(semantic_shape: str, validation_family: str, proof_mode: str) -> float:
    score = 0.30

    if semantic_shape != "unknown":
        score += 0.15
    if validation_family in {"runtime_probe_validation", "static_trace_validation"}:
        score += 0.20
    if proof_mode == "static_and_runtime_artifacts_present_proof_gap_open":
        score += 0.18
    elif proof_mode in {"runtime_artifacts_present_proof_gap_open", "static_trace_artifacts_present_proof_gap_open"}:
        score += 0.12
    elif proof_mode == "causal_hypothesis_only":
        score += 0.05

    return round(min(score, 1.0), 4)


def infer_contract_quality(semantic_shape: str, runtimes: List[str], validation_family: str, proof_mode: str) -> str:
    score = 0

    if semantic_shape != "unknown":
        score += 1
    if runtimes and runtimes != ["unknown"]:
        score += 1
    if validation_family != "unknown":
        score += 1
    if proof_mode != "candidate_only_until_runtime_or_static_proof":
        score += 1

    if score >= 4:
        return "strong_semantic_contract"
    if score == 3:
        return "usable_semantic_contract"
    if score == 2:
        return "weak_semantic_contract"
    return "raw_or_unknown_contract"


def build_semantic_story(apk_output_dir: Path) -> Dict[str, Any]:
    evidence_story = load_json(apk_output_dir / "evidence_story_v1.json") or {}

    artifacts = {
        "apk_characterization": load_json(apk_output_dir / "apk_characterization.json"),
        "semantic_entity_graph": load_json(apk_output_dir / "phase_b/semantic_entity_graph_v4.json"),
        "merged_research_objects": load_json(apk_output_dir / "phase_b/merged_research_objects.json"),
        "capability_graphs": load_json(apk_output_dir / "phase_b_brain/capability_graphs.json"),
        "semantic_capabilities": load_json(apk_output_dir / "phase_b_brain/semantic_capabilities.json"),
        "causal_reachability": load_json(apk_output_dir / "phase_b_brain/causal_reachability_v2.json"),
        "proof_evaluations": load_json(apk_output_dir / "phase_b_brain/proof_evaluations.json"),
        "research_strategy_memory": load_json(apk_output_dir / "phase_b_brain/research_strategy_memory.json"),
        "reasoning_session": load_json(apk_output_dir / "generalization/reasoning_session_v2.json"),
        "source_to_sink_paths": load_json(apk_output_dir / "source_to_sink_paths_v1.json"),
        "runtime_plan": load_json(apk_output_dir / "runtime_source_to_sink_plan_v1.json"),
        "runtime_probe_results": load_json(apk_output_dir / "source_to_sink_probe_results_v1.json"),
        "universal_causal_graph": load_json(apk_output_dir / "universal_causal_graph_v1.json"),
        "deeplink_candidates": load_json(apk_output_dir / "deeplink_manifest_candidates.json"),
        "webview_candidates": load_json(apk_output_dir / "webview_static_candidates.json"),
    }

    blob = text_blob(evidence_story, artifacts, apk_output_dir.name)

    runtimes = classify_runtime(blob)
    semantic_shape = classify_semantic_shape(blob)
    strategy_family = classify_strategy_family(blob)
    validation_family = classify_validation_family(blob)
    proof_mode = infer_proof_mode(artifacts, blob)
    expected_information_gain = infer_expected_information_gain(
        semantic_shape,
        validation_family,
        proof_mode,
    )
    contract_quality = infer_contract_quality(
        semantic_shape,
        runtimes,
        validation_family,
        proof_mode,
    )

    apk_name = (
        evidence_story.get("apk_name")
        or evidence_story.get("target")
        or evidence_story.get("package")
        or apk_output_dir.name
    )

    semantic_story = {
        "schema": "semantic_story_v1",
        "generated_at": now_iso(),
        "apk_name": apk_name,
        "output_dir": str(apk_output_dir),
        "source_evidence_story": str(apk_output_dir / "evidence_story_v1.json"),
        "guardrails": {
            "candidate_only": True,
            "finding_allowed": False,
            "report_allowed": False,
            "target_specific_detectors_allowed": False,
            "learns_findings": False,
            "learns_cves": False,
        },
        "semantic_contract": {
            "runtime_model": runtimes,
            "framework_family": primary_framework_family(runtimes),
            "semantic_shape": semantic_shape,
            "strategy_family": strategy_family,
            "validation_family": validation_family,
            "proof_mode": proof_mode,
            "contract_quality": contract_quality,
            "expected_information_gain": expected_information_gain,
        },
        "learning_fields": {
            "source_to_sink_state": evidence_story.get("source_to_sink_state") or evidence_story.get("source_to_sink") or "unknown",
            "runtime_probe_state": evidence_story.get("runtime_probe_state") or "unknown",
            "missing_proof": evidence_story.get("missing_proof") or evidence_story.get("proof_gap") or "unknown",
            "next_best_experiment": evidence_story.get("next_best_experiment") or "unknown",
            "learning_value": evidence_story.get("learning_value") or expected_information_gain,
            "expected_information_gain": expected_information_gain,
            "proof_mode": proof_mode,
            "contract_quality": contract_quality,
            "strategy_family": strategy_family,
            "validation_family": validation_family,
            "blockers": evidence_story.get("blockers") or [],
            "counter_evidence": evidence_story.get("counter_evidence") or [],
        },
        "artifact_presence": {
            k: v is not None for k, v in artifacts.items()
        },
    }

    return semantic_story


def normalize_apk_output(apk_output_dir: Path, out: Optional[Path] = None) -> Dict[str, Any]:
    semantic_story = build_semantic_story(apk_output_dir)
    out = out or apk_output_dir / "semantic_story_v1.json"
    save_json(out, semantic_story)
    return semantic_story


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk_output_dir")
    parser.add_argument("--out")
    args = parser.parse_args()

    story = normalize_apk_output(
        Path(args.apk_output_dir),
        Path(args.out) if args.out else None,
    )

    print(json.dumps({
        "ok": True,
        "out": str(Path(args.out) if args.out else Path(args.apk_output_dir) / "semantic_story_v1.json"),
        "semantic_contract": story.get("semantic_contract"),
    }, indent=2))


if __name__ == "__main__":
    main()
