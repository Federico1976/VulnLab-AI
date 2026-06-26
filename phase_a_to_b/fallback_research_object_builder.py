#!/usr/bin/env python3
import json
import sys
import hashlib
from pathlib import Path


def sid(prefix, payload):
    raw = json.dumps(payload, sort_keys=True, default=str)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:10]}"


def load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return {}


def build_research_objects(out_dir):
    out_dir = Path(out_dir)

    characterization = load_json(out_dir / "apk_characterization.json")
    summary = load_json(out_dir / "universal_apk_summary.json")

    apk_id = characterization.get("sha256") or characterization.get("package") or out_dir.name
    package = characterization.get("package")
    label = characterization.get("label")
    features = characterization.get("features", {})
    recommended = characterization.get("recommended_pipelines") or summary.get("recommended") or []

    objects = []

    if "kotlin_compose_static_hunt" in recommended or "jetpack_compose" in features:
        ro = {
            "object_id": sid("RO", {"apk": apk_id, "type": "kotlin_compose_surface"}),
            "apk_id": apk_id,
            "package": package,
            "label": label,
            "runtime_family": "android_native_kotlin_compose",
            "object_type": "ui_runtime_surface",
            "primary_capability": "ui_to_logic_reachability",
            "normalized_candidates": [
                {
                    "candidate_id": "APK-KOTLIN-COMPOSE-SURFACE-001",
                    "apk_id": apk_id,
                    "runtime_family": "android_native_kotlin_compose",
                    "evidence_type": "apk_characterization",
                    "reachability_result": "candidate",
                    "entrypoints": [],
                    "sources": ["Compose UI interaction", "Android lifecycle"],
                    "sinks": [],
                    "confidence_score": 0.35,
                    "raw_title": "Kotlin/Compose runtime surface",
                    "raw_category": "kotlin_compose",
                    "raw": {
                        "features": features,
                        "recommended_pipelines": recommended,
                        "risk": "Compose UI may invoke application logic, file/network flows, or external intents. Requires static proof.",
                        "next_tests": [
                            "Identify composable event handlers and ViewModel actions.",
                            "Trace UI actions into file, network, IPC, WebView, storage, or crypto sinks.",
                            "Recover Activity/navigation entrypoints."
                        ],
                    }
                }
            ],
            "merged_entrypoints": [],
            "merged_sources": ["Compose UI interaction", "Android lifecycle"],
            "merged_sinks": [],
            "evidence_sources": ["apk_characterization.json", "universal_apk_summary.json"],
            "qualification": {
                "status": "fallback_research_object",
                "reason": "No specialized research object builder produced output for this runtime yet."
            }
        }
        objects.append(ro)

    if "fileprovider_hunt" in recommended:
        ro = {
            "object_id": sid("RO", {"apk": apk_id, "type": "fileprovider_surface"}),
            "apk_id": apk_id,
            "package": package,
            "label": label,
            "runtime_family": "android_native",
            "object_type": "fileprovider_surface",
            "primary_capability": "file_uri_sharing",
            "normalized_candidates": [
                {
                    "candidate_id": "APK-FILEPROVIDER-SURFACE-001",
                    "apk_id": apk_id,
                    "runtime_family": "android_native",
                    "evidence_type": "apk_characterization",
                    "reachability_result": "candidate",
                    "entrypoints": [],
                    "sources": ["Intent input", "URI/path input", "user-selected file"],
                    "sinks": ["FileProvider URI exposure", "content URI grant", "external intent share"],
                    "confidence_score": 0.45,
                    "raw_title": "FileProvider/file sharing surface",
                    "raw_category": "fileprovider",
                    "raw": {
                        "features": features,
                        "recommended_pipelines": recommended,
                        "risk": "FileProvider/file sharing surfaces may expose content URIs or file paths if attacker-influenced.",
                        "next_tests": [
                            "Inspect AndroidManifest provider entries.",
                            "Inspect file_paths XML configuration.",
                            "Trace URI/path source into FileProvider/getUriForFile/share intents.",
                            "Check grant flags and target app boundary."
                        ],
                        "execution_path": {
                            "source": {
                                "type": "candidate",
                                "name": "URI/path/user-selected file",
                            },
                            "source_argument_usage": {
                                "uri_or_path": [
                                    {
                                        "line_in_method": None,
                                        "code": "fallback candidate: URI/path source must be recovered by static analysis"
                                    }
                                ]
                            },
                            "sink_lines": [
                                {
                                    "line_in_method": None,
                                    "pattern": "FileProvider/content URI/share intent",
                                    "code": "fallback candidate: FileProvider sink must be recovered by static analysis"
                                }
                            ]
                        }
                    }
                }
            ],
            "merged_entrypoints": [],
            "merged_sources": ["Intent input", "URI/path input", "user-selected file"],
            "merged_sinks": ["FileProvider URI exposure", "content URI grant", "external intent share"],
            "evidence_sources": ["apk_characterization.json", "universal_apk_summary.json"],
            "qualification": {
                "status": "fallback_research_object",
                "reason": "Recommended fileprovider_hunt but no specialized research object builder output exists yet."
            }
        }
        objects.append(ro)

    return {
        "apk_id": apk_id,
        "package": package,
        "label": label,
        "raw_candidates": 0,
        "normalized_candidates": sum(len(o.get("normalized_candidates", [])) for o in objects),
        "research_objects": objects,
        "summary": {
            "fallback_builder": True,
            "research_object_count": len(objects),
            "recommended_pipelines": recommended,
            "features": features,
        }
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_a_to_b.fallback_research_object_builder <phase_a_out_dir> <out.json>")
        sys.exit(1)

    out_dir = Path(sys.argv[1])
    out_json = Path(sys.argv[2])

    data = build_research_objects(out_dir)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "research_objects": len(data["research_objects"]),
        "output": str(out_json),
    }, indent=2))


if __name__ == "__main__":
    main()
