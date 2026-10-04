from __future__ import annotations

from .lab import read_ledger
from .tools import EXPERIMENT_TOOLS


def _call(event):
    data = event.get("data") or {}
    name = event.get("target") or (data.get("name") if isinstance(data, dict) else None)
    args = data.get("arguments", {}) if isinstance(data, dict) else {}
    return name, args or {}


def preregistration_gate(event):
    if event.get("type") != "tool_call":
        return None
    name, args = _call(event)
    if name not in EXPERIMENT_TOOLS:
        return None
    pid = args.get("prereg_id")
    known = {e["hash"] for e in read_ledger() if e["kind"] == "preregistration"}
    if pid not in known:
        return {"result": "DENY",
                "reason": "Pre-register the hypothesis (prediction + falsification rule) before running experiments."}
    return None


def approve_recommendations(event):
    if event.get("type") == "tool_call" and _call(event)[0] == "issue_recommendation":
        return {"result": "ASK", "reason": "A recommended real-world measurement needs scientist approval."}
    return None
