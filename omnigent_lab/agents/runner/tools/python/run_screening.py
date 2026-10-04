import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def run_screening(prereg_id: str, trajectories: int = 8, structure: str = 'kinetic') -> str:
    """Morris screening of all uncertain inputs on the chlorine-activation target."""
    return _t.run_screening(prereg_id, trajectories, structure)
