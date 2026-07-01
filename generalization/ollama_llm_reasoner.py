#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else {}


def save(p, d):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False))


def deterministic_fallback(packet, source_packet, reason="ollama_unavailable_or_invalid_json"):
    top = packet.get("top_candidate", {})
    return {
        "schema": "ollama_llm_reasoning_v1",
        "backend": "deterministic_fallback",
        "reasoning_mode": "safe_fallback",
        "fallback_used": True,
        "fallback_reason": reason,
        "source_packet": str(source_packet),
        "most_promising_path": top.get("entry_component"),
        "finding_allowed": False,
        "candidate_only": True,
        "report_allowed": False,
        "next_best_experiment": {
            "step": "method_level_trace_review",
            "target": top.get("entry_component"),
            "why": "Concrete ordered source-to-sink proof is still missing."
        },
        "missing_proof": top.get("missing_edges", [
            "runtime marker propagation",
            "ordered method-level call chain",
            "sanitizer decision",
            "impact proof"
        ]),
        "counter_evidence": [
            "no confirmed runtime propagation",
            "no concrete exploitability proof"
        ]
    }


def build_prompt(packet):
    return f"""
You are a defensive Android APK security research reasoning layer.

Rules:
- Use only the evidence in the packet.
- Do not invent facts.
- Do not claim a vulnerability.
- Keep finding_allowed=false unless concrete proof exists.
- Keep candidate_only=true unless concrete proof exists.
- Select only the next best experiment.

Return strict JSON only with:
schema, backend, reasoning_mode, fallback_used, finding_allowed, candidate_only,
report_allowed, most_promising_path, next_best_experiment, missing_proof, counter_evidence.

Packet:
{json.dumps(packet, ensure_ascii=False)}
""".strip()


def extract_json(text):
    text = text.strip()
    if not text:
        raise ValueError("empty ollama response")

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in Ollama response")

    return json.loads(text[start:end + 1])


def normalize_reasoning(obj, packet, source_packet, backend="ollama"):
    top = packet.get("top_candidate", {})

    out = dict(obj) if isinstance(obj, dict) else {}
    out["schema"] = "ollama_llm_reasoning_v1"
    out["backend"] = out.get("backend") or backend
    out["reasoning_mode"] = out.get("reasoning_mode") or "llm_json_reasoning"
    out["fallback_used"] = bool(out.get("fallback_used", False))
    out["source_packet"] = str(source_packet)

    out["finding_allowed"] = False
    out["candidate_only"] = True
    out["report_allowed"] = False

    out.setdefault("most_promising_path", top.get("entry_component"))
    out.setdefault("next_best_experiment", {
        "step": "method_level_trace_review",
        "target": top.get("entry_component"),
        "why": "Concrete ordered source-to-sink proof is still missing."
    })
    out.setdefault("missing_proof", top.get("missing_edges", []))
    out.setdefault("counter_evidence", [
        "no confirmed runtime propagation",
        "no concrete exploitability proof"
    ])

    return out


def reason_from_packet(packet_path, output_path=None, model="llama3.2:3b", timeout=90):
    packet = load(packet_path)
    prompt = build_prompt(packet)

    try:
        r = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
        )

        if r.returncode != 0:
            out = deterministic_fallback(packet, packet_path, reason=f"ollama_returncode_{r.returncode}")
        else:
            parsed = extract_json(r.stdout)
            out = normalize_reasoning(parsed, packet, packet_path, backend=f"ollama:{model}")

    except Exception as e:
        out = deterministic_fallback(packet, packet_path, reason=str(e))

    if output_path:
        save(output_path, out)

    return out


def run_ollama_llm_reasoning(packet_path: str, output_path: str, model: str = "llama3.2:3b"):
    return reason_from_packet(packet_path=packet_path, output_path=output_path, model=model)


def main():
    ap = argparse.ArgumentParser(description="Ollama LLM Reasoner v1")
    ap.add_argument("--packet", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--timeout", type=int, default=90)
    args = ap.parse_args()

    out = reason_from_packet(
        packet_path=args.packet,
        output_path=args.out,
        model=args.model,
        timeout=args.timeout,
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
