# Exuvia

Exuvia is a small AI research lab for one specific question: when old satellites burn up in the atmosphere, they leave aluminium oxide dust behind. Can that dust help destroy ozone, and what should scientists measure first to find out?

The name comes from biology. An exuvia is the empty shell an insect leaves behind after it moults. Here, the "shell" is the dust that dying satellites leave in the sky.

I built this for the Hack-Nation 7th Global AI Hackathon, Challenge 3 (Agentic Scientific Discovery, Databricks). The lab runs on Omnigent.

## Why this problem

Thousands of satellites are launched every year, and most of them come back down after about five years. When they re-enter, they burn at 60 to 85 km. Part of their aluminium turns into tiny Al2O3 particles. Alumina is a known surface for the reaction ClONO2 + HCl → Cl2 + HNO3, the same kind of chemistry that causes the ozone hole.

When I read the recent papers, I found three open problems:

1. **Nobody agrees on how fast the dust arrives.** Ferreira et al. (2024) say it takes about 30 years for the particles to fall to the ozone layer. Maloney et al. (2025) include the movement of the air and get 1 to 3 years.
2. **The surface chemistry is missing.** Maloney et al. treat the particles as chemically inert. Barker et al. (2026) assume they are covered by sulfate immediately. Vattioni et al. (2023) show that the reaction rates on alumina are uncertain by almost two orders of magnitude.
3. **Lab data is thin.** Lostier et al. (2026) measured HCl uptake on alumina, but at room temperature, not at stratospheric temperatures.

So instead of guessing one big "ozone loss" number, I asked a more useful question:

> Which measurement should be done next to reduce the uncertainty the most: particle formation, surface chemistry, or how the particles change in the atmosphere?

## How it works

The project has three parts.

**1. A physics model** (`exuvia/sim.py`). It is a 1-D column of the high-latitude atmosphere from 10 to 92.5 km, split into 33 levels, with 8 particle sizes:
- Particles fall by gravity (Stokes settling with the Cunningham slip correction).
- The air also carries them down, and eddy diffusion mixes them.
- Each particle is tracked as either bare alumina or sulfate-coated.
- From the surface area, the model calculates how much extra chlorine activation the particles cause compared with the natural sulfate background.

The system is linear, so one run takes about 10 ms. That makes it possible to run thousands of experiments.

**2. The lab tools** (`exuvia/lab.py`, `exuvia/tools.py`):
- A validation gate against published results.
- Morris screening to find which inputs matter.
- The same inputs run under three different coating models.
- A value-of-information ranking of seven possible measurements.
- A search for "counterexample worlds" where the answer could flip.
- A benchmark that compares the agent strategy with random sampling.

Every step is written to a hash-chained research record (`results/ledger.jsonl`), so you can check the full history.

**3. The agents** (`omnigent_lab/`). Five agents run on Omnigent:

| Agent | What it decides |
|---|---|
| PI | Runs the loop and decides the next step after each result |
| Researcher | Checks that every input range has a real source |
| Planner | Suggests at least two tests, picks one and pre-registers it with a prediction |
| Runner | Runs exactly the pre-registered experiment on the solver |
| Critic | Checks the result and accepts it, rejects it or asks for a new test |

The agents never write numbers themselves. They can only call the solver through tools. Four Omnigent policies control them:
- `preregistration_gate` blocks any experiment that was not pre-registered with a prediction.
- `human_approval` asks a scientist before a recommendation leaves the lab.
- `cost_budget` caps spending at $5 and asks for approval at $3.
- `max_tool_calls_per_session` caps a session at 120 tool calls.

## Results

### The model passes the validation gate

| Check | Published value | My model |
|---|---|---|
| Alumina at 10-30 km for 10 kt/yr (Maloney 2025), used for calibration | 20-40 kt | 24.0 kt |
| Time to reach the ozone layer with air movement (Maloney 2025) | 1-3 years | half-way after 2.1 years |
| Bigger particles give a smaller load (Maloney 2025) | yes | 14.2 kt (100 nm) vs 24.0 kt (10 nm) |
| Time by falling only, 4 nm particles (Ferreira 2024) | about 30 years | 10% after 22 years, half-way after 65 |

Only one parameter was calibrated (the descent speed in the lower stratosphere). The other checks were held out.

### Why the two papers disagree

It is the transport assumption. The same 4 nm particles reach the ozone layer half-way after 2.6 years once the air movement is included. With falling alone, it takes decades.

### How big is the effect?

For the 2040 megaconstellation scenario, the extra chlorine activation at 15-30 km is:

| Coating model | Median | 5-95% range |
|---|---|---|
| Gradual coating | about 1% of the natural background | 0.04-22% |
| Instant coating | about 0.8% | 0.03-15% |
| Never coated | about 1.5% | 0.01-153% |

The median is small. The tail is wide, and the tail is where the coating assumption matters.

### What to measure next

| Measurement | Uncertainty removed (gradual / instant / never coated) |
|---|---|
| **M3: particle size and oxide fraction from reentry-like ablation (plasma wind tunnel)** | **65% / 72% / 36%** |
| M5: aircraft sampling in the polar lower stratosphere | 12% / 25% / 3% |
| M2: coating speed of sulfate on nano-alumina | 9% / 19% / 2% |
| M1: reaction rate on bare alumina at cold temperature | 3% / 0% / 35% |

The recommendation is **M3**. It has zero regret across the three coating models, and it stays first in every stress test I tried. The "obvious" choice, measuring the cold reaction rate (M1), only becomes useful if the particles are never coated.

### Hypotheses

Every hypothesis was pre-registered before it ran. H1 to H5 come from the reference run. G1 and H6 to H10 were written by the agents themselves during the live Omnigent session.

