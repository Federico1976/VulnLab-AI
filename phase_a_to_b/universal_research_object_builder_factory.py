#!/usr/bin/env python3
import json
import sys
import subprocess
from pathlib import Path


REGISTRY = Path("phase_a_to_b/registry/research_object_builders.json")


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def should_run(builder, recommended):
    if builder.get("always"):
        return True
    reqs = builder.get("requires_any_pipeline") or []
    return any(r in recommended for r in reqs)


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 -m phase_a_to_b.universal_research_object_builder_factory <apk_output_dir>")
        sys.exit(1)

    apk_out = Path(sys.argv[1])
    phase_b = apk_out / "phase_b"
    phase_b.mkdir(parents=True, exist_ok=True)

    char = load(apk_out / "apk_characterization.json")
    recommended = char.get("recommended_pipelines") or char.get("recommended") or []

    registry = load(REGISTRY)
    builders = registry.get("builders", [])

    results = []

    for b in builders:
        output = phase_b / b["output"]

        if not should_run(b, recommended):
            results.append({
                "builder": b["id"],
                "status": "skipped",
                "reason": "required pipeline not recommended",
                "output": str(output)
            })
            continue

        cmd = [sys.executable, "-m", b["module"], str(apk_out), str(output)]
        print(f"[RO_FACTORY] {' '.join(cmd)}")
        rc = subprocess.call(cmd)

        payload = load(output)
        count = payload.get("count")
        if count is None:
            ros = payload.get("research_objects") if isinstance(payload, dict) else []
            count = len(ros) if isinstance(ros, list) else 0

        results.append({
            "builder": b["id"],
            "status": "ok" if rc == 0 else "failed",
            "rc": rc,
            "count": count,
            "output": str(output)
        })

    factory_report = {
        "schema": "vulnlab_ai.research_object_builder_factory.v2_declarative",
        "registry": str(REGISTRY),
        "apk_output_dir": str(apk_out),
        "recommended_pipelines": recommended,
        "builders": results,
        "summary": {
            "builders_total": len(results),
            "builders_ok": sum(1 for r in results if r.get("status") == "ok"),
            "builders_skipped": sum(1 for r in results if r.get("status") == "skipped"),
            "research_objects_declared": sum((r.get("count") or 0) for r in results if r.get("status") == "ok")
        }
    }

    out = phase_b / "research_object_factory_report.json"
    save(out, factory_report)

    print(json.dumps({
        "status": "ok",
        "recommended_pipelines": recommended,
        "summary": factory_report["summary"],
        "builders": results,
        "output": str(out)
    }, indent=2))


if __name__ == "__main__":
    main()
