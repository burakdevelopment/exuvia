import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def run_simulation(prereg_id: str, overrides_json: str = '{}') -> str:
    """Single solver run with JSON parameter overrides."""
    return _t.run_simulation(prereg_id, overrides_json)
