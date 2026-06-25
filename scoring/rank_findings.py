import json
import sys
from pathlib import Path

from scoring.risk_scoring import RiskScoringEngine


def load_findings(path: Path):
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["findings", "results", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]

    raise ValueError("Unsupported findings JSON format")


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m scoring.rank_findings <input.json> <output.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    findings = load_findings(input_path)
    engine = RiskScoringEngine()

    scored = [engine.score(f) for f in findings]
    scored.sort(key=lambda x: x["risk_score"]["total"], reverse=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)

    print(f"[+] Loaded findings: {len(findings)}")
    print(f"[+] Ranked findings written to: {output_path}")
    print("[+] Top 20:")

    for i, finding in enumerate(scored[:20], 1):
        print(
            f"{i:02d}. "
            f"score={finding['risk_score']['total']} "
            f"priority={finding['priority']} "
            f"id={finding.get('finding_id', 'N/A')} "
            f"title={finding.get('title', 'N/A')} "
            f"status={finding.get('status', 'N/A')}"
        )


if __name__ == "__main__":
    main()
