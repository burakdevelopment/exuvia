import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def rank_measurements(prereg_id: str, structure: str = 'kinetic', n: int = 1200, restrict_json: str = '{}') -> str:
    """Preposterior value (variance removed, per cost) of each candidate measurement."""
    return _t.rank_measurements(prereg_id, structure, n, restrict_json)
