from typing import Dict, Any

from intelligence_layer.cognitive_architecture.state import CognitiveState
from intelligence_layer.cognitive_architecture.investigation_planner import InvestigationPlanner


class CognitiveController:
    """
    Cognitive Architecture v1 controller.

    It receives a ResearchCase and builds a CognitiveState:
    - facts
    - hypotheses
    - missing evidence
    - negative evidence
    - next investigation actions
    - verdict
    """

    def __init__(self):
        self.planner = InvestigationPlanner()

    def initialize(self, research_case: Dict[str, Any]) -> Dict[str, Any]:
        confidence = research_case.get("confidence", {}).get("dynamic_confidence", 0.0)

        state = CognitiveState(
            case_id=research_case.get("case_id", "unknown"),
            apk_id=research_case.get("apk_id", "unknown"),
            runtime_family=research_case.get("runtime_family", "unknown"),
            research_case=research_case,
            active_hypotheses=research_case.get("hypotheses", []),
            known_facts=self._extract_known_facts(research_case),
            missing_evidence=research_case.get("missing_evidence", []),
            negative_evidence=research_case.get("negative_evidence", []),
            next_actions=self.planner.plan(research_case),
            current_verdict=research_case.get("current_verdict", "candidate_only"),
            confidence=confidence,
            reasoning_trace=research_case.get("reasoning_trace", []) + [
                "Cognitive state initialized.",
                "Investigation planner generated next actions."
            ]
        )

        return state.to_dict()

    def _extract_known_facts(self, research_case: Dict[str, Any]):
        facts = []

        graph = research_case.get("causal_graph", {})
        proof = graph.get("proof_level", "none")

        facts.append(f"runtime_family={research_case.get('runtime_family', 'unknown')}")
        facts.append(f"proof_level={proof}")
        facts.append(f"current_verdict={research_case.get('current_verdict', 'candidate_only')}")

        for edge in graph.get("edges", []):
            facts.append(
                f"{edge.get('edge_type')}:{edge.get('source')}->{edge.get('target')} evidence={edge.get('evidence')}"
            )

        for match in research_case.get("knowledge_memory", {}).get("matches", []):
            facts.append(
                f"knowledge_match={match.get('vulnerability_class')} indicators={len(match.get('positive_indicators', []))}"
            )

        return facts
