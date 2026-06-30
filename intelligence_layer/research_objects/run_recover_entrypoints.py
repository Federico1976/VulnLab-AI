import json
import sys
from pathlib import Path

from intelligence_layer.research_objects.entrypoint_recovery import ResearchObjectEntrypointRecovery
from intelligence_layer.research_objects.qualifier import CandidateQualificationEngine
from intelligence_layer.research_objects.entrypoint_quality import EntrypointQualityScorer
from intelligence_layer.research_objects.bridge_method_recovery import BridgeMethodRecovery


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m intelligence_layer.research_objects.run_recover_entrypoints <research_objects.json> <output.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(input_path.read_text())
    recovery = ResearchObjectEntrypointRecovery()
    qualifier = CandidateQualificationEngine()
    quality = EntrypointQualityScorer()
    bridge_recovery = BridgeMethodRecovery()

    recovered_objects = []

    for obj in data.get("research_objects", []):
        obj = recovery.recover(obj)
        obj = bridge_recovery.recover(obj)
        obj["entrypoint_quality"] = quality.score_entrypoints(obj.get("merged_entrypoints", []))
        obj["merged_entrypoints"] = obj["entrypoint_quality"]["real_entrypoints"]
        obj["qualification"] = qualifier.qualify(obj)
        recovered_objects.append(obj)

    data["research_objects"] = recovered_objects
    data["summary_after_recovery"] = {
        "total_research_objects": len(recovered_objects),
        "with_entrypoints": sum(1 for o in recovered_objects if o.get("merged_entrypoints")),
        "by_qualification": {},
        "by_route": {}
    }

    for obj in recovered_objects:
        q = obj["qualification"]
        data["summary_after_recovery"]["by_qualification"][q["qualification_level"]] = data["summary_after_recovery"]["by_qualification"].get(q["qualification_level"], 0) + 1
        data["summary_after_recovery"]["by_route"][q["route"]] = data["summary_after_recovery"]["by_route"].get(q["route"], 0) + 1

    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(json.dumps(data["summary_after_recovery"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
