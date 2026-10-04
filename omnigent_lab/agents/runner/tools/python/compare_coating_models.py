import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def compare_coating_models(prereg_id: str, n: int = 600) -> str:
    """Run identical inputs through instant / kinetic / no-coating models."""
    return _t.compare_coating_models(prereg_id, n)
