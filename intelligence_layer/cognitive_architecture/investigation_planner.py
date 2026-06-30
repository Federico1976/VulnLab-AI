from typing import Dict, Any, List


class InvestigationPlanner:
    """
    Decides the next research actions from a ResearchCase.
    It does not claim vulnerabilities.
    It decides what evidence must be acquired next.
    """

    PRIORITY = {
        "prove_causal_reachability": 100,
        "check_sanitization": 90,
        "define_security_boundary": 80,
        "run_dynamic_validation": 70,
        "collect_counter_evidence": 60,
        "prepare_disclosure_candidate": 30,
    }

    def plan(self, research_case: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions = []

        proof_level = research_case.get("causal_graph", {}).get("proof_level", "none")
        missing = set(research_case.get("missing_evidence", []))
        verdict = research_case.get("current_verdict", "candidate_only")

        if "Joern-backed causal reachability proof" in missing or proof_level in {
            "fallback_causal_candidate",
            "predicted_only",
            "incomplete",
        }:
            actions.append(self._action(
                "prove_causal_reachability",
                "Upgrade candidate using Joern call graph/data flow/propagation proof.",
                "causal_reachability",
            ))

        actions.append(self._action(
            "check_sanitization",
            "Check normalization, canonical path validation, guards and allowlists.",
            "counter_evidence",
        ))

        if "explicit security boundary definition" in missing:
            actions.append(self._action(
                "define_security_boundary",
                "Identify attacker-controlled input, trust boundary and protected asset.",
                "security_modeling",
            ))

        if "dynamic validation result" in missing:
            actions.append(self._action(
                "run_dynamic_validation",
                "Execute or prepare runtime validation only after causal path is sufficiently proven.",
                "dynamic_validation",
            ))

        if verdict == "strong_candidate_requires_dynamic_validation":
            actions.append(self._action(
                "prepare_disclosure_candidate",
                "Prepare disclosure draft only after dynamic validation confirms impact.",
                "responsible_disclosure",
            ))

        return sorted(actions, key=lambda x: x["priority"], reverse=True)

    def _action(self, action_type: str, description: str, layer: str) -> Dict[str, Any]:
        return {
            "action_type": action_type,
            "layer": layer,
            "priority": self.PRIORITY[action_type],
            "description": description,
            "status": "planned",
        }
