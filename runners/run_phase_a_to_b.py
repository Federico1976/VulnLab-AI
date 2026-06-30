#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

from phase_b.find_research_objects import find_research_objects


def run(cmd):
    print("\n[RUN]", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 runners/run_phase_a_to_b.py <phase_a_output_dir> <phase_b_output_dir>")
        sys.exit(1)

    phase_a_dir = Path(sys.argv[1])
    phase_b_dir = Path(sys.argv[2])

    ro = find_research_objects(phase_a_dir)
    if not ro:
        print(f"ERROR: no research_objects json found or buildable under {phase_a_dir}")
        sys.exit(2)

    print(f"[OK] research_objects={ro}")

    run([
        "python3", "-m", "phase_b.run_cognitive_pipeline_v2",
        str(ro),
        str(phase_b_dir)
    ])

    run([
        "python3", "-m", "phase_b.research_strategy_memory.strategy_memory_builder",
        str(phase_b_dir / "proof_evaluations.json"),
        str(phase_b_dir / "unknown_resolution_tasks.json"),
        str(phase_b_dir / "dynamic_validation_plans.json"),
        str(phase_b_dir / "research_strategy_memory.json")
    ])

    run([
        "python3", "-m", "phase_b.reports.phase_b_final_report",
        str(phase_b_dir),
        str(phase_b_dir / "phase_b_final_report.json")
    ])

    print("\nOK Phase A → Phase B merge complete")
    print(f"OUTPUT_DIR={phase_b_dir}")


if __name__ == "__main__":
    main()
