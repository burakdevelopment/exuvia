import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def read_research_record(last_n: int = 20) -> str:
    """Read the last entries of the hash-chained research ledger."""
    return _t.read_research_record(last_n)
