import json
import sys
from pathlib import Path

from intelligence_layer.research_memory.episode_builder import InvestigationEpisodeBuilder
from intelligence_layer.research_memory.episode_store import InvestigationEpisodeStore


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 -m intelligence_layer.research_memory.run_record_episodes <states.json> <episode_store.json>")
        sys.exit(1)

    states_path = Path(sys.argv[1])
    store_path = sys.argv[2]

    data = json.loads(states_path.read_text())
    states = data.get("cognitive_states", [])

    builder = InvestigationEpisodeBuilder()
    store = InvestigationEpisodeStore(store_path)

    for state in states:
        store.append(builder.build_from_state(state))

    print(json.dumps(store.summarize(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
