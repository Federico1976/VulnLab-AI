from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class ValidationFeedback:
    candidate_id: str
    apk_id: str
    runtime_family: str
    evidence_type: str
    original_confidence: float
    validation_result: str
    reachability_result: str
    dynamic_result: str
    analyst_verdict: str
    notes: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not data["timestamp"]:
            data["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return data


VALIDATION_RESULTS = {
    "confirmed",
    "rejected",
    "inconclusive",
    "needs_more_evidence",
}

REACHABILITY_RESULTS = {
    "proven",
    "predicted",
    "not_reachable",
    "unknown",
}

DYNAMIC_RESULTS = {
    "validated",
    "not_validated",
    "not_tested",
    "blocked",
}

ANALYST_VERDICTS = {
    "true_positive",
    "false_positive",
    "benign_behavior",
    "interesting_candidate",
    "insufficient_evidence",
}
