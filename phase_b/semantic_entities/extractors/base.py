from typing import Any, Dict, List


class EntityExtractor:
    name = "base"

    def extract_from_research_object(self, ro: Dict[str, Any]) -> List[Any]:
        return []

    def extract_from_candidate(self, ro: Dict[str, Any], candidate: Dict[str, Any]) -> List[Any]:
        return []
