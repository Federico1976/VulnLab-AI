from typing import Dict, Any, List


class CausalProofRequestBuilder:
    """
    Builds structured proof requests for upgrading candidates from
    predicted/fallback reachability to causal/proven reachability.

    This is the bridge between the cognitive controller and Joern/data-flow tools.
    """

    def build_from_state(self, cognitive_state: Dict[str, Any]) -> Dict[str, Any]:
        case = cognitive_state.get("research_case", {})
        graph = case.get("causal_graph", {})
        candidate = case.get("candidate", {})

        return {
            "case_id": cognitive_state.get("case_id"),
            "apk_id": cognitive_state.get("apk_id"),
            "runtime_family": cognitive_state.get("runtime_family"),
            "current_proof_level": graph.get("proof_level", "none"),
            "requested_upgrade": self._requested_upgrade(graph),
            "entrypoints": graph.get("entrypoints", []),
            "sources": graph.get("sources", []),
            "sinks": graph.get("sinks", []),
            "candidate_methods": self._candidate_methods(candidate, graph),
            "joern_tasks": self._joern_tasks(graph),
            "expected_evidence": self._expected_evidence(graph),
            "promotion_rule": self._promotion_rule(graph),
            "blocked_until": self._blocked_until(case),
        }

    def _requested_upgrade(self, graph: Dict[str, Any]) -> str:
        proof = graph.get("proof_level", "none")

        if proof == "fallback_causal_candidate":
            return "fallback_causal_candidate_to_proven_local_causal"

        if proof == "predicted_only":
            return "predicted_only_to_strong_causal"

        if proof == "strong_causal":
            return "strong_causal_to_proven_local_causal"

        return "no_upgrade_required"

    def _candidate_methods(self, candidate: Dict[str, Any], graph: Dict[str, Any]) -> List[str]:
        methods = []

        for entry in graph.get("entrypoints", []):
            methods.append(entry)

        raw = candidate.get("raw", {})
        for key in ["method", "class", "component"]:
            value = raw.get(key) if isinstance(raw, dict) else None
            if value:
                methods.append(str(value))

        return list(dict.fromkeys(methods))

    def _joern_tasks(self, graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        tasks = []

        for entry in graph.get("entrypoints", []):
            for source in graph.get("sources", []):
                tasks.append({
                    "task_type": "entrypoint_to_source_call_path",
                    "from": entry,
                    "to": source,
                    "required": True
                })

        for source in graph.get("sources", []):
            for sink in graph.get("sinks", []):
                tasks.append({
                    "task_type": "source_to_sink_data_flow",
                    "from": source,
                    "to": sink,
                    "required": True
                })

                tasks.append({
                    "task_type": "sanitization_guard_search",
                    "from": source,
                    "to": sink,
                    "required": True
                })

        return tasks

    def _expected_evidence(self, graph: Dict[str, Any]) -> List[str]:
        evidence = [
            "method-level call path",
            "argument propagation path",
            "source parameter reaches sink argument",
            "line or method references for each path step",
            "sanitization or guard presence/absence"
        ]

        if graph.get("proof_level") == "fallback_causal_candidate":
            evidence.append("fallback source text upgraded to Joern-backed proof")

        return evidence

    def _promotion_rule(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "promote_to": "proven_local_causal",
            "requires": [
                "entrypoint_to_source path exists",
                "source_to_sink data flow exists",
                "no blocking sanitizer or guard invalidates attacker control",
                "proof contains method or line evidence"
            ],
            "demote_if": [
                "source cannot reach sink",
                "entrypoint is not connected to source",
                "sanitizer enforces safe boundary",
                "sink input is constant or trusted"
            ]
        }

    def _blocked_until(self, case: Dict[str, Any]) -> List[str]:
        blocked = []

        for item in case.get("missing_evidence", []):
            if item != "Joern-backed causal reachability proof":
                blocked.append(item)

        return blocked
