import json
import sys
from pathlib import Path

from intelligence_layer.evidence_case.normalizer import EvidenceCaseNormalizer
from intelligence_layer.research_objects.merger import ResearchObjectMerger
from intelligence_layer.research_objects.qualifier import CandidateQualificationEngine


def load_candidates(path: Path):
    data = json.loads(path.read_text())

    if isinstance(data, list):
        return data

    for key in ["candidates", "findings", "evidence", "items", "results", "raw_candidates"]:
        if isinstance(data.get(key), list):
            return data[key]

    return [data]


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 -m intelligence_layer.research_objects.run_research_objects <apk_id> <raw_candidates.json> <output.json>")
        sys.exit(1)

    apk_id = sys.argv[1]
    raw_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_candidates = load_candidates(raw_path)
    normalizer = EvidenceCaseNormalizer()
    normalized = [normalizer.normalize(c, apk_id=apk_id) for c in raw_candidates]

    objects = ResearchObjectMerger().merge(normalized)
    qualifier = CandidateQualificationEngine()

    for obj in objects:
        obj["qualification"] = qualifier.qualify(obj)

    output = {
        "apk_id": apk_id,
        "raw_candidates": len(raw_candidates),
        "normalized_candidates": len(normalized),
        "research_objects": objects,
        "summary": {
            "total_research_objects": len(objects),
            "by_qualification": {},
            "by_route": {},
            "by_capability": {}
        }
    }

    for obj in objects:
        q = obj["qualification"]
        output["summary"]["by_qualification"][q["qualification_level"]] = output["summary"]["by_qualification"].get(q["qualification_level"], 0) + 1
        output["summary"]["by_route"][q["route"]] = output["summary"]["by_route"].get(q["route"], 0) + 1
        cap = obj.get("primary_capability", "unknown")
        output["summary"]["by_capability"][cap] = output["summary"]["by_capability"].get(cap, 0) + 1

    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(json.dumps(output["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
