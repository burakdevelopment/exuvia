from __future__ import annotations

import hashlib
import os
import json
import time
from pathlib import Path

import numpy as np

from .sim import Params, run, as_dict

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
LEDGER = Path(os.environ.get("EXUVIA_LEDGER", RESULTS / "ledger.jsonl"))

PRIORS = {
    "r_med_nm": (2.0, 200.0, "log", "Ferreira+2024 GRL: ~4 nm AlO clusters (MD); Maloney+2025 JGR brackets 0.01-1.7 um"),
    "sigma_g": (1.3, 2.0, "lin", "lognormal width; unconstrained for reentry particles"),
    "oxide_fraction": (0.2, 1.0, "lin", "Ferreira+2024: ~20-32% of Al oxidised; ESA 2026 workshop: metallic Al with oxide shell also found"),
    "w_meso_mm_s": (0.5, 10.0, "log", "polar-winter mesospheric descent (Maloney+2025 transport argument)"),
    "w_lstrat_mm_s": (0.075, 0.3, "log", "calibrated 0.15 mm/s on Maloney+2025 10-30 km burden; +/- factor 2"),
    "tau_coat_days": (1.0, 1000.0, "log", "Barker+2026 assumes immediate uptake into sulfate; Vattioni+2023 partial coating; Murphy+2023 metals inside H2SO4 particles"),
    "p_sep": (0.0, 1.0, "lin", "coated particle stays separate (adds SAD) vs absorbed into existing droplet; unconstrained"),
    "gamma_alu": (1e-4, 3e-2, "log", "Molina+1997 ~0.02 near 210 K; Vattioni+2023: ~2 orders of magnitude extrapolation uncertainty"),
    "theta_hcl": (0.05, 1.0, "lin", "Lostier+2026 ACS ESC: HCl coverage differs by orders of magnitude between minerals (296 K)"),
    "gamma_sulf": (1e-4, 1e-2, "log", "ClONO2+HCl on cold sulfate in polar lower stratosphere (JPL evaluation range)"),
}
NAMES = list(PRIORS)
SCENARIO = {"al_ablated_gg_per_yr": 0.912}

MEASUREMENTS = [
    {"id": "M1", "kind": "lab", "cost_k": 150,
     "name": "Cold (195-220 K) ClONO2+HCl reaction probability and Cl2 yield on bare alumina",
     "constrains": {"gamma_alu": ("factor", 1.5)}},
    {"id": "M2", "kind": "lab", "cost_k": 250,
     "name": "H2SO4 coating kinetics on nano-alumina, bare vs partially coated (flow tube)",
     "constrains": {"tau_coat_days": ("factor", 2.0), "p_sep": ("abs", 0.2)}},
    {"id": "M3", "kind": "lab", "cost_k": 400,
     "name": "Reentry-analog ablation particles: size distribution and oxide fraction (plasma wind tunnel)",
     "constrains": {"r_med_nm": ("factor", 1.5), "sigma_g": ("abs", 0.1), "oxide_fraction": ("abs", 0.1)}},
    {"id": "M4", "kind": "lab", "cost_k": 100,
     "name": "HCl surface coverage on alumina at stratospheric T and p(HCl)",
     "constrains": {"theta_hcl": ("abs", 0.1)}},
    {"id": "M5", "kind": "field", "cost_k": 2500,
     "name": "Polar lower-stratosphere aircraft single-particle mass spectrometry (mixing state + size)",
     "constrains": {"p_sep": ("abs", 0.15), "tau_coat_days": ("factor", 3.0), "w_lstrat_mm_s": ("factor", 1.3)}},
    {"id": "M6", "kind": "analysis", "cost_k": 80,
     "name": "Mesospheric descent rate from satellite tracers / reanalysis",
     "constrains": {"w_meso_mm_s": ("factor", 1.3)}},
    {"id": "M7", "kind": "lab", "cost_k": 100,
     "name": "Re-evaluation of ClONO2+HCl on cold sulfate",
     "constrains": {"gamma_sulf": ("factor", 1.5)}},
]


def _last_hash() -> str:
    if not LEDGER.exists():
        return "genesis"
    lines = LEDGER.read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[-1])["hash"] if lines else "genesis"


