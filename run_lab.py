import json
import time

import numpy as np

from exuvia import lab
from exuvia.sim import Params, run


def main(fast: bool = False):
    t_start = time.time()
    if lab.LEDGER.exists():
        lab.LEDGER.unlink()
    rng = np.random.default_rng(42)

    question = ("Which next measurement most reduces the uncertainty in chlorine activation by satellite-reentry "
                "alumina: particle formation, surface chemistry, or atmospheric processing?")
    lab.record("question", {"question": question, "scenario": lab.SCENARIO,
                            "target": "log10 of reentry/background ClONO2+HCl activation rate, 15-30 km, high-latitude column"})
    lab.record("evidence", {"priors": {k: {"range": [v[0], v[1]], "scale": v[2], "source": v[3]}
                                       for k, v in lab.PRIORS.items()}})

    hyps = {
        "H1": ("Rapid mixing: alumina is coated by sulfate quickly, so bare-alumina chemistry contributes little.",
               "Median share of reentry activation on bare alumina < 10% (kinetic coating model).",
               "median bare share >= 10%"),
        "H2": ("Persistent reactive surface: partial coating keeps bare alumina exposed long enough to dominate.",
               "P(bare share > 50%) > 0.5.", "P(bare share > 50%) <= 0.5"),
        "H3": ("Gas availability: HCl coverage limits activation more than the amount of surface.",
               "Morris mu*(theta_hcl) > mu*(r_med_nm).", "mu*(theta_hcl) <= mu*(r_med_nm)"),
        "H4": ("Microphysics: the initial size distribution controls the outcome more than any surface-chemistry rate.",
               "mu*(r_med_nm) is the largest Morris effect and the particle-formation measurement ranks first.",
               "another input has larger mu* or M3 is not ranked first"),
        "H5": ("Transport: the time to reach chemically favourable altitudes controls the outcome.",
               "mu*(w_meso)+mu*(w_lstrat) >= 30% of the largest mu*.", "combined transport mu* < 30% of max"),
    }
    prereg = {h: lab.preregister(h, *v, experiment="Morris screening + structural comparison + preposterior ranking")
              for h, v in hyps.items()}

    lab.record("decision", {
        "step": 1, "options": [
            {"test": "Global sensitivity analysis right away", "expected_learning": "high", "cost_runs": 1000,
             "risk": "results are meaningless if transport is wrong"},
            {"test": "Reproduce published transport benchmarks first", "expected_learning": "medium", "cost_runs": 5,
             "risk": "low"}],
        "chosen": "Reproduce published transport benchmarks first",
        "why": "Cheapest test that can invalidate every later result; gate before spending budget."})
    val = lab.validation_benchmarks()
    lab.record("result", {"experiment": "validation_benchmarks", **val})
    if not val["all_pass"]:
        raise SystemExit("Validation gate failed: stop before drawing conclusions.")

    i4 = run(Params(r_med_nm=4.0, sigma_g=1.05), keep_profiles=True)
    s4 = run(Params(r_med_nm=4.0, sigma_g=1.05, transport="sedimentation_only"), keep_profiles=True)
    reference = run(Params(), keep_profiles=True)

    lab.record("decision", {"step": 2, "chosen": "Morris screening (10 trajectories, kinetic coating)",
                            "why": "Validated transport; next cheapest way to find which of 10 inputs matter."})
    scr = lab.morris_screening(lab.STRUCTURES["kinetic"], trajectories=6 if fast else 10, rng=rng)
    lab.record("result", {"experiment": "morris_screening", **scr})
    mu = scr["mu_star"]
    top = max(mu, key=mu.get)
    negligible = [k for k, v in mu.items() if v < 0.05 * mu[top]]
    lab.record("decision", {"step": 3, "learned": f"largest effect: {top}; negligible: {negligible}",
                            "chosen": "Spend the budget on structural (coating) uncertainty and measurement value; "
                                      "stop refining negligible transport inputs.",
                            "why": "Screening shows where variance lives."})

    n_struct = 400 if fast else 1200
    comp, x, outs = lab.compare_structures(n_struct, rng)
    lab.record("result", {"experiment": "structural_comparison", "n": n_struct, **comp})

    rankings = {name: lab.measurement_value(x, lab.target(out), rng) for name, out in outs.items()}
    lab.record("result", {"experiment": "measurement_value", "rankings": rankings})

    ids = [m["id"] for m in lab.MEASUREMENTS]
    best_by = {s: {r["id"]: r["variance_removed"] for r in rk} for s, rk in rankings.items()}
    regret = {i: max(max(best_by[s].values()) - best_by[s][i] for s in best_by) for i in ids}
    robust = min(regret, key=regret.get)
    per_cost = {s: max(rk, key=lambda r: r["value_per_100k"])["id"] for s, rk in rankings.items()}

    q_kin = lab.target(outs["kinetic"])
    cex = lab.counterexamples(x, q_kin, rng)
    lab.record("result", {"experiment": "counterexample_search", "worlds": cex})

    bare = outs["kinetic"]["activation_bare_share"]
    verdicts = {
        "H1": float(np.median(bare)) < 0.10,
        "H2": float(np.mean(bare > 0.5)) > 0.5,
        "H3": mu["theta_hcl"] > mu["r_med_nm"],
        "H4": top == "r_med_nm" and rankings["kinetic"][0]["id"] == "M3",
        "H5": (mu["w_meso_mm_s"] + mu["w_lstrat_mm_s"]) >= 0.3 * mu[top],
    }
    evidence = {
        "H1": f"median bare share = {np.median(bare):.3f}",
        "H2": f"P(bare share > 0.5) = {np.mean(bare > 0.5):.2f}",
        "H3": f"mu*(theta_hcl) = {mu['theta_hcl']:.2f} vs mu*(r_med_nm) = {mu['r_med_nm']:.2f}",
        "H4": f"largest mu* = {top}; top measurement (kinetic) = {rankings['kinetic'][0]['id']}",
        "H5": f"transport mu* = {mu['w_meso_mm_s'] + mu['w_lstrat_mm_s']:.2f} vs max {mu[top]:.2f}",
    }
    for h in hyps:
        lab.record("verdict", {"hypothesis": h, "prereg": prereg[h],
                               "status": "supported" if verdicts[h] else "falsified", "evidence": evidence[h]})

    bench = lab.acceleration_benchmark(reference_n=1500 if fast else 3000,
                                       budgets=[50, 100, 200, 400, 800], seeds=3 if fast else 5,
                                       structure=lab.STRUCTURES["kinetic"])
    lab.record("result", {"experiment": "acceleration_benchmark", **bench})

    rec = next(m for m in lab.MEASUREMENTS if m["id"] == robust)
    recommendation = {
        "measurement": rec, "robust_choice_min_regret": robust, "regret": regret,
        "best_value_per_cost": per_cost,
        "spec": "Generate alumina particles under reentry-like ablation (plasma wind tunnel, 60-85 km pressure "
                "equivalents) and measure the number size distribution down to ~2 nm (SMPS/TEM) and the Al2O3 vs "
                "metallic-Al fraction. Target precision: median radius within a factor 1.5, oxide fraction +/-0.1.",
        "discriminates": "H4 (microphysics) vs H1/H2 (coating): sets how much surface exists before coating matters.",
        "caveat": "Value is computed inside this reduced-order model and its priors; it is a design assessment "
                  "with hypothetical outcomes, not a measured reduction of physical uncertainty.",
    }
    lab.record("recommendation", recommendation)

    summary = {
        "question": question, "scenario": lab.SCENARIO, "validation": val,
        "reconciliation_curves": {"t_yr": i4.profiles["t_yr"],
                                  "circulation": i4.profiles["ozone_layer_fill_fraction"],
                                  "sedimentation_only": s4.profiles["ozone_layer_fill_fraction"]},
        "reference_profiles": reference.profiles, "screening": scr, "structures": comp,
        "rankings": rankings, "verdicts": {h: {"statement": hyps[h][0], "prediction": hyps[h][1],
                                              "status": "supported" if verdicts[h] else "falsified",
                                              "evidence": evidence[h], "prereg": prereg[h]} for h in hyps},
        "counterexamples": cex, "benchmark": bench, "recommendation": recommendation,
        "ledger": lab.read_ledger(), "runtime_s": round(time.time() - t_start, 1),
        "priors": {k: {"range": [v[0], v[1]], "scale": v[2], "source": v[3]} for k, v in lab.PRIORS.items()},
    }
    (lab.RESULTS / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    site = lab.ROOT / "site"
    site.mkdir(exist_ok=True)
    (site / "data.js").write_text("window.LAB_DATA = " + json.dumps(summary, default=str) + ";", encoding="utf-8")
    print(json.dumps({"validation": val["all_pass"], "top_effect": top, "verdicts": verdicts,
                      "robust_measurement": robust, "per_cost": per_cost,
                      "benchmark": {k: bench[k] for k in ("sims_needed_80pct", "speedup_vs_random", "wall_time_s")},
                      "runtime_s": summary["runtime_s"]}, indent=1))


if __name__ == "__main__":
    import sys
    main(fast="--fast" in sys.argv)
