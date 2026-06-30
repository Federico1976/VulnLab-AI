import json
import sys
from pathlib import Path


def main() -> None:
    registry_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("phase_c/knowledge_sources/source_registry.json")

    with registry_path.open("r", encoding="utf-8") as f:
        reg = json.load(f)

    sources = reg.get("sources", [])

    report = {
        "status": "ok",
        "schema": "vulnlab.knowledge_source_registry_report.v1",
        "sources_total": len(sources),
        "enabled_sources": sum(1 for s in sources if s.get("enabled")),
        "disabled_sources": sum(1 for s in sources if not s.get("enabled")),
        "source_types": sorted(set(s.get("type", "unknown") for s in sources)),
        "guardrail": reg.get("guardrail", {})
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
