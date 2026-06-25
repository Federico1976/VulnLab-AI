import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd):
    p = subprocess.run(cmd, text=True)
    return p.returncode


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    if len(sys.argv) != 6:
        print("Usage: python3 -m scoped_cpg.run_scoped_joern_for_candidates <source_root> <candidates.json> <start_idx> <end_idx_exclusive> <out_dir>")
        sys.exit(1)

    source_root = Path(sys.argv[1])
    candidates_json = Path(sys.argv[2])
    start = int(sys.argv[3])
    end = int(sys.argv[4])
    out_dir = Path(sys.argv[5])

    candidates = json.loads(candidates_json.read_text(encoding="utf-8"))
    selected = candidates[start:end]

    out_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    summary = []

    for offset, candidate in enumerate(selected):
        idx = start + offset
        slug = f"c{idx+1:03d}_{candidate.get('class','unknown').split('.')[-1].lower()}"

        scoped_sources = out_dir / "scoped_sources" / slug
        scoped_cpg = out_dir / "scoped_cpg" / slug / "cpg.bin"
        candidate_one = out_dir / "candidate_json" / f"{slug}.json"
        local_paths = out_dir / "local_paths" / f"{slug}.json"

        scoped_sources.parent.mkdir(parents=True, exist_ok=True)
        scoped_cpg.parent.mkdir(parents=True, exist_ok=True)
        candidate_one.parent.mkdir(parents=True, exist_ok=True)
        local_paths.parent.mkdir(parents=True, exist_ok=True)

        if scoped_sources.exists():
            shutil.rmtree(scoped_sources)

        write_json(candidate_one, [candidate])

        print(f"\n=== [{idx+1}/{len(candidates)}] {candidate.get('class')} ===")

        rc_scope = run([
            "python3", "-m", "scoped_cpg.build_scoped_sources",
            str(source_root),
            str(candidates_json),
            str(idx),
            str(scoped_sources),
        ])

        rc_parse = 1
        rc_reconstruct = 1

        if rc_scope == 0:
            rc_parse = run([
                "joern-parse",
                str(scoped_sources),
                "--output",
                str(scoped_cpg),
            ])

        if rc_parse == 0 and scoped_cpg.exists():
            rc_reconstruct = run([
                "python3", "-m", "joern_engine.local_path_reconstruct",
                str(scoped_cpg),
                str(candidate_one),
                str(local_paths),
            ])

        result = None
        if rc_reconstruct == 0 and local_paths.exists():
            try:
                arr = json.loads(local_paths.read_text(encoding="utf-8"))
                if arr:
                    result = arr[0]
                    all_results.append(result)
            except Exception:
                result = None

        method_count = result.get("joern_local_path", {}).get("method_count", 0) if result else 0
        flow_count = 0
        strategies = []

        if result:
            for m in result.get("joern_local_path", {}).get("methods", []):
                strategies.append(m.get("resolution_strategy"))
                flow_count += len(
                    m.get("local_path_reconstruction", {}).get("flow_candidates", [])
                )

        summary.append({
            "index": idx,
            "class": candidate.get("class"),
            "signature": candidate.get("signature"),
            "rc_scope": rc_scope,
            "rc_parse": rc_parse,
            "rc_reconstruct": rc_reconstruct,
            "method_count": method_count,
            "flow_count": flow_count,
            "strategies": strategies,
            "scoped_sources": str(scoped_sources),
            "scoped_cpg": str(scoped_cpg),
            "local_paths": str(local_paths),
        })

        print(f"[+] method_count={method_count} flow_count={flow_count} strategies={strategies}")

    write_json(out_dir / "scoped_results.json", all_results)
    write_json(out_dir / "scoped_summary.json", summary)

    print("\n[+] Done")
    print(f"[+] results: {out_dir / 'scoped_results.json'}")
    print(f"[+] summary: {out_dir / 'scoped_summary.json'}")


if __name__ == "__main__":
    main()
