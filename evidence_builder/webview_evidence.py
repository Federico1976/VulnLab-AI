import json
from pathlib import Path
from core.manifest_utils import load_manifest, find_component_by_class, is_externally_reachable

def class_from_method(method_fullname: str) -> str:
    # esempio: com.pkg.Activity.onCreate:void(...)
    left = method_fullname.split(":", 1)[0]
    return left.rsplit(".", 1)[0]

def build(output_dir, detector_json="webview_intent_loadurl.json"):
    output_dir = Path(output_dir)
    manifest = load_manifest(output_dir)
    detector = json.loads((output_dir / detector_json).read_text())

    evidences = []

    for f in detector.get("findings", []):
        method = f.get("method", "")
        class_name = class_from_method(method)
        component = find_component_by_class(manifest, class_name)
        reachable = is_externally_reachable(component)

        severity = "high" if reachable else "medium"
        status = "externally_reachable_candidate" if reachable else "internal_chain_candidate"

        evidence = {
            "finding_id": f.get("id"),
            "title": f.get("title"),
            "category": f.get("category"),
            "severity": severity,
            "confidence": f.get("confidence", "medium"),
            "status": status,
            "class": class_name,
            "method": method,
            "component": component,
            "externally_reachable": reachable,
            "sources": f.get("sources", []),
            "sinks": f.get("sinks", []),
            "risk_notes": [
                "Source-to-sink flow detected statically.",
                "Risk depends on component reachability and caller controllability.",
                "Dynamic validation is required before disclosure."
            ],
            "next_tests": [
                "Correlate source with exported component, deeplink, provider, receiver, service, or JS bridge.",
                "Extract exact code window for source and sink.",
                "Check validation, allowlist, scheme filtering, auth checks, and caller restrictions.",
                "Run dynamic test only within authorized bounty scope."
            ]
        }
        evidences.append(evidence)

    out = output_dir / "evidence_webview.json"
    out.write_text(json.dumps(evidences, indent=2, ensure_ascii=False))
    print(json.dumps(evidences, indent=2, ensure_ascii=False))
    return evidences

if __name__ == "__main__":
    import sys
    build(sys.argv[1])
