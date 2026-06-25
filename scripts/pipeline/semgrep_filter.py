#!/usr/bin/env python3
"""
semgrep_filter.py - Riduce falsi positivi noti su findings Semgrep
Principio: non eliminiamo nulla silenziosamente, declassiamo con motivazione esplicita
"""
import re
from pathlib import Path

# Pattern di contesto che indicano uso NON crittografico di hash deboli
NON_CRYPTO_HASH_CONTEXT = [
    r"VIN\s*identifier",
    r"cache\s*key",
    r"file\s*name",
    r"checksum",  # checksum di integrità non-adversariale è spesso ok con hash debole
    r"\.substring\(",  # troncamento per ID breve è un segnale (non prova) di uso non crypto
]

def get_code_context(filepath: str, line: int, window: int = 15) -> str:
    """Legge righe attorno al finding per dare contesto reale"""
    try:
        with open(filepath) as f:
            lines = f.readlines()
        start = max(0, line - window)
        end = min(len(lines), line + 5)
        return "".join(lines[start:end])
    except Exception as e:
        return f"[errore lettura contesto: {e}]"

def classify_finding(finding: dict) -> dict:
    """
    Aggiunge un campo 'triage' al finding:
    - 'needs_review': richiede lettura umana (default sicuro)
    - 'likely_false_positive': pattern di contesto noto, ma SEMPRE con motivazione esplicita
    """
    filepath = finding["path"]
    line = finding["start"]["line"]
    context = get_code_context(filepath, line)

    finding["triage"] = {
        "status": "needs_review",
        "reason": "default: nessun pattern di esclusione automatica applicato",
        "code_context": context[:1500],
    }

    check_id = finding["check_id"]
    if "use-of-sha1" in check_id or "use-of-md5" in check_id:
        for pattern in NON_CRYPTO_HASH_CONTEXT:
            if re.search(pattern, context, re.IGNORECASE):
                finding["triage"]["status"] = "likely_false_positive"
                finding["triage"]["reason"] = (
                    f"Hash debole ({check_id}) ma contesto suggerisce uso non-crittografico "
                    f"(pattern trovato: '{pattern}'). VERIFICARE SEMPRE A MANO prima di scartare."
                )
                break

    return finding


def triage_all(findings: list[dict]) -> dict:
    classified = [classify_finding(f) for f in findings]
    needs_review = [f for f in classified if f["triage"]["status"] == "needs_review"]
    likely_fp = [f for f in classified if f["triage"]["status"] == "likely_false_positive"]

    return {
        "total": len(classified),
        "needs_review": needs_review,
        "likely_false_positive": likely_fp,
        "summary": (
            f"{len(classified)} findings totali: "
            f"{len(needs_review)} richiedono revisione, "
            f"{len(likely_fp)} probabili falsi positivi (DA VERIFICARE COMUNQUE)"
        ),
    }


if __name__ == "__main__":
    import json
    import sys

    with open(sys.argv[1]) as f:
        data = json.load(f)

    triaged = triage_all(data.get("results", []))
    print(triaged["summary"])
    print()
    for f in triaged["likely_false_positive"]:
        print(f"[PROBABILE FP] {f['check_id']} @ {f['path']}:{f['start']['line']}")
        print(f"  Motivo: {f['triage']['reason']}")
        print()
    for f in triaged["needs_review"]:
        print(f"[DA RIVEDERE] {f['check_id']} @ {f['path']}:{f['start']['line']}")
        print(f"  {f['extra']['message'][:150]}")
        print()
