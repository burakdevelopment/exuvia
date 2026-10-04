from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "omnigent_lab"

WRAP = '''import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[{depth}]))
from omnigent_client import tool
from exuvia import tools as _t


@tool
def {name}({sig}) -> str:
    """{doc}"""
    return _t.{name}({args})
'''

TOOLS = {
    "list_evidence": ("", "", "Uncertain inputs with ranges and primary sources, plus candidate next measurements."),
    "preregister_hypothesis": (
        "hypothesis_id: str, statement: str, prediction: str, falsified_if: str, experiment: str",
        "hypothesis_id, statement, prediction, falsified_if, experiment",
        "Pre-register a hypothesis with a quantitative prediction and falsification rule; returns prereg_id."),
    "run_validation": ("prereg_id: str", "prereg_id",
                       "Reproduce published transport benchmarks (Maloney+2025, Ferreira+2024) and numerical checks."),
    "run_screening": ("prereg_id: str, trajectories: int = 8, structure: str = 'kinetic'",
                      "prereg_id, trajectories, structure",
                      "Morris screening of all uncertain inputs on the chlorine-activation target."),
    "compare_coating_models": ("prereg_id: str, n: int = 600", "prereg_id, n",
                               "Run identical inputs through instant / kinetic / no-coating models."),
    "rank_measurements": ("prereg_id: str, structure: str = 'kinetic', n: int = 1200, restrict_json: str = '{}'",
                          "prereg_id, structure, n, restrict_json",
                          "Preposterior value (variance removed, per cost) of each candidate measurement."),
    "search_counterexamples": ("prereg_id: str, n: int = 1200", "prereg_id, n",
                               "Find plausible sub-worlds where the recommended measurement changes."),
    "run_simulation": ("prereg_id: str, overrides_json: str = '{}'", "prereg_id, overrides_json",
                       "Single solver run with JSON parameter overrides."),
    "run_acceleration_benchmark": ("prereg_id: str, seeds: int = 3", "prereg_id, seeds",
                                   "Simulations needed by random / LHS / screen-then-focus to recover the reference decision."),
    "read_research_record": ("last_n: int = 20", "last_n", "Read the last entries of the hash-chained research ledger."),
    "issue_recommendation": ("measurement_id: str, rationale: str", "measurement_id, rationale",
                             "Publish the next-measurement recommendation (human approval required)."),
}

SUB = {
    "researcher": (
        "Source researcher. Owns the evidence decision: is every input range traceable to a primary source?",
        ["list_evidence", "read_research_record"],
        "You are the lab's source researcher. Call list_evidence, check every prior range against its cited source, "
        "flag ranges that rest on extrapolation (e.g. 296 K lab data used at 200 K) and report a short evidence "
        "table: parameter, range, source, confidence (high/medium/low). Never invent a number; if a source is "
        "missing say so. Always write in English."),
    "planner": (
        "Experiment planner. Owns the 'what next' decision under a simulation budget.",
        ["read_research_record", "preregister_hypothesis"],
        "You are the experiment planner. Read the research record. For the current question propose at least two "
        "candidate tests, score each on expected learning, feasibility and cost (number of solver runs), choose one "
        "and pre-register the hypothesis it tests (prediction + falsification rule). Return the prereg_id and your "
        "rationale. Budget: 15,000 solver runs per session. Always write in English."),
    "runner": (
        "Experiment runner. Executes solver experiments exactly as pre-registered.",
        ["run_validation", "run_screening", "compare_coating_models", "rank_measurements", "run_simulation",
         "run_acceleration_benchmark", "read_research_record"],
        "You are the experiment runner. Run only the experiment named in the pre-registration you are given, with "
        "the given prereg_id. Report the raw numbers returned by the tool; do not round away uncertainty and never "
        "write a number that did not come from a tool result. Always write in English."),
    "critic": (
        "Critic. Owns accept / reject of results.",
        ["read_research_record", "run_simulation", "search_counterexamples"],
        "You are the critic. For each new result check: units, mass balance, whether the validation gate passed, "
        "whether the conclusion depends on one structural assumption (coating model), and search for "
        "counterexamples. Answer ACCEPT, REJECT or NEW-EXPERIMENT with a one-paragraph reason. Always write in English."),
}

PI = """spec_version: 1
name: exuvia
description: >-
  Agentic lab that finds which measurement most reduces the uncertainty in chlorine activation by
  satellite-reentry alumina. Agents choose experiments; a validated reduced-order solver produces every number.

executor:
  type: omnigent
  config:
    harness: claude-sdk

prompt: |
  You are the principal investigator of Exuvia, an AI lab for satellite-reentry alumina.
  Scientific question: which next measurement most reduces the uncertainty in heterogeneous chlorine
  activation (ClONO2 + HCl on bare / sulfate-coated alumina, 15-30 km) caused by satellite-reentry alumina:
  particle formation, surface chemistry, or atmospheric processing?

  Run the discovery loop: question -> evidence -> hypothesis -> experiment -> result -> updated decision.
  1. Ask `researcher` for the evidence table (sources and confidence of every input range).
  2. Ask `planner` to propose >=2 candidate tests, choose one by expected learning / feasibility / cost and
     pre-register it. The first test must be the validation gate (run_validation); if it fails, stop.
  3. Ask `runner` to execute exactly the pre-registered experiment with its prereg_id.
  4. Ask `critic` to ACCEPT / REJECT / request a NEW-EXPERIMENT. Independent experiments may run in parallel.
  5. After each accepted result write one sentence: what we learned and how it changes the next decision.
     Let surprising results reopen earlier assumptions.
  6. Finish with a ranked measurement recommendation that is robust across coating models, then call
     issue_recommendation (a human scientist must approve it).
  Always write in English. Rules: every number must come from a tool result; label agent-generated hypotheses; keep uncertainty;
  state what validation is still needed before real-world use.

tools:
  agents:
    - researcher
    - planner
    - runner
    - critic

guardrails:
  ask_timeout: 3600
  policies:
    preregistration_gate:
      type: function
      on: [tool_call]
      function:
        path: exuvia.policies.preregistration_gate
    human_approval:
      type: function
      on: [tool_call]
      function:
        path: exuvia.policies.approve_recommendations
    cap_calls:
      type: function
      function:
        path: omnigent.policies.builtins.safety.max_tool_calls_per_session
        arguments:
          limit: 120
    budget:
      type: function
      function:
        path: omnigent.policies.builtins.cost.cost_budget
        arguments:
          max_cost_usd: 5.0
          ask_thresholds_usd: [3.0]
"""


def wrappers(d: Path, names, depth: int):
    p = d / "tools" / "python"
    p.mkdir(parents=True, exist_ok=True)
    for n in names:
        sig, args, doc = TOOLS[n]
        (p / f"{n}.py").write_text(WRAP.format(name=n, sig=sig, args=args, doc=doc, depth=depth), encoding="utf-8")


def main():
    for name, (desc, tools, prompt) in SUB.items():
        d = ROOT / "agents" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.yaml").write_text(
            f"spec_version: 1\nname: {name}\ndescription: >-\n  {desc}\nexecutor:\n  type: omnigent\n  config:\n"
            f"    harness: claude-sdk\nprompt: |\n  {prompt}\n", encoding="utf-8")
        wrappers(d, tools, 5)
    (ROOT / "config.yaml").write_text(PI, encoding="utf-8")
    wrappers(ROOT, ["read_research_record", "issue_recommendation", "list_evidence"], 3)
    print("written:", sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("*.yaml")))


if __name__ == "__main__":
    main()
