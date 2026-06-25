from typing import Dict, Any, List


class DynamicConfidenceLearner:
    def __init__(self, feedback_records: List[Dict[str, Any]]):
        self.feedback_records = feedback_records

    def learn_adjustments(self) -> Dict[str, Any]:
        adjustments = {
            "runtime_family": {},
            "evidence_type": {},
            "reachability_result": {},
        }

        for record in self.feedback_records:
            delta = self._verdict_delta(record)

            for key in ["runtime_family", "evidence_type", "reachability_result"]:
                value = record.get(key, "unknown")
                bucket = adjustments[key].setdefault(value, {
                    "samples": 0,
                    "total_delta": 0.0,
                    "average_delta": 0.0,
                })

                bucket["samples"] += 1
                bucket["total_delta"] += delta
                bucket["average_delta"] = round(
                    bucket["total_delta"] / bucket["samples"], 4
                )

        return adjustments

    def adjust_candidate_confidence(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        learned = self.learn_adjustments()
        base = float(candidate.get("confidence_score", candidate.get("confidence", 0.5)))

        applied = []

        for key in ["runtime_family", "evidence_type", "reachability_result"]:
            value = candidate.get(key)
            if value in learned.get(key, {}):
                delta = learned[key][value]["average_delta"]
                base += delta
                applied.append({
                    "factor": key,
                    "value": value,
                    "delta": delta,
                    "samples": learned[key][value]["samples"],
                })

        base = max(0.0, min(1.0, base))

        enriched = dict(candidate)
        enriched["dynamic_confidence"] = round(base, 4)
        enriched["confidence_learning_applied"] = applied
        return enriched

    def _verdict_delta(self, record: Dict[str, Any]) -> float:
        verdict = record.get("analyst_verdict", "insufficient_evidence")
        validation = record.get("validation_result", "inconclusive")
        reachability = record.get("reachability_result", "unknown")
        dynamic = record.get("dynamic_result", "not_tested")

        delta = 0.0

        if verdict == "true_positive":
            delta += 0.12
        elif verdict == "false_positive":
            delta -= 0.15
        elif verdict == "benign_behavior":
            delta -= 0.10
        elif verdict == "interesting_candidate":
            delta += 0.03
        elif verdict == "insufficient_evidence":
            delta -= 0.03

        if validation == "confirmed":
            delta += 0.08
        elif validation == "rejected":
            delta -= 0.10
        elif validation == "needs_more_evidence":
            delta -= 0.02

        if reachability == "proven":
            delta += 0.10
        elif reachability == "not_reachable":
            delta -= 0.12
        elif reachability == "predicted":
            delta += 0.01

        if dynamic == "validated":
            delta += 0.10
        elif dynamic == "blocked":
            delta -= 0.03

        return round(delta, 4)
