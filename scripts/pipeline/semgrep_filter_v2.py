#!/usr/bin/env python3
"""
semgrep_filter_v2.py - Esegue tutte le regole custom apk-agent validate
(sessione 2, 23/06/2026) + i pack community gia testati (sessione 1).

Ogni regola e stata validata con test positivo+negativo sintetico prima
di entrare in questo modulo. Vedi knowledge_base/maswe/ per la
documentazione completa di ciascun pattern.
"""
import subprocess
import json
import sys
from pathlib import Path

CUSTOM_RULES_DIR = Path(__file__).parent / "semgrep_rules"

COMMUNITY_PACKS = ["p/java", "p/security-audit", "p/owasp-top-ten"]

VALIDATED_CUSTOM_RULES = [
    "insecure_random.yml",          # CRYPTO #3
    "biometric_bypass.yml",         # AUTH #1
    "trustmanager_permissive.yml",  # NETWORK #1
    "hostnameverifier_permissive.yml",  # NETWORK #2
    "sensitive_logging.yml",        # CODE #4
]


def run_full_semgrep_scan(target_dir: Path, output_file: Path) -> dict:
    """
    Esegue community pack + tutte le regole custom validate in un'unica
    scansione. Ritorna i findings grezzi (il triage va fatto a parte
    con semgrep_filter.py, gia esistente da sessione 1).
    """
    config_args = []
    for pack in COMMUNITY_PACKS:
        config_args += ["--config", pack]
    for rule_file in VALIDATED_CUSTOM_RULES:
        rule_path = CUSTOM_RULES_DIR / rule_file
        if not rule_path.exists():
            print(f"[!] ATTENZIONE: regola {rule_file} non trovata, salto")
            continue
        config_args += ["--config", str(rule_path)]

    cmd = ["semgrep"] + config_args + [str(target_dir), "--json",
                                         "--output", str(output_file), "--quiet"]

    print(f"[*] Scansione completa su {target_dir}")
    print(f"[*] Pack community: {COMMUNITY_PACKS}")
    print(f"[*] Regole custom validate: {len(VALIDATED_CUSTOM_RULES)}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if not output_file.exists():
        print(f"[!] Semgrep non ha prodotto output. stderr: {result.stderr[:500]}")
        return {"results": [], "errors": ["semgrep_failed"]}

    with open(output_file) as f:
        data = json.load(f)

    findings = data.get("results", [])

    # Separiamo i findings delle nostre regole custom da quelli community,
    # per dare priorita visiva ai pattern che abbiamo validato a mano
    custom_rule_ids = {f"apk-agent-{r.replace('.yml','').replace('_','-')}"
                        for r in VALIDATED_CUSTOM_RULES}
    custom_findings = [f for f in findings if f["check_id"] in custom_rule_ids
                        or "apk-agent" in f["check_id"]]
    community_findings = [f for f in findings if f not in custom_findings]

    print(f"[+] Totale: {len(findings)} findings")
    print(f"    - Da regole custom apk-agent (validate): {len(custom_findings)}")
    print(f"    - Da pack community: {len(community_findings)}")

    return {
        "results": findings,
        "custom_findings": custom_findings,
        "community_findings": community_findings,
        "raw_count": len(findings),
    }


if __name__ == "__main__":
    target = Path(sys.argv[1])
    output = target.parent / "semgrep_full_results.json"
    res = run_full_semgrep_scan(target, output)
    print()
    print("=== FINDINGS DA REGOLE CUSTOM (priorita) ===")
    for f in res["custom_findings"]:
        print(f"  {f['check_id']} @ {f['path']}:{f['start']['line']}")
