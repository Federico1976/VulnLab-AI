#!/usr/bin/env python3
import subprocess
from pathlib import Path


def run(cmd):
    print("\n[PHASE_B]", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def run_phase_b_brain(research_objects_json, output_dir):
    research_objects_json = Path(research_objects_json)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run([
        "python3", "-m", "phase_b.run_cognitive_pipeline_v2",
        str(research_objects_json),
        str(output_dir)
    ])

    run([
        "python3", "-m", "phase_b.research_strategy_memory.strategy_memory_builder_v2",
        str(output_dir / "proof_evaluations.json"),
        str(output_dir / "unknown_resolution_tasks.json"),
        str(output_dir / "dynamic_validation_plans.json"),
        str(output_dir / "research_strategy_memory.json")
    ])

    run([
        "python3", "-m", "phase_b.reports.phase_b_final_report",
        str(output_dir),
        str(output_dir / "phase_b_final_report.json")
    ])

    return output_dir / "phase_b_final_report.json"
