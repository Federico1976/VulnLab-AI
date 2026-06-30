import json
import subprocess
import sys
from pathlib import Path


def run_phase_c(out_dir: Path):
    cmd = [sys.executable, "-m", "phase_c.run_phase_c", str(out_dir)]
    rc = subprocess.call(cmd)
    summary_path = out_dir / "phase_c" / "phase_c_summary.json"

    if rc != 0 or not summary_path.exists():
        return {
            "apk_output_dir": str(out_dir),
            "status": "failed",
            "return_code": rc
        }

    with summary_path.open("r", encoding="utf-8") as f:
        summary = json.load(f)

    return {
        "apk_output_dir": str(out_dir),
        "status": "ok",
        "summary": summary.get("summary", {}),
        "outputs": summary.get("outputs", {})
    }


def discover_outputs(base: Path):
    results = []
    for p in sorted(base.glob("*")):
        if p.is_dir() and (p / "phase_b_brain").exists():
            results.append(p)
    return results


def main():
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: python3 -m phase_c.campaigns.run_phase_c_batch <output_base_dir> [campaign_output_json]"
        )

    base = Path(sys.argv[1])
    campaign_output = Path(sys.argv[2]) if len(sys.argv) > 2 else base / "phase_c_batch_campaign_report.json"

    targets = discover_outputs(base)

    records = []
    for t in targets:
        print(f"[C14] running Phase C on {t}")
        records.append(run_phase_c(t))

    ok = [r for r in records if r["status"] == "ok"]

    report = {
        "status": "ok",
        "schema": "vulnlab.phase_c_batch_campaign.v1",
        "summary": {
            "targets_discovered": len(targets),
            "runs_ok": len(ok),
            "runs_failed": len(records) - len(ok),
            "finding_allowed": False,
            "requires_dynamic_validation": True
        },
        "records": records
    }

    campaign_output.parent.mkdir(parents=True, exist_ok=True)
    with campaign_output.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(json.dumps({
        "status": "ok",
        "summary": report["summary"],
        "output": str(campaign_output)
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
