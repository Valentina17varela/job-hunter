"""Create the demo workspace (fictional data) in data/demo/ (or the folder given as argument).

    uv run python scripts/seed_demo.py
    uv run jobhunter ui --config data/demo/config.yaml

Same as `uv run jobhunter demo`. Nothing here touches your real database, CV or configuration.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from jobhunter.demo import seed  # noqa: E402

if __name__ == "__main__":
    config = seed(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "demo")
    print(f"Demo workspace ready. Start it with: uv run jobhunter ui --config {config}")
