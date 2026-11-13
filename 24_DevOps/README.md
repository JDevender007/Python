<div align="center">

# 🛠 DevOps Projects

### Five offline DevOps tools written from scratch: layered config with provenance, log aggregation and alerting, a dependency auditor, a CI pipeline simulator with matrix fan-out and retries, and a release/rollback simulator with health gates and SLO error budgets.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Stdlib](https://img.shields.io/badge/Runtime-Standard%20Library-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

DevOps work is mostly **merging, measuring and deciding**: merge configuration layers, measure logs and pipelines, decide whether a deploy may proceed. Each of those is a small algorithm with a large surface for subtle mistakes — a precedence rule applied in the wrong order, a cancelled job counted as a failure, a retry that hides a hard error, or a rollback that lands on a version which is just as broken as the one it replaced.

This category implements each tool from first principles and proves its claims with numbers:

- **Config_Manager** layers `defaults → file → environment`, validates a declarative schema, coerces string-typed environment values, and reports **per-key provenance** so every final value knows which layer set it.
- **Log_Monitor** parses two log formats (key=value and bracketed), aggregates per-service error rates, raises threshold alerts and ranks the top offenders.
- **Dependency_Checker** parses `requirements.txt` and `pyproject.toml`, compares pinned ranges against locally installed metadata, and classifies every line as ok, conflict, missing or unpinned.
- **Ci_Pipeline_Simulator** validates a pipeline DAG, expands matrix stages, applies `hard` vs `flaky` failures, and reports wall-clock versus serial time plus the critical path — showing exactly how fail-fast and continue-on-failure disagree.
- **Release_Rollback_Simulator** runs a canary, rolling or blue-green ladder against a health gate, drives an explicit state machine, rolls back to the previous release, and prices every soak interval in SLO error budget.

Every project runs on bundled data, finishes its demo in about a second, and **asserts its own claims** — three layers resolving to the identical value still report three different sources, the same broken release costs 62.9% of the error budget as a canary and 704.2% blue-green, and a cancelled job has `attempts = 0` rather than a phantom retry.

---

# 🎯 Learning Objectives

- Implement layered configuration with deterministic precedence and per-key provenance
- Validate a declarative schema and coerce string inputs into typed values
- Distinguish parse errors from policy findings (skip vs fail) in a log pipeline
- Aggregate events per service and turn rates into threshold alerts with minimum sample sizes
- Parse Python requirement specifiers, including operators, extras and environment markers
- Compare declared ranges with installed versions instead of guessing
- Model a CI pipeline as a DAG and validate it before running anything
- Expand matrix stages as a cartesian product of labelled parallel jobs
- Simulate dependency-driven start times and compute a critical path from real spans
- Separate `cancelled` from `skipped` and model retries as attempt budgets
- Design a rollout state machine whose illegal transitions raise
- Price progressive delivery with error budgets, burn rates and alert severities
- Write demos that assert the interesting claim and a negative control, not just "it ran"

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Config_Manager | Layered YAML/JSON/env config with schema validation, type coercion and a per-key provenance report. | ✅
02 | Log_Monitor | Structured + unstructured log parsing, per-service error rates, threshold alerts and a top-offenders ranking. | ✅
03 | Dependency_Checker | Requirement/pyproject parsing checked against installed metadata: ok, conflict, missing, unpinned. | ✅
04 | Ci_Pipeline_Simulator | Pipeline DAG with matrix fan-out, hard/flaky retries, fail-fast vs continue, wall clock and critical path. | ✅
05 | Release_Rollback_Simulator | Canary/rolling/blue-green ladders, health gates, a legal state machine, rollback and SLO burn accounting. | ✅

---

# 💡 Concepts Covered