def record(kind: str, payload: dict) -> str:
    RESULTS.mkdir(exist_ok=True)
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "payload": payload, "prev": _last_hash()}
    entry["hash"] = hashlib.sha256(json.dumps(entry, sort_keys=True, default=str).encode()).hexdigest()[:16]
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return entry["hash"]


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]


def preregister(hypothesis_id: str, statement: str, prediction: str, falsified_if: str, experiment: str) -> str:
    return record("preregistration", {"hypothesis": hypothesis_id, "statement": statement,
                                      "prediction": prediction, "falsified_if": falsified_if,
                                      "experiment": experiment})


def require_preregistration(prereg_id: str) -> dict:
    for e in read_ledger():
        if e["hash"] == prereg_id and e["kind"] == "preregistration":
            return e
    raise PermissionError(f"Experiment blocked: '{prereg_id}' is not a pre-registered hypothesis in the ledger.")


def from_unit(u: np.ndarray, restrict: dict | None = None) -> np.ndarray:
    x = np.empty_like(u, dtype=float)
    for j, n in enumerate(NAMES):
        lo, hi, sc, _ = PRIORS[n]
        if restrict and n in restrict:
            lo, hi = restrict[n]
        x[:, j] = np.exp(np.log(lo) + u[:, j] * np.log(hi / lo)) if sc == "log" else lo + u[:, j] * (hi - lo)
    return x


def lhs(n: int, rng: np.random.Generator, d: int | None = None) -> np.ndarray:
    d = d or len(NAMES)
    perm = np.argsort(rng.random((n, d)), axis=0)
    return (perm + rng.random((n, d))) / n


def simulate(theta: np.ndarray, structure: dict, scenario: dict | None = None, fixed: dict | None = None):
    kw = {**(scenario or SCENARIO), **structure, **dict(zip(NAMES, map(float, theta))), **(fixed or {})}
    return run(Params(**kw))


def evaluate(x: np.ndarray, structure: dict, scenario: dict | None = None) -> dict[str, np.ndarray]:
    rows = [as_dict(simulate(t, structure, scenario)) for t in x]
    keys = [k for k in rows[0] if k != "profiles"]
    return {k: np.array([r[k] for r in rows], dtype=float) for k in keys}


def target(out: dict[str, np.ndarray]) -> np.ndarray:
    return np.log10(np.maximum(out["activation_ratio"], 1e-12))


