import json
from pathlib import Path
from typing import Dict, Any, List


class InvestigationEpisodeStore:
    """
    Stores full investigation episodes.

    Feedback records teach local confidence.
    Episodes teach research strategy:
    what was tried, what worked, what failed, and why.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text())

    def append(self, episode: Dict[str, Any]) -> None:
        data = self.load()
        data.append(episode)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def summarize(self) -> Dict[str, Any]:
        data = self.load()
        summary = {
            "total_episodes": len(data),
            "by_final_verdict": {},
            "by_runtime_family": {},
            "by_vulnerability_class": {},
            "by_successful_action": {},
        }

        for ep in data:
            self._count(summary["by_final_verdict"], ep.get("final_verdict", "unknown"))
            self._count(summary["by_runtime_family"], ep.get("runtime_family", "unknown"))

            for vc in ep.get("vulnerability_classes", []):
                self._count(summary["by_vulnerability_class"], vc)

            for action in ep.get("successful_actions", []):
                self._count(summary["by_successful_action"], action)

        return summary

    def _count(self, bucket: Dict[str, int], key: str) -> None:
        bucket[key] = bucket.get(key, 0) + 1
