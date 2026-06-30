import json
from pathlib import Path
from typing import Dict, Any, List


class KnowledgeMemoryMatcher:
    def __init__(self, patterns_path: str = "intelligence_layer/knowledge_memory/patterns.json"):
        self.patterns_path = Path(patterns_path)
        self.patterns = json.loads(self.patterns_path.read_text())

    def enrich_case(self, research_case: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(research_case)
        matches = []

        for hyp in research_case.get("hypotheses", []):
            vuln_class = hyp.get("vulnerability_class", "unknown_candidate")
            pattern = self.patterns.get(vuln_class)

            if not pattern:
                continue

            matches.append({
                "hypothesis_id": hyp.get("hypothesis_id"),
                "vulnerability_class": vuln_class,
                "knowledge_description": pattern.get("description"),
                "positive_indicators": self._matched_indicators(research_case, pattern.get("positive_indicators", [])),
                "false_positive_checks": pattern.get("false_positive_indicators", []),
                "required_proofs": pattern.get("required_proofs", []),
                "validation_strategy": pattern.get("validation_strategy", [])
            })

        enriched["knowledge_memory"] = {
            "matches": matches,
            "total_matches": len(matches)
        }

        enriched["reasoning_trace"] = enriched.get("reasoning_trace", []) + [
            f"Knowledge memory matched {len(matches)} hypothesis pattern(s)."
        ]

        return enriched

    def _matched_indicators(self, research_case: Dict[str, Any], indicators: List[str]) -> List[str]:
        blob = json.dumps(research_case).lower()
        matched = []

        for indicator in indicators:
            terms = indicator.lower().replace("(", " ").replace(")", " ").split()
            score = sum(1 for t in terms if t in blob)
            if score > 0:
                matched.append(indicator)

        return matched
