<div align="center">

# 🚦 CI Pipeline Simulator

### Simulate a CI pipeline DAG offline: matrix fan-out, retries, fail-fast vs continue-on-failure, and a deterministic wall-clock timeline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Runner-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

A CI workflow is a small programming language: stages declare dependencies, matrix axes multiply jobs, retries re-run failures, and one failure can cancel everything behind it. This project simulates that language without a runner, a container or a network call.

A pipeline document — **JSON or TOML**, both parsed with the standard library — is validated into a DAG:

```text
checkout ─┬─► lint ─────────────────┐
          ├─► unit[python, os] ×4 ──► integration[shard] ×3 ──► package ──► deploy
          └─► docs ─────────────────────────────────────────────┘
```

**Stages start as soon as their dependencies finish**, so `docs` and `unit` overlap, and the wall clock is the longest dependency chain rather than the sum of everything:

| Run | Wall time | Serial time | Speed-up |
| --- | --: | --: | --: |
| clean, 12 jobs | 130 s | 360 s | 2.77x |

The critical path is computed from the actual spans by dynamic programming over the topological order, then asserted to sum back to the wall clock: `checkout → unit → integration → package → deploy` = 12 + 45 + 30 + 25 + 18 = **130 s**.

**Two failure policies, and the difference is exactly measurable.** Injecting `unit=flaky` and `integration=hard`:

| | success | failed | skipped | cancelled |
| --- | --: | --: | --: | --: |
| fail-fast | 7 | 1 | 0 | 4 |
| continue on failure | 7 | 3 | 2 | 0 |

A failure does not just change one verdict — it decides whether the remaining shards **run and fail** (`cancelled` versus `failed`) and whether blocked stages are **cancelled** or **skipped**. The demo asserts that the two runs disagree on exactly four jobs and no others.

**Retries are modelled, not hand-waved.** A failure has a *mode*:

- `hard` — fails every attempt, up to `retries + 1`, so `integration` with no retries burns exactly one attempt and fails;
- `flaky` — fails the first attempt and passes on the retry, which means the stage costs **two** durations (`unit` goes from `12→57` to `12→102`), and a flaky job on a stage with `retries = 0` degrades to a plain failure.

That last rule is the kind of thing a simulator gets wrong by accident, so it is a first-class test and a demo cross-check.

**Every interesting claim in the report is falsifiable.** Parsing the JSON and the TOML copies must yield the *same* `Pipeline` object; the topological order must place every dependency before its dependent and must be stable across calls; a hand-built two-node cycle must be rejected; matrix jobs must share one start time and one span while costing four times that in serial time; status counts must always total the job count, for every policy and failure combination.

No network, no runner, no Docker, no API keys.

---

# ✨ Features

- Pipeline documents in **JSON and TOML** (`tomllib`), with the bundled pair proven equivalent
- Strict validation: stage names, `needs` lists, duplicate/self dependencies, durations, retries, matrix shape and matrix size
- Cycle detection with the offending stages named
- Kahn topological order with a stable, declaration-order tie-break
- Matrix fan-out to `name[key=value,key=value]` job labels, in cartesian order
- Dependency depth per stage (longest chain of `needs`)
- Deterministic simulated timings: stages start at the latest dependency finish
- `hard` and `flaky` failure injection, per stage or per individual matrix job
- Fail-fast vs continue-on-failure, with `cancelled` distinguished from `skipped`
- Retry accounting that ignores jobs that never ran
- Critical path derived from real spans, verified against the wall clock
- Job table, stage timeline and summary report, plus `--json` and `--save`
- `--fail STAGE=MODE` (repeatable), `--no-fail-fast`, `--quiet`
- Exit code `0` for a passing pipeline, `1` for a failed one, `2` for bad input
- 117 passing pytest tests

---

# 📂 Folder Structure

