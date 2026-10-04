import json

from exuvia import lab, tools

H8 = "f476f8400f8db7da"
RUNS = {
    "H9": ("21a757930c841898", {"oxide_fraction": [0.20, 0.32]}, "top1 equal"),
    "H10": ("ce5c6b6fa0ae987c", {"w_lstrat_mm_s": [0.08, 0.19]}, "top1 equal and top3 set equal"),
}
base = json.loads(tools.rank_measurements(H8, "kinetic", 800))
for h, (pid, restrict, rule) in RUNS.items():
    rk = json.loads(tools.rank_measurements(pid, "kinetic", 800, json.dumps(restrict)))
    top1 = rk[0]["id"] == base[0]["id"]
    top3 = {r["id"] for r in rk[:3]} == {r["id"] for r in base[:3]}
    ok = top1 and (top3 if h == "H10" else True)
    lab.record("verdict", {"hypothesis": h, "prereg": pid, "status": "supported" if ok else "falsified",
                           "evidence": f"restricted {restrict}: top3 {[r['id'] for r in rk[:3]]} "
                                       f"({rk[0]['variance_removed']:.0%}) vs unrestricted {[r['id'] for r in base[:3]]}",
                           "executed_by": "scripts/complete_preregistered.py (agent session halted by cost_budget policy)"})
    print(h, "supported" if ok else "falsified", [r["id"] for r in rk[:3]], rk[0]["variance_removed"])
