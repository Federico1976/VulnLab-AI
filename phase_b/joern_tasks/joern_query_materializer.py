#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


def find_strings(obj):
    values = []

    if isinstance(obj, dict):
        for v in obj.values():
            values.extend(find_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            values.extend(find_strings(v))
    elif isinstance(obj, str):
        values.append(obj)

    return values


def extract_method_hints(task):
    strings = find_strings(task.get("query_hints", {}))
    hints = set()

    for s in strings:
        for m in re.findall(r'\b([A-Za-z_$][A-Za-z0-9_$]*)\s*\(', s):
            if len(m) > 1 and m not in {"if", "for", "while", "switch", "catch"}:
                hints.add(m)

    return sorted(hints)


def extract_field_hints(task):
    strings = find_strings(task.get("query_hints", {}))
    hints = set()

    for s in strings:
        for q in re.findall(r'"([^"]{1,80})"', s):
            if q.strip():
                hints.add(q.strip())

    return sorted(hints)


def extract_class_hints(task):
    strings = find_strings(task.get("query_hints", {}))
    hints = set()

    for s in strings:
        for c in re.findall(r'\b([a-z][a-zA-Z0-9_]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*){2,})\b', s):
            hints.add(c)

    return sorted(hints)


def build_queries(task):
    task_type = task.get("task_type")
    method_hints = extract_method_hints(task)
    field_hints = extract_field_hints(task)
    class_hints = extract_class_hints(task)

    queries = []

    if task_type == "source_to_sink_causal_flow_proof":
        queries.append({
            "name": "method_hint_search",
            "purpose": "Find methods/calls matching source, propagation, and sink hints.",
            "scala": 'cpg.method.name(".*").filter(m => List(%s).exists(h => m.name.contains(h))).map(m => (m.fullName, m.filename, m.lineNumber)).l' % ",".join([f'"{h}"' for h in method_hints[:20]])
        })

        queries.append({
            "name": "call_hint_search",
            "purpose": "Find sink/propagation call sites matching extracted method hints.",
            "scala": 'cpg.call.name(".*").filter(c => List(%s).exists(h => c.name.contains(h))).map(c => (c.name, c.method.fullName, c.code, c.lineNumber)).l' % ",".join([f'"{h}"' for h in method_hints[:20]])
        })

        queries.append({
            "name": "literal_hint_search",
            "purpose": "Find literals/field keys such as url/path/header propagated through code.",
            "scala": 'cpg.literal.code(".*").filter(l => List(%s).exists(h => l.code.contains(h))).map(l => (l.code, l.method.fullName, l.lineNumber)).l' % ",".join([f'"{h}"' for h in field_hints[:20]])
        })

    elif task_type == "source_controllability_proof":
        queries.append({
            "name": "argument_usage_search",
            "purpose": "Find parameter usage and reads related to source controllability.",
            "scala": 'cpg.method.parameter.name(".*").filter(p => List(%s).exists(h => p.name.contains(h))).map(p => (p.name, p.method.fullName, p.lineNumber)).l' % ",".join([f'"{h}"' for h in method_hints[:20] + field_hints[:20]])
        })

        queries.append({
            "name": "read_call_search",
            "purpose": "Find getter/read calls such as getString/getBoolean/hasKey.",
            "scala": 'cpg.call.name("get.*|has.*|read.*|value.*").map(c => (c.name, c.code, c.method.fullName, c.lineNumber)).l'
        })

    elif task_type == "sanitizer_effectiveness_proof":
        queries.append({
            "name": "sanitizer_guard_search",
            "purpose": "Find validation, guard, allowlist, permission, URL, path, or origin checks.",
            "scala": 'cpg.call.name(".*").filter(c => List("validate","sanitize","check","verify","allow","permission","hasKey","parse","Uri","URL").exists(h => c.name.toLowerCase.contains(h.toLowerCase))).map(c => (c.name, c.code, c.method.fullName, c.lineNumber)).l'
        })

        queries.append({
            "name": "conditional_guard_search",
            "purpose": "Find conditional guards in methods related to the candidate.",
            "scala": 'cpg.controlStructure.controlStructureType("IF").map(i => (i.code, i.method.fullName, i.lineNumber)).l'
        })

    return {
        "method_hints": method_hints,
        "field_hints": field_hints,
        "class_hints": class_hints,
        "queries": queries,
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m phase_b.joern_tasks.joern_query_materializer <joern_tasks.json> <out.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    data = json.loads(in_path.read_text())
    requests = []

    for task in data.get("joern_tasks", []):
        materialized = build_queries(task)
        requests.append({
            "joern_request_id": f"JQR-{task['joern_task_id']}",
            "joern_task_id": task["joern_task_id"],
            "hypothesis_id": task["hypothesis_id"],
            "story_id": task["story_id"],
            "research_object_id": task["research_object_id"],
            "candidate_id": task["candidate_id"],
            "task_type": task["task_type"],
            "query_goal": task["query_goal"],
            "hints": {
                "methods": materialized["method_hints"],
                "fields": materialized["field_hints"],
                "classes": materialized["class_hints"],
            },
            "queries": materialized["queries"],
            "status": "materialized_not_executed",
            "quality_gates": {
                "declares_vulnerability": False,
                "candidate_evidence_only": True,
                "requires_joern_execution": True,
                "requires_proof_evaluator": True,
            },
        })

    output = {
        "schema": "vulnlab.joern_query_requests.v1",
        "input_schema": data.get("schema"),
        "request_count": len(requests),
        "summary": {
            "source_to_sink_causal_flow_proof": sum(1 for r in requests if r["task_type"] == "source_to_sink_causal_flow_proof"),
            "source_controllability_proof": sum(1 for r in requests if r["task_type"] == "source_controllability_proof"),
            "sanitizer_effectiveness_proof": sum(1 for r in requests if r["task_type"] == "sanitizer_effectiveness_proof"),
        },
        "joern_query_requests": requests,
        "quality_gates": {
            "declares_vulnerability": False,
            "planned_queries_only": True,
            "requires_execution": True,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(json.dumps({
        "status": "ok",
        "requests": len(requests),
        "summary": output["summary"],
        "output": str(out_path),
    }, indent=2))


if __name__ == "__main__":
    main()
