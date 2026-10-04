import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def search_counterexamples(prereg_id: str, n: int = 1200) -> str:
    """Find plausible sub-worlds where the recommended measurement changes."""
    return _t.search_counterexamples(prereg_id, n)
