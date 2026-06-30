from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List


@dataclass
class ResearchObject:
    object_id: str
    apk_id: str
    runtime_family: str
    object_type: str
    primary_capability: str
    normalized_candidates: List[Dict[str, Any]] = field(default_factory=list)
    merged_entrypoints: List[str] = field(default_factory=list)
    merged_sources: List[str] = field(default_factory=list)
    merged_sinks: List[str] = field(default_factory=list)
    evidence_sources: List[str] = field(default_factory=list)
    qualification: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
