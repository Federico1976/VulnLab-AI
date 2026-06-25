# Quick Start

## Run Universal APK Analysis

```bash
cd ~/apk_agent
PYTHONPATH=$PWD python3 -m pipelines.run_universal_apk_hunt <apk_or_target_path> <output_dir>
Expected Output

The pipeline should produce runtime characterization, semantic evidence, evidence graph artifacts, reachability candidates, validation plans, and disclosure candidates.

Rule

Every output is a candidate until reachability and dynamic validation are proven.
