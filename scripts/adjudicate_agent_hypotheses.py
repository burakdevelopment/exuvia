import json
import math

from exuvia import lab

L = lab.read_ledger()
res = lambda exp, pid: [e["payload"] for e in L if e["payload"].get("experiment") == exp and e["payload"].get("prereg") == pid]

m = res("morris_screening", "f6a7ba3a3a3a225f")[0]
pf = ["r_med_nm", "sigma_g", "oxide_fraction"]
p = max(pf, key=lambda k: m["mu_star"][k]); q = max((k for k in m["mu_star"] if k not in pf), key=lambda k: m["mu_star"][k])
d = m["mu_star"][p] - m["mu_star"][q]
se = math.hypot(m["sigma"][p] / math.sqrt(8), m["sigma"][q] / math.sqrt(8))
h6 = "supported" if d > 2 * se else "falsified" if d < -2 * se else "inconclusive"
lab.record("verdict", {"hypothesis": "H6", "prereg": "f6a7ba3a3a3a225f", "status": h6,
                       "evidence": f"P={p} {m['mu_star'][p]:.3f}, Q={q} {m['mu_star'][q]:.3f}, D={d:.3f}, 2*SE_D={2*se:.3f}: top input not resolved at r=8"})

s = res("structural_comparison", "074d7ec03c6eb8c9")[0]
med = {k: v["activation_ratio_pct"]["p50"] for k, v in s.items() if isinstance(v, dict) and "activation_ratio_pct" in v}
p95 = {k: v["activation_ratio_pct"]["p95"] for k, v in s.items() if isinstance(v, dict) and "activation_ratio_pct" in v}
r50, r95 = max(med.values()) / min(med.values()), max(p95.values()) / min(p95.values())
h7 = "falsified" if r95 <= 5 or r50 > 2.35 else "supported" if r50 < 1.7 else "inconclusive"
lab.record("verdict", {"hypothesis": "H7", "prereg": "074d7ec03c6eb8c9", "status": h7,
                       "evidence": f"R50={r50:.2f}, R95={r95:.2f}; kinetic/instant R95={p95['kinetic']/p95['instant']:.2f}: the no-coating end-member drives the tail"})

rk = {r["structure"]: [x["id"] for x in r["ranking"]] for r in res("measurement_value", "f476f8400f8db7da")}
h8 = "supported" if rk["kinetic"][0] == rk["instant"][0] and set(rk["kinetic"][:3]) == set(rk["instant"][:3]) else "falsified"
lab.record("verdict", {"hypothesis": "H8", "prereg": "f476f8400f8db7da", "status": h8,
                       "evidence": f"kinetic top-3 {rk['kinetic'][:3]}, instant top-3 {rk['instant'][:3]}"})
print("H6", h6, round(d, 3), round(2 * se, 3)); print("H7", h7, round(r50, 2), round(r95, 2)); print("H8", h8, rk["kinetic"][:3], rk["instant"][:3])
