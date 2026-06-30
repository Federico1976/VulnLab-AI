#!/usr/bin/env python3
from __future__ import annotations
import json, re, urllib.request
from pathlib import Path

FDROID_INDEX="https://f-droid.org/repo/index-v2.json"
FDROID_REPO="https://f-droid.org/repo"

SEEDS=[
"org.fdroid.fdroid","org.schabi.newpipe","com.termux","org.tasks",
"org.mozilla.fennec_fdroid","com.nextcloud.client","org.kde.kdeconnect_tp",
"net.osmand.plus","com.aurora.store","org.videolan.vlc","org.isoron.uhabits",
"com.jarsilio.android.waveup","org.openfoodfacts.scanner","de.danoeh.antennapod",
"org.kiwix.kiwixmobile","org.wikipedia","com.fsck.k9","org.openhab.habdroid",
"com.github.axet.bookreader","org.secuso.privacyfriendlynotes",
"com.simplemobiletools.calendar.pro","org.thoughtcrime.securesms",
"org.openstreetmap.josm","com.owncloud.android","org.torproject.android",
"org.quantumbadger.redreader","org.fox.tttrss","org.openintents.filemanager",
"de.blinkt.openvpn","org.adaway"
]

def dl(url, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=180) as r:
        out.write_bytes(r.read())

def safe(x):
    return re.sub(r"[^a-zA-Z0-9_.-]+","_",x).replace(".","_")

root=Path("output/generalization/fdroid_campaign30")
apkdir=Path("apks/fdroid_campaign30")
root.mkdir(parents=True, exist_ok=True); apkdir.mkdir(parents=True, exist_ok=True)

idx_path=root/"index-v2.json"
if not idx_path.exists():
    dl(FDROID_INDEX, idx_path)

idx=json.loads(idx_path.read_text())
pkgs=idx.get("packages",{})

manifest=[]
downloaded=0

for package in SEEDS:
    if downloaded>=30: break
    pkg=pkgs.get(package)
    if not pkg or not pkg.get("versions"):
        manifest.append({"package":package,"status":"missing_from_index"})
        continue

    versions=pkg["versions"]
    latest=sorted(versions.keys(), key=lambda k: versions[k].get("manifest",{}).get("versionCode",0), reverse=True)[0]
    ver=versions[latest]
    name=ver.get("file",{}).get("name")
    if not name:
        manifest.append({"package":package,"status":"missing_apk"})
        continue

    apk=apkdir/Path(name).name
    if not apk.exists():
        print(f"[+] download {package}")
        dl(f"{FDROID_REPO}/{name}", apk)

    out=Path("output")/f"fdroid_campaign30_{safe(package)}"
    out.mkdir(parents=True, exist_ok=True)

    item={
        "package":package,
        "status":"prepared",
        "apk":str(apk),
        "output_dir":str(out),
        "version_code":ver.get("manifest",{}).get("versionCode"),
        "version_name":ver.get("manifest",{}).get("versionName")
    }
    (out/"apk_input.json").write_text(json.dumps(item,indent=2),encoding="utf-8")
    manifest.append(item)
    downloaded+=1

(root/"prepared_outputs.json").write_text(json.dumps([m for m in manifest if m.get("status")=="prepared"],indent=2),encoding="utf-8")
(root/"full_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

print(json.dumps({
    "prepared": downloaded,
    "prepared_manifest": str(root/"prepared_outputs.json"),
    "full_manifest": str(root/"full_manifest.json")
},indent=2))
