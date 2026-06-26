#!/usr/bin/env python3
import json
import sys
from pathlib import Path


EFFECT_RULES = [
    {
        "effect_type": "IntentInjectionOrUnsafeIPCDelegateCandidate",
        "requires": ["ExternalInputCapability", "IntentLaunchCapability"],
        "severity_floor": "medium",
        "proof_focus": [
            "prove attacker influence over action/data/extras/component",
            "prove whether intent leaves app boundary",
            "prove permission/package/component restrictions or absence"
        ],
    },
    {
        "effect_type": "WebViewNavigationControlCandidate",
        "requires": ["ExternalInputCapability", "WebViewNavigationCapability"],
        "severity_floor": "medium",
        "proof_focus": [
            "prove attacker influence over loaded URL",
            "prove scheme/host allowlist effectiveness",
            "check privileged WebView settings and JS bridges"
        ],
    },
    {
        "effect_type": "PathOrUriInfluencedFileAccessCandidate",
        "requires": ["ExternalInputCapability", "FileAccessCapability"],
        "severity_floor": "medium",
        "proof_focus": [
            "prove attacker influence over path/URI",
            "prove canonicalization and directory constraints",
            "prove whether sensitive app/private/external files are reachable"
        ],
    },
    {
        "effect_type": "FileProviderExposureCandidate",
        "requires": ["ExternalInputCapability", "FileProviderCapability"],
        "severity_floor": "medium",
        "proof_focus": [
            "prove attacker influence over file converted to content URI",
            "inspect FileProvider path configuration",
            "prove whether another app can receive unintended file access"
        ],
    },
    {
        "effect_type": "LocalFileToNetworkUploadCandidate",
        "requires": ["FileAccessCapability", "NetworkOrUploadCapability"],
        "severity_floor": "high",
        "proof_focus": [
            "prove file read feeds upload/body/form-data",
            "prove attacker can select sensitive file or URI",
            "prove destination and authentication context"
        ],
    },
    {
        "effect_type": "DocumentProviderScopeCandidate",
        "requires": ["ExternalInputCapability", "DocumentPickerCapability"],
        "severity_floor": "low",
        "proof_focus": [
            "prove user-mediated selection exists",
            "prove persistence/scope of granted URI permission",
            "prove attacker influence over initial URI or picker behavior"
        ],
    },
]


def node_types(graph):
    return {n["type"] for n in graph.get("nodes", [])}


def has_guard(graph):
    return "SanitizerOrGuardCapability" in node_types(graph)


def infer_effects(graph):
    types = node_types(graph)
    effects = []

    for rule in EFFECT_RULES:
        if all(req in types for req in rule["requires"]):
            modifiers = []
            if has_guard(graph):
                modifiers.append("sanitizer_or_guard_present_requires_effectiveness_evaluation")

            effects.append({
                "effect_type": rule["effect_type"],
                "status": "security_effect_candidate",
                "severity_floor": rule["severity_floor"],
                "required_capabilities": rule["requires"],
                "modifiers": modifiers,
                "proof_focus": rule["proof_focus"],
                "declares_vulnerability": False,
            })

    return effects


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.security_effects.security_effect_inference <capability_graphs.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())
    graphs = data.get("capability_graphs", [])

    objects = []
    total_effects = 0

    for graph in graphs:
        effects = infer_effects(graph)
        total_effects += len(effects)

        objects.append({
            "security_effect_object_id": f"SE-{graph['capability_graph_id']}",
            "capability_graph_id": graph["capability_graph_id"],
            "hypothesis_id": graph["hypothesis_id"],
            "story_id": graph["story_id"],
            "research_object_id": graph["research_object_id"],
            "candidate_id": graph["candidate_id"],
            "task_type": graph["task_type"],
            "effect_count": len(effects),
            "effects": effects,
            "quality_gates": {
                "declares_vulnerability": False,
                "candidate_evidence_only": True,
                "requires_proof_evaluator": True,
                "requires_dynamic_validation_for_disclosure": True,
            }
        })

    summary = {}
    for obj in objects:
        for eff in obj["effects"]:
            summary[eff["effect_type"]] = summary.get(eff["effect_type"], 0) + 1

    output = {
        "schema": "vulnlab.security_effects.v1",
        "input_schema": data.get("schema"),
        "security_effect_object_count": len(objects),
        "effect_count": total_effects,
        "summary": summary,
        "security_effect_objects": objects,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "security_effects_are_not_findings": True,
            "requires_proof_evaluator": True,
        }
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "objects": len(objects),
        "effects": total_effects,
        "summary": summary,
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
