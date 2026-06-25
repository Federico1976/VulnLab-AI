import subprocess
import sys
from pathlib import Path

def run(cmd):
    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m pipelines.run_rn_hunting_pipeline <target_output_dir> <rn_findings_json>")
        sys.exit(1)

    out_dir = Path(sys.argv[1])
    rn_input = Path(sys.argv[2])

    enriched = out_dir / "react_native_bridge_enriched.json"
    queue = out_dir / "rn_sensitive_candidate_queue.json"
    paths = out_dir / "rn_sensitive_execution_paths.json"
    cards_dir = out_dir / "investigation_cards/rn"
    readme = cards_dir / "README.md"

    run([
        "python3", "-m", "enrichment.rn_bridge_enricher",
        str(rn_input),
        str(enriched),
    ])

    run([
        "python3", "-m", "candidate_queue.build_rn_sensitive_queue",
        str(enriched),
        str(queue),
    ])

    run([
        "python3", "-m", "path_builder.rn_execution_path_builder",
        str(queue),
        str(paths),
    ])

    run([
        "python3", "-m", "reports.rn_investigation_cards",
        str(paths),
        str(cards_dir),
    ])

    run([
        "python3", "-m", "reports.rn_index_markdown",
        str(cards_dir / "index.json"),
        str(readme),
    ])

    print("\n[+] RN hunting pipeline completed")
    print(f"[+] Queue: {queue}")
    print(f"[+] Execution paths: {paths}")
    print(f"[+] Cards: {cards_dir}")
    print(f"[+] README: {readme}")

if __name__ == "__main__":
    main()