- Configuration precedence and deep merging of nested mappings
- Dotted-key flattening and the `flatten`/`unflatten` round trip
- Declarative schema validation with required keys, bounds and choice lists
- Type coercion of string inputs (`"9090"`, `"true"`, `"0.25"`) and strict rejection of bad values
- Provenance tracking: which layer produced the final value
- Log line grammars: key=value fields versus bracketed service tags
- Lenient versus strict parsing and error budgets for skipped lines
- Error rates, minimum sample sizes and threshold alerting
- PEP 440 version specifiers, extra/comment/marker handling
- Semantic version comparison between declared ranges and installed metadata
- Directed acyclic graphs, topological order and cycle detection
- Matrix expansion as a cartesian product with derived job labels
- Dependency-driven scheduling and critical-path analysis over measured spans
- Retry semantics: hard failures, flaky failures and attempt budgets
- Fail-fast versus continue-on-failure, and `cancelled` versus `skipped`
- Progressive delivery: canary, rolling and blue-green traffic ladders
- Health gates with ordered failure reasons
- Rollout state machines and rollback onto healthy, unhealthy or absent releases
- SLI/SLO/error budget, multi-window burn rates and alert severity classes

---

# 📁 Repository Structure

```text
24_DevOps/
│
├── Config_Manager/
├── Log_Monitor/
├── Dependency_Checker/
├── Ci_Pipeline_Simulator/
├── Release_Rollback_Simulator/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library module
├── tests/            # pytest test suite
├── data/             # bundled deterministic inputs
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- PyYAML 6.0.3 (config documents only; the pipeline and rollout projects use `json`/`tomllib`)
- Standard library (`json`, `tomllib`, `argparse`, `dataclasses`, `itertools`, `pathlib`, `logging`, `contextlib`, `importlib.metadata`)
- pytest

No Docker, no Kubernetes, no cloud SDK, no CI service, no network access.

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Config Manager | ✅ |
| Log Monitor | ✅ |
| Dependency Checker | ✅ |
| CI Pipeline Simulator | ✅ |
| Release Rollback Simulator | ✅ |

**Completed:** **5 / 5 Projects** · 457 passing tests

---

# ▶️ Quick Start

```bash
cd 24_DevOps/Release_Rollback_Simulator

python src/main.py --demo     # offline, self-checking demo
python -m pytest tests/ -q    # run the tests
```

Each project follows the same shape: `python src/main.py --demo` for a self-checking offline run, `python -m pytest tests/ -q` for the suite. Every demo exits `0`, honours `--quiet`, and prints its cross-checks before `Demo completed successfully.`

---

# 📚 Skills Developed

- Implementing merge, aggregation and scheduling algorithms instead of reaching for a framework
- Reading version specifiers and log grammars with explicit, testable parsers
- Modelling systems as state machines and making illegal states unrepresentable
- Reasoning about time: dependency-driven start times, retries, soak windows, critical paths
- Separating "the operation succeeded" from "the system is healthy"
- Pricing failure in error budget and choosing a rollout strategy from the numbers
- Designing cross-checks that can fail: negative controls, pinned seeds and bounded claims
- Writing 52-165 pytest cases per project, including every error path and CLI flag

---

# 🚀 Key Learning Outcomes

- Build a layered configuration system with schema validation and provenance
- Turn raw logs into per-service rates, alerts and a ranked offender list
- Audit a dependency list against what is actually installed, with precise severities
- Validate and simulate a CI pipeline, and explain why two failure policies differ by four jobs
- Run a rollout through health gates, roll back safely, and quantify the blast radius of an identical mistake

---

# 🔮 Future Enhancements

- Config_Manager: remote layers (etcd/Consul) behind the same precedence contract
- Log_Monitor: streaming ingestion with a bounded memory window and percentile latencies
- Dependency_Checker: resolver backtracking to prove a conflict is unsatisfiable
- Ci_Pipeline_Simulator: resource-constrained scheduling with runner pools and queueing
- Release_Rollback_Simulator: multi-window burn-rate alerts and automated rollback triggers

---

# 🤝 Contributions

Contributions, issues and feature requests are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this category useful, consider giving this repository a star.

</div>
