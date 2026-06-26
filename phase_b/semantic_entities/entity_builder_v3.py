#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


def run(cmd):
    print("[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.semantic_entities.entity_builder_v3 <research_objects.json> <semantic_entities.json>")
        sys.exit(1)

    ro = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)

    run(["python3", "-m", "phase_b.semantic_entities.entity_builder", str(ro), str(out)])
    run(["python3", "-m", "phase_b.semantic_entities.research_object_semantic_expander_v2", str(ro), str(out), str(out)])

    print(f"[OK] semantic_entity_builder_v3 -> {out}")


if __name__ == "__main__":
    main()
