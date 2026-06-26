#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import Counter


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def models(payload):
    return payload.get("evidence_models") or payload.get("models") or payload.get("items") or []


def collect_entities_by_rid(semantic):
    out = {}
    for e in semantic.get("entities", []):
        if not isinstance(e, dict):
            continue
        rid = e.get("research_object_id")
        if rid:
            out.setdefault(rid, []).append(e)
    return out


def extract_rid_from_obj(obj):
    if not isinstance(obj, dict):
        return None

    direct_keys = [
        "research_object_id",
        "source_research_object_id",
        "object_id",
        "ro_id",
    ]

    for k in direct_keys:
        if obj.get(k):
            return obj.get(k)

    for k in ("hypothesis", "story", "causal_story", "source", "target"):
        v = obj.get(k)
        if isinstance(v, dict):
            rid = extract_rid_from_obj(v)
            if rid:
                return rid

    return None


def collect_candidate_rids(*payloads):
    rids = []

    def walk(x):
        if isinstance(x, dict):
            rid = extract_rid_from_obj(x)
            if rid:
                rids.append(rid)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for p in payloads:
        walk(p)

    return rids


def normalize_rid(rid, known_rids):
    if not rid:
        return None

    if rid in known_rids:
        return rid

    # Fallback: story IDs often contain RO-derived fragments but not exact RO ids.
    for known in known_rids:
        if str(known) in str(rid) or str(rid) in str(known):
            return known

    return rid


def extract_semantic_requirements(entities):
    reqs = []
    unknowns = []
    policies = []
    effects = []
    capabilities = []

    for e in entities:
        t = e.get("type")
        p = e.get("payload", {})

        if t == "ProofRequirementEntity":
            reqs.append(p.get("proof_requirement") or e.get("name"))
        elif t == "UnknownEntity":
            unknowns.append(p.get("unknown") or e.get("name"))
        elif t == "FindingPolicyEntity":
            policies.append(p)
        elif t == "SecurityEffectHintEntity":
            effects.append(p.get("security_effect") or e.get("name"))
        elif t == "CapabilityHintEntity":
            capabilities.append(p.get("capability") or e.get("name"))

    return {
        "proof_requirements": [x for x in reqs if x],
        "unknowns": [x for x in unknowns if x],
        "finding_policies": policies,
        "security_effect_hints": [x for x in effects if x],
        "capability_hints": [x for x in capabilities if x],
        "candidate_only_guardrail": any(
            p.get("candidate_only_guardrail") is True
            or p.get("may_declare_vulnerability") is False
            for p in policies
        ),
    }


def main():
    if len(sys.argv) not in (4, 7):
        print(
            "Usage:\n"
            "  python3 -m phase_b.evidence_model.evidence_model_enricher_v2 "
            "<semantic_entities.json> <evidence_models.json> <output.json>\n"
            "Optional v2 context:\n"
            "  ... <ranked_stories.json> <causal_stories.json> <security_effects_aggregated.json>"
        )
        sys.exit(1)

    semantic = load(sys.argv[1])
    evidence = load(sys.argv[2])

    ranked = load(sys.argv[4]) if len(sys.argv) == 7 else {}
    causal = load(sys.argv[5]) if len(sys.argv) == 7 else {}
    aggregated = load(sys.argv[6]) if len(sys.argv) == 7 else {}

    by_rid = collect_entities_by_rid(semantic)
    known_rids = set(by_rid.keys())

    context_rids = [
        normalize_rid(r, known_rids)
        for r in collect_candidate_rids(ranked, causal, aggregated, evidence)
    ]
    context_rids = [r for r in context_rids if r in known_rids]

    dominant_rid = None
    if context_rids:
        dominant_rid = Counter(context_rids).most_common(1)[0][0]
    elif len(known_rids) == 1:
        dominant_rid = next(iter(known_rids))

    enriched = 0
    model_list = models(evidence)

    for idx, m in enumerate(model_list):
        if not isinstance(m, dict):
            continue

        rid = extract_rid_from_obj(m)
        rid = normalize_rid(rid, known_rids)

        if rid not in known_rids:
            rid = dominant_rid

        if rid not in known_rids:
            continue

        req = extract_semantic_requirements(by_rid.get(rid, []))

        m["research_object_id"] = rid
        m["v2_semantic_requirements"] = {
            "research_object_id": rid,
            **req,
        }
        m["v2_evidence_state"] = "semantic_requirements_attached"
        m["v2_identity_link"] = {
            "method": "direct_or_contextual_research_object_resolution",
            "dominant_rid": dominant_rid,
            "model_index": idx,
        }

        enriched += 1

    evidence["schema"] = "vulnlab.evidence_models.v2_enriched"
    evidence["v2_summary"] = {
        "enriched_models": enriched,
        "total_models": len(model_list),
        "known_research_objects": len(known_rids),
        "dominant_research_object_id": dominant_rid,
    }

    save(sys.argv[3], evidence)

    print(json.dumps({
        "status": "ok",
        "enriched_models": enriched,
        "total_models": len(model_list),
        "known_research_objects": len(known_rids),
        "dominant_research_object_id": dominant_rid,
        "output": sys.argv[3],
    }, indent=2))


if __name__ == "__main__":
    main()
