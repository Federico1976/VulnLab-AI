from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class ReachabilityNode:
    id: str
    kind: str
    label: str
    owner: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReachabilityEdge:
    src: str
    dst: str
    kind: str
    confidence: str
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReachabilityPath:
    path_id: str
    nodes: List[ReachabilityNode]
    edges: List[ReachabilityEdge]
    sink: Dict[str, Any]
    confidence: str
    status: str
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
