#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


def safe_name(package: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", package).replace(".", "_")


manifest = json.loads(Path("output/generalization/fdroid_smoke10/fdroid_smoke10_manifest.json").read_text())

prepared = []

for item in manifest:
    if item.get("status") != "downloaded":
        continue

    package = item["package"]
    out = Path("output") / f"fdroid_smoke10_{safe_name(package)}"
    out.mkdir(parents=True, exist_ok=True)

    (out / "apk_input.json").write_text(json.dumps(item, indent=2), encoding="utf-8")

    prepared.append({
        "package": package,
        "apk": item["apk"],
        "output_dir": str(out),
        "status": "prepared"
    })

Path("output/generalization/fdroid_smoke10/prepared_outputs.json").write_text(
    json.dumps(prepared, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(json.dumps({
    "prepared": len(prepared),
    "manifest": "output/generalization/fdroid_smoke10/prepared_outputs.json"
}, indent=2))
