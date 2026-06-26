#!/usr/bin/env python3
import json
import sys
import subprocess
from pathlib import Path


def load(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def apk_name(path):
    return Path(path).stem.replace(" ", "_").replace("-", "_")


def run_cmd(cmd):
    print("[RUN]", " ".join(cmd))
    return subprocess.call(cmd)


def collect_summary(out_dir):
    final = load(out_dir / "phase_b_brain" / "phase_b_final_report.json")
    char = load(out_dir / "apk_characterization.json")
    reg = load(out_dir / "pipeline_registry_validation.json")

    return {
        "apk_output": str(out_dir),
        "package": char.get("package"),
        "label": char.get("label"),
        "features": list((char.get("detected_features") or char.get("features") or {}).keys()) if isinstance(char.get("detected_features") or char.get("features"), dict) else char.get("features"),
        "recommended_pipelines": char.get("recommended_pipelines") or char.get("recommended"),
        "phase_b_summary": final.get("summary", {}),
        "registry_ok": reg.get("ok"),
        "registry_missing": reg.get("missing"),
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 -m campaigns.run_universal_5apk_campaign <apk_dir_or_manifest.json> <campaign_out_dir>")
        print("Manifest format: {\"apks\": [\"path1.apk\", \"path2.apk\"]}")
        sys.exit(1)

    src = Path(sys.argv[1])
    campaign_out = Path(sys.argv[2])
    campaign_out.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        apks = sorted(str(p) for p in src.rglob("*.apk"))
    else:
        manifest = load(src)
        apks = manifest.get("apks", [])

    if len(apks) < 1:
        print("[ERR] no APKs found")
        sys.exit(2)

    results = []

    for i, apk in enumerate(apks, 1):
        name = f"{i:02d}_{apk_name(apk)}"
        out_dir = campaign_out / name

        cmd = [
            sys.executable,
            "-m",
            "pipelines.run_universal_apk_hunt",
            apk,
            str(out_dir),
        ]

        rc = run_cmd(cmd)

        reg_rc = run_cmd([
            sys.executable,
            "pipeline_registry/validate_pipeline_outputs.py",
            "pipeline_registry/universal_apk_hunt_registry.json",
            str(out_dir),
        ])

        summary = collect_summary(out_dir)
        summary["apk"] = apk
        summary["run_rc"] = rc
        summary["registry_rc"] = reg_rc
        results.append(summary)

    campaign = {
        "schema": "vulnlab.campaign.universal_5apk.v1",
        "campaign_out": str(campaign_out),
        "apk_count": len(results),
        "results": results,
        "aggregate": {
            "successful_runs": sum(1 for r in results if r["run_rc"] == 0),
            "registry_ok": sum(1 for r in results if r.get("registry_ok") is True),
            "total_dynamic_plans": sum((r.get("phase_b_summary") or {}).get("dynamic_validation_plans") or 0 for r in results),
            "total_causal_ready": sum((r.get("phase_b_summary") or {}).get("causal_ready_for_dynamic_validation") or 0 for r in results),
            "total_semantic_entities": sum((r.get("phase_b_summary") or {}).get("semantic_entities") or 0 for r in results),
        },
    }

    out = campaign_out / "campaign_summary.json"
    out.write_text(json.dumps(campaign, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "apk_count": len(results),
        "summary": str(out),
        "aggregate": campaign["aggregate"],
    }, indent=2))


if __name__ == "__main__":
    main()
