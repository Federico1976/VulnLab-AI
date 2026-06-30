from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_adjacency(graph: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    adj: Dict[str, List[Dict[str, Any]]] = {}
    for e in graph.get("edges", []):
        adj.setdefault(e["source"], []).append(e)
    return adj


def node_map(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {n["node_id"]: n for n in graph.get("nodes", [])}


def traverse_from_strategy(
    strategy_node: Dict[str, Any],
    nodes: Dict[str, Dict[str, Any]],
    adj: Dict[str, List[Dict[str, Any]]],
    max_depth: int = 4,
) -> Dict[str, Any]:
    start = strategy_node["node_id"]
    visited = set()
    frontier = [(start, 0, [])]
    paths = []

    while frontier:
        current, depth, path = frontier.pop(0)

        if depth > max_depth:
            continue

        if current in visited and depth > 0:
            continue

        visited.add(current)

        for edge in adj.get(current, []):
            target = edge["target"]
            target_node = nodes.get(target)
            if not target_node:
                continue

            new_path = path + [{
                "edge_type": edge["edge_type"],
                "target_node_type": target_node["node_type"],
                "target_label": target_node["label"],
                "reason": edge.get("reason"),
            }]

            paths.append(new_path)
            frontier.append((target, depth + 1, new_path))

    return {
        "start_strategy_id": start,
        "strategy_shape": strategy_node.get("data", {}).get("strategy_shape"),
        "paths": paths,
        "reachable_node_types": sorted(set(
            step["target_node_type"]
            for path in paths
            for step in path
        )),
        "path_count": len(paths),
    }


def build_v2(graph_v1: Dict[str, Any]) -> Dict[str, Any]:
    nodes = node_map(graph_v1)
    adj = build_adjacency(graph_v1)

    strategy_nodes = [
        n for n in graph_v1.get("nodes", [])
        if n.get("node_type") == "ResearchStrategy"
    ]

    traversals = [
        traverse_from_strategy(s, nodes, adj)
        for s in strategy_nodes
    ]

    reasoning_routes = []

    for t in traversals:
        shape = t["strategy_shape"]
        route = {
            "strategy_shape": shape,
            "candidate_only": True,
            "finding_allowed": False,
            "recommended_reasoning_route": [
                "match_semantic_shape",
                "load_distilled_pattern",
                "load_strategy_family",
                "apply_meta_strategy",
                "read_confidence_calibration",
                "seek_counterevidence",
                "predict_failure_modes",
                "plan_runtime_validation",
                "stop_before_finding_until_proof"
            ],
            "reachable_node_types": t["reachable_node_types"],
            "path_count": t["path_count"],
        }
        reasoning_routes.append(route)

    return {
        "schema": "universal_cognitive_graph_v2",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "active traversal layer over the universal cognitive graph",
        "source_schema": graph_v1.get("schema"),
        "summary": {
            "nodes": graph_v1.get("summary", {}).get("nodes"),
            "edges": graph_v1.get("summary", {}).get("edges"),
            "strategy_traversals": len(traversals),
            "reasoning_routes": len(reasoning_routes),
        },
        "nodes": graph_v1.get("nodes", []),
        "edges": graph_v1.get("edges", []),
        "strategy_traversals": traversals,
        "reasoning_routes": reasoning_routes,
    }


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 -m memory.universal_cognitive_graph_v2 <universal_cognitive_graph_v1.json> <universal_cognitive_graph_v2.json>")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2])

    graph_v1 = load_json(inp)
    graph_v2 = build_v2(graph_v1)
    save_json(out, graph_v2)

    print(json.dumps(graph_v2["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