def morris_screening(structure: dict, trajectories: int, rng: np.random.Generator, levels: int = 4):
    d = len(NAMES)
    delta = levels / (2 * (levels - 1))
    base_grid = np.arange(levels // 2) / (levels - 1)
    effects = [[] for _ in range(d)]
    runs = 0
    for _ in range(trajectories):
        u = rng.choice(base_grid, size=d)
        y0 = target(evaluate(from_unit(u[None]), structure))[0]
        runs += 1
        for j in rng.permutation(d):
            u2 = u.copy()
            u2[j] += delta
            y1 = target(evaluate(from_unit(u2[None]), structure))[0]
            runs += 1
            effects[j].append((y1 - y0) / delta)
            u, y0 = u2, y1
    mu_star = np.array([np.mean(np.abs(e)) for e in effects])
    sigma = np.array([np.std(e) for e in effects])
    return {"runs": runs, "mu_star": dict(zip(NAMES, mu_star.round(4).tolist())),
            "sigma": dict(zip(NAMES, sigma.round(4).tolist()))}


def _distance(x: np.ndarray, t: int, constrains: dict) -> np.ndarray:
    d2 = np.zeros(len(x))
    for p, (kind, w) in constrains.items():
        j = NAMES.index(p)
        dj = (np.log(x[:, j]) - np.log(x[t, j])) / np.log(w) if kind == "factor" else (x[:, j] - x[t, j]) / w
        d2 = np.maximum(d2, np.abs(dj))
    return d2


def measurement_value(x: np.ndarray, q: np.ndarray, rng: np.random.Generator,
                      n_truth: int = 150, k_min: int = 25) -> list[dict]:
    var0 = float(q.var())
    truths = rng.choice(len(q), size=min(n_truth, len(q)), replace=False)
    out = []
    for m in MEASUREMENTS:
        post = []
        for t in truths:
            dist = _distance(x, t, m["constrains"])
            idx = np.where(dist <= 1.0)[0]
            if idx.size < k_min:
                idx = np.argsort(dist)[:k_min]
            post.append(q[idx].var())
        ev = float(np.mean(post))
        frac = max(0.0, 1 - ev / var0)
        out.append({"id": m["id"], "name": m["name"], "kind": m["kind"], "cost_k": m["cost_k"],
                    "variance_removed": round(frac, 4),
                    "info_gain_bits": round(0.5 * np.log2(var0 / max(ev, 1e-12)), 4),
                    "value_per_100k": round(frac / (m["cost_k"] / 100), 4)})
    return sorted(out, key=lambda r: -r["variance_removed"])


STRUCTURES = {
    "kinetic": {"transport": "circulation", "coating": "kinetic"},
    "instant": {"transport": "circulation", "coating": "instant"},
    "none": {"transport": "circulation", "coating": "none"},
}


def summarize(v: np.ndarray) -> dict:
    p = np.percentile(v, [5, 25, 50, 75, 95])
    return dict(zip(["p5", "p25", "p50", "p75", "p95"], [float(f"{a:.4g}") for a in p]))


def validation_benchmarks() -> dict:
    checks = []
    a = run(Params(alumina_gg_per_yr=10.0, r_med_nm=10.0))
    checks.append({"id": "V1", "reference": "Maloney+2025 JGR: 20-40 Gg Al2O3 at 10-30 km for 10 Gg/yr (calibration target)",
                   "model": round(a.burden_10_30km_gg, 1), "unit": "Gg", "pass": 20 <= a.burden_10_30km_gg <= 40,
                   "role": "calibration"})
    checks.append({"id": "V2", "reference": "Maloney+2025 JGR: reaches ozone-layer altitudes in 1-3 yr with circulation (held out)",
                   "model": f"t10={a.arrival_t10_yr:.2f} yr, t50={a.arrival_t50_yr:.2f} yr", "unit": "yr",
                   "pass": 0.5 <= a.arrival_t50_yr <= 3.0, "role": "validation"})
    big = run(Params(alumina_gg_per_yr=10.0, r_med_nm=100.0))
    checks.append({"id": "V3", "reference": "Maloney+2025 JGR: larger aerosol -> smaller stratospheric burden (held out, qualitative)",
                   "model": f"{big.burden_10_30km_gg:.1f} Gg (100 nm) < {a.burden_10_30km_gg:.1f} Gg (10 nm)",
                   "unit": "Gg", "pass": big.burden_10_30km_gg < a.burden_10_30km_gg, "role": "validation"})
    f = run(Params(r_med_nm=4.0, sigma_g=1.05, transport="sedimentation_only"))
    checks.append({"id": "V4", "reference": "Ferreira+2024 GRL: ~30 yr for 4 nm particles by sedimentation alone (held out)",
                   "model": f"t10={f.arrival_t10_yr:.1f} yr, t50={f.arrival_t50_yr:.1f} yr", "unit": "yr",
                   "pass": f.arrival_t10_yr <= 30 <= f.arrival_t50_yr * 1.5, "role": "validation"})
    d = run(Params())
    expected_total = d.alumina_gg_per_yr
    checks.append({"id": "N1", "reference": "Mass balance: burden / input flux = mean residence time (positive, finite)",
                   "model": f"{d.burden_total_gg / expected_total:.2f} yr", "unit": "yr",
                   "pass": 0.1 < d.burden_total_gg / expected_total < 20, "role": "numerics"})
    return {"checks": checks, "all_pass": all(c["pass"] for c in checks),
            "reconciliation": "Sedimentation-only transport (Ferreira) vs residual circulation (Maloney) explains "
                              f"the published 30 yr vs 1-3 yr gap: same 4 nm particles arrive with t50 "
                              f"{run(Params(r_med_nm=4.0, sigma_g=1.05)).arrival_t50_yr:.1f} yr once descent is included."}


def compare_structures(n: int, rng: np.random.Generator) -> tuple[dict, np.ndarray, dict]:
    x = from_unit(lhs(n, rng))
    res, outs = {}, {}
    for name, st in STRUCTURES.items():
        out = evaluate(x, st)
        outs[name] = out
        res[name] = {"activation_ratio_pct": summarize(100 * out["activation_ratio"]),
                     "bare_share": summarize(out["activation_bare_share"]),
                     "exposed_fraction": summarize(out["exposed_fraction_ozone_layer"]),
                     "burden_10_30km_gg": summarize(out["burden_10_30km_gg"])}
    return res, x, outs


def counterexamples(x: np.ndarray, q: np.ndarray, rng: np.random.Generator) -> list[dict]:
    j_tau, j_gam = NAMES.index("tau_coat_days"), NAMES.index("gamma_alu")
    worlds = {
        "fast coating (tau < 10 d, Barker-like)": x[:, j_tau] < 10,
        "slow coating (tau > 100 d)": x[:, j_tau] > 100,
        "low bare reactivity (gamma_alu < 1e-3)": x[:, j_gam] < 1e-3,
        "high bare reactivity (gamma_alu > 5e-3)": x[:, j_gam] > 5e-3,
    }
    rows = []
    for label, mask in worlds.items():
        if mask.sum() < 80:
            continue
        rank = measurement_value(x[mask], q[mask], rng, n_truth=80, k_min=15)
        rows.append({"world": label, "n": int(mask.sum()), "top": rank[0]["id"],
                     "ranking": [r["id"] for r in rank[:4]],
                     "variance_removed_top": rank[0]["variance_removed"]})
    return rows


def _ranking(x, q, seed):
    return [r["id"] for r in measurement_value(x, q, np.random.default_rng(seed), n_truth=80, k_min=15)]


def acceleration_benchmark(reference_n: int, budgets: list[int], seeds: int, structure: dict) -> dict:
    t0 = time.perf_counter()
    rng = np.random.default_rng(0)
    xr = from_unit(lhs(reference_n, rng))
    ref = _ranking(xr, target(evaluate(xr, structure)), 1)
    stats = {"random": {}, "lhs": {}, "screen_then_focus": {}}
    sims = {k: {} for k in stats}
    for s in range(seeds):
        rng = np.random.default_rng(100 + s)
        pool_u = rng.random((max(budgets), len(NAMES)))
        pool_x = from_unit(pool_u)
        pool_q = target(evaluate(pool_x, structure))
        scr = morris_screening(structure, trajectories=4, rng=rng)
        mu = np.array(list(scr["mu_star"].values()))
        active = mu >= 0.05 * mu.max()
        focus_u = rng.random((max(budgets), len(NAMES)))
        focus_u[:, ~active] = 0.5
        focus_x = from_unit(focus_u)
        focus_q = target(evaluate(focus_x, structure))
        for b in budgets:
            ux = from_unit(lhs(b, rng))
            cand = {"random": (pool_x[:b], pool_q[:b], b),
                    "lhs": (ux, target(evaluate(ux, structure)), b),
                    "screen_then_focus": (focus_x[:b - scr["runs"]], focus_q[:b - scr["runs"]], b)}
            for k, (xx, qq, cost) in cand.items():
                if len(qq) < 20:
                    stats[k].setdefault(b, []).append(False)
                    continue
                rk = _ranking(xx, qq, 1)
                ok = rk[0] == ref[0] and set(rk[:3]) == set(ref[:3])
                stats[k].setdefault(b, []).append(ok)
    curve = {k: {b: float(np.mean(v)) for b, v in d.items()} for k, d in stats.items()}

    def needed(k):
        for b in budgets:
            if curve[k][b] >= 0.8:
                return b
        return None
    need = {k: needed(k) for k in curve}
    speedup = (need["random"] / need["screen_then_focus"]
               if need["random"] and need["screen_then_focus"] else None)
    return {"reference_ranking": ref, "reference_n": reference_n, "success_rate": curve,
            "sims_needed_80pct": need, "speedup_vs_random": speedup,
            "wall_time_s": round(time.perf_counter() - t0, 1),
            "criterion": "top-1 measurement and top-3 set match the 3000-run reference in >=80% of seeds"}
