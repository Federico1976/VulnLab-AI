import csv
import json
import sys
from pathlib import Path


def get(d, path, default=0):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p, default)
    return cur


def main():
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output/universal_abc_campaign_report.json")
    out_csv = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output/universal_abc_coverage_matrix.csv")
    out_json = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("output/universal_abc_coverage_matrix.json")

    report = json.load(open(report_path, "r", encoding="utf-8"))
    rows = []

    for r in report["records"]:
        rep = r.get("report", {})
        b = rep.get("phase_b", {})
        c = rep.get("phase_c", {})
        bs = b.get("summary", {})
        cs = c.get("summary", {})

        row = {
            "name": r["name"],
            "status": r["status"],
            "apk": r["apk"],
            "output": r["output"],

            "phase_b_completed": b.get("completed", False),
            "phase_c_completed": c.get("completed", False),

            "semantic_entities": bs.get("semantic_entities", 0),
            "semantic_edges": bs.get("semantic_edges", 0),
            "capabilities": bs.get("semantic_capabilities", 0),
            "capability_graphs": bs.get("capability_graphs", 0),
            "security_effects": bs.get("security_effects", 0),
            "evidence_models": bs.get("evidence_models", 0),
            "proof_evaluations": bs.get("proof_evaluations", 0),
            "causal_ready": bs.get("causal_ready_for_dynamic_validation", 0),
            "unknown_tasks": bs.get("unknown_resolution_tasks", 0),
            "dynamic_plans": bs.get("dynamic_validation_plans", 0),
            "learning_memories": bs.get("learning_memories", 0),
            "phase_b_strategies": bs.get("research_strategies", 0),

            "observed_patterns": get(cs, ["observed_patterns", "patterns"]),
            "research_hypotheses": get(cs, ["research_hypotheses", "hypotheses"]),
            "pattern_memory": get(cs, ["pattern_memory", "patterns"]),
            "strategy_memory": get(cs, ["research_strategy_memory", "strategies"]),
            "knowledge_patterns": get(cs, ["knowledge_matches", "patterns"]),
            "patterns_with_match": get(cs, ["knowledge_matches", "patterns_with_match"]),
            "strong_matches": get(cs, ["knowledge_matches", "strong_matches"]),
            "medium_matches": get(cs, ["knowledge_matches", "medium_matches"]),
            "weak_matches": get(cs, ["knowledge_matches", "weak_matches"]),
            "investigation_groups": get(cs, ["reasoning", "investigation_groups"]),
            "finding_allowed": cs.get("finding_allowed", False),
            "requires_dynamic_validation": cs.get("requires_dynamic_validation", True)
        }

        rows.append(row)

    out_json.write_text(json.dumps({
        "schema": "vulnlab.universal_abc_coverage_matrix.v1",
        "rows": rows
    }, indent=2), encoding="utf-8")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)

    print(json.dumps({
        "status": "ok",
        "rows": len(rows),
        "csv": str(out_csv),
        "json": str(out_json)
    }, indent=2))


if __name__ == "__main__":
    main()
