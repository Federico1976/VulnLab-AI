#!/usr/bin/env python3
"""
import_bughunter.py
====================
Importa i pattern da Claude-BugHunter (docs/disclosed-reports/*.md e
skills/*/SKILL.md) nella Knowledge Base (Qdrant), spezzando ogni file
nei suoi sotto-pattern (### sections) invece di indicizzarlo come blob.

Uso:
    python3 import_bughunter.py --repo-path ~/apk_agent/external_sources/Claude-BugHunter --dry-run
    python3 import_bughunter.py --repo-path ~/apk_agent/external_sources/Claude-BugHunter
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "knowledge_base"))
from knowledge_base import add_document  # riusa la KB già costruita


def extract_frontmatter(text: str) -> tuple[dict, str]:
    """Estrae il frontmatter YAML semplice (key: value) da una SKILL.md.
    Ritorna (metadata_dict, resto_del_testo)."""
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    fm_raw, body = parts[1], parts[2]
    metadata = {}
    for line in fm_raw.strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip()
    return metadata, body.strip()


def category_from_filename(path: Path) -> str:
    """hunt-idor.md -> idor ; hunt-sqli -> sqli ; bb-methodology -> bb-methodology"""
    stem = path.stem  # senza estensione
    stem = re.sub(r"^hunt-", "", stem)
    return stem


def split_by_h2(body: str) -> list[tuple[str, str]]:
    """Spezza il body in sezioni di livello 2 (## Titolo).
    Ritorna lista di (titolo_sezione, contenuto_sezione)."""
    pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    sections = []
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        sections.append((title, content))
    return sections


def split_by_h3(section_content: str) -> list[tuple[str, str]]:
    """Spezza una sezione di livello 2 nei suoi sotto-pattern di livello 3
    (### Titolo). Se non ci sono ###, ritorna l'intera sezione come unico
    blocco con titolo vuoto."""
    pattern = re.compile(r"^###\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(section_content))
    if not matches:
        return [("", section_content.strip())] if section_content.strip() else []

    blocks = []
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section_content)
        content = section_content[start:end].strip()
        blocks.append((title, content))
    return blocks


def is_anti_pattern_section(section_title: str) -> bool:
    return "anti-pattern" in section_title.lower() or "fp trap" in section_title.lower()


def process_file(path: Path, source_tag: str, dry_run: bool) -> int:
    """Processa un singolo file .md, ritorna il numero di documenti estratti."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    metadata, body = extract_frontmatter(raw)
    category = category_from_filename(path)

    count = 0
    sections = split_by_h2(body)

    if not sections:
        # Nessuna sezione ## trovata: indicizza il documento intero come fallback
        text = body.strip()
        if text:
            count += 1
            if dry_run:
                print(f"  [DRY] {path.name} :: (intero file) :: {len(text)} char")
            else:
                add_document(
                    text=text[:4000],  # taglio di sicurezza per testi enormi
                    source=source_tag,
                    category=category,
                    cwe=None,
                    extra_metadata={"section": "full_file", "file": str(path.relative_to(path.parents[2]))},
                )
        return count

    for section_title, section_content in sections:
        blocks = split_by_h3(section_content)
        anti = is_anti_pattern_section(section_title)

        for block_title, block_content in blocks:
            if not block_content or len(block_content) < 30:
                continue  # salta blocchi troppo corti per essere utili

            text = f"{block_title}\n{block_content}" if block_title else block_content
            count += 1

            if dry_run:
                tag = "ANTI-PATTERN" if anti else "pattern"
                print(f"  [DRY] {path.name} :: [{section_title}] {block_title or '(senza titolo)'} ({tag}, {len(text)} char)")
            else:
                add_document(
                    text=text[:4000],
                    source=source_tag,
                    category=category,
                    cwe=None,
                    extra_metadata={
                        "section": section_title,
                        "subtitle": block_title,
                        "is_anti_pattern": anti,
                        "file": str(path.name),
                    },
                )

    return count


def main():
    parser = argparse.ArgumentParser(description="Importa Claude-BugHunter nella Knowledge Base")
    parser.add_argument("--repo-path", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Mostra cosa verrebbe importato senza scrivere su Qdrant")
    args = parser.parse_args()

    repo = args.repo_path.resolve()
    if not repo.exists():
        print(f"[!] Path non trovato: {repo}", file=sys.stderr)
        sys.exit(1)

    total = 0

    # 1. docs/disclosed-reports/*.md
    disclosed_dir = repo / "docs" / "disclosed-reports"
    if disclosed_dir.exists():
        print(f"\n=== docs/disclosed-reports ({len(list(disclosed_dir.glob('*.md')))} file) ===")
        for md_file in sorted(disclosed_dir.glob("*.md")):
            n = process_file(md_file, source_tag="claude-bughunter-disclosed-reports", dry_run=args.dry_run)
            print(f"[{md_file.name}] -> {n} documenti")
            total += n

    # 2. skills/*/SKILL.md
    skills_dir = repo / "skills"
    if skills_dir.exists():
        skill_files = sorted(skills_dir.glob("*/SKILL.md"))
        print(f"\n=== skills/*/SKILL.md ({len(skill_files)} file) ===")
        for skill_file in skill_files:
            n = process_file(skill_file, source_tag="claude-bughunter-skills", dry_run=args.dry_run)
            print(f"[{skill_file.parent.name}] -> {n} documenti")
            total += n

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Totale documenti {'identificati' if args.dry_run else 'importati'}: {total}")


if __name__ == "__main__":
    main()
