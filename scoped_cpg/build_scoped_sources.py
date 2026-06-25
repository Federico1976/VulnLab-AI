import json
import re
import shutil
import sys
from pathlib import Path


CLASS_RE = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+)\b')


def clean_file_path(p):
    s = str(p or "")
    marker = "output/"
    first = s.find(marker)
    if first == -1:
        return Path(s)
    second = s.find(marker, first + len(marker))
    if second != -1:
        s = s[second:]
    else:
        s = s[first:]
    return Path(s)


def class_to_relpath(cls):
    return Path(*cls.split(".")).with_suffix(".java")


def find_source_file(root, cls, candidate_file=None):
    root = Path(root)

    if candidate_file:
        p = clean_file_path(candidate_file)
        if p.exists():
            return p
        full = Path.cwd() / p
        if full.exists():
            return full

    direct = root / class_to_relpath(cls)
    if direct.exists():
        return direct

    short = cls.split(".")[-1] + ".java"
    matches = list(root.rglob(short))
    if matches:
        return matches[0]

    return None


def extract_referenced_classes(text):
    refs = set()

    for m in CLASS_RE.finditer(text):
        v = m.group(1)

        if v.startswith(("android.", "java.", "javax.", "kotlin.", "org.jetbrains.")):
            continue

        if "." in v and not v.endswith(".java"):
            refs.add(v)

    return refs


def copy_file(src, source_root, dest_root):
    src = Path(src)
    source_root = Path(source_root)
    dest_root = Path(dest_root)

    try:
        rel = src.relative_to(source_root)
    except ValueError:
        rel = Path(src.name)

    dst = dest_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return str(dst)


def main():
    if len(sys.argv) != 5:
        print("Usage: python3 -m scoped_cpg.build_scoped_sources <source_root> <candidate.json> <candidate_index> <out_dir>")
        sys.exit(1)

    source_root = Path(sys.argv[1])
    candidates = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    idx = int(sys.argv[3])
    out_dir = Path(sys.argv[4])

    c = candidates[idx]
    cls = c.get("class", "")
    cand_file = c.get("file", "")

    out_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    missing = []

    src = find_source_file(source_root, cls, cand_file)

    if not src:
        missing.append(cls)
    else:
        copied.append(copy_file(src, source_root, out_dir))
        text = Path(src).read_text(encoding="utf-8", errors="ignore")

        refs = extract_referenced_classes(text)

        for ref in sorted(refs):
            ref_file = find_source_file(source_root, ref)
            if ref_file:
                copied.append(copy_file(ref_file, source_root, out_dir))

    manifest = {
        "candidate_index": idx,
        "class": cls,
        "signature": c.get("signature"),
        "source_file": str(src) if src else None,
        "copied_count": len(set(copied)),
        "copied_files": sorted(set(copied)),
        "missing": missing,
    }

    (out_dir / "scope_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[+] candidate_index={idx}")
    print(f"[+] class={cls}")
    print(f"[+] source_file={src}")
    print(f"[+] copied_files={len(set(copied))}")
    print(f"[+] scope={out_dir}")


if __name__ == "__main__":
    main()
