from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class ScoreBreakdown:
    total: float
    reachability: float
    source_controllability: float
    sink_sensitivity: float
    manifest_exposure: float
    dataflow_confidence: float
    owasp_mapping: float
    noise_penalty: float


class RiskScoringEngine:
    """
    Generic APK finding scorer.

    This is NOT a vulnerability classifier.
    It ranks candidates for human/agent review.
    """

    def score(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        reachability = self._score_reachability(finding)
        source = self._score_source_controllability(finding)
        sink = self._score_sink_sensitivity(finding)
        manifest = self._score_manifest_exposure(finding)
        dataflow = self._score_dataflow_confidence(finding)
        owasp = self._score_owasp_mapping(finding)
        noise_penalty = self._score_noise_penalty(finding)

        total = (
            reachability * 0.25
            + source * 0.20
            + sink * 0.20
            + manifest * 0.15
            + dataflow * 0.15
            + owasp * 0.05
            - noise_penalty
        )

        total = max(0.0, min(100.0, total))

        breakdown = ScoreBreakdown(
            total=round(total, 2),
            reachability=reachability,
            source_controllability=source,
            sink_sensitivity=sink,
            manifest_exposure=manifest,
            dataflow_confidence=dataflow,
            owasp_mapping=owasp,
            noise_penalty=noise_penalty,
        )

        finding["risk_score"] = asdict(breakdown)
        finding["priority"] = self._priority(total)
        return finding

    def _score_reachability(self, finding: Dict[str, Any]) -> float:
        status = finding.get("status", "")

        if status == "externally_reachable":
            return 100.0
        if status == "internal_chain_candidate":
            return 45.0
        if status == "unreachable":
            return 5.0

        return 25.0

    def _score_source_controllability(self, finding: Dict[str, Any]) -> float:
        sources = str(finding.get("sources", "")).lower()
        text = str(finding).lower()

        strong = [
            "intent",
            "getstringextra",
            "getdata",
            "readablemap",
            "reactmethod",
            "deeplink",
            "uri",
            "bundle",
        ]

        if any(x in text for x in strong):
            return 80.0

        if "user" in sources or "external" in sources:
            return 60.0

        return 20.0

    def _score_sink_sensitivity(self, finding: Dict[str, Any]) -> float:
        enrichment = finding.get("rn_enrichment", {})
        sink_types = enrichment.get("sink_types", [])
        sink_count = enrichment.get("sink_count", 0)

        critical = {
            "webview",
            "command_execution",
            "dynamic_code",
            "reflection",
            "crypto",
        }

        high = {
            "intent",
            "activity_launch",
            "broadcast",
            "service",
            "content_resolver",
            "file",
            "bluetooth",
            "nfc",
            "network",
        }

        if any(s in sink_types for s in critical):
            return 95.0

        if any(s in sink_types for s in high):
            return 75.0

        if sink_count > 0:
            return 45.0

        return 5.0

    def _score_manifest_exposure(self, finding: Dict[str, Any]) -> float:
        text = str(finding).lower()

        if '"exported": true' in text or "'exported': true" in text:
            return 100.0

        if '"exported": false' in text or "'exported': false" in text:
            return 10.0

        if "not exported" in text or "non esportata" in text:
            return 10.0

        if "component" in finding and finding.get("component"):
            return 40.0

        return 20.0

    def _score_dataflow_confidence(self, finding: Dict[str, Any]) -> float:
        text = str(finding).lower()

        if "reachablebyflows" in text or "joern_dataflow" in text:
            return 90.0

        if "trace" in finding and finding.get("trace"):
            return 60.0

        if "evidence" in finding and finding.get("evidence"):
            return 45.0

        return 20.0

    def _score_owasp_mapping(self, finding: Dict[str, Any]) -> float:
        text = str(finding).lower()

        if "maswe" in text or "masvs" in text or "mastg" in text:
            return 80.0

        return 20.0

    def _score_noise_penalty(self, finding: Dict[str, Any]) -> float:
        enrichment = finding.get("rn_enrichment", {})
        sink_count = enrichment.get("sink_count", 0)
        body_extracted = enrichment.get("body_extracted", False)

        penalty = 0.0

        if body_extracted and sink_count == 0:
            penalty += 35.0

        if not body_extracted:
            penalty += 10.0

        if finding.get("confidence") == "low":
            penalty += 20.0

        if finding.get("status") == "internal_chain_candidate":
            penalty += 10.0

        return penalty

    def _priority(self, score: float) -> str:
        if score >= 75:
            return "P1_REVIEW_NOW"
        if score >= 55:
            return "P2_HIGH_VALUE_CANDIDATE"
        if score >= 35:
            return "P3_REVIEW_LATER"
        return "P4_LOW_SIGNAL"
