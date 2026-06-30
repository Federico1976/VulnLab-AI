from typing import Dict, Any


class CandidateQualificationEngine:
    """
    Scores Research Objects before they reach the cognitive reasoning layer.

    It decides whether an object is worth deep investigation.
    """

    def qualify(self, research_object: Dict[str, Any]) -> Dict[str, Any]:
        score = 0.0
        reasons = []
        blockers = []

        entries = research_object.get("merged_entrypoints", [])
        sources = research_object.get("merged_sources", [])
        sinks = research_object.get("merged_sinks", [])
        capability = research_object.get("primary_capability", "unknown_capability")
        object_type = research_object.get("object_type", "generic_security_surface")
        evidence_count = len(research_object.get("normalized_candidates", []))

        if entries:
            score += 0.25
            reasons.append("has entrypoint evidence")
        else:
            blockers.append("missing entrypoint evidence")

        if sources:
            score += 0.20
            reasons.append("has source evidence")
        else:
            blockers.append("missing source evidence")

        if sinks:
            score += 0.25
            reasons.append("has sink evidence")
        else:
            blockers.append("missing sink evidence")

        if capability in {"file_access", "web_content_loading", "intent_handoff"}:
            score += 0.15
            reasons.append(f"security-relevant capability: {capability}")

        if object_type in {"runtime_bridge_surface", "webview_surface", "intent_or_deeplink_surface"}:
            score += 0.10
            reasons.append(f"interesting surface: {object_type}")

        if evidence_count > 1:
            score += min(0.05, evidence_count * 0.01)
            reasons.append(f"merged evidence count: {evidence_count}")

        score = round(min(score, 1.0), 4)

        if score >= 0.75:
            level = "high_value_research_object"
            route = "deep_cognitive_analysis"
        elif score >= 0.55:
            level = "research_candidate"
            route = "standard_cognitive_analysis"
        elif score >= 0.35:
            level = "weak_research_candidate"
            route = "enrichment_required"
        else:
            level = "archive_only"
            route = "do_not_spend_joern"

        return {
            "qualification_score": score,
            "qualification_level": level,
            "route": route,
            "reasons": reasons,
            "blockers": blockers
        }