```text
Ci_Pipeline_Simulator/
│
├── src/
│   ├── main.py       # CLI: --fail, --no-fail-fast, --json, --save
│   └── pipeline.py   # parsing, DAG order, simulation, report, demo
│
├── tests/
│   └── test_pipeline.py
│
├── data/
│   ├── pipeline.json   # 7 stages, 12 jobs, 2 matrix stages
│   └── pipeline.toml   # the same pipeline in TOML
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 24_DevOps/Ci_Pipeline_Simulator

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: three runs, tables, timelines, 15 self-checks
python src/main.py --demo

# Simulate the bundled pipeline
python src/main.py

# A flaky matrix stage: 4 retries, +45 s each
python src/main.py --fail unit=flaky

# A hard failure with fail-fast off: skips instead of cancels
python src/main.py --fail integration=hard --no-fail-fast

# One specific matrix cell fails
python src/main.py --fail "integration[shard=2]=hard"

# Save both the report and the machine-readable run
python src/main.py --fail integration=hard --save report.txt --json run.json
```

**Pipeline document:**

```toml
name = "demo"

[[stages]]
name = "unit"
needs = ["checkout"]
duration = 45          # simulated seconds per attempt
retries = 1

[stages.matrix]
python = ["3.11", "3.12"]
os = ["ubuntu", "windows"]        # 2 x 2 = 4 parallel jobs
```

**Exit codes:** `0` = the pipeline passed · `1` = the pipeline failed (a valid result) · `2` = usage or parse error.

---

# 🧠 How It Works

```text
pipeline.json / pipeline.toml
        │  parse + validate (names, needs, durations, matrix, cycles)
        ▼
   Pipeline(stages)  ──►  topological_order()   Kahn, stable tie-break
        │                       │
        │                       └──► dependency_depth()
        ▼
   simulate(failures, fail_fast)
        │
        ├── stage start = max(finish of its dependencies, default 0)
        ├── matrix jobs all start together; span = one job's runtime
        ├── job_attempts(stage, mode) -> (attempts, passed)
        │        None    -> (1, True)
        │        hard    -> (retries + 1, False)
        │        flaky   -> (2, True) if retries >= 1 else (1, False)
        ├── a failed job with fail_fast aborts the remaining dispatch
        └── a stage with a failed dependency is skipped (or cancelled)
        ▼
   Run(jobs, spans, wall_time, serial_time, critical_path)
        │
        └──► critical_path(): DP over spans, then sum == wall_time
```

Details worth knowing:

- **Dispatch order is topological, not chronological.** `docs` is dispatched in the same wave as `unit`, so it completes even when `integration` fails later — which is what a real scheduler does, and the demo asserts it rather than pretending everything after the failure is cancelled.
- **`cancelled` and `skipped` are different verdicts.** Fail-fast cancels work that was never dispatched; continue-on-failure marks unreachable stages as skipped because their dependency failed. Tests pin both.
- **A cancelled job has `attempts = 0`**, so `retries_used` sums `max(0, attempts - 1)`. The naive sum went negative — a real bug caught by the demo.
- **Parallelism is visible in the numbers**: the `unit` matrix is four jobs that cost 180 s serially but only 45 s on the clock.

---

# 🛠 Technologies

- Python 3 standard library: `tomllib`, `json`, `itertools.product`, `dataclasses`, `argparse`, `pathlib`, `logging`, `contextlib`
- pytest

No runner, no YAML parser, no Docker, no network access.

---

# 📚 Concepts Covered

- Directed acyclic graphs: `needs` edges, topological order, cycle detection
- Kahn's algorithm with a deterministic tie-break
- Matrix expansion as a cartesian product and job-label generation
- Dependency depth as the longest chain of predecessors
- Critical-path analysis over measured spans
- Simulated timing: dependency-driven start times and parallel spans
- Failure semantics: hard vs flaky, retry budgets and exponential-ish cost
- Fail-fast vs continue-on-failure and the `cancelled`/`skipped` distinction
- Invariant testing: status counts always total the job count
- Self-asserting deterministic demos with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**117 tests passed** covering every parse and validation error (document shape, names, `needs`, duplicates, self-dependency, durations, retries, matrix shape/size, unknown dependencies, cycles), JSON/TOML loading and their decode errors, both bundled formats being equivalent, matrix labels and sizes, topological ordering, stability and tie-breaks, dependency depth, every retry rule, clean/failed/cancelled/skipped runs, span and wall-clock invariants, critical paths, determinism, report contents, demo idempotency, and every CLI path including `--fail`, `--no-fail-fast`, `--json`, `--save` and each exit code.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
