#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, time
from pathlib import Path

def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() and p.is_file() else {}

def save(p,d):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    import argparse
    ap=argparse.ArgumentParser(description="Ollama LLM Reasoner v1")
    ap.add_argument("--packet", required=True)
    ap.add_argument("--model", default="llama3.1")
    ap.add_argument("--out", required=True)
    args=ap.parse_args()

    packet=load(args.packet)

    prompt = f"""
Return ONLY valid JSON. No markdown. No explanation.

You are an APK security reasoning reviewer.

STRICT RULES:
- Do not claim a vulnerability.
- Do not write a bug bounty report.
- finding_allowed must be false.
- Use only the evidence in the packet.

Return exactly this JSON object shape:
{{
  "triage_state": "candidate_needs_trace",
  "most_promising_path": "string",
  "counter_evidence_to_resolve": ["string"],
  "missing_proof": ["string"],
  "next_best_experiment": {{
    "goal": "string",
    "safe_command_or_static_task": "string",
    "expected_information_gain": "high",
    "why_this_before_other_tests": "string"
  }},
  "finding_allowed": false
}}

PACKET:
{json.dumps(packet, ensure_ascii=False)}
"""

    r=subprocess.run(
        ["ollama", "run", args.model],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=180
    )

    raw=r.stdout.strip()
    parsed=None
    try:
        start=raw.find("{")
        end=raw.rfind("}")+1
        parsed=json.loads(raw[start:end])
    except Exception:
        fallback_cmd = [
            "python3", "-m", "generalization.llm_reasoning_output_v1",
            "--packet", args.packet,
            "--out", str(Path(args.out).with_suffix(".fallback.json"))
        ]
        subprocess.run(fallback_cmd, text=True, capture_output=True, timeout=60)
        fallback = load(Path(args.out).with_suffix(".fallback.json"))
        parsed = fallback if fallback else {
            "triage_state":"llm_output_parse_failed",
            "most_promising_path":packet.get("top_candidate",{}).get("entry_component"),
            "counter_evidence_to_resolve":[],
            "missing_proof":packet.get("top_candidate",{}).get("missing_edges",[]),
            "next_best_experiment":{
                "goal":"Retry LLM reasoning with stricter JSON output or use deterministic reviewer.",
                "safe_command_or_static_task":"Inspect causal graph packet manually.",
                "expected_information_gain":"medium",
                "why_this_before_other_tests":"LLM response was not parseable JSON."
            },
            "finding_allowed":False
        }

    parsed["finding_allowed"]=False
    parsed["candidate_only"]=True

    out={
        "schema_version":"ollama_llm_reasoner.v1",
        "created_at":int(time.time()),
        "model":args.model,
        "source_packet":args.packet,
        "ollama_returncode":r.returncode,
        "raw_output":raw,
        "reasoning_output":parsed,
        "guardrail_result":{
            "finding_allowed_forced_false":True,
            "candidate_only":True,
            "no_report_generation":True
        }
    }

    save(args.out,out)
    print(json.dumps(parsed, indent=2, ensure_ascii=False))

if __name__=="__main__":
    main()


def run_ollama_llm_reasoning(packet_path: str, output_path: str, model: str = "llama3.2:3b"):
    """
    Stable runner API used by complete APK research agent.
    Wraps the existing ollama_llm_reasoner implementation.
    """
    try:
        return ollama_llm_reasoner(
            packet_path=packet_path,
            output_path=output_path,
            model=model,
        )
    except TypeError:
        return ollama_llm_reasoner(
            packet_path,
            output_path,
            model,
        )
