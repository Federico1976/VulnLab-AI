#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path
from collections import Counter


def run(cmd, cwd):
    print(f"\n[+] RUN: {' '.join(map(str, cmd))}")
    subprocess.run([str(x) for x in cmd], cwd=cwd, check=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def count_items(data):
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("findings", "candidates", "items", "results"):
            if isinstance(data.get(key), list):
                return len(data[key])
    return 0


def pick_source_root(target):
    candidates = [
        target / "code" / "decompiled" / "sources",
        target / "code" / "decompiled_tesla_only",
        target / "sources",
        target / "jadx_sources",
        target / "decompiled",
        target,
    ]
    for p in candidates:
        if p.exists():
            return p
    raise SystemExit("[!] Could not find source root")


def main():
    if len(sys.argv) != 2:
        print("Usage: PYTHONPATH=$PWD python3 -m pipelines.run_rn_multilayer_hunt output/<target_dir>")
        sys.exit(1)

    repo = Path.cwd()
    target = Path(sys.argv[1]).resolve()

    rn_input = target / "rn_sensitive_execution_paths.json"
    scoped_dir = target / "scoped_joern_all"
    scoped_results = scoped_dir / "scoped_results.json"
    scoped_precise = scoped_dir / "scoped_joern_evidence_precise.json"
    fallback_out = target / "rn_source_text_fallback.json"
    flow_out = target / "rnfs_flow_reconstruction.json"
    final_out = target / "rn_final_multilayer_evidence.json"
    exploitability_out = target / "rn_exploitability_reasoning.json"
    final_with_exploitability = target / "rn_final_with_exploitability.json"
    cards_dir = target / "investigation_cards" / "rn_final_multilayer"
    exploitability_cards_dir = target / "investigation_cards" / "rn_final_with_exploitability"

    if not target.exists():
        raise SystemExit(f"[!] Target path not found: {target}")

    if not rn_input.exists():
        raise SystemExit(f"[!] Missing input: {rn_input}")

    print("[+] RN multilayer hunt started")
    print(f"[+] Target: {target}")
    print(f"[+] Input:  {rn_input}")

    candidates_data = load_json(rn_input)
    total_candidates = count_items(candidates_data)

    if total_candidates == 0:
        raise SystemExit("[!] No candidates found in rn_sensitive_execution_paths.json")

    source_root = pick_source_root(target)

    print(f"[+] Source root: {source_root}")
    print(f"[+] Total candidates: {total_candidates}")

    scoped_dir.mkdir(parents=True, exist_ok=True)

    existing_local_paths = list((scoped_dir / "local_paths").glob("*.json")) if (scoped_dir / "local_paths").exists() else []

    if scoped_results.exists() and len(existing_local_paths) >= total_candidates:
        print(f"[+] Reusing existing scoped Joern results: {scoped_results}")
        print(f"[+] Existing local path files: {len(existing_local_paths)}")
    else:
        run([
            "python3", "-m", "scoped_cpg.run_scoped_joern_for_candidates",
            source_root,
            rn_input,
            "0",
            total_candidates,
            scoped_dir
        ], repo)

    if not scoped_results.exists():
        raise SystemExit(f"[!] Missing scoped results: {scoped_results}")

    run([
        "python3", "-m", "joern_engine.extract_scoped_joern_evidence_precise",
        scoped_results,
        scoped_precise
    ], repo)

    if not scoped_precise.exists():
        raise SystemExit(f"[!] Missing precise Joern evidence: {scoped_precise}")

    run([
        "python3", "-m", "joern_engine.source_text_fallback",
        scoped_precise,
        fallback_out
    ], repo)

    run([
        "python3", "-m", "joern_engine.flow_reconstruction",
        fallback_out,
        flow_out
    ], repo)

    run([
        "python3", "-m", "joern_engine.merge_evidence_layers",
        scoped_precise,
        flow_out,
        final_out
    ], repo)

    if not final_out.exists():
        raise SystemExit(f"[!] Missing final evidence: {final_out}")

    run([
        "python3", "-m", "reasoning_agent.exploitability_engine",
        final_out,
        exploitability_out
    ], repo)

    if not exploitability_out.exists():
        raise SystemExit(f"[!] Missing exploitability reasoning: {exploitability_out}")

    run([
        "python3", "-m", "reasoning_agent.attach_exploitability_to_evidence",
        final_out,
        exploitability_out,
        final_with_exploitability
    ], repo)

    if not final_with_exploitability.exists():
        raise SystemExit(f"[!] Missing final with exploitability: {final_with_exploitability}")

    if cards_dir.exists():
        subprocess.run(["rm", "-rf", str(cards_dir)], check=True)

    run([
        "python3", "-m", "reports.rn_investigation_cards",
        final_out,
        cards_dir
    ], repo)

    if exploitability_cards_dir.exists():
        subprocess.run(["rm", "-rf", str(exploitability_cards_dir)], check=True)

    run([
        "python3", "-m", "reports.rn_investigation_cards",
        final_with_exploitability,
        exploitability_cards_dir
    ], repo)

    findings = load_json(final_out)
    findings_list = findings.get("findings", findings) if isinstance(findings, dict) else findings

    evidence_counter = Counter()
    for item in findings_list:
        status = (
            item.get("joern_evidence_status")
            or item.get("evidence_status")
            or item.get("evidence_layer")
            or item.get("status")
            or "unknown"
        )
        evidence_counter[status] += 1

    readme = cards_dir / "README.md"
    readme.parent.mkdir(parents=True, exist_ok=True)

    expected = {
        "cpg_local_proven": 7,
        "source_text_fallback": 12,
        "no_joern_evidence": 28,
    }

    actual = {
        "cpg_local_proven": evidence_counter.get("cpg_local_proven", 0),
        "source_text_fallback": evidence_counter.get("source_text_fallback", 0),
        "no_joern_evidence": evidence_counter.get("no_joern_evidence", 0),
    }

    if len(findings_list) == 47 and actual != expected:
        raise SystemExit(f"[!] RN evidence distribution regression: expected={expected} actual={actual}")

    readme.write_text(
        "# RN Final Multilayer Investigation Cards\n\n"
        "These are candidate investigation artifacts, not confirmed vulnerabilities.\n\n"
        "**Status:** candidate evidence only. No item is a confirmed vulnerability without validation.\n\n"
        f"- Total candidates: {len(findings_list)}\n"
        f"- cpg_local_proven: {evidence_counter.get('cpg_local_proven', 0)}\n"
        f"- source_text_fallback: {evidence_counter.get('source_text_fallback', 0)}\n"
        f"- no_joern_evidence: {evidence_counter.get('no_joern_evidence', 0)}\n\n"
        f"Final evidence file:\n\n`{final_out}`\n\n"
        f"Exploitability reasoning file:\n\n`{exploitability_out}`\n\n"
        f"Final evidence + exploitability file:\n\n`{final_with_exploitability}`\n\n"
        f"Cards path:\n\n`{cards_dir}`\n\n"
        f"Exploitability cards path:\n\n`{exploitability_cards_dir}`\n",
        encoding="utf-8"
    )

    print("\n========== RN MULTILAYER SUMMARY ==========")
    print(f"total candidates:      {len(findings_list)}")
    print(f"cpg_local_proven:      {evidence_counter.get('cpg_local_proven', 0)}")
    print(f"source_text_fallback:  {evidence_counter.get('source_text_fallback', 0)}")
    print(f"no_joern_evidence:     {evidence_counter.get('no_joern_evidence', 0)}")
    print(f"final evidence:        {final_out}")
    print(f"exploitability:        {exploitability_out}")
    print(f"final + exploitability:{final_with_exploitability}")
    print(f"cards output path:     {cards_dir}")
    print(f"exploitability cards:  {exploitability_cards_dir}")
    print("===========================================")


if __name__ == "__main__":
    main()