| | Hypothesis | Result |
|---|---|---|
| H1 | Fast sulfate coating makes bare-alumina chemistry minor | supported (median share on bare alumina 6%) |
| H2 | Bare alumina dominates | falsified |
| H3 | HCl availability is the limit | falsified |
| H4 | Particle size is the single top driver | falsified (it is tied with mixing state) |
| H5 | Transport timing controls the amount | falsified (it controls *when*, not *how much*) |
| G1 | The solver reproduces the published benchmarks | supported (plus 9 extra checks by the critic) |
| H6 | Particle formation leads the screening | inconclusive (the lead is inside the error bars) |
| H7 | The coating choice matters only in the tail | inconclusive (the tail is driven by the "never coated" case) |
| H8 | The recommendation does not depend on the coating model | supported |
| H9 | The recommendation survives the poorly sourced oxide fraction | supported |
| H10 | The recommendation survives the critic's calibration finding | supported |

Two things from the agent session surprised me:

- **The critic found a problem in my own input range.** I gave the lower-stratosphere descent speed a range of 0.075-0.3 mm/s, but the calibration only passes up to about 0.19 mm/s. The planner then opened H10 to test whether this changes the answer. It does not.
- **The researcher flagged a weak source.** The oxide fraction is only backed by data between 0.20 and 0.32, which led to H9.

The live session was stopped by my own `cost_budget` policy when spending passed $3, so the governance worked. I then ran H9 and H10 exactly as the agents had pre-registered them (`scripts/complete_preregistered.py`). After that, I judged H6 to H8 with the agents' own decision rules (`scripts/adjudicate_agent_hypotheses.py`).

### Did it make discovery faster?

To be honest, not in the number of solver runs: the speedup was **1.0×**. Because the solver takes only 10 ms per run, random sampling, Latin hypercube sampling and the agent strategy all needed about 200 runs to find the right decision.

The real gain is the workflow. The full loop ran in about 4 minutes on a laptop: validation, screening, three structural models, a ranking of seven measurements, stress tests and a complete record of every decision. In the literature, the transport question took two papers and about nine months. With a slow 3-D model, where one run takes hours, the screening and planning steps would save much more.

## Try it

The website has an interactive simulator. It is a JavaScript copy of the Python model, so you can change the particle size, coating time, reactivity and so on, and see the result straight away. I checked it against the Python version on five cases: the steady-state results are the same, and the arrival times differ by less than 1%.

```bash
cd site
python -m http.server 8766
```

Then open http://localhost:8766.

## Run it yourself

```bash
pip install -e .
python run_lab.py
```

This runs the full reference loop (about 4 minutes) and writes `results/summary.json`, `results/ledger.jsonl` and `site/data.js`.

To run the agents:

```bash
uv tool install omnigent
uv pip install --python <path to the omnigent tool python> -e .
python scripts/build_omnigent_agents.py
omnigent run omnigent_lab
```

The agents use the `claude-sdk` harness, so you need a Claude subscription or an API key configured in Omnigent (`omnigent setup`).

Notes for Windows (Omnigent 0.16):
- Set `PYTHONUTF8=1`. Without it, the host process crashes on Turkish and other non-UTF-8 console code pages.
- Local Python tools use `pass_fds`, which only works on Linux and macOS. I switched them to Omnigent's own stdout protocol by adding `or sys.platform == "win32"` to the `use_stdout` line in `omnigent/tools/local.py`. On Linux, macOS or WSL nothing needs to change.

## Project structure

```
exuvia/            physics model, lab methods, agent tools, policies
omnigent_lab/      Omnigent agent configs (PI + 4 sub-agents) and tool wrappers
scripts/           agent build, session export, completion of pre-registered tests
results/           summary, reference ledger, agent session ledger
site/              website and in-browser simulator
run_lab.py         reference discovery loop
```

## Limitations

- It is a 1-D model, so there is no 3-D transport and no coagulation. The outputs are chlorine activation indicators, not a global ozone loss number.
- The model is calibrated against another model, not against real observations.
- The surface chemistry inputs come from very few lab studies, and some were measured at room temperature.
- The value of each measurement is a design estimate with hypothetical outcomes. Running more simulations does not reduce the real physical uncertainty.
- Before anyone uses this for real decisions, the ranking should be checked again with a full chemistry-climate model that includes surface chemistry on reentry particles.

## References

- Ferreira, J. P. et al. (2024). Potential ozone depletion from satellite demise during atmospheric reentry in the era of mega-constellations. *Geophysical Research Letters*. doi:10.1029/2024GL109280
- Maloney, C. M., Portmann, R. W., Ross, M. N., Rosenlof, K. H. (2025). Investigating the potential atmospheric accumulation and radiative impact of the coming increase in satellite reentry frequency. *JGR Atmospheres*. doi:10.1029/2024JD042442
- Barker, C. et al. (2026). Radiative forcing and ozone depletion of a decade of satellite megaconstellation missions. *Earth's Future*. doi:10.1029/2025EF007229
- Vattioni, S. et al. (2023). Chemical impact of stratospheric alumina particle injection for solar radiation modification and related uncertainties. *Geophysical Research Letters*.
- Lostier, A. et al. (2026). Uptake of stratospheric species on minerals proposed for stratospheric aerosol injection. *ACS Earth and Space Chemistry*. doi:10.1021/acsearthspacechem.6c00142
- Murphy, D. M. et al. (2023). Metals from spacecraft reentry in stratospheric aerosol particles. *PNAS*.
- Molina, M. J. et al. (1997). Reaction of ClONO2 with HCl on aluminum oxide. *Geophysical Research Letters*.

## License

MIT
