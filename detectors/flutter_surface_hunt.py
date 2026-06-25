import json
import sys
import zipfile
from pathlib import Path


FLUTTER_RUNTIME_PATTERNS = [
    "flutter_assets",
    "libflutter.so",
    "libapp.so",
    "io/flutter",
    "FlutterActivity",
    "FlutterFragmentActivity",
    "FlutterEngine",
    "DartExecutor",
    "GeneratedPluginRegistrant",
]

CHANNEL_PATTERNS = [
    "MethodChannel",
    "EventChannel",
    "BasicMessageChannel",
    "BinaryMessenger",
    "setMethodCallHandler",
]

SENSITIVE_PLUGIN_HINTS = [
    "image_picker",
    "fluttertoast",
    "firebase",
    "shared_preferences",
    "url_launcher",
    "webview_flutter",
    "path_provider",
    "permission_handler",
    "camera",
    "file_picker",
    "in_app_purchase",
    "google_sign_in",
    "flutter_secure_storage",
]


def add_finding(findings, **kw):
    findings.append({
        "id": f"APK-FLUTTER-SURFACE-{len(findings)+1:03d}",
        "title": kw.get("title", "Flutter runtime surface"),
        "category": "flutter_surface",
        "status": "candidate_not_confirmed",
        "runtime": "flutter",
        "evidence_type": kw.get("evidence_type"),
        "file": kw.get("file"),
        "pattern": kw.get("pattern"),
        "detail": kw.get("detail"),
        "candidate_score": kw.get("candidate_score", 50),
        "priority": kw.get("priority", "medium_candidate_priority"),
        "impact_hypothesis": kw.get(
            "impact_hypothesis",
            "Flutter runtime or plugin surface may bridge Dart-controlled input into Android native APIs. Impact depends on MethodChannel/EventChannel reachability, plugin registration, argument control, and native sink behavior."
        ),
        "required_next_analysis": [
            "Identify FlutterActivity/FlutterEngine entrypoint.",
            "Identify MethodChannel/EventChannel/BasicMessageChannel usage.",
            "Map plugins registered through GeneratedPluginRegistrant.",
            "Trace MethodCall arguments to Android native APIs.",
            "Validate dynamically with benign Flutter channel instrumentation before any security claim."
        ],
        "validation_guardrail": "Do not report as vulnerability without Dart-to-native reachability and dynamic validation."
    })


def scan_zip(apk: Path):
    findings = []
    try:
        with zipfile.ZipFile(apk) as z:
            names = z.namelist()
    except Exception as e:
        add_finding(findings, title="APK read failed", evidence_type="error", file=str(apk), detail=str(e), candidate_score=0, priority="informational")
        return findings

    for name in names:
        low = name.lower()

        for pat in FLUTTER_RUNTIME_PATTERNS:
            if pat.lower() in low:
                # Avoid one finding per asset file. Only top-level runtime markers are high signal.
                if pat == "flutter_assets" and name.count("/") > 2:
                    continue

                add_finding(
                    findings,
                    title="Flutter runtime artifact",
                    evidence_type="apk_zip_entry",
                    file=str(apk),
                    pattern=pat,
                    detail=name,
                    candidate_score=90 if pat in {"libflutter.so", "libapp.so"} else 70,
                    priority="high_candidate_priority" if pat in {"libflutter.so", "libapp.so"} else "medium_candidate_priority",
                )

        for plugin in SENSITIVE_PLUGIN_HINTS:
            if plugin.lower() in low:
                add_finding(
                    findings,
                    title="Flutter plugin or asset hint",
                    evidence_type="apk_zip_entry",
                    file=str(apk),
                    pattern=plugin,
                    detail=name,
                    candidate_score=60,
                    priority="medium_candidate_priority",
                )

    return findings


def scan_sources(target_dir: Path):
    findings = []
    src = target_dir / "code" / "decompiled" / "sources"
    if not src.exists():
        return findings

    for f in src.rglob("*.java"):
        try:
            lines = f.read_text(errors="ignore").splitlines()
        except Exception:
            continue

        for i, line in enumerate(lines, start=1):
            for pat in FLUTTER_RUNTIME_PATTERNS + CHANNEL_PATTERNS:
                if pat in line:
                    add_finding(
                        findings,
                        title="Flutter Android embedding or channel evidence",
                        evidence_type="source_text",
                        file=str(f),
                        pattern=pat,
                        detail={"line": i, "code": line.strip()[:500]},
                        candidate_score=90 if pat in CHANNEL_PATTERNS else 70,
                        priority="high_candidate_priority" if pat in CHANNEL_PATTERNS else "medium_candidate_priority",
                    )

    return findings


def main():
    if len(sys.argv) != 4:
        print("Usage: PYTHONPATH=$PWD python3 -m detectors.flutter_surface_hunt <target_dir> <apk_or_apk_dir> <out_json>")
        sys.exit(1)

    target_dir = Path(sys.argv[1])
    apk_input = Path(sys.argv[2])
    out_json = Path(sys.argv[3])

    findings = []

    apks = sorted(apk_input.glob("*.apk")) if apk_input.is_dir() else [apk_input]
    for apk in apks:
        findings.extend(scan_zip(apk))

    findings.extend(scan_sources(target_dir))

    # dedupe
    seen = set()
    deduped = []
    for f in findings:
        key = json.dumps({k: f.get(k) for k in ["evidence_type", "file", "pattern", "detail"]}, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)

    out_json.write_text(json.dumps(deduped, indent=2), encoding="utf-8")

    print(f"[+] written {out_json}")
    print(f"[+] flutter findings={len(deduped)}")
    for f in deduped[:20]:
        print(f"- {f['candidate_score']} {f['priority']} {f['pattern']} {f['detail']}")


if __name__ == "__main__":
    main()
