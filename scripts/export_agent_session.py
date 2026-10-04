import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
summary = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))
ledger_path = ROOT / "results" / "agent_session_ledger.jsonl"
entries = [json.loads(x) for x in ledger_path.read_text(encoding="utf-8").splitlines() if x.strip()] if ledger_path.exists() else []


def brief(e):
    p = e["payload"]
    if e["kind"] == "preregistration":
        return f"{p['hypothesis']}: {p['statement']} | prediction: {p['prediction']} | falsified if: {p['falsified_if']}"
    if e["kind"] == "verdict":
        return f"{p['hypothesis']} {p['status'].upper()}: {p['evidence']}"
    if e["kind"] == "recommendation":
        return f"{p['measurement']['id']}: {p['measurement']['name']} | {p.get('rationale', '')}"
    exp = p.get("experiment", "")
    if exp == "measurement_value":
        return f"{exp} ({p.get('structure')}): " + ", ".join(f"{r['id']} {r['variance_removed']:.0%}" for r in p["ranking"][:4])
    if exp == "validation_benchmarks":
        return f"{exp}: all_pass={p.get('all_pass')}"
    if exp == "morris_screening":
        mu = p.get("mu_star", {})
        return f"{exp}: top " + ", ".join(f"{k} {v:.2f}" for k, v in sorted(mu.items(), key=lambda kv: -kv[1])[:3])
    if exp == "structural_comparison":
        return f"{exp}: median activation % " + ", ".join(
            f"{k} {v['activation_ratio_pct']['p50']}" for k, v in p.items() if isinstance(v, dict) and "activation_ratio_pct" in v)
    if exp == "counterexample_search":
        return f"{exp}: " + "; ".join(f"{w['world']} -> {w['top']}" for w in p.get("worlds", []))
    if exp == "single_run":
        o = p.get("outputs", {})
        return f"{exp}: activation_ratio={o.get('activation_ratio')}, t50={o.get('arrival_t50_yr')} yr"
    return f"{exp} (prereg {p.get('prereg', '-')})"


verdicts = {e["payload"]["prereg"]: e["payload"] for e in entries if e["kind"] == "verdict"}
summary["agent_hypotheses"] = [
    {"id": e["payload"]["hypothesis"], "hash": e["hash"], "statement": e["payload"]["statement"],
     "prediction": e["payload"]["prediction"], "status": verdicts.get(e["hash"], {}).get("status", "pending"),
     "evidence": verdicts.get(e["hash"], {}).get("evidence", "")}
    for e in entries if e["kind"] == "preregistration"]
gate = [e for e in entries if e["payload"].get("experiment") == "validation_benchmarks"]
if gate:
    summary["agent_hypotheses"][0]["status"] = "supported" if gate[0]["payload"].get("all_pass") else "falsified"
summary["agent_session"] = [{"ts": e["ts"], "kind": e["kind"], "hash": e["hash"], "prev": e["prev"],
                             "prereg": e["payload"].get("prereg"), "text": brief(e)} for e in entries]
(ROOT / "site" / "data.js").write_text("window.LAB_DATA = " + json.dumps(summary, default=str) + ";", encoding="utf-8")
print(f"agent session entries: {len(entries)}")
