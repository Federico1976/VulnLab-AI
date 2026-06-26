#!/usr/bin/env python3
import json
import sys
import hashlib
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sid(prefix, *parts):
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}-{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


def get_models(payload):
    return payload.get("evidence_models") or payload.get("models") or payload.get("items") or []


def get_joern_results(payload):
    if isinstance(payload, dict):
        return payload.get("results") or payload.get("items") or []
    if isinstance(payload, list):
        return payload
    return []


def get_entities(payload):
    return payload.get("entities") or []


def collect_entity_stats(semantic, rid):
    stats = {
        "sources": 0,
        "sinks": 0,
        "propagations": 0,
        "bridges": 0,
        "capability_hints": 0,
        "proof_requirements": 0,
        "unknowns": 0,
        "finding_policy": 0,
    }

    for e in get_entities(semantic):
        if not isinstance(e, dict):
            continue

        if rid and e.get("research_object_id") not in (None, rid):
            continue

        t = e.get("type")
        if t == "SourceEntity":
            stats["sources"] += 1
        elif t == "SinkEntity":
            stats["sinks"] += 1
        elif t == "PropagationEntity":
            stats["propagations"] += 1
        elif t == "BridgeMethodEntity":
            stats["bridges"] += 1
        elif t == "CapabilityHintEntity":
            stats["capability_hints"] += 1
        elif t == "ProofRequirementEntity":
            stats["proof_requirements"] += 1
        elif t == "UnknownEntity":
            stats["unknowns"] += 1
        elif t == "FindingPolicyEntity":
            stats["finding_policy"] += 1

    return stats


def collect_joern_stats(results):
    methods = set()
    files = set()
    sources = set()
    sinks = set()
    classes = set()

    for r in results:
        if not isinstance(r, dict):
            continue
        if r.get("method"):
            methods.add(str(r.get("method")))
        if r.get("file"):
            files.add(str(r.get("file")))
        if r.get("source"):
            sources.add(str(r.get("source")))
        if r.get("sink"):
            sinks.add(str(r.get("sink")))
        if r.get("class"):
            classes.add(str(r.get("class")))

    return {
        "normalized_results": len(results),
        "methods": len(methods),
        "files": len(files),
        "sources": len(sources),
        "sinks": len(sinks),
        "classes": len(classes),
        "has_static_context": len(results) > 0,
        "has_source_sink_labels": bool(sources and sinks),
    }


def infer_state(model, entity_stats, joern_stats):
    req = model.get("v2_semantic_requirements", {})
    proof_reqs = req.get("proof_requirements", [])
    unknowns = req.get("unknowns", [])

    has_ro_semantics = bool(proof_reqs or unknowns or entity_stats["proof_requirements"] or entity_stats["unknowns"])
    has_source_sink_entities = entity_stats["sources"] > 0 and entity_stats["sinks"] > 0
    has_static_context = joern_stats["has_static_context"]
    has_enough_static = joern_stats["normalized_results"] >= 5

    if has_static_context and has_ro_semantics and (has_source_sink_entities or has_enough_static):
        return "causal_static_evidence_ready_for_dynamic_validation"

    if has_static_context and has_ro_semantics:
        return "static_context_available_needs_source_sink_correlation"

    if has_static_context:
        return "joern_results_available_but_not_yet_causal"

    return "needs_more_static_evidence"


def main():
    if len(sys.argv) != 5:
        print("Usage: python3 -m phase_b.causal_reachability.causal_reachability_engine_v2 <semantic_entities.json> <evidence_models.json> <normalized_joern_results.json> <output.json>")
        sys.exit(1)

    semantic = load(sys.argv[1])
    evidence = load(sys.argv[2])
    joern = load(sys.argv[3])

    models = get_models(evidence)
    joern_results = get_joern_results(joern)
    joern_stats = collect_joern_stats(joern_results)

    objects = []
    summary = {}

    for idx, m in enumerate(models):
        if not isinstance(m, dict):
            continue

        rid = m.get("research_object_id") or m.get("v2_semantic_requirements", {}).get("research_object_id")
        entity_stats = collect_entity_stats(semantic, rid)
        state = infer_state(m, entity_stats, joern_stats)

        obj = {
            "causal_reachability_id": sid("CRV2", rid, idx, state),
            "research_object_id": rid,
            "evidence_model_index": idx,
            "state": state,
            "candidate_only": True,
            "may_declare_vulnerability": False,
            "dynamic_validation_recommended": state == "causal_static_evidence_ready_for_dynamic_validation",
            "causal_static_evidence": {
                "entity_stats": entity_stats,
                "joern_stats": joern_stats,
                "semantic_requirements_present": bool(m.get("v2_semantic_requirements")),
                "causal_chain_claimed": False,
                "reason": "Static evidence is sufficient to plan dynamic validation, not to declare a vulnerability.",
            },
            "required_next_steps": [
                "validate_source_controllability",
                "validate_sink_reachability",
                "validate_guard_or_sanitizer_behavior",
                "perform_dynamic_validation_before_disclosure",
            ],
        }

        objects.append(obj)
        summary[state] = summary.get(state, 0) + 1

    out = {
        "schema": "vulnlab.causal_reachability.v2",
        "causal_reachability_objects": objects,
        "summary": summary,
        "count": len(objects),
    }

    save(sys.argv[4], out)

    print(json.dumps({
        "status": "ok",
        "objects": len(objects),
        "summary": summary,
        "output": sys.argv[4],
    }, indent=2))


if __name__ == "__main__":
    main()
