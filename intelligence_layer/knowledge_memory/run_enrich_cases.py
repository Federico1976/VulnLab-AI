import json
import sys
from pathlib import Path

from intelligence_layer.knowledge_memory.matcher import KnowledgeMemoryMatcher


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m intelligence_layer.knowledge_memory.run_enrich_cases <research_cases.json> <output.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(input_path.read_text())
    matcher = KnowledgeMemoryMatcher()

    cases = data.get("research_cases", [])
    enriched_cases = [matcher.enrich_case(c) for c in cases]

    data["research_cases"] = enriched_cases
    data["summary"]["knowledge_memory_enriched"] = len(enriched_cases)

    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    for c in enriched_cases:
        print(c["case_id"], "knowledge_matches=", c["knowledge_memory"]["total_matches"])


if __name__ == "__main__":
    main()
