from typing import Dict, Any, List
from datetime import datetime


class InvestigationEpisodeBuilder:
    """
    Builds an investigation episode from a final or intermediate cognitive state.
    """

    def build_from_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        case = state.get("research_case", {})
        hypotheses = case.get("hypotheses", [])

        return {
            "episode_id": f"{state.get('apk_id', 'unknown')}::{state.get('case_id', 'unknown')}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "case_id": state.get("case_id"),
            "apk_id": state.get("apk_id"),
            "runtime_family": state.get("runtime_family"),
            "final_verdict": state.get("current_verdict"),
            "confidence": state.get("confidence"),
            "proof_level": case.get("causal_graph", {}).get("proof_level"),
            "vulnerability_classes": [
                h.get("vulnerability_class", "unknown")
                for h in hypotheses
            ],
            "selected_actions": [
                state.get("current_decision", {}).get("selected_action", {}).get("action_type")
            ] if state.get("current_decision") else [],
            "successful_actions": self._successful_actions(state),
            "blocking_conditions": state.get("current_decision", {}).get("blocking_conditions", []),
            "negative_evidence": state.get("negative_evidence", []),
            "missing_evidence": state.get("missing_evidence", []),
            "learning_feedback_draft": state.get("learning_feedback_draft"),
            "reasoning_trace": state.get("reasoning_trace", []),
        }

    def _successful_actions(self, state: Dict[str, Any]) -> List[str]:
        verdict = state.get("current_verdict", "")
        proof = state.get("research_case", {}).get("causal_graph", {}).get("proof_level", "")

        actions = []

        if proof == "proven_local_causal":
            actions.append("prove_causal_reachability")

        if verdict == "demoted_false_positive_or_safe_behavior":
            actions.append("collect_counter_evidence")

        if "dynamic_validation" in verdict:
            actions.append("prepare_dynamic_validation")

        return actions
