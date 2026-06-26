import subprocess
import sys
from pathlib import Path
from phase_b.find_research_objects import find_research_objects, write_merged_research_objects
from phase_b.brain_runner import run_phase_b_brain



def run(cmd):
    print("[RUN]", " ".join(cmd))
    rc = subprocess.run(cmd).returncode
    print("[RC]", rc)
    return rc


def ensure_decompiled_workspace(apk: Path, out: Path):
    sources = out / "code" / "decompiled" / "sources"
    if sources.exists() and any(sources.iterdir()):
        print("[+] Decompiled workspace already exists:", sources)
        return

    decompiled = out / "code" / "decompiled"
    decompiled.mkdir(parents=True, exist_ok=True)

    print("[+] Creating guaranteed decompiled workspace")
    rc = run(["jadx", "-d", str(decompiled), str(apk)])
    if rc != 0:
        print("[!] jadx completed with errors or failed; continuing if partial sources exist")

    if sources.exists():
        print("[+] Sources:", sources)
    else:
        print("[!] Sources directory not found after jadx:", sources)


def main():
    if len(sys.argv) != 3:
        print("Usage: PYTHONPATH=$PWD python3 -m pipelines.run_universal_apk_hunt <apk_or_dir> <out_dir>")
        sys.exit(1)

    apk = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    print("[+] Universal APK hunt started")
    print("[+] APK:", apk)
    print("[+] Out:", out)

    ensure_decompiled_workspace(apk, out)

    run(["python3", "-m", "pipelines.run_apk_characterization", str(apk), str(out)])

    rn_input = out / "rn_sensitive_execution_paths.json"
    if rn_input.exists():
        run(["python3", "-m", "pipelines.run_rn_multilayer_hunt", str(out)])
    else:
        print("[+] RN multilayer skipped: rn_sensitive_execution_paths.json not present")

    # Phase B Cognitive Brain integration
    _run_phase_a_to_b_research_object_builders(out)
    _try_run_phase_b_brain_after_phase_a(out)

    print("[+] Universal APK hunt completed")




def _run_phase_a_to_b_research_object_builders(out_dir: Path):
    phase_b_dir = out_dir / "phase_b"
    phase_b_dir.mkdir(parents=True, exist_ok=True)

    steps = [
        [
            sys.executable,
            "-m",
            "phase_b.joern_results.joern_execution_result_normalizer",
            str(out_dir),
            str(phase_b_dir / "normalized_joern_results.json"),
        ],
        [
            sys.executable,
            "-m",
            "phase_a_to_b.universal_research_object_builder_factory",
            str(out_dir),
        ],
    ]

    for cmd in steps:
        print(f"[PHASE_A_TO_B] {' '.join(cmd)}")
        rc = subprocess.call(cmd)
        print(f"[PHASE_A_TO_B_RC] {rc}")


def _try_run_phase_b_brain_after_phase_a(phase_a_output_dir):
    """Run Phase B cognitive brain if Phase A produced Research Objects."""
    try:
        phase_a_output_dir = Path(phase_a_output_dir)
        research_objects = find_research_objects(phase_a_output_dir)

        if not research_objects:
            print(f"[WARN] Phase B skipped: no research_objects json found under {phase_a_output_dir}")
            return None

        phase_b_output_dir = phase_a_output_dir / "phase_b_brain"
        merged_research_objects_json = write_merged_research_objects(phase_a_output_dir)

        cmd = [
            sys.executable,
            "-m",
            "phase_a_to_b.research_object_enricher_v2",
            str(merged_research_objects_json),
            str(merged_research_objects_json),
        ]
        print(f"[PHASE_A_TO_B] {' '.join(cmd)}")
        rc = subprocess.call(cmd)
        print(f"[PHASE_A_TO_B_RC] {rc}")

        report = run_phase_b_brain(merged_research_objects_json, phase_b_output_dir)
        print(f"[OK] Phase B cognitive brain completed: {report}")
        return report

    except Exception as e:
        print(f"[WARN] Phase B cognitive brain failed: {e}")
        return None


if __name__ == "__main__":
    main()
