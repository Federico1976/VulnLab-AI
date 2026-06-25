import json
import sys
from pathlib import Path

from .engine import UniversalReachabilityEngine
from .entrypoint_correlator import UniversalEntryPointCorrelator
from .activity_navigation_correlator import ActivityNavigationCorrelator
from .next_hop_extractor import NextHopExtractor


def main():
    if len(sys.argv) != 2:
        print("Usage: PYTHONPATH=$PWD python3 -m reachability_engine.run_universal_reachability output/<target_dir>")
        sys.exit(1)

    target_dir = Path(sys.argv[1])
    out = target_dir / "universal_reachability_paths.json"

    engine = UniversalReachabilityEngine(str(target_dir))
    paths = engine.run()

    correlator = UniversalEntryPointCorrelator(str(target_dir), paths)
    paths = correlator.run()

    nav_correlator = ActivityNavigationCorrelator(str(target_dir), paths)
    paths = nav_correlator.run()

    next_hop_extractor = NextHopExtractor(paths)
    paths = next_hop_extractor.run()

    out.write_text(json.dumps(paths, indent=2), encoding="utf-8")

    print(f"[+] Universal Reachability Engine completed")
    print(f"[+] Paths: {len(paths)}")
    print(f"[+] Out: {out}")


if __name__ == "__main__":
    main()
