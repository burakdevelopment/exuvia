import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def run_acceleration_benchmark(prereg_id: str, seeds: int = 3) -> str:
    """Simulations needed by random / LHS / screen-then-focus to recover the reference decision."""
    return _t.run_acceleration_benchmark(prereg_id, seeds)
