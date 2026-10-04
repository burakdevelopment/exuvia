import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def run_validation(prereg_id: str) -> str:
    """Reproduce published transport benchmarks (Maloney+2025, Ferreira+2024) and numerical checks."""
    return _t.run_validation(prereg_id)
