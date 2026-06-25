import json
from collections import Counter

with open(
    "output/base_449df7fd46/react_native_bridge_enriched.json",
    "r",
    encoding="utf-8"
) as f:
    findings = json.load(f)

counter = Counter()

for finding in findings:
    enrich = finding.get("rn_enrichment", {})
    for sink in enrich.get("sink_types", []):
        counter[sink] += 1

print()
print("=== Sink Distribution ===")
print()

for sink, count in counter.most_common():
    print(f"{sink:20} {count}")
