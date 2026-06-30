from __future__ import annotations

import json
import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{h}"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def classify_external_item(item: Dict[str, Any]) -> str:
    text = json.dumps(item, ensure_ascii=False).lower()

    if "webview" in text or "javascriptinterface" in text:
        return "bridge_to_webview_sink"

    if "fileprovider" in text or "content uri" in text or "content://" in text:
        return "entrypoint_to_content_uri_asset"

    if "bridge" in text and "file" in text:
        return "bridge_to_file_asset"

    if "auth" in text or "token" in text or "credential" in text:
        return "credential_or_token_flow"

    return "generic_external_security_knowledge"


def build_external_knowledge_node(item: Dict[str, Any]) -> Dict[str, Any]:
    shape = classify_external_item(item)
    return {
        "external_knowledge_id": stable_id("EXTK1", shape, item.get("id"), item.get("title"), item.get("source")),
        "candidate_only": True,
        "finding_allowed": False,
        "source": item.get("source", "unknown"),
        "title": item.get("title") or item.get("id") or "external_knowledge_item",
        "knowledge_shape": shape,
        "summary": item.get("summary") or item.get("description") or "",
        "raw": item,
    }


def merge_external(items_doc: Dict[str, Any], cognitive_graph_v2: Dict[str, Any]) -> Dict[str, Any]:
    raw_items = items_doc.get("items", items_doc if isinstance(items_doc, list) else [])
    external_nodes = [build_external_knowledge_node(x) for x in raw_items if isinstance(x, dict)]

    by_shape: Dict[str, int] = {}
    for n in external_nodes:
        by_shape[n["knowledge_shape"]] = by_shape.get(n["knowledge_shape"], 0) + 1

    links = []

    for n in external_nodes:
        for route in cognitive_graph_v2.get("reasoning_routes", []):
            if route.get("strategy_shape") == n["knowledge_shape"]:
                links.append({
                    "external_knowledge_id": n["external_knowledge_id"],
                    "strategy_shape": route.get("strategy_shape"),
                    "link_type": "supports_or_informs_strategy_shape",
                    "candidate_only": True,
                    "finding_allowed": False,
                })

    return {
        "schema": "knowledge_merge_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "merge external/public/internal knowledge into cognitive strategy shapes without creating target findings",
        "summary": {
            "external_items": len(external_nodes),
            "links_to_cognitive_graph": len(links),
            "by_shape": by_shape,
        },
        "external_knowledge": external_nodes,
        "links": links,
    }


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: python3 -m memory.knowledge_merge_engine_v1 <external_items.json> <universal_cognitive_graph_v2.json> <knowledge_merge_v1.json>")
        sys.exit(1)

    items = load_json(Path(sys.argv[1]))
    graph = load_json(Path(sys.argv[2]))
    out = Path(sys.argv[3])

    merged = merge_external(items, graph)
    save_json(out, merged)

    print(json.dumps(merged["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
