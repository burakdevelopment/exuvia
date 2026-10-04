import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def issue_recommendation(measurement_id: str, rationale: str) -> str:
    """Publish the next-measurement recommendation (human approval required)."""
    return _t.issue_recommendation(measurement_id, rationale)
