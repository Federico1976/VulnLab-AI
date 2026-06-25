import subprocess
import sys
from pathlib import Path


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

    print("[+] Universal APK hunt completed")


if __name__ == "__main__":
    main()
