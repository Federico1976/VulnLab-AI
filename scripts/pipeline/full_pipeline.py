#!/usr/bin/env python3
"""
full_pipeline.py - Orchestratore APK Bug Bounty
Step 1: modulo Semgrep (Java)
"""
import subprocess
import json
import sys
from pathlib import Path

def run_semgrep_java(target_dir: Path, output_file: Path) -> dict:
    """
    Esegue Semgrep su codice Java decompilato.
    Ritorna findings filtrati per rilevanza di sicurezza reale.
    """
    cmd = [
        "semgrep",
        "--config", "p/java",
        "--config", "p/security-audit",
        "--config", "p/owasp-top-ten",
        str(target_dir),
        "--json",
        "--output", str(output_file),
        "--quiet",
    ]
    print(f"[*] Semgrep su {target_dir} ...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if not output_file.exists():
        print(f"[!] Semgrep non ha prodotto output. stderr: {result.stderr[:500]}")
        return {"results": [], "errors": ["semgrep_failed"]}

    with open(output_file) as f:
        data = json.load(f)

    findings = data.get("results", [])
    print(f"[+] Semgrep: {len(findings)} findings grezzi trovati")
    return {"results": findings, "raw_count": len(findings)}


if __name__ == "__main__":
    target = Path(sys.argv[1])
    output = target.parent / "semgrep_results.json"
    res = run_semgrep_java(target, output)
    print(json.dumps(res, indent=2)[:2000])
