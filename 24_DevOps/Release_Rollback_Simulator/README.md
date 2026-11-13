<div align="center">

# 🚦 Release / Rollback Simulator

### Simulate a canary, rolling or blue-green rollout offline: health gates, a legal state machine, rollback, and SLO error-budget arithmetic.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Cluster-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

A deploy is a state machine wrapped around a bet. You send a version to a slice of traffic, watch a gate, and either promote it or put the old version back. This project simulates that entire loop — no cluster, no Kubernetes, no network — and prices every step in error budget so the blast radius is a number instead of a feeling.

A deployment document lists a service, a gate, an SLO and a release history:

```text
checkout-api   1.4.0 → 1.5.0 → 1.6.0-rc1 → 1.6.0-rc2 → 1.6.0
gate:  errors <= 2%   latency <= 350 ms   saturation <= 0.85
slo :  99.9% over 60 min, 6000 req/min, 5 min soak  =>  360 bad requests
```

**The gate is only half the story; the price is the other half.** Three traffic ladders are supported:

| Strategy | Ladder | Blast radius |
| --- | --- | --- |
| `canary` | 5 → 25 → 50 → 100% | small first step, four gate checks |
| `rolling` | 25 → 50 → 75 → 100% | coarser, three gate checks |
| `blue_green` | 100% | one gate check, everything at once |

Rolling out the same **broken** release (`1.6.0-rc1`, 8.1% errors) under two strategies produces the same verdict and very different bills:

| | canary | blue-green |
| --- | --: | --: |
| bad requests | 121.5 at 5% + 105 for the rollback soak | 2430 at 100% + 105 |
| budget consumed | **62.9%** of the window | **704.2%** of the window |
| peak burn rate | 4.05x (`fast`) | 81.0x (`critical`) |

Both end `rolled_back` — a rollback that works is a *healthy* outcome, and the code says so. Blue-green costs **11.2x** the budget for the identical mistake, which is the entire argument for a canary.

**Budget arithmetic is explicit, not vibes:**

```text
bad_requests = soak_minutes × rpm × traffic_share × error_rate
burn_rate    = bad_requests / (soak_minutes × rpm × (1 - target))
budget_used  = Σ bad_requests / (window_minutes × rpm × (1 - target))
```

At 99.9% over an hour with 6000 req/min, the window allows 360 bad requests and each 5-minute soak at full traffic allows 30 — so a 1x burn is spending exactly the budget, and 81x is not a typo.

**The state machine refuses shortcuts.** `pending → progressing → succeeded` on the happy path; `progressing → failed → rolling_back → rolled_back` when a gate fires. `succeeded → rolling_back` and `pending → succeeded` raise. Rollback only succeeds if the *previous* release passes the same gate, which yields the two hard cases this project exists to model:

- **`1.6.0-rc2`** fails on latency alone (520 ms > 350 ms) at a cost of 6 bad requests — then the rollback soaks `1.6.0-rc1` at full traffic and re-runs the 8.1% error release, costing **676.7%** of the window. The cheap failure is not the cheap outcome.
- **the first release** has nothing to roll back to (`1.4.0`), so a failure there is terminal: `rollback_failed`.

**Every claim in the demo is falsifiable.** The demo asserts the parsed history and the rollback target, all three ladders plus four rejected custom ladders (non-increasing, missing 100%, out of range, descending), one gate failure and one rollback observation, the pinned budgets, the exact transition path and event names, that a latency-only release reports exactly one reason, that a healthy release climbs all four steps inside 13.5% of the window, that a first release cannot roll back, that an illegal transition raises, and that the whole run is deterministic on re-execution.

No network, no cluster, no Docker, no API keys.

---

# ✨ Features

- Deployment documents in JSON, validated field by field (service, release history, duplicates, gate thresholds, SLO bounds)
- Canary, rolling and blue-green traffic ladders plus validated custom ladders
- Three-threshold health gate — error rate, latency, saturation — reporting every reason it failed, in order
- Explicit rollout state machine with a transition history; illegal transitions raise
- Rollback to the previous release, which must itself pass the gate
- `rolled_back` counts as healthy; `rollback_failed` does not
- SLO error-budget accounting per observation: bad requests, burn rate, window percentage
- SRE-style burn-rate alert levels: `ok` / `slow` / `fast` / `critical`
- Failure happens at the first step that trips the gate — later steps are never dispatched
- Deterministic: same document, same result, byte-identical report
- Job table with per-step reasons, plus a summary state line
- `--release`, `--strategy`, `--steps`, `--file`, `--json`, `--quiet`, `--demo`
- Exit codes: `0` healthy, `1` unhealthy, `2` usage or parse error
- 165 passing pytest tests

---

# 📂 Folder Structure

