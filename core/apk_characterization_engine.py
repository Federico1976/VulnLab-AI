#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from pathlib import Path
from collections import defaultdict


def run(cmd):
    try:
        p = subprocess.run(cmd, text=True, capture_output=True, check=False)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"missing binary: {cmd[0]}"


def write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_rules():
    p = Path("knowledge_base/apk_framework_indicators.json")
    return json.loads(p.read_text(encoding="utf-8"))


def contains_any(blob, needles):
    blob_l = blob.lower()
    hits = []
    for n in needles:
        token = n.replace("*", "").lower()
        if token and token in blob_l:
            hits.append(n)
    return hits


def parse_badging(text):
    out = {}

    m = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", text)
    if m:
        out["package"] = m.group(1)
        out["version_code"] = m.group(2)
        out["version_name"] = m.group(3)

    m = re.search(r"sdkVersion:'([^']+)'", text)
    if m:
        out["min_sdk"] = m.group(1)

    m = re.search(r"targetSdkVersion:'([^']+)'", text)
    if m:
        out["target_sdk"] = m.group(1)

    m = re.search(r"application-label:'([^']+)'", text)
    if m:
        out["label"] = m.group(1)

    m = re.search(r"launchable-activity: name='([^']+)'", text)
    if m:
        out["launchable_activity"] = m.group(1)

    perms = re.findall(r"uses-permission: name='([^']+)'", text)
    out["permissions"] = sorted(set(perms))

    native = re.search(r"native-code: (.+)", text)
    if native:
        out["native_abis"] = re.findall(r"'([^']+)'", native.group(1))
    else:
        out["native_abis"] = []

    return out


def extract_manifest_surfaces(manifest):
    components = []
    deeplinks = {
        "schemes": set(),
        "hosts": set(),
        "paths": set()
    }

    current = None
    in_intent_filter = False

    for line in manifest.splitlines():
        stripped = line.strip()

        m = re.match(r"E: (activity|activity-alias|service|receiver|provider)\b", stripped)
        if m:
            if current:
                components.append(current)
            current = {
                "type": m.group(1),
                "name": None,
                "exported": None,
                "permission": None,
                "has_intent_filter": False,
                "actions": [],
                "categories": [],
                "data": []
            }
            in_intent_filter = False
            continue

        if current and stripped.startswith("E: intent-filter"):
            current["has_intent_filter"] = True
            in_intent_filter = True
            continue

        if current and stripped.startswith("E: ") and not stripped.startswith(("E: action", "E: category", "E: data")):
            in_intent_filter = False

        if current and "android:name" in stripped and "Raw:" in stripped:
            m = re.search(r'Raw: "([^"]+)"', stripped)
            if m and current["name"] is None:
                current["name"] = m.group(1)

        if current and "android:permission" in stripped and "Raw:" in stripped:
            m = re.search(r'Raw: "([^"]+)"', stripped)
            if m:
                current["permission"] = m.group(1)

        if current and "android:exported" in stripped:
            if "0xffffffff" in stripped:
                current["exported"] = True
            elif "0x0" in stripped:
                current["exported"] = False

        if current and in_intent_filter and "android:name" in stripped and "Raw:" in stripped:
            m = re.search(r'Raw: "([^"]+)"', stripped)
            if m:
                raw = m.group(1)
                if "action" in stripped.lower():
                    current["actions"].append(raw)
                elif "category" in stripped.lower():
                    current["categories"].append(raw)

        if current and in_intent_filter and "android:scheme" in stripped and "Raw:" in stripped:
            m = re.search(r'Raw: "([^"]+)"', stripped)
            if m:
                val = m.group(1)
                deeplinks["schemes"].add(val)
                current["data"].append({"scheme": val})

        if current and in_intent_filter and "android:host" in stripped and "Raw:" in stripped:
            m = re.search(r'Raw: "([^"]+)"', stripped)
            if m:
                val = m.group(1)
                deeplinks["hosts"].add(val)
                current["data"].append({"host": val})

        if current and in_intent_filter and ("android:path" in stripped or "android:pathPrefix" in stripped or "android:pathPattern" in stripped) and "Raw:" in stripped:
            m = re.search(r'Raw: "([^"]+)"', stripped)
            if m:
                val = m.group(1)
                deeplinks["paths"].add(val)
                current["data"].append({"path": val})

    if current:
        components.append(current)

    exported_components = [
        c for c in components
        if c.get("exported") is True or (c.get("exported") is None and c.get("has_intent_filter"))
    ]

    return {
        "exported_components": exported_components,
        "activities": [c for c in components if c["type"] in ("activity", "activity-alias")],
        "services": [c for c in components if c["type"] == "service"],
        "receivers": [c for c in components if c["type"] == "receiver"],
        "providers": [c for c in components if c["type"] == "provider"],
        "deeplinks": {
            "schemes": sorted(deeplinks["schemes"]),
            "hosts": sorted(deeplinks["hosts"]),
            "paths": sorted(deeplinks["paths"])
        }
    }

