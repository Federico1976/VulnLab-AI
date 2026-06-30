import json
import sys
from pathlib import Path
from typing import Dict, Any, List

from intelligence_layer.evidence_case.normalizer import EvidenceCaseNormalizer
from intelligence_layer.causal_reachability.builder import CausalReachabilityBuilder
from intelligence_layer.confidence_learning.learner import DynamicConfidenceLearner
from intelligence_layer.research_case.builder import ResearchCaseBuilder
from intelligence_layer.knowledge_memory.matcher import KnowledgeMemoryMatcher
from intelligence_layer.cognitive_architecture.controller import CognitiveController
from intelligence_layer.cognitive_architecture.reasoning_loop import ReasoningLoop
from intelligence_layer.causal_reachability.proof_request import CausalProofRequestBuilder
from intelligence_layer.research_memory.episode_builder import InvestigationEpisodeBuilder
from intelligence_layer.research_memory.episode_store import InvestigationEpisodeStore
from validation_feedback.store import ValidationFeedbackStore


CANDIDATE_FILES = [
    "rn_final_multilayer_evidence.json",
    "rn_final_evidence.json",
    "rn_bridge_evidence.json",
    "webview_evidence.json",
    "deeplink_findings.json",
    "flutter_surface_findings.json",
    "runtime_ontology_v4.json",
    "evidence_graph_v5.json",
    "responsible_disclosure_candidates.json",
]


