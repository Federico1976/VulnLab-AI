#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ARTIFACTS = {
    "source_to_sink_paths": ["source_to_sink_paths_v1.json"],
    "static_trace": ["static_trace_v1.json"],
    "runtime_plan": ["runtime_source_to_sink_plan_v1.json"],
    "probe_results": ["source_to_sink_probe_results_v1.json"],
    "probe_interpretation": ["source_to_sink_probe_interpretation_v1.json"],
    "causal_graph": ["universal_causal_graph_v1.json"],
    "llm_trace_review": ["llm_trace_reviewer_v1.json"],
    "causal_llm_packet": ["causal_graph_llm_packet_v1.json"],
    "ollama_reasoning": ["ollama_llm_reasoning_v1.json"],
    "closure_report": ["research_closure_report_v1.json"],
    "episode_memory": ["research_episode_memory_v1.json"],
    "evidence_story": ["evidence_story_v1.json"],
    "local_plan": ["generalization/local_investigation_plan_v1.json"],
    "proof_graph": ["generalization/evidence_proof_graph_v1.json", "evidence_proof_graph_v1.json"],
    "research_objects": ["phase_b/merged_research_objects.json"],
}


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def canonical_output_dir_from_manifest_item(item):
    if item.get("output_dir"):
        return Path(item["output_dir"])

    pkg = item.get("package", "").replace(".", "_")
    if pkg:
        return Path(f"output/bugbounty_{pkg}")

    return None


def candidate_dirs(item):
    dirs = []

    out = canonical_output_dir_from_manifest_item(item)
    if out:
        dirs.append(out)

    apk = item.get("apk", "")
    package = item.get("package", "")
    name_parts = []

    if "opera" in apk.lower() or "opera" in package.lower():
        name_parts = ["opera_android", "bugbounty_opera_android"]
    elif "skyscanner" in apk.lower() or "skyscanner" in package.lower():
        name_parts = ["skyscanner_android", "bugbounty_skyscanner_android"]
    elif "opsgenie" in apk.lower() or "opsgenie" in package.lower():
        name_parts = ["opsgenie_android", "bugbounty_opsgenie_android"]
    elif "quizlet" in apk.lower() or "quizlet" in package.lower():
        name_parts = ["quizlet_android", "bugbounty_quizlet_android"]
    elif "trello" in apk.lower() or "trello" in package.lower():
        name_parts = ["trello_android", "bugbounty_trello_android"]

    for n in name_parts:
        dirs.append(Path("output") / n)
        dirs.append(Path("output/bugbounty") / n.replace("bugbounty_", ""))

    # preserve order, remove duplicates
    seen = set()
    clean = []
    for d in dirs:
        s = str(d)
        if s not in seen:
            seen.add(s)
            clean.append(d)

    return clean


def resolve_artifact(item, artifact_name):
    for base in candidate_dirs(item):
        for rel in ARTIFACTS.get(artifact_name, []):
            p = base / rel
            if p.exists():
                return str(p)
    return None


def resolve_layout_for_item(item):
    dirs = [str(x) for x in candidate_dirs(item)]
    artifacts = {
        name: resolve_artifact(item, name)
        for name in ARTIFACTS
    }

    return {
        "package": item.get("package"),
        "target": item.get("target"),
        "program": item.get("program"),
        "manifest_output_dir": item.get("output_dir"),
        "candidate_dirs": dirs,
        "canonical_output_dir": str(canonical_output_dir_from_manifest_item(item)) if canonical_output_dir_from_manifest_item(item) else None,
        "artifacts": artifacts,
        "artifact_presence": {k: bool(v) for k, v in artifacts.items()},
    }


def resolve_manifest(manifest_path):
    data = load(manifest_path)
    if not isinstance(data, list):
        return {
            "schema": "output_layout_resolution_v1",
            "manifest": str(manifest_path),
            "error": "manifest is not a list",
            "items": [],
        }

    items = [resolve_layout_for_item(x) for x in data]

    return {
        "schema": "output_layout_resolution_v1",
        "manifest": str(manifest_path),
        "items_total": len(items),
        "items": items,
    }


def main():
    ap = argparse.ArgumentParser(description="Universal Output Layout Resolver")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    result = resolve_manifest(args.manifest)
    save(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
