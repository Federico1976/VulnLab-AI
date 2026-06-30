#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
from pathlib import Path


FDROID_INDEX = "https://f-droid.org/repo/index-v2.json"
FDROID_REPO = "https://f-droid.org/repo"

SELECTED_PACKAGES = [
    "org.fdroid.fdroid",
    "org.schabi.newpipe",
    "com.termux",
    "org.tasks",
    "org.mozilla.fennec_fdroid",
    "com.nextcloud.client",
    "org.kde.kdeconnect_tp",
    "net.osmand.plus",
    "com.aurora.store",
    "org.openfoodfacts.scanner",
    "org.videolan.vlc",
    "com.jarsilio.android.waveup",
    "org.isoron.uhabits",
]


def download(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as r:
        out.write_bytes(r.read())


def main() -> None:
    out_dir = Path("apks/fdroid_smoke10")
    meta_dir = Path("output/generalization/fdroid_smoke10")
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    index_path = meta_dir / "index-v2.json"

    if not index_path.exists():
        print("[+] downloading F-Droid index-v2.json")
        download(FDROID_INDEX, index_path)

    index = json.loads(index_path.read_text(encoding="utf-8"))
    packages = index.get("packages", {})

    manifest = []

    downloaded_count = 0

    for package_name in SELECTED_PACKAGES:
        if downloaded_count >= 10:
            break
        pkg = packages.get(package_name)
        if not pkg:
            manifest.append({
                "package": package_name,
                "status": "missing_from_index",
            })
            continue

        versions = pkg.get("versions", {})
        if not versions:
            manifest.append({
                "package": package_name,
                "status": "no_versions",
            })
            continue

        latest_key = sorted(
            versions.keys(),
            key=lambda k: versions[k].get("manifest", {}).get("versionCode", 0),
            reverse=True,
        )[0]

        version = versions[latest_key]
        file_info = version.get("file", {})
        apk_name = file_info.get("name")

        if not apk_name:
            manifest.append({
                "package": package_name,
                "status": "missing_apk_name",
            })
            continue

        apk_url = f"{FDROID_REPO}/{apk_name}"
        apk_out = out_dir / Path(apk_name).name

        if not apk_out.exists():
            print(f"[+] downloading {package_name} -> {apk_out}")
            download(apk_url, apk_out)
        else:
            print(f"[=] exists {package_name} -> {apk_out}")

        manifest.append({
            "package": package_name,
            "status": "downloaded",
            "apk": str(apk_out),
            "version_code": version.get("manifest", {}).get("versionCode"),
            "version_name": version.get("manifest", {}).get("versionName"),
        })
        downloaded_count += 1

    manifest_path = meta_dir / "fdroid_smoke10_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "manifest": str(manifest_path),
        "downloaded": sum(1 for m in manifest if m.get("status") == "downloaded"),
        "total": len(manifest),
    }, indent=2))


if __name__ == "__main__":
    main()
