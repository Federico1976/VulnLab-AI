import json
import subprocess
import sys
from pathlib import Path


def run(cmd):
    print("[PHASE_C]", " ".join(cmd))
    rc = subprocess.call(cmd)
    print("[PHASE_C_RC]", rc)
    if rc != 0:
        raise SystemExit(rc)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 -m phase_c.run_phase_c <universal_run_output_dir>")

    out_dir = Path(sys.argv[1])
    brain_dir = out_dir / "phase_b_brain"
    phase_c_dir = out_dir / "phase_c"
    phase_c_dir.mkdir(parents=True, exist_ok=True)

    observed = phase_c_dir / "observed_investigation_patterns.json"
    hypotheses = phase_c_dir / "research_hypotheses.json"
    pattern_memory = phase_c_dir / "pattern_memory_snapshot.json"
    strategy_memory = phase_c_dir / "research_strategy_memory.json"
    matches = phase_c_dir / "vulnerability_case_matches.json"
    reasoning = phase_c_dir / "investigation_reasoning_plan.json"
    summary = phase_c_dir / "phase_c_summary.json"
    markdown_report = phase_c_dir / "PHASE_C_REPORT.md"

    run([
        sys.executable, "-m",
        "phase_c.investigation_patterns.observed_pattern_builder",
        str(brain_dir),
        str(observed)
    ])

    run([
        sys.executable, "-m",
        "phase_c.research_hypotheses.research_hypothesis_engine",
        str(observed),
        str(hypotheses)
    ])

    run([
        sys.executable, "-m",
        "phase_c.pattern_memory.pattern_memory_extractor",
        "phase_c/knowledge_memory/seed_cases",
        str(pattern_memory)
    ])

    run([
        sys.executable, "-m",
        "phase_c.research_strategy_memory.strategy_memory_builder",
        str(pattern_memory),
        str(strategy_memory)
    ])

    run([
        sys.executable, "-m",
        "phase_c.investigation_patterns.vulnerability_case_matcher",
        str(observed),
        "phase_c/knowledge_memory/seed_cases",
        str(matches)
    ])

    run([
        sys.executable, "-m",
        "phase_c.investigation_patterns.investigation_reasoning_planner",
        str(matches),
        str(reasoning)
    ])

    observed_doc = load_json(observed)
    hypotheses_doc = load_json(hypotheses)
    pattern_memory_doc = load_json(pattern_memory)
    strategy_memory_doc = load_json(strategy_memory)
    matches_doc = load_json(matches)
    reasoning_doc = load_json(reasoning)

    report = {
        "status": "ok",
        "schema": "vulnlab.phase_c.summary.v1",
        "phase_c_completed": True,
        "architecture": {
            "mode": "research_hypothesis_then_knowledge_guided_investigation",
            "llm_required": False,
            "model_independent": True,
            "candidate_only_guardrail": True,
            "finding_allowed": False
        },
        "pipeline": [
            "Evidence Models",
            "Observed Investigation Pattern",
            "Research Hypothesis Engine",
            "Knowledge Memory",
            "Pattern Matching",
            "Investigation Reasoning",
            "Dynamic Validation"
        ],
        "summary": {
            "observed_patterns": observed_doc.get("summary", {}),
            "research_hypotheses": hypotheses_doc.get("summary", {}),
            "pattern_memory": pattern_memory_doc.get("summary", {}),
            "research_strategy_memory": strategy_memory_doc.get("summary", {}),
            "knowledge_matches": matches_doc.get("summary", {}),
            "reasoning": reasoning_doc.get("summary", {}),
            "finding_allowed": False,
            "requires_dynamic_validation": True
        },
        "outputs": {
            "observed_investigation_patterns": str(observed),
            "research_hypotheses": str(hypotheses),
            "pattern_memory": str(pattern_memory),
            "research_strategy_memory": str(strategy_memory),
            "vulnerability_case_matches": str(matches),
            "investigation_reasoning_plan": str(reasoning)
        }
    }

    with open(summary, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    run([
        sys.executable, "-m",
        "phase_c.phase_c_markdown_report",
        str(phase_c_dir),
        str(markdown_report)
    ])

    print(json.dumps({
        "status": "ok",
        "phase_c_completed": True,
        "pipeline": report["pipeline"],
        "summary": report["summary"],
        "outputs": {
            "summary": str(summary),
            "markdown_report": str(markdown_report)
        }
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
