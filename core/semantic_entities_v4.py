from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import hashlib


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{h}"


@dataclass
class UniversalEntity:
    entity_id: str
    entity_type: str
    name: str

    source_runtime: str = "unknown"
    framework_origin: str = "unknown"

    observations: List[Dict[str, Any]] = field(default_factory=list)
    inferred_capabilities: List[str] = field(default_factory=list)
    trust_boundaries: List[str] = field(default_factory=list)
    related_assets: List[str] = field(default_factory=list)
    related_sinks: List[str] = field(default_factory=list)

    confidence: float = 0.0
    uncertainty_reasons: List[str] = field(default_factory=list)
    counter_evidence: List[Dict[str, Any]] = field(default_factory=list)
    source_artifacts: List[Dict[str, Any]] = field(default_factory=list)

    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


ENTITY_TYPES = {
    "EntrypointEntity",
    "TrustBoundaryEntity",
    "CapabilityEntity",
    "AssetEntity",
    "PropagationEntity",
    "SinkEntity",
    "SecurityControlEntity",
    "ValidationEvidenceEntity",
    "CounterEvidenceEntity",
    "RuntimeArtifactEntity",
    "FrameworkArtifactEntity",
    "BridgeEntity",
    "RouteEntity",
    "AuthEntity",
    "StorageEntity",
}
