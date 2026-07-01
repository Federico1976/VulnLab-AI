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




def compress_packet_for_llm(packet):
    """
    Keep only high-signal fields for local small LLMs.
    Prevents long causal graph packets from degrading JSON compliance.
    """
    top = packet.get("top_candidate", {})
    return {
        "schema_version": packet.get("schema_version"),
        "target": packet.get("target"),
        "package": packet.get("package"),
        "top_candidate": {
            "entry_component": top.get("entry_component"),
            "causal_state": top.get("causal_state"),
            "causal_score": top.get("causal_score"),
            "missing_edges": top.get("missing_edges", []),
            "node_kinds": top.get("node_kinds", []),
            "edge_kinds": top.get("edge_kinds", []),
        },
        "guardrails": {
            "finding_allowed": False,
            "candidate_only": True,
            "report_allowed": False,
        },
        "allowed_decision": {
            "only_choose_next_best_experiment": True,
            "never_claim_vulnerability_without_runtime_proof": True,
        },
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

Compressed packet:
{json.dumps(compress_packet_for_llm(packet), ensure_ascii=False)}
""".strip()


def repair_json_control_chars(s):
    """
    Repair common local-LLM JSON issue: raw newlines inside quoted strings.
    """
    out = []
    in_string = False
    escape = False

    for ch in s:
        if escape:
            out.append(ch)
            escape = False
            continue

        if ch == "\\":
            out.append(ch)
            escape = True
            continue

        if ch == '"':
            out.append(ch)
            in_string = not in_string
            continue

        if in_string and ch in ("\n", "\r", "\t"):
            out.append(" ")
            continue

        out.append(ch)

    return "".join(out)


def extract_json(text):
    text = text.strip()
    if not text:
        raise ValueError("empty ollama response")

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in Ollama response")

    candidate = text[start:end + 1]

    try:
        return json.loads(candidate, strict=False)
    except Exception:
        repaired = repair_json_control_chars(candidate)
        return json.loads(repaired, strict=False)




def salvage_reasoning_from_text(raw_text, packet, source_packet, backend):
    """
    Last-mile parser for local LLMs that emit almost-JSON.
    Extracts useful intent but still enforces all safety guardrails.
    """
    top = packet.get("top_candidate", {})
    text = raw_text or ""

    missing = top.get("missing_edges", [])
    if not missing:
        missing = [
            "runtime marker propagation",
            "ordered method-level call chain",
            "sanitizer decision",
            "impact proof"
        ]

    next_step = "method_level_trace_review"
    if "runtime" in text.lower() and "marker" in text.lower():
        next_step = "runtime_marker_propagation_probe"
    elif "sanitizer" in text.lower():
        next_step = "sanitizer_decision_review"

    return {
        "schema": "ollama_llm_reasoning_v1",
        "backend": backend,
        "reasoning_mode": "llm_text_salvaged",
        "fallback_used": False,
        "source_packet": str(source_packet),
        "most_promising_path": top.get("entry_component"),
        "finding_allowed": False,
        "candidate_only": True,
        "report_allowed": False,
        "next_best_experiment": {
            "step": next_step,
            "target": top.get("entry_component"),
            "why": "LLM output was malformed JSON but agreed that concrete proof is still missing."
        },
        "missing_proof": missing,
        "counter_evidence": [
            "no confirmed runtime propagation",
            "no concrete exploitability proof"
        ],
        "llm_json_parse_repaired": False,
        "llm_text_salvaged": True
    }


def normalize_experiment(value, top):
    entry = top.get("entry_component")

    if isinstance(value, dict) and value.get("step"):
        return {
            "step": str(value.get("step")),
            "target": value.get("target") or entry,
            "why": value.get("why") or "Concrete ordered source-to-sink proof is still missing."
        }

    return {
        "step": "method_level_trace_review",
        "target": entry,
        "why": "Concrete ordered source-to-sink proof is still missing."
    }


def normalize_reasoning(obj, packet, source_packet, backend="ollama"):
    top = packet.get("top_candidate", {})

    out = {}
    out["schema"] = "ollama_llm_reasoning_v1"
    out["backend"] = backend
    out["reasoning_mode"] = "llm_json_reasoning"
    out["fallback_used"] = False
    out["source_packet"] = str(source_packet)

    out["finding_allowed"] = False
    out["candidate_only"] = True
    out["report_allowed"] = False

    out["most_promising_path"] = top.get("entry_component")
    out["next_best_experiment"] = normalize_experiment(
        obj.get("next_best_experiment") if isinstance(obj, dict) else None,
        top,
    )

    missing = top.get("missing_edges") or []
    if not missing:
        missing = [
            "runtime marker propagation",
            "ordered method-level call chain",
            "sanitizer decision",
            "impact proof"
        ]

    out["missing_proof"] = missing
    out["counter_evidence"] = [
        "no confirmed runtime propagation",
        "no concrete exploitability proof"
    ]

    out["llm_raw_fields_seen"] = sorted(list(obj.keys())) if isinstance(obj, dict) else []
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

        raw_path = None
        if output_path:
            raw_path = str(Path(output_path).with_suffix(".raw.txt"))
            Path(raw_path).write_text(
                "STDOUT:\n" + r.stdout + "\n\nSTDERR:\n" + r.stderr,
                encoding="utf-8",
            )

        if r.returncode != 0:
            out = deterministic_fallback(packet, packet_path, reason=f"ollama_returncode_{r.returncode}")
            out["raw_output_path"] = raw_path
        else:
            try:
                parsed = extract_json(r.stdout)
                out = normalize_reasoning(parsed, packet, packet_path, backend=f"ollama:{model}")
                out["raw_output_path"] = raw_path
            except Exception as e:
                out = salvage_reasoning_from_text(
                    raw_text=r.stdout,
                    packet=packet,
                    source_packet=packet_path,
                    backend=f"ollama:{model}",
                )
                out["json_parse_error"] = str(e)
                out["raw_output_path"] = raw_path

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
