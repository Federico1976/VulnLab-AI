import json
import sys
from pathlib import Path

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m reports.rn_index_markdown <index.json> <output.md>")
        sys.exit(1)

    index = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    lines = []
    lines.append("# RN Sensitive Candidate Queue")
    lines.append("")
    lines.append("| Rank | Score | Confidence | Class | Signature | Card |")
    lines.append("|---:|---:|---:|---|---|---|")

    for item in index:
        card = item["card"]
        lines.append(
            f"| {item['rank']} "
            f"| {item['queue_score']} "
            f"| {item['path_confidence']} "
            f"| `{item['class']}` "
            f"| `{item['signature']}` "
            f"| [{Path(card).name}]({Path(card).name}) |"
        )

    Path(sys.argv[2]).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[+] written {sys.argv[2]}")

if __name__ == "__main__":
    main()
