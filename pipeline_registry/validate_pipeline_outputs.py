#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 pipeline_registry/validate_pipeline_outputs.py <registry.json> <apk_output_dir>")
        sys.exit(1)

    registry = load(sys.argv[1])
    base = Path(sys.argv[2])

    checks = []
    missing = []

    for stage in registry.get("stages", []):
        for rel in stage.get("produces", []):
            p = base / rel
            ok = p.exists()
            item = {
                "stage": stage.get("id"),
                "artifact": rel,
                "exists": ok,
                "path": str(p)
            }
            checks.append(item)
            if not ok:
                missing.append(item)

    result = {
        "schema": "vulnlab.pipeline_registry.validation.v1",
        "pipeline": registry.get("pipeline"),
        "apk_output_dir": str(base),
        "total_checks": len(checks),
        "missing": len(missing),
        "ok": len(missing) == 0,
        "checks": checks,
        "missing_items": missing
    }

    out = base / "pipeline_registry_validation.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "ok" if result["ok"] else "missing_outputs",
        "total_checks": result["total_checks"],
        "missing": result["missing"],
        "output": str(out)
    }, indent=2))

    if missing:
        sys.exit(2)


if __name__ == "__main__":
    main()
