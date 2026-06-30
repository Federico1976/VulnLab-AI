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


def add_node(nodes: Dict[str, Dict[str, Any]], node_id: str, node_type: str, label: str, data: Dict[str, Any]) -> None:
    if node_id not in nodes:
        nodes[node_id] = {
            "node_id": node_id,
            "node_type": node_type,
            "label": label,
            "candidate_only": True,
            "finding_allowed": False,
            "data": data,
        }


def add_edge(edges: Dict[str, Dict[str, Any]], src: str, dst: str, edge_type: str, reason: str) -> None:
    edge_id = stable_id("EDGE1", src, edge_type, dst, reason)
    if edge_id not in edges:
        edges[edge_id] = {
            "edge_id": edge_id,
            "source": src,
            "target": dst,
            "edge_type": edge_type,
            "reason": reason,
        }


def build_graph(
    strategy_v3: Dict[str, Any],
    distillation: Dict[str, Any],
    confidence: Dict[str, Any],
    failure: Dict[str, Any],
    counter: Dict[str, Any],
    experience: Dict[str, Any],
) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: Dict[str, Dict[str, Any]] = {}

    # Strategy decision profiles
    for s in strategy_v3.get("decision_profiles", []):
        sid = s.get("strategy_id")
        add_node(nodes, sid, "ResearchStrategy", s.get("strategy_shape", "strategy"), s)

    # Distilled patterns
    for p in distillation.get("patterns", []):
        pid = p.get("pattern_id")
        add_node(nodes, pid, "DistilledPattern", p.get("pattern_shape", "pattern"), p)

        sid = p.get("source_strategy_id")
        if sid:
            add_edge(edges, sid, pid, "distills_to_pattern", "strategy compressed into distilled pattern")

    # Distilled strategies
    for st in distillation.get("strategies", []):
        sid = st.get("strategy_id")
        add_node(nodes, sid, "DistilledStrategyFamily", st.get("strategy_family", "strategy_family"), st)

        for pid in st.get("patterns", []):
            add_edge(edges, pid, sid, "belongs_to_strategy_family", "pattern belongs to distilled strategy family")

    # Meta strategies
    for m in distillation.get("meta_strategies", []):
        mid = m.get("meta_strategy_id")
        add_node(nodes, mid, "MetaStrategy", m.get("name", "meta_strategy"), m)

        for family in m.get("applies_to_strategy_families", []):
            fid = stable_id("KSTRAT1", family)
            add_edge(edges, fid, mid, "governed_by_meta_strategy", "strategy family governed by meta strategy")

    # Confidence nodes
    for c in confidence.get("calibrated_strategies", []):
        cid = stable_id("CONF1", c.get("strategy_id"), c.get("calibrated_confidence"), c.get("priority"))
        add_node(nodes, cid, "ConfidenceCalibration", c.get("strategy_shape", "confidence"), c)

        sid = c.get("strategy_id")
        if sid:
            add_edge(edges, sid, cid, "has_calibrated_confidence", "strategy confidence calibrated by experience and counterevidence")

    # Failure nodes
    for f in failure.get("failures", []):
        fid = f.get("failure_id")
        add_node(nodes, fid, "FailurePattern", f.get("failure_type", "failure"), f)

        shape = f.get("strategy_shape")
        for s in strategy_v3.get("decision_profiles", []):
            if s.get("strategy_shape") == shape:
                add_edge(edges, s.get("strategy_id"), fid, "may_fail_as", "strategy has observed failure mode")

    # CounterEvidence nodes
    for ce in counter.get("counterevidence", []):
        cid = ce.get("counterevidence_id")
        add_node(nodes, cid, "CounterEvidencePattern", ce.get("counterevidence_type", "counterevidence"), ce)

        shape = ce.get("strategy_shape")
        for s in strategy_v3.get("decision_profiles", []):
            if s.get("strategy_shape") == shape:
                add_edge(edges, s.get("strategy_id"), cid, "should_seek_counterevidence", "strategy should actively seek this counterevidence")

    # Experience episodes
    for ep in experience.get("episodes", []):
        eid = ep.get("episode_id")
        add_node(nodes, eid, "InvestigationEpisode", ep.get("apk", "episode"), ep)

        focus = ep.get("experience_summary", {}).get("semantic_focus", "")
        runtime = ep.get("experience_summary", {}).get("dominant_runtime", "")

        for s in strategy_v3.get("decision_profiles", []):
            shape = s.get("strategy_shape", "")

            if "bridge" in shape and "bridge" in focus:
                add_edge(edges, eid, s.get("strategy_id"), "supports_strategy_shape", "episode has compatible bridge semantic focus")

            if "entrypoint" in shape and "asset" in focus:
                add_edge(edges, eid, s.get("strategy_id"), "supports_strategy_shape", "episode has compatible entrypoint asset focus")

        # Runtime node
        rid = stable_id("RUNTIME1", runtime)
        add_node(nodes, rid, "RuntimeFamily", runtime, {"runtime": runtime})
        add_edge(edges, eid, rid, "observed_runtime", "episode observed runtime family")

    node_list = list(nodes.values())
    edge_list = list(edges.values())

    by_node_type: Dict[str, int] = {}
    by_edge_type: Dict[str, int] = {}

    for n in node_list:
        by_node_type[n["node_type"]] = by_node_type.get(n["node_type"], 0) + 1

    for e in edge_list:
        by_edge_type[e["edge_type"]] = by_edge_type.get(e["edge_type"], 0) + 1

    return {
        "schema": "universal_cognitive_graph_v1",
        "candidate_only": True,
        "finding_allowed": False,
        "purpose": "unified cognitive graph connecting strategies, patterns, experience, failures, counterevidence and confidence",
        "summary": {
            "nodes": len(node_list),
            "edges": len(edge_list),
            "by_node_type": by_node_type,
            "by_edge_type": by_edge_type,
        },
        "nodes": node_list,
        "edges": edge_list,
    }


def main() -> None:
    if len(sys.argv) != 8:
        print("Usage: python3 -m memory.universal_cognitive_graph_v1 <strategy_v3.json> <knowledge_distillation.json> <confidence.json> <failure.json> <counterevidence.json> <experience.json> <out.json>")
        sys.exit(1)

    strategy_v3 = load_json(Path(sys.argv[1]))
    distillation = load_json(Path(sys.argv[2]))
    confidence = load_json(Path(sys.argv[3]))
    failure = load_json(Path(sys.argv[4]))
    counter = load_json(Path(sys.argv[5]))
    experience = load_json(Path(sys.argv[6]))
    out = Path(sys.argv[7])

    graph = build_graph(strategy_v3, distillation, confidence, failure, counter, experience)
    save_json(out, graph)

    print(json.dumps(graph["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
