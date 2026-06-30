from typing import Dict, Any, List

from validation_feedback.schema import ValidationFeedback
from validation_feedback.store import ValidationFeedbackStore


class LearningFeedbackCommitter:
    """
    Commits approved learning feedback drafts into the validation feedback store.

    In automatic mode this should be used only for non-destructive local learning.
    In disclosure workflows analyst approval should remain required.
    """

    def __init__(self, feedback_path: str):
        self.store = ValidationFeedbackStore(feedback_path)

    def commit_from_states(
        self,
        states: List[Dict[str, Any]],
        require_analyst_approval: bool = False,
    ) -> Dict[str, Any]:

        committed = []
        skipped = []

        for state in states:
            draft = state.get("learning_feedback_draft")
            if not draft:
                skipped.append({
                    "case_id": state.get("case_id"),
                    "reason": "no learning feedback draft"
                })
                continue

            if require_analyst_approval and not draft.get("analyst_approved"):
                skipped.append({
                    "case_id": state.get("case_id"),
                    "reason": "analyst approval required"
                })
                continue

            record = ValidationFeedback(
                candidate_id=draft.get("candidate_id", "unknown"),
                apk_id=draft.get("apk_id", "unknown"),
                runtime_family=draft.get("runtime_family", "unknown"),
                evidence_type=draft.get("evidence_type", "unknown"),
                original_confidence=float(draft.get("original_confidence", 0.0)),
                validation_result=draft.get("validation_result", "inconclusive"),
                reachability_result=draft.get("reachability_result", "unknown"),
                dynamic_result=draft.get("dynamic_result", "not_tested"),
                analyst_verdict=draft.get("analyst_verdict", "insufficient_evidence"),
                notes=draft.get("notes", "")
            ).to_dict()

            self.store.append(record)
            committed.append(record)

        return {
            "committed": len(committed),
            "skipped": skipped,
            "summary": self.store.summarize()
        }
