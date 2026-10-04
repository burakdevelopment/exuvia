from __future__ import annotations

import json

import numpy as np

from . import lab
from .sim import Params, run, as_dict

EXPERIMENT_TOOLS = {"run_validation", "run_screening", "compare_coating_models", "rank_measurements",
                    "search_counterexamples", "run_simulation", "run_acceleration_benchmark"}


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o))


def list_evidence() -> str:
    return _dump({"priors": {k: {"range": [v[0], v[1]], "scale": v[2], "source": v[3]} for k, v in lab.PRIORS.items()},
                  "measurements": lab.MEASUREMENTS, "scenario": lab.SCENARIO})


def preregister_hypothesis(hypothesis_id: str, statement: str, prediction: str, falsified_if: str, experiment: str) -> str:
    return _dump({"prereg_id": lab.preregister(hypothesis_id, statement, prediction, falsified_if, experiment)})


def run_validation(prereg_id: str) -> str:
    lab.require_preregistration(prereg_id)
    out = lab.validation_benchmarks()
    lab.record("result", {"experiment": "validation_benchmarks", "prereg": prereg_id, **out})
    return _dump(out)


def run_screening(prereg_id: str, trajectories: int = 8, structure: str = "kinetic") -> str:
    lab.require_preregistration(prereg_id)
    out = lab.morris_screening(lab.STRUCTURES[structure], int(trajectories), np.random.default_rng(7))
    lab.record("result", {"experiment": "morris_screening", "prereg": prereg_id, **out})
    return _dump(out)


def compare_coating_models(prereg_id: str, n: int = 600) -> str:
    lab.require_preregistration(prereg_id)
    res, _, _ = lab.compare_structures(int(n), np.random.default_rng(11))
    lab.record("result", {"experiment": "structural_comparison", "prereg": prereg_id, "n": n, **res})
    return _dump(res)


def rank_measurements(prereg_id: str, structure: str = "kinetic", n: int = 1200, restrict_json: str = "{}") -> str:
    lab.require_preregistration(prereg_id)
    rng = np.random.default_rng(13)
    restrict = json.loads(restrict_json or "{}")
    x = lab.from_unit(lab.lhs(int(n), rng), restrict)
    rank = lab.measurement_value(x, lab.target(lab.evaluate(x, lab.STRUCTURES[structure])), rng)
    lab.record("result", {"experiment": "measurement_value", "prereg": prereg_id, "structure": structure,
                          "restrict": restrict, "ranking": rank})
    return _dump(rank)


def search_counterexamples(prereg_id: str, n: int = 1200) -> str:
    lab.require_preregistration(prereg_id)
    rng = np.random.default_rng(17)
    x = lab.from_unit(lab.lhs(int(n), rng))
    rows = lab.counterexamples(x, lab.target(lab.evaluate(x, lab.STRUCTURES["kinetic"])), rng)
    lab.record("result", {"experiment": "counterexample_search", "prereg": prereg_id, "worlds": rows})
    return _dump(rows)


def run_simulation(prereg_id: str, overrides_json: str = "{}") -> str:
    lab.require_preregistration(prereg_id)
    kw = {**lab.SCENARIO, **json.loads(overrides_json or "{}")}
    out = as_dict(run(Params(**kw)))
    out.pop("profiles", None)
    lab.record("result", {"experiment": "single_run", "prereg": prereg_id, "inputs": kw, "outputs": out})
    return _dump(out)


def run_acceleration_benchmark(prereg_id: str, seeds: int = 3) -> str:
    lab.require_preregistration(prereg_id)
    out = lab.acceleration_benchmark(1500, [50, 100, 200, 400, 800], int(seeds), lab.STRUCTURES["kinetic"])
    lab.record("result", {"experiment": "acceleration_benchmark", "prereg": prereg_id, **out})
    return _dump(out)


def read_research_record(last_n: int = 20) -> str:
    return _dump(lab.read_ledger()[-int(last_n):])


def issue_recommendation(measurement_id: str, rationale: str) -> str:
    m = next(x for x in lab.MEASUREMENTS if x["id"] == measurement_id)
    h = lab.record("recommendation", {"measurement": m, "rationale": rationale, "approved_by": "human (policy gate)"})
    return _dump({"recorded": h, "measurement": m})
