import json
from pathlib import Path

APK_ROOTS = [Path("apks")]
OUT = Path("campaigns/universal_abc_campaign_manifest.json")

items = []
for root in APK_ROOTS:
    if not root.exists():
        continue
    for apk in sorted(root.glob("**/*.apk")):
        name = apk.parent.name.replace("-", "_").replace(" ", "_")
        out_dir = f"output/campaign_abc_{name}"
        items.append({
            "name": name,
            "apk": str(apk),
            "output": out_dir,
            "enabled": True
        })

doc = {
    "schema": "vulnlab.universal_abc_campaign_manifest.v1",
    "items": items
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")

print(json.dumps({
    "status": "ok",
    "items": len(items),
    "output": str(OUT)
}, indent=2))
