import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def list_evidence() -> str:
    """Uncertain inputs with ranges and primary sources, plus candidate next measurements."""
    return _t.list_evidence()
