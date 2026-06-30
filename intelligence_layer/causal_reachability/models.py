from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any


@dataclass
class CausalEdge:
    source: str
    target: str
    edge_type: str
    evidence: str
    confidence: float = 0.5


@dataclass
class CausalReachabilityGraph:
    candidate_id: str
    apk_id: str
    runtime_family: str
    entrypoints: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    sinks: List[str] = field(default_factory=list)
    edges: List[CausalEdge] = field(default_factory=list)
    proof_level: str = "none"
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["edges"] = [asdict(edge) for edge in self.edges]
        return data
