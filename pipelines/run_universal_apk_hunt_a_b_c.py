import json
import subprocess
import sys
from pathlib import Path


def run(cmd):
    print("[A_B_C]", " ".join(cmd))
    rc = subprocess.call(cmd)
    print("[A_B_C_RC]", rc)
    if rc != 0:
        raise SystemExit(rc)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: python3 -m pipelines.run_universal_apk_hunt_a_b_c <apk_path> <output_dir>"
        )

    apk = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    run([
        sys.executable, "-m",
        "pipelines.run_universal_apk_hunt",
        str(apk),
        str(out)
    ])

    run([
        sys.executable, "-m",
        "phase_c.run_phase_c",
        str(out)
    ])

    phase_b_report = out / "phase_b_brain" / "phase_b_final_report.json"
    phase_c_summary = out / "phase_c" / "phase_c_summary.json"
    final_report = out / "UNIVERSAL_APK_A_B_C_REPORT.json"

    b = load_json(phase_b_report) if phase_b_report.exists() else {}
    c = load_json(phase_c_summary) if phase_c_summary.exists() else {}

    report = {
        "status": "ok",
        "schema": "vulnlab.universal_apk_a_b_c_report.v1",
        "apk": str(apk),
        "output_dir": str(out),
        "phase_b": {
            "completed": b.get("health", {}).get("phase_b_completed", False),
            "candidate_only_guardrail": b.get("health", {}).get("candidate_only_guardrail", True),
            "finding_allowed": b.get("health", {}).get("finding_allowed", False),
            "summary": b.get("summary", {})
        },
        "phase_c": {
            "completed": c.get("phase_c_completed", False),
            "architecture": c.get("architecture", {}),
            "summary": c.get("summary", {}),
            "outputs": c.get("outputs", {})
        },
        "global_guardrail": {
            "candidate_only": True,
            "finding_allowed": False,
            "requires_dynamic_validation": True
        }
    }

    with final_report.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(json.dumps({
        "status": "ok",
        "apk": str(apk),
        "output": str(final_report),
        "phase_b_completed": report["phase_b"]["completed"],
        "phase_c_completed": report["phase_c"]["completed"],
        "global_guardrail": report["global_guardrail"]
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
