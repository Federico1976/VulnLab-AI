from typing import Dict, Any, List


class CausalProofEvaluator:
    """
    Evaluates causal proof results and decides whether a candidate can be
    promoted, kept as candidate, or demoted.

    It is intentionally strict: no dynamic validation, no vulnerability claim.
    """

    def evaluate(
        self,
        proof_request: Dict[str, Any],
        proof_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        checks = self._checks(proof_result)
        decision = self._decision(checks)

        return {
            "case_id": proof_request.get("case_id"),
            "apk_id": proof_request.get("apk_id"),
            "runtime_family": proof_request.get("runtime_family"),
            "requested_upgrade": proof_request.get("requested_upgrade"),
            "proof_decision": decision,
            "checks": checks,
            "new_proof_level": self._new_proof_level(decision, proof_request),
            "confidence_signal": self._confidence_signal(decision, checks),
            "promotion_evidence": proof_result.get("evidence", []),
            "counter_evidence": proof_result.get("counter_evidence", []),
            "next_required_evidence": self._next_required_evidence(decision, proof_request),
        }

    def _checks(self, proof_result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "entrypoint_to_source": bool(proof_result.get("entrypoint_to_source")),
            "source_to_sink": bool(proof_result.get("source_to_sink")),
            "argument_propagation": bool(proof_result.get("argument_propagation")),
            "line_or_method_evidence": bool(proof_result.get("line_or_method_evidence")),
            "blocking_sanitizer": bool(proof_result.get("blocking_sanitizer")),
            "trusted_constant_input": bool(proof_result.get("trusted_constant_input")),
        }

    def _decision(self, checks: Dict[str, Any]) -> str:
        if checks["blocking_sanitizer"] or checks["trusted_constant_input"]:
            return "demote_due_to_counter_evidence"

        if (
            checks["entrypoint_to_source"]
            and checks["source_to_sink"]
            and checks["argument_propagation"]
            and checks["line_or_method_evidence"]
        ):
            return "promote_to_proven_local_causal"

        if checks["source_to_sink"] and checks["line_or_method_evidence"]:
            return "keep_as_strong_causal_candidate"

        return "keep_as_candidate_needs_more_evidence"

    def _new_proof_level(self, decision: str, proof_request: Dict[str, Any]) -> str:
        if decision == "promote_to_proven_local_causal":
            return "proven_local_causal"

        if decision == "keep_as_strong_causal_candidate":
            return "strong_causal"

        if decision == "demote_due_to_counter_evidence":
            return "not_reachable_or_safely_guarded"

        return proof_request.get("current_proof_level", "none")

    def _confidence_signal(self, decision: str, checks: Dict[str, Any]) -> Dict[str, Any]:
        if decision == "promote_to_proven_local_causal":
            delta = 0.18
        elif decision == "keep_as_strong_causal_candidate":
            delta = 0.07
        elif decision == "demote_due_to_counter_evidence":
            delta = -0.20
        else:
            delta = -0.03

        return {
            "delta": delta,
            "reason": decision,
            "positive_checks": [k for k, v in checks.items() if v and k not in {
                "blocking_sanitizer",
                "trusted_constant_input"
            }],
            "negative_checks": [k for k, v in checks.items() if v and k in {
                "blocking_sanitizer",
                "trusted_constant_input"
            }]
        }

    def _next_required_evidence(self, decision: str, proof_request: Dict[str, Any]) -> List[str]:
        if decision == "promote_to_proven_local_causal":
            return [
                "explicit security boundary definition",
                "dynamic validation result",
                "sanitization review completed"
            ]

        if decision == "keep_as_strong_causal_candidate":
            return [
                "complete entrypoint-to-source proof",
                "argument propagation proof",
                "sanitization guard review"
            ]

        if decision == "demote_due_to_counter_evidence":
            return [
                "record false-positive learning feedback",
                "preserve counter-evidence for future pruning"
            ]

        return [
            "collect more Joern evidence",
            "expand scoped CPG",
            "re-run source/sink extraction"
        ]
