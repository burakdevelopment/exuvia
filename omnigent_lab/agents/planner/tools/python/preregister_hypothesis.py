import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def preregister_hypothesis(hypothesis_id: str, statement: str, prediction: str, falsified_if: str, experiment: str) -> str:
    """Pre-register a hypothesis with a quantitative prediction and falsification rule; returns prereg_id."""
    return _t.preregister_hypothesis(hypothesis_id, statement, prediction, falsified_if, experiment)
