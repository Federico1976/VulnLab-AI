#!/usr/bin/env python3
import json, re, sys, subprocess
from pathlib import Path

SKIP_OUTPUT_JSONS = {
    "universal_runtime_kg.json",
    "runtime_fingerprint_v2.json",
    "universal_apk_summary.json",
    "apk_characterization.json",
}

INTERESTING_EXTS = (
    "*.so", "*.dex", "*.arsc", "*.bin", "*.dat", "*.json", "*.txt"
)

STRONG_RUNTIME_PATTERNS = [
    r"^flutter/[a-z0-9_./-]+$",
    r"^plugins\.[a-z0-9_./-]+$",
    r"^plugins/flutter\.io/[a-z0-9_./-]+$",
    r"^dev\.flutter\.pigeon\.[A-Za-z0-9_.]+$",
    r"^io\.flutter\.plugins\.[A-Za-z0-9_./$;-]+$",
]

NOISE_PREFIXES = (
    "Landroid/", "Ljava/", "Lkotlin/", "Landroidx/",
    "[L", "(", ")", "\"", "'", "#", "$", "%", "&", "*",
    "+", ",", "-", ":", ";", "<", "=", ">", "@",
)

NOISE_CONTAINS = (
    "profileinstaller",
    "FlutterEngineConnectionRegistry",
    "FlutterActivityAndFragmentDelegate",
    "InputConnectionCompat",
    "EditorInfoCompat",
    "MotionEvent",
    "AccessibilityEvent",
    "runtime_fingerprint",
    "apk_characterization",
    "universal_runtime_kg",
    "output/",
)

CAPABILITY_KEYWORDS = {
    "file_storage": ["file", "files", "path", "storage", "cache", "external", "document"],
    "permissions": ["permission", "permissions", "camera", "location", "notifications"],
    "webview_url": ["webview", "url_launcher", "http", "https", "uri"],
    "preferences": ["shared_preferences", "SharedPreferences", "preferences"],
    "media_camera": ["image_picker", "camera", "gallery", "photo", "video"],
    "crypto": ["Cipher", "MessageDigest", "secure", "keystore"],
}

def strings_of_file(p: Path):
    try:
        r = subprocess.run(
            ["strings", "-a", "-n", "4", str(p)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
        return r.stdout.splitlines()
    except Exception:
        return []

def score_string(s: str):
    raw = s
    s = s.strip()

    if not s or len(s) < 4 or len(s) > 220:
        return None

    if any(s.startswith(x) for x in NOISE_PREFIXES):
        return None

    low = s.lower()
    if any(x.lower() in low for x in NOISE_CONTAINS):
        return None

    score = 0
    reasons = []

    for pat in STRONG_RUNTIME_PATTERNS:
        if re.search(pat, s):
            score += 50
            reasons.append("strong_runtime_pattern")

    if "dev.flutter.pigeon." in s:
        score += 35
        reasons.append("pigeon_api")

    if "plugins." in s or "plugins/" in s:
        score += 30
        reasons.append("plugin_namespace")

    if s.startswith("flutter/"):
        score += 30
        reasons.append("flutter_builtin_channel")

    if "/" in s or "." in s:
        score += 10
        reasons.append("structured_name")

    capabilities = []
    for family, keys in CAPABILITY_KEYWORDS.items():
        if any(k.lower() in low for k in keys):
            capabilities.append(family)
            score += 8

    if score < 18:
        return None

    if score >= 50:
        confidence = "high"
    elif score >= 30:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "value": s,
        "raw": raw[:240],
        "score": score,
        "confidence": confidence,
        "reasons": sorted(set(reasons)),
        "capability_families": sorted(set(capabilities)),
    }

def build(target_dir):
    target = Path(target_dir).resolve()
    artifacts = []

    for pat in INTERESTING_EXTS:
        for f in target.rglob(pat):
            if f.name in SKIP_OUTPUT_JSONS:
                continue

            rel = str(f.relative_to(target))
            for s in strings_of_file(f):
                hit = score_string(s)
                if hit:
                    hit["file"] = rel
                    artifacts.append(hit)

    uniq = {}
    for a in artifacts:
        key = (a["value"], a["file"])
        if key not in uniq or a["score"] > uniq[key]["score"]:
            uniq[key] = a

    artifacts = sorted(
        uniq.values(),
        key=lambda x: (-x["score"], x["value"], x["file"])
    )

    out = {
        "target": str(target),
        "total_artifacts": len(artifacts),
        "summary": {
            "by_confidence": {
                c: sum(1 for a in artifacts if a["confidence"] == c)
                for c in ["high", "medium", "low"]
            },
            "capability_families": sorted(set(
                fam for a in artifacts for fam in a["capability_families"]
            )),
        },
        "artifacts": artifacts,
    }

    out_path = target / "universal_runtime_artifacts.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(json.dumps(out["summary"], indent=2))
    print(f"[+] wrote {out_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: PYTHONPATH=$PWD python3 -m runtime_artifacts.extract_runtime_artifacts output/<target_dir>")
        sys.exit(1)
    build(sys.argv[1])
