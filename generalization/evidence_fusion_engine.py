#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generalization.output_layout_resolver import resolve_manifest


def load(path):
    if not path:
        return {}
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


def first(*values):
    for v in values:
        if v not in (None, "", [], {}):
            return v
    return None


def score_level(score):
    if score is None:
        return "unknown"
    try:
        s = float(score)
    except Exception:
        return "unknown"
    if s >= 0.75:
        return "strong"
    if s >= 0.55:
        return "medium"
    if s > 0:
        return "weak"
    return "none"


def build_evidence_story(manifest_path):
    layout = resolve_manifest(manifest_path)
    item = layout.get("items", [{}])[0] if layout.get("items") else {}
    artifacts = item.get("artifacts", {})

    sts = load(artifacts.get("source_to_sink_paths"))
    static_trace = load(artifacts.get("static_trace"))
    runtime_plan = load(artifacts.get("runtime_plan"))
    probe_results = load(artifacts.get("probe_results"))
    probe_interpretation = load(artifacts.get("probe_interpretation"))
    causal_graph = load(artifacts.get("causal_graph"))
    llm_review = load(artifacts.get("llm_trace_review"))
    packet = load(artifacts.get("causal_llm_packet"))
    ollama = load(artifacts.get("ollama_reasoning"))
    proof_graph = load(artifacts.get("proof_graph"))
    local_plan = load(artifacts.get("local_plan"))

    top_candidate = packet.get("top_candidate", {})

    entry_component = first(
        top_candidate.get("entry_component"),
        causal_graph.get("top_entry_component"),
        static_trace.get("top_entry_component"),
        sts.get("top_entry_component"),
        llm_review.get("top_entry_component"),
    )

    causal_state = first(
        top_candidate.get("causal_state"),
        causal_graph.get("top_causal_state"),
        sts.get("top_causal_state"),
    )

    causal_score = first(
        top_candidate.get("causal_score"),
        causal_graph.get("top_causal_score"),
        sts.get("top_path_score"),
    )

    static_state = static_trace.get("top_static_trace_state")
    source_to_sink_state = sts.get("top_causal_state")
    probe_state = causal_graph.get("probe_research_state") or probe_interpretation.get("research_state")

    missing_proof = first(
        ollama.get("missing_proof"),
        top_candidate.get("missing_edges"),
        [
            "runtime marker propagation",
            "ordered method-level call chain",
            "sanitizer decision",
            "impact proof",
        ],
    )

    next_best_experiment = first(
        ollama.get("next_best_experiment"),
        local_plan.get("next_best_experiment"),
        causal_graph.get("next_step"),
        sts.get("next_step"),
    )

    evidence_chain = [
        {
            "stage": "entrypoint",
            "state": "identified" if entry_component else "missing",
            "value": entry_component,
        },
        {
            "stage": "source_to_sink",
            "state": source_to_sink_state or "unknown",
            "score": sts.get("top_path_score"),
            "next_step": sts.get("next_step"),
        },
        {
            "stage": "static_trace",
            "state": static_state or "unknown",
            "score": static_trace.get("top_static_trace_score"),
            "next_step": static_trace.get("next_step"),
        },
        {
            "stage": "runtime_plan",
            "state": "planned" if artifacts.get("runtime_plan") else "missing",
            "candidate_paths": runtime_plan.get("candidate_paths"),
            "next_step": runtime_plan.get("next_step"),
        },
        {
            "stage": "runtime_probe",
            "state": probe_state or "not_confirmed",
            "has_results": bool(artifacts.get("probe_results")),
            "has_interpretation": bool(artifacts.get("probe_interpretation")),
        },
        {
            "stage": "causal_graph",
            "state": causal_state or "unknown",
            "score": causal_score,
            "score_level": score_level(causal_score),
            "nodes": causal_graph.get("nodes"),
            "edges": causal_graph.get("edges"),
        },
        {
            "stage": "llm_review",
            "state": "ready" if llm_review.get("ready_for_llm_review") else "unknown",
            "risk_tags": llm_review.get("top_risk_tags", []),
        },
        {
            "stage": "ollama_reasoning",
            "state": ollama.get("reasoning_mode") or "missing",
            "backend": ollama.get("backend"),
            "fallback_used": ollama.get("fallback_used"),
            "next_best_experiment": ollama.get("next_best_experiment"),
        },
    ]

    blockers = []
    if "runtime marker propagation" in missing_proof:
        blockers.append("runtime_marker_propagation_missing")
    if "ordered method-level call chain" in missing_proof:
        blockers.append("ordered_method_chain_missing")
    if "sanitizer decision" in missing_proof:
        blockers.append("sanitizer_decision_missing")
    if "impact proof" in missing_proof:
        blockers.append("impact_proof_missing")

    confidence_inputs = {
        "causal_score": causal_score,
        "static_trace_score": static_trace.get("top_static_trace_score"),
        "source_to_sink_score": sts.get("top_path_score"),
        "llm_reasoning_present": bool(ollama),
        "runtime_probe_confirmed": probe_state in ("confirmed", "strong_confirmed", "runtime_confirmed"),
    }

    evidence_strength = "candidate"
    if confidence_inputs["runtime_probe_confirmed"]:
        evidence_strength = "runtime_supported_candidate"
    elif score_level(causal_score) == "strong":
        evidence_strength = "strong_static_causal_candidate"
    elif score_level(causal_score) == "medium":
        evidence_strength = "medium_static_causal_candidate"

    story = {
        "schema": "evidence_story_v1",
        "package": item.get("package"),
        "target": item.get("target"),
        "program": item.get("program"),
        "manifest": str(manifest_path),
        "canonical_output_dir": item.get("canonical_output_dir"),
        "entry_component": entry_component,
        "primary_causal_state": causal_state,
        "primary_causal_score": causal_score,
        "evidence_strength": evidence_strength,
        "candidate_only": True,
        "finding_allowed": False,
        "report_allowed": False,
        "evidence_chain": evidence_chain,
        "missing_proof": missing_proof,
        "blockers": blockers,
        "counter_evidence": first(
            ollama.get("counter_evidence"),
            ["no confirmed runtime propagation", "no concrete exploitability proof"],
        ),
        "next_best_experiment": next_best_experiment,
        "confidence_inputs": confidence_inputs,
        "resolved_artifacts": artifacts,
        "artifact_presence": item.get("artifact_presence", {}),
        "learning_value": {
            "usable_for_strategy_memory": True,
            "usable_for_continuous_training": True,
            "teaches": [
                "which proof edge is missing",
                "which experiment should run next",
                "which counter-evidence blocks reporting",
                "which causal state repeats across APKs",
            ],
        },
    }

    return story


def main():
    ap = argparse.ArgumentParser(description="Evidence Fusion Engine v1")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    story = build_evidence_story(args.manifest)
    save(args.out, story)
    print(json.dumps({
        "schema": story["schema"],
        "package": story["package"],
        "target": story["target"],
        "entry_component": story["entry_component"],
        "primary_causal_state": story["primary_causal_state"],
        "primary_causal_score": story["primary_causal_score"],
        "evidence_strength": story["evidence_strength"],
        "candidate_only": story["candidate_only"],
        "finding_allowed": story["finding_allowed"],
        "next_best_experiment": story["next_best_experiment"],
        "missing_proof": story["missing_proof"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
