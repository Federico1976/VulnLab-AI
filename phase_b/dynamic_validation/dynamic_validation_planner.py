#!/usr/bin/env python3
import json
import sys
from pathlib import Path


EFFECT_TO_DYNAMIC = {
    "IntentInjectionOrUnsafeIPCDelegateCandidate": [
        "instrument intent creation and launch",
        "observe action/data/extras/component at runtime",
        "verify whether launched component crosses app boundary"
    ],
    "WebViewNavigationControlCandidate": [
        "instrument WebView URL loading",
        "observe final URL after validation",
        "test scheme/host allowlist behavior with safe benign payloads"
    ],
    "PathOrUriInfluencedFileAccessCandidate": [
        "instrument file/URI access",
        "observe canonical path and resolved URI",
        "test whether path escapes intended directory with benign test files"
    ],
    "FileProviderExposureCandidate": [
        "observe generated content URI",
        "verify provider authority and grant flags",
        "confirm receiving app visibility using benign file"
    ],
    "LocalFileToNetworkUploadCandidate": [
        "instrument file read and upload call",
        "observe whether file bytes feed request body",
        "verify destination and authentication context"
    ],
    "DocumentProviderScopeCandidate": [
        "observe document picker flow",
        "verify user-mediated selection",
        "inspect persisted URI permissions"
    ],
}


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m phase_b.dynamic_validation.dynamic_validation_planner <proof_evaluations.json> <evidence_models.json> <out.json>")
        sys.exit(1)

    evals = json.loads(Path(sys.argv[1]).read_text())
    models = json.loads(Path(sys.argv[2]).read_text())

    model_by_id = {m["evidence_model_id"]: m for m in models.get("evidence_models", [])}
    plans = []

    for e in evals.get("evaluations", []):
        if e["verdict"] not in {
            "needs_unknown_resolution",
            "candidate_supported_needs_dynamic_validation",
            "candidate_supported_not_proven"
        }:
            continue

        m = model_by_id.get(e["evidence_model_id"], {})
        plans.append({
            "dynamic_plan_id": "DVP-" + e["proof_evaluation_id"],
            "proof_evaluation_id": e["proof_evaluation_id"],
            "evidence_model_id": e["evidence_model_id"],
            "hypothesis_id": e["hypothesis_id"],
            "effect_type": e["effect_type"],
            "validation_goal": "Resolve remaining runtime uncertainty without declaring vulnerability.",
            "recommended_observations": EFFECT_TO_DYNAMIC.get(e["effect_type"], ["collect runtime evidence relevant to unresolved unknowns"]),
            "unknowns_to_resolve": m.get("unknowns", []),
            "safety": {
                "benign_payloads_only": True,
                "authorized_scope_only": True,
                "no_exploitation": True,
                "no_data_exfiltration": True,
            },
            "status": "planned_not_executed",
            "declares_vulnerability": False,
        })

    summary = {}
    for p in plans:
        summary[p["effect_type"]] = summary.get(p["effect_type"], 0) + 1

    out = {
        "schema": "vulnlab.dynamic_validation_plans.v1",
        "input_schemas": {
            "proof_evaluations": evals.get("schema"),
            "evidence_models": models.get("schema"),
        },
        "plan_count": len(plans),
        "summary": summary,
        "dynamic_validation_plans": plans,
        "quality_gates": {
            "declares_vulnerability": False,
            "authorized_testing_only": True,
            "benign_validation_only": True,
        }
    }

    Path(sys.argv[3]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[3]).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({"status": "ok", "plans": len(plans), "summary": summary, "output": sys.argv[3]}, indent=2))


if __name__ == "__main__":
    main()
