import json
import subprocess
import sys
from pathlib import Path


def load(path):
    return json.load(open(path, "r", encoding="utf-8"))


def run(cmd):
    print("[CAMPAIGN]", " ".join(cmd))
    return subprocess.call(cmd)


def main():
    manifest_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("campaigns/universal_abc_campaign_manifest.json")
    report_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output/universal_abc_campaign_report.json")

    manifest = load(manifest_path)
    records = []

    for item in manifest["items"]:
        if not item.get("enabled", True):
            continue

        apk = item["apk"]
        out = item["output"]

        rc = run([
            sys.executable, "-m",
            "pipelines.run_universal_apk_hunt_a_b_c",
            apk,
            out
        ])

        final = Path(out) / "UNIVERSAL_APK_A_B_C_REPORT.json"

        rec = {
            "name": item["name"],
            "apk": apk,
            "output": out,
            "return_code": rc,
            "status": "ok" if rc == 0 and final.exists() else "failed"
        }

        if final.exists():
            rec["report"] = load(final)

        records.append(rec)

    ok = [r for r in records if r["status"] == "ok"]

    report = {
        "schema": "vulnlab.universal_abc_campaign_report.v1",
        "status": "ok",
        "summary": {
            "targets": len(records),
            "ok": len(ok),
            "failed": len(records) - len(ok),
            "candidate_only": True,
            "finding_allowed": False,
            "requires_dynamic_validation": True
        },
        "records": records
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "summary": report["summary"],
        "output": str(report_path)
    }, indent=2))


if __name__ == "__main__":
    main()
