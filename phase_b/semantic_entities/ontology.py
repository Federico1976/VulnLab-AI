from dataclasses import dataclass, asdict
from typing import Any, Dict, List
import hashlib
import json


ENTITY_TYPES = {
    "bridge": "BridgeMethodEntity",
    "entrypoint": "EntrypointEntity",
    "source": "SourceEntity",
    "sink": "SinkEntity",
    "asset": "AssetEntity",
    "trust_boundary": "TrustBoundaryEntity",
    "sanitizer": "SanitizerEntity",
    "propagation": "PropagationEntity",
    "validation_evidence": "ValidationEvidenceEntity",
    "counter_evidence": "CounterEvidenceEntity",
}


def stable_id(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


@dataclass
class SemanticEntity:
    id: str
    type: str
    research_object_id: str
    candidate_id: str | None
    runtime_family: str | None
    role: str
    confidence: str
    evidence: Any
    source_field: str
    links: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def make_entity(
    entity_type: str,
    research_object_id: str,
    candidate_id: str | None,
    runtime_family: str | None,
    role: str,
    evidence: Any,
    source_field: str,
    confidence: str = "candidate",
) -> SemanticEntity:
    payload = {
        "entity_type": entity_type,
        "research_object_id": research_object_id,
        "candidate_id": candidate_id,
        "role": role,
        "evidence": evidence,
        "source_field": source_field,
    }

    return SemanticEntity(
        id=stable_id(entity_type, payload),
        type=entity_type,
        research_object_id=research_object_id,
        candidate_id=candidate_id,
        runtime_family=runtime_family,
        role=role,
        confidence=confidence,
        evidence=evidence,
        source_field=source_field,
        links=[],
    )
