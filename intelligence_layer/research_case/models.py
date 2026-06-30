from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List


@dataclass
class ResearchHypothesis:
    hypothesis_id: str
    title: str
    description: str
    vulnerability_class: str
    required_proofs: List[str] = field(default_factory=list)
    blocking_questions: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class ResearchCase:
    case_id: str
    apk_id: str
    runtime_family: str
    candidate: Dict[str, Any]
    causal_graph: Dict[str, Any]
    confidence: Dict[str, Any]
    hypotheses: List[ResearchHypothesis] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    negative_evidence: List[str] = field(default_factory=list)
    validation_plan: List[str] = field(default_factory=list)
    current_verdict: str = "candidate_only"
    reasoning_trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["hypotheses"] = [asdict(h) for h in self.hypotheses]
        return data