class ComparativeCognitiveCampaignRunner:
    def __init__(self, feedback_path: str):
        feedback = ValidationFeedbackStore(feedback_path).load()

        self.normalizer = EvidenceCaseNormalizer()
        self.learner = DynamicConfidenceLearner(feedback)
        self.causal_builder = CausalReachabilityBuilder()
        self.case_builder = ResearchCaseBuilder()
        self.knowledge_matcher = KnowledgeMemoryMatcher()
        self.controller = CognitiveController()
        self.reasoning_loop = ReasoningLoop()
        self.proof_request_builder = CausalProofRequestBuilder()
        self.episode_builder = InvestigationEpisodeBuilder()

    def run_campaign(self, labs: List[str], output_root: str) -> Dict[str, Any]:
        output_root_path = Path(output_root)
        output_root_path.mkdir(parents=True, exist_ok=True)

        campaign = {
            "labs": [],
            "summary": {
                "total_labs": 0,
                "total_raw_candidates": 0,
                "total_research_cases": 0,
                "total_cognitive_states": 0,
                "total_proof_requests": 0,
                "by_runtime_family": {},
                "by_verdict": {},
                "by_proof_level": {},
                "by_selected_action": {},
            }
        }

        episode_store = InvestigationEpisodeStore(
            str(output_root_path / "investigation_episodes.json")
        )

        for lab in labs:
            lab_path = Path(lab)
            apk_id = lab_path.name

            lab_output_dir = output_root_path / apk_id
            lab_output_dir.mkdir(parents=True, exist_ok=True)

            raw_candidates = self._load_candidates_from_lab(lab_path)

            normalized = [
                self.normalizer.normalize(raw, apk_id=apk_id)
                for raw in raw_candidates
            ]

            research_cases = []
            cognitive_states = []
            proof_requests = []

            for candidate in normalized:
                confidence = self.learner.adjust_candidate_confidence(candidate)
                causal_graph = self.causal_builder.build(candidate)

                case = self.case_builder.build(
                    candidate=candidate,
                    causal_graph=causal_graph,
                    confidence=confidence,
                )

                case = self.knowledge_matcher.enrich_case(case)

                state = self.controller.initialize(case)
                state = self.reasoning_loop.run_once(state)

                cognitive_states.append(state)
                research_cases.append(case)

                selected = state.get("current_decision", {}).get("selected_action", {}).get("action_type")
                if selected == "prove_causal_reachability":
                    proof_requests.append(
                        self.proof_request_builder.build_from_state(state)
                    )

                episode_store.append(self.episode_builder.build_from_state(state))

            lab_report = {
                "apk_id": apk_id,
                "lab_path": str(lab_path),
                "raw_candidates": raw_candidates,
                "normalized_candidates": normalized,
                "research_cases": research_cases,
                "cognitive_states": cognitive_states,
                "proof_requests": proof_requests,
                "summary": self._summarize_lab(
                    raw_candidates,
                    research_cases,
                    cognitive_states,
                    proof_requests,
                )
            }

            self._write_json(lab_output_dir / "research_cases.json", {
                "apk_id": apk_id,
                "research_cases": research_cases,
                "summary": lab_report["summary"]
            })

            self._write_json(lab_output_dir / "cognitive_states.json", {
                "apk_id": apk_id,
                "cognitive_states": cognitive_states,
                "summary": lab_report["summary"]
            })

            self._write_json(lab_output_dir / "proof_requests.json", {
                "apk_id": apk_id,
                "proof_requests": proof_requests,
                "summary": {
                    "total_proof_requests": len(proof_requests)
                }
            })

            campaign["labs"].append({
                "apk_id": apk_id,
                "lab_path": str(lab_path),
                "summary": lab_report["summary"]
            })

            self._accumulate_campaign_summary(campaign["summary"], lab_report)

        campaign["summary"]["total_labs"] = len(labs)
        campaign["summary"]["episode_memory"] = episode_store.summarize()

        self._write_json(output_root_path / "comparative_cognitive_campaign.json", campaign)
        return campaign

    def _load_candidates_from_lab(self, lab_path: Path) -> List[Dict[str, Any]]:
        candidates = []

        for name in CANDIDATE_FILES:
            path = lab_path / name
            if not path.exists():
                continue

            loaded = self._load_candidate_file(path)
            for item in loaded:
                item["_source_file"] = str(path)
                candidates.append(item)

        if not candidates:
            fallback = self._scan_json_candidates(lab_path)
            candidates.extend(fallback)

        return candidates

    def _load_candidate_file(self, path: Path) -> List[Dict[str, Any]]:
        try:
            data = json.loads(path.read_text())
        except Exception:
            return []

        return self._extract_candidate_items(data)

    def _extract_candidate_items(self, data: Any) -> List[Dict[str, Any]]:
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]

        if isinstance(data, dict):
            for key in [
                "candidates",
                "findings",
                "evidence",
                "items",
                "results",
                "responsible_disclosure_candidates",
                "nodes",
            ]:
                value = data.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]

            if self._looks_like_candidate(data):
                return [data]

        return []

    def _scan_json_candidates(self, lab_path: Path) -> List[Dict[str, Any]]:
        candidates = []

        for path in lab_path.rglob("*.json"):
            if any(skip in str(path) for skip in [
                "node_modules",
                "workspace",
                "decompiled",
                "sources",
            ]):
                continue

            try:
                data = json.loads(path.read_text())
            except Exception:
                continue

            for item in self._extract_candidate_items(data):
                if self._looks_like_candidate(item):
                    item["_source_file"] = str(path)
                    candidates.append(item)

        return candidates

    def _looks_like_candidate(self, item: Dict[str, Any]) -> bool:
        blob = json.dumps(item).lower()

        indicators = [
            "finding",
            "candidate",
            "sink",
            "source",
            "reachability",
            "webview",
            "reactmethod",
            "intent",
            "fileinputstream",
            "loadurl",
            "runtime_family",
            "evidence",
        ]

        return any(i in blob for i in indicators)

    def _summarize_lab(
        self,
        raw_candidates: List[Dict[str, Any]],
        research_cases: List[Dict[str, Any]],
        cognitive_states: List[Dict[str, Any]],
        proof_requests: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        summary = {
            "raw_candidates": len(raw_candidates),
            "research_cases": len(research_cases),
            "cognitive_states": len(cognitive_states),
            "proof_requests": len(proof_requests),
            "by_runtime_family": {},
            "by_verdict": {},
            "by_proof_level": {},
            "by_selected_action": {},
        }

        for case in research_cases:
            self._count(summary["by_runtime_family"], case.get("runtime_family", "unknown"))
            self._count(summary["by_verdict"], case.get("current_verdict", "unknown"))
            self._count(summary["by_proof_level"], case.get("causal_graph", {}).get("proof_level", "unknown"))

        for state in cognitive_states:
            action = state.get("current_decision", {}).get("selected_action", {}).get("action_type", "none")
            self._count(summary["by_selected_action"], action)

        return summary

    def _accumulate_campaign_summary(
        self,
        campaign_summary: Dict[str, Any],
        lab_report: Dict[str, Any],
    ) -> None:

        summary = lab_report["summary"]

        campaign_summary["total_raw_candidates"] += summary["raw_candidates"]
        campaign_summary["total_research_cases"] += summary["research_cases"]
        campaign_summary["total_cognitive_states"] += summary["cognitive_states"]
        campaign_summary["total_proof_requests"] += summary["proof_requests"]

        for key in ["by_runtime_family", "by_verdict", "by_proof_level", "by_selected_action"]:
            for value, count in summary[key].items():
                campaign_summary[key][value] = campaign_summary[key].get(value, 0) + count

    def _count(self, bucket: Dict[str, int], key: str) -> None:
        bucket[key] = bucket.get(key, 0) + 1

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    if len(sys.argv) < 4:
        print(
            "Usage: python3 -m intelligence_layer.cognitive_architecture.run_comparative_cognitive_campaign "
            "<feedback.json> <output_root> <lab_dir_1> [lab_dir_2 ...]"
        )
        sys.exit(1)

    feedback_path = sys.argv[1]
    output_root = sys.argv[2]
    labs = sys.argv[3:]

    runner = ComparativeCognitiveCampaignRunner(feedback_path)
    campaign = runner.run_campaign(labs, output_root)

    print(json.dumps(campaign["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
