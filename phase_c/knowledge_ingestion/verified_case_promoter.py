import json
import shutil
import sys
from pathlib import Path

from phase_c.knowledge_memory.vulnerability_case_validator import validate_vulnerability_case


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: python3 -m phase_c.knowledge_ingestion.verified_case_promoter "
            "<candidate_json> <verified_cases_dir> <knowledge_memory_seed_cases_dir>"
        )

    candidate_path = Path(sys.argv[1])
    verified_dir = Path(sys.argv[2])
    seed_dir = Path(sys.argv[3])

    verified_dir.mkdir(parents=True, exist_ok=True)
    seed_dir.mkdir(parents=True, exist_ok=True)

    case = load_json(candidate_path)
    validation = validate_vulnerability_case(case)

    if validation["status"] != "valid":
        print(json.dumps({
            "status": "quarantine",
            "reason": "candidate_validation_failed",
            "validation": validation
        }, indent=2, ensure_ascii=False))
        raise SystemExit(1)

    meta = case.get("candidate_metadata", {})
    if not meta.get("candidate"):
        raise SystemExit("not_a_candidate")

    source_notes = case.get("identity", {}).get("source_refs", [])
    source_quality = case.get("identity", {}).get("source_quality", "")

    # Safety gate:
    # Automated web acquisitions must not be promoted blindly.
    # Only manually reviewed / safe-for-training candidates should be promoted.
    # Other valid candidates remain candidates until LLM/human review enriches root cause,
    # counterevidence, and validation semantics.
    if source_quality in {"nvd_cve", "android_security_bulletin", "osv", "github_advisory"}:
        print(json.dumps({
            "status": "quarantine",
            "reason": "automated_source_requires_review_before_promotion",
            "source_quality": source_quality,
            "validation": validation
        }, indent=2, ensure_ascii=False))
        raise SystemExit(2)

    case["candidate_metadata"]["verified"] = True
    case["candidate_metadata"]["promotion_review"] = {
        "status": "promoted_to_verified_case",
        "review_mode": "manual_local_review",
        "finding_allowed": False,
        "candidate_only": True
    }

    case_id = case.get("identity", {}).get("case_id", candidate_path.stem)
    out_name = f"{case_id}.json"

    verified_path = verified_dir / out_name
    seed_path = seed_dir / out_name

    with verified_path.open("w", encoding="utf-8") as f:
        json.dump(case, f, indent=2, ensure_ascii=False)

    shutil.copyfile(verified_path, seed_path)

    print(json.dumps({
        "status": "ok",
        "promoted": True,
        "verified_case": str(verified_path),
        "knowledge_memory_case": str(seed_path),
        "validation": validation
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
