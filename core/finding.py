from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

@dataclass
class Finding:
    id: str
    title: str
    category: str
    severity: str = "info"
    confidence: str = "low"
    status: str = "candidate"
    masvs: List[str] = field(default_factory=list)
    maswe: List[str] = field(default_factory=list)
    cwe: List[str] = field(default_factory=list)
    component: Dict[str, Any] | None = None
    source: Dict[str, Any] | None = None
    sink: Dict[str, Any] | None = None
    trace: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    risk: str = ""
    validation_steps: List[str] = field(default_factory=list)
    false_positive_checks: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
