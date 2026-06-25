import json
from pathlib import Path
from typing import Dict, Any, List


class ValidationFeedbackStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text())

    def append(self, record: Dict[str, Any]) -> None:
        data = self.load()
        data.append(record)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def summarize(self) -> Dict[str, Any]:
        data = self.load()
        summary = {
            "total_feedback_records": len(data),
            "by_runtime_family": {},
            "by_validation_result": {},
            "by_analyst_verdict": {},
        }

        for item in data:
            for key, bucket in [
                ("runtime_family", "by_runtime_family"),
                ("validation_result", "by_validation_result"),
                ("analyst_verdict", "by_analyst_verdict"),
            ]:
                value = item.get(key, "unknown")
                summary[bucket][value] = summary[bucket].get(value, 0) + 1

        return summary