def recommend_pipelines(features, surfaces):
    rec = []

    if features.get("react_native", {}).get("present"):
        rec.append("rn_multilayer_hunt")

    if features.get("flutter", {}).get("present"):
        rec.append("flutter_surface_hunt")

    if features.get("jetpack_compose", {}).get("present") or features.get("kotlin", {}).get("present"):
        rec.append("kotlin_compose_static_hunt")

    if features.get("webview", {}).get("present"):
        rec.append("webview_hunt")

    dl = surfaces.get("deeplinks", {})
    if dl.get("schemes") or dl.get("hosts") or dl.get("paths"):
        rec.append("deeplink_manifest_hunt")

    if features.get("firebase", {}).get("present"):
        rec.append("firebase_auth_fcm_hunt")

    if any(p.get("name", "").lower().endswith("fileprovider") or "fileprovider" in p.get("name", "").lower() for p in surfaces.get("providers", [])):
        rec.append("fileprovider_hunt")

    if not rec:
        rec.append("generic_android_static_hunt")

    return rec


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m core.apk_characterization_engine <apk> <out_dir>")
        sys.exit(1)

    apk = Path(sys.argv[1]).resolve()
    out_dir = Path(sys.argv[2]).resolve()

    if not apk.exists():
        raise SystemExit(f"[!] APK not found: {apk}")

    out_dir.mkdir(parents=True, exist_ok=True)

    rc, badging, err = run(["aapt", "dump", "badging", str(apk)])
    if rc != 0:
        raise SystemExit(f"[!] aapt badging failed: {err}")

    rc, manifest, err = run(["aapt", "dump", "xmltree", str(apk), "AndroidManifest.xml"])
    if rc != 0:
        raise SystemExit(f"[!] aapt manifest failed: {err}")

    rc, ziplist, err = run(["unzip", "-l", str(apk)])
    if rc != 0:
        raise SystemExit(f"[!] unzip listing failed: {err}")

    (out_dir / "badging.txt").write_text(badging, encoding="utf-8")
    (out_dir / "manifest_tree.txt").write_text(manifest, encoding="utf-8")
    (out_dir / "zip_listing.txt").write_text(ziplist, encoding="utf-8")

    rules = load_rules()
    blob = "\n".join([badging, manifest, ziplist])

    features = {}
    for name, needles in rules.items():
        hits = contains_any(blob, needles)
        features[name] = {
            "present": bool(hits),
            "hits": hits
        }

    meta = parse_badging(badging)
    surfaces = extract_manifest_surfaces(manifest)

    characterization = {
        "schema": "vulnlab_ai.apk_characterization.v1",
        "apk": str(apk),
        "size_bytes": apk.stat().st_size,
        "sha256": run(["sha256sum", str(apk)])[1].split()[0],
        "package_metadata": meta,
        "features": features,
        "manifest_surfaces": surfaces,
        "recommended_pipelines": recommend_pipelines(features, surfaces),
        "candidate_only_note": "This is characterization only, not vulnerability confirmation."
    }

    write(out_dir / "apk_characterization.json", characterization)

    print(f"[+] written {out_dir / 'apk_characterization.json'}")
    print(f"[+] package={meta.get('package')}")
    print(f"[+] label={meta.get('label')}")
    print(f"[+] size_mb={round(apk.stat().st_size / 1024 / 1024, 2)}")
    print("[+] detected features:")
    for k, v in features.items():
        if v["present"]:
            print(f"  - {k}: {v['hits']}")
    print("[+] recommended pipelines:")
    for r in characterization["recommended_pipelines"]:
        print(f"  - {r}")


if __name__ == "__main__":
    main()