```text
Release_Rollback_Simulator/
│
├── src/
│   ├── main.py       # CLI: --release, --strategy, --steps, --json, --quiet
│   └── rollout.py    # parsing, gate, state machine, SLO burn, report, demo
│
├── tests/
│   └── test_rollout.py
│
├── data/
│   └── deployment.json   # 5 releases, 1 gate, 1 SLO, canary strategy
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 24_DevOps/Release_Rollback_Simulator

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: canary vs blue-green, a healthy climb, 12 self-checks
python src/main.py --demo

# Roll the newest release forward through the bundled ladder
python src/main.py

# A known-bad canary: fails at 5% and rolls back to 1.5.0
python src/main.py --release 1.6.0-rc1

# The same release, promoted all at once
python src/main.py --release 1.6.0-rc1 --strategy blue_green

# A latency-only failure whose rollback target is also bad
python src/main.py --release 1.6.0-rc2

# A custom ladder (must strictly increase and end at 100)
python src/main.py --release 1.6.0 --steps "10,50,100"

# Machine-readable result
python src/main.py --release 1.6.0-rc1 --json rollout.json
```

**Deployment document:**

```json
{
  "service": "checkout-api",
  "strategy": "canary",
  "gate": { "max_error_rate": 0.02, "max_latency_ms": 350, "max_saturation": 0.85 },
  "slo":  { "target": 0.999, "window_minutes": 60,
            "requests_per_minute": 6000, "soak_minutes": 5 },
  "releases": [
    { "version": "1.5.0",     "error_rate": 0.0035, "latency_ms": 238, "saturation": 0.61 },
    { "version": "1.6.0-rc1", "error_rate": 0.081,  "latency_ms": 296, "saturation": 0.74 }
  ]
}
```

**Exit codes:** `0` = healthy (promoted **or** safely rolled back) · `1` = unhealthy (`rollback_failed`) · `2` = usage or parse error.

---

# 🧠 How It Works

```text
deployment.json
      │  parse + validate (service, releases, duplicates, gate, SLO)
      ▼
 Deployment(service, Gate, Slo, releases, strategy)
      │
      ├── plan_steps(strategy) -> (5, 25, 50, 100) | (25,50,75,100) | (100,)
      ▼
 execute(deployment, version)
      │
      ├── observe(release, traffic) ..... gate.failures() + bad_requests + burn
      │        pass  -> next step, or succeeded after the last one
      │        fail  -> failed, then rollback
      │                   ├── previous is None        -> rollback_failed
      │                   ├── previous passes gate    -> rolled_back
      │                   └── previous also fails     -> rollback_failed
      ▼
 RolloutResult(state, observations, transitions, budget_used, peak_burn)
      │
      └──► render_report()  ── steps, reasons, state, budget, HEALTHY/UNHEALTHY
```

Details worth knowing:

- **The rollback soak is a real observation.** Restoring `1.5.0` sends 100% of traffic for one soak interval, so it costs budget and appears in the table. Hiding it would make a rollback look free.
- **A failed rollback is expensive on purpose.** `1.6.0-rc2`'s own failure costs 6 bad requests; the rollback onto `1.6.0-rc1` costs 2430. The simulator charges for both.
- **Everything is deterministic.** No randomness, no clock, no sleeps: the same document produces the same result object, so the tests can compare results directly.
- **Validation happens before the simulation.** A bad ladder or unknown release exits `2` without printing a partial rollout.

---

# 🛠 Technologies

- Python 3 standard library: `json`, `dataclasses`, `argparse`, `pathlib`, `logging`, `contextlib`, `typing`
- pytest

No Kubernetes, no cloud SDK, no network access.

---

# 📚 Concepts Covered

- Progressive delivery: canary vs rolling vs blue-green, and their blast radii
- Health gates as multi-threshold predicates with ordered failure reasons
- An explicit rollout state machine with legal transitions and a history
- Rollback semantics, including rollback onto an unhealthy or absent release
- SLI/SLO/error budget: allowed bad requests, soak windows, budget consumption
- Multi-window burn rates and alert severity classification
- Separation of "did the release work" from "did the deploy leave the service healthy"
- Deterministic simulation and falsifiable cross-checks with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**165 tests passed** covering every parse and validation error (document shape, service, release list, versions, duplicates, error rate, latency, saturation, gate thresholds, SLO target/window/rpm/soak, unknown strategies), JSON loading and its decode errors, the bundled document's exact values, release lookup and `previous()`, all three ladders and every rejected custom ladder, gate reasons and their order, SLO budget and allowance maths, burn-rate alert boundaries, every legal and illegal state transition, promotion and rollback paths, rollback failure with and without a previous release, budget and peak-burn aggregation, determinism, report contents, demo idempotency, and every CLI path including `--release`, `--strategy`, `--steps`, `--json`, `--quiet` and each exit code.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
