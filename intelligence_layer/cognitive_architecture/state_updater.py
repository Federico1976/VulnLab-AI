from typing import Dict, Any, List


class CognitiveStateUpdater:
    """
    Applies proof evaluations to cognitive states.

    This closes the first reasoning loop:
    state -> proof request -> proof evaluation -> updated state.
    """

    def apply_proof_evaluation(
        self,
        cognitive_state: Dict[str, Any],
        proof_evaluation: Dict[str, Any],
    ) -> Dict[str, Any]:

        state = dict(cognitive_state)
        case = dict(state.get("research_case", {}))
        graph = dict(case.get("causal_graph", {}))

        new_proof = proof_evaluation.get("new_proof_level")
        decision = proof_evaluation.get("proof_decision")

        graph["proof_level"] = new_proof
        graph["proof_evaluation"] = proof_evaluation
        graph["reasoning"] = graph.get("reasoning", []) + [
            f"Proof evaluator decision: {decision}.",
            f"Proof level updated to: {new_proof}."
        ]

        case["causal_graph"] = graph
        case["negative_evidence"] = self._merge_negative(
            case.get("negative_evidence", []),
            proof_evaluation.get("counter_evidence", [])
        )
        case["missing_evidence"] = self._update_missing(
            case.get("missing_evidence", []),
            proof_evaluation
        )
        case["current_verdict"] = self._new_verdict(case, proof_evaluation)

        state["research_case"] = case
        state["current_verdict"] = case["current_verdict"]
        state["missing_evidence"] = case["missing_evidence"]
        state["negative_evidence"] = case["negative_evidence"]
        state["confidence"] = self._update_confidence(
            state.get("confidence", 0.0),
            proof_evaluation.get("confidence_signal", {}).get("delta", 0.0)
        )
        state["reasoning_trace"] = state.get("reasoning_trace", []) + [
            f"Applied proof evaluation: {decision}.",
            f"Cognitive verdict updated to: {state['current_verdict']}."
        ]

        state["learning_feedback_draft"] = self._learning_feedback_draft(state, proof_evaluation)

        return state

    def _merge_negative(self, current: List[str], counter: List[str]) -> List[str]:
        merged = list(current)

        for item in counter:
            if item not in merged:
                merged.append(item)

        return merged

    def _update_missing(
        self,
        missing: List[str],
        proof_evaluation: Dict[str, Any]
    ) -> List[str]:

        decision = proof_evaluation.get("proof_decision")
        updated = list(missing)

        if decision == "promote_to_proven_local_causal":
            updated = [
                item for item in updated
                if item != "Joern-backed causal reachability proof"
            ]

        if decision == "demote_due_to_counter_evidence":
            updated = [
                item for item in updated
                if item != "Joern-backed causal reachability proof"
            ]
            if "false-positive learning feedback" not in updated:
                updated.append("false-positive learning feedback")

        return updated

    def _new_verdict(
        self,
        case: Dict[str, Any],
        proof_evaluation: Dict[str, Any]
    ) -> str:

        decision = proof_evaluation.get("proof_decision")

        if decision == "promote_to_proven_local_causal":
            if "dynamic validation result" in case.get("missing_evidence", []):
                return "proven_causal_requires_dynamic_validation"
            return "validated_disclosure_candidate"

        if decision == "demote_due_to_counter_evidence":
            return "demoted_false_positive_or_safe_behavior"

        if decision == "keep_as_strong_causal_candidate":
            return "strong_candidate_requires_more_proof"

        return "candidate_requires_more_evidence"

    def _update_confidence(self, current: float, delta: float) -> float:
        return round(max(0.0, min(1.0, float(current) + float(delta))), 4)

    def _learning_feedback_draft(
        self,
        state: Dict[str, Any],
        proof_evaluation: Dict[str, Any]
    ) -> Dict[str, Any]:

        decision = proof_evaluation.get("proof_decision")

        if decision == "promote_to_proven_local_causal":
            verdict = "interesting_candidate"
            validation = "confirmed"
            reachability = "proven"
        elif decision == "demote_due_to_counter_evidence":
            verdict = "false_positive"
            validation = "rejected"
            reachability = "not_reachable"
        else:
            verdict = "insufficient_evidence"
            validation = "needs_more_evidence"
            reachability = "predicted"

        case = state.get("research_case", {})
        candidate = case.get("candidate", {})

        return {
            "candidate_id": state.get("case_id"),
            "apk_id": state.get("apk_id"),
            "runtime_family": state.get("runtime_family"),
            "evidence_type": candidate.get("evidence_type", "unknown"),
            "original_confidence": candidate.get("confidence_score", 0.0),
            "validation_result": validation,
            "reachability_result": reachability,
            "dynamic_result": "not_tested",
            "analyst_verdict": verdict,
            "notes": f"Auto-generated feedback draft from proof decision: {decision}"
        }
