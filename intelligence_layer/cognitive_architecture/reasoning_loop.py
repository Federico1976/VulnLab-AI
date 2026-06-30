from typing import Dict, Any, List


class ReasoningLoop:
    """
    First deterministic reasoning loop.

    The loop does not claim vulnerabilities.
    It decides the next best research move and explains why.
    """

    def run_once(self, cognitive_state: Dict[str, Any]) -> Dict[str, Any]:
        state = dict(cognitive_state)

        actions = state.get("next_actions", [])
        selected = self._select_next_action(actions)

        decision = {
            "case_id": state.get("case_id"),
            "selected_action": selected,
            "decision_reason": self._reason(state, selected),
            "blocking_conditions": self._blocking_conditions(state),
            "promotion_conditions": self._promotion_conditions(state),
            "disclosure_allowed": self._disclosure_allowed(state),
        }

        state["current_decision"] = decision
        state["reasoning_trace"] = state.get("reasoning_trace", []) + [
            f"Reasoning loop selected action: {selected.get('action_type', 'none')}.",
            decision["decision_reason"]
        ]

        return state

    def _select_next_action(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not actions:
            return {
                "action_type": "no_action",
                "priority": 0,
                "description": "No next action available.",
                "status": "blocked"
            }

        return sorted(actions, key=lambda x: x.get("priority", 0), reverse=True)[0]

    def _reason(self, state: Dict[str, Any], action: Dict[str, Any]) -> str:
        action_type = action.get("action_type")

        if action_type == "prove_causal_reachability":
            return (
                "The candidate cannot be promoted because causal reachability is not yet proven. "
                "The next step is to upgrade the path using Joern call graph, data flow or propagation evidence."
            )

        if action_type == "check_sanitization":
            return (
                "The candidate has a causal path, but sanitization and guard conditions must be checked "
                "before any vulnerability claim."
            )

        if action_type == "define_security_boundary":
            return (
                "The candidate requires an explicit trust boundary and protected asset definition "
                "to determine security impact."
            )

        if action_type == "run_dynamic_validation":
            return (
                "The candidate requires runtime validation before it can become a disclosure-ready finding."
            )

        if action_type == "prepare_disclosure_candidate":
            return (
                "The candidate is structurally strong, but disclosure is allowed only after dynamic validation."
            )

        return "No research decision could be made."

    def _blocking_conditions(self, state: Dict[str, Any]) -> List[str]:
        blocking = []

        for item in state.get("missing_evidence", []):
            blocking.append(item)

        for item in state.get("negative_evidence", []):
            blocking.append(f"negative evidence: {item}")

        if state.get("confidence", 0.0) < 0.50:
            blocking.append("dynamic confidence below investigation threshold")

        return blocking

    def _promotion_conditions(self, state: Dict[str, Any]) -> List[str]:
        return [
            "causal reachability proven",
            "sanitization and guard checks completed",
            "security boundary explicitly defined",
            "dynamic validation confirms impact",
            "no blocking negative evidence remains"
        ]

    def _disclosure_allowed(self, state: Dict[str, Any]) -> bool:
        missing = set(state.get("missing_evidence", []))
        negative = state.get("negative_evidence", [])
        verdict = state.get("current_verdict")

        if negative:
            return False

        if "dynamic validation result" in missing:
            return False

        if "explicit security boundary definition" in missing:
            return False

        return verdict in {
            "validated_disclosure_candidate",
            "dynamic_validation_confirmed"
        }
