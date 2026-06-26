#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def classify_unknown(u):
    q = (u.get("question") or "").lower()

    if "sanitizer" in q or "validate" in q or "allowlist" in q:
        return "sanitizer_resolution_task", "static_semantic_slice"
    if "path" in q or "uri" in q or "canonical" in q:
        return "path_uri_resolution_task", "joern_and_fileprovider_config"
    if "intent" in q or "component" in q or "permission" in q:
        return "intent_ipc_resolution_task", "manifest_and_static_slice"
    if "webview" in q or "url" in q or "host" in q or "scheme" in q:
        return "webview_resolution_task", "static_webview_policy_check"
    if "upload" in q or "network" in q or "destination" in q:
        return "network_upload_resolution_task", "static_network_flow_check"
    return "generic_unknown_resolution_task", "static_review"


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.unknown_resolver.unknown_resolver <evidence_models.json> <out.json>")
        sys.exit(1)

    data = json.loads(Path(sys.argv[1]).read_text())
    tasks = []

    for m in data.get("evidence_models", []):
        for i, u in enumerate(m.get("unknowns", []), 1):
            task_type, engine = classify_unknown(u)
            tasks.append({
                "unknown_task_id": f"UR-{m['evidence_model_id']}-{i}",
                "evidence_model_id": m["evidence_model_id"],
                "hypothesis_id": m["hypothesis_id"],
                "effect_type": m["effect_type"],
                "unknown": u,
                "task_type": task_type,
                "recommended_engine": engine,
                "status": "planned_not_executed",
                "declares_vulnerability": False,
            })

    summary = {}
    for t in tasks:
        summary[t["task_type"]] = summary.get(t["task_type"], 0) + 1

    out = {
        "schema": "vulnlab.unknown_resolution_tasks.v1",
        "input_schema": data.get("schema"),
        "task_count": len(tasks),
        "summary": summary,
        "unknown_resolution_tasks": tasks,
        "quality_gates": {
            "declares_vulnerability": False,
            "candidate_evidence_only": True,
            "tasks_resolve_uncertainty_not_findings": True,
        }
    }

    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({"status": "ok", "tasks": len(tasks), "summary": summary, "output": sys.argv[2]}, indent=2))


if __name__ == "__main__":
    main()
