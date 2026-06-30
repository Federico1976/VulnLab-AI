from typing import Dict, Any, List

from intelligence_layer.research_case.models import ResearchCase, ResearchHypothesis


class ResearchCaseBuilder:
    """
    Builds the central reasoning object for Phase B.

    This is the object that LLMs, Joern, validation feedback,
    CVE knowledge and disclosure logic will reason over.
    """

    def build(
        self,
        candidate: Dict[str, Any],
        causal_graph: Dict[str, Any],
        confidence: Dict[str, Any],
    ) -> Dict[str, Any]:

        hypotheses = self._generate_initial_hypotheses(candidate, causal_graph)
        missing = self._missing_evidence(candidate, causal_graph)
        negative = self._negative_evidence(candidate, causal_graph)
        validation = self._validation_plan(candidate, causal_graph, hypotheses)

        case = ResearchCase(
            case_id=candidate.get("candidate_id", candidate.get("id", "unknown")),
            apk_id=candidate.get("apk_id", "unknown"),
            runtime_family=candidate.get("runtime_family", "unknown"),
            candidate=candidate,
            causal_graph=causal_graph,
            confidence=confidence,
            hypotheses=hypotheses,
            missing_evidence=missing,
            negative_evidence=negative,
            validation_plan=validation,
            current_verdict=self._verdict(causal_graph, confidence),
            reasoning_trace=[
                "Research case created from candidate evidence.",
                "Causal graph attached.",
                "Dynamic confidence attached.",
                "Initial hypotheses and missing evidence generated."
            ]
        )

        return case.to_dict()

    def _generate_initial_hypotheses(
        self,
        candidate: Dict[str, Any],
        causal_graph: Dict[str, Any]
    ) -> List[ResearchHypothesis]:

        sinks = candidate.get("sinks", [])
        joined = " ".join(sinks).lower()

        hypotheses = []

        if "fileinputstream" in joined or "new file" in joined:
            hypotheses.append(ResearchHypothesis(
                hypothesis_id="HYP-FILE-PATH-CONTROL-001",
                title="Externally influenced file path may reach file access sink",
                description="A runtime-controlled value appears to influence file path construction or file read operations.",
                vulnerability_class="path_traversal_or_sensitive_file_access",
                required_proofs=[
                    "external entrypoint controls the path value",
                    "path value reaches file sink without safe normalization",
                    "target file scope can cross intended app boundary",
                    "dynamic validation confirms readable sensitive target or security impact"
                ],
                blocking_questions=[
                    "Is the entrypoint externally reachable?",
                    "Is the path constrained to app-private safe directories?",
                    "Is there canonical path validation?"
                ],
                confidence=0.55
            ))

        if "intent" in joined or "uri.fromfile" in joined:
            hypotheses.append(ResearchHypothesis(
                hypothesis_id="HYP-INTENT-FILE-EXPOSURE-001",
                title="File URI or intent handoff may expose local file content",
                description="A file-derived URI or intent sink appears reachable from runtime-controlled input.",
                vulnerability_class="unsafe_intent_file_exposure",
                required_proofs=[
                    "input controls file or URI target",
                    "intent can be triggered from reachable runtime path",
                    "receiving component or external app can access unintended content",
                    "dynamic validation confirms exposure impact"
                ],
                blocking_questions=[
                    "Is FileProvider used safely?",
                    "Is the URI app-private only?",
                    "Is the intent explicit or implicit?"
                ],
                confidence=0.60
            ))

        if not hypotheses:
            hypotheses.append(ResearchHypothesis(
                hypothesis_id="HYP-GENERIC-CANDIDATE-001",
                title="Security-relevant candidate requires more semantic evidence",
                description="The candidate has security-relevant signals but not enough semantic detail for a specific hypothesis.",
                vulnerability_class="unknown_candidate",
                required_proofs=[
                    "identify source",
                    "identify sink",
                    "prove reachability",
                    "validate runtime impact"
                ],
                blocking_questions=[
                    "What is the controlled input?",
                    "What is the security boundary?",
                    "What impact can be demonstrated?"
                ],
                confidence=0.30
            ))

        return hypotheses

    def _missing_evidence(self, candidate: Dict[str, Any], causal_graph: Dict[str, Any]) -> List[str]:
        missing = []

        if not candidate.get("entrypoints"):
            missing.append("entrypoint evidence")

        if causal_graph.get("proof_level") not in {"proven_local_causal", "strong_causal"}:
            missing.append("Joern-backed causal reachability proof")

        if not candidate.get("dynamic_validation"):
            missing.append("dynamic validation result")

        if not candidate.get("security_boundary"):
            missing.append("explicit security boundary definition")

        return missing

    def _negative_evidence(self, candidate: Dict[str, Any], causal_graph: Dict[str, Any]) -> List[str]:
        negative = []

        proof = causal_graph.get("proof_level")

        if proof == "no_entrypoint":
            negative.append("no entrypoint correlated to candidate")

        if proof == "incomplete":
            negative.append("missing source or sink prevents causal claim")

        if candidate.get("reachability_result") == "not_reachable":
            negative.append("candidate currently marked not reachable")

        return negative

    def _validation_plan(
        self,
        candidate: Dict[str, Any],
        causal_graph: Dict[str, Any],
        hypotheses: List[ResearchHypothesis]
    ) -> List[str]:

        plan = [
            "Reconstruct entrypoint-to-source path.",
            "Reconstruct source-to-sink path.",
            "Check sanitization, normalization and guard conditions.",
            "Map security boundary and attacker control.",
        ]

        for h in hypotheses:
            for proof in h.required_proofs:
                plan.append(f"Validate: {proof}")

        if causal_graph.get("proof_level") != "proven_local_causal":
            plan.append("Upgrade candidate with Joern call graph/data flow proof before disclosure.")

        plan.append("Only prepare disclosure if dynamic validation confirms impact.")

        return list(dict.fromkeys(plan))

    def _verdict(self, causal_graph: Dict[str, Any], confidence: Dict[str, Any]) -> str:
        proof = causal_graph.get("proof_level", "none")
        dyn = confidence.get("dynamic_confidence", 0.0)

        if proof == "proven_local_causal" and dyn >= 0.80:
            return "strong_candidate_requires_dynamic_validation"

        if proof in {"fallback_causal_candidate", "strong_causal"}:
            return "candidate_requires_causal_upgrade"

        return "candidate_only"
