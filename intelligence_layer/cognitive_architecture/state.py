from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List


@dataclass
class CognitiveState:
    case_id: str
    apk_id: str
    runtime_family: str

    research_case: Dict[str, Any]

    active_hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    known_facts: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    negative_evidence: List[str] = field(default_factory=list)

    next_actions: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_trace: List[str] = field(default_factory=list)

    current_verdict: str = "candidate_only"
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
