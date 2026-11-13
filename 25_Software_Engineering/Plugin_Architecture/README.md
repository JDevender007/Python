<div align="center">

# 🔌 Plugin Architecture

### Dynamic plugin discovery with lifecycle hooks, dependency ordering, and sandboxed failure handling — bundled sample plugins, fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Plugins](https://img.shields.io/badge/Plugins-5-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Plugin_Architecture loads **Python plugin modules from a `plugins/` folder at runtime** (no imports hard-coded into the application), registers every `Plugin` subclass by its `name`, plans a **dependency-respecting execution order** with a deterministic topological sort, runs each plugin through a **setup → process → teardown** lifecycle, and **sandboxes every failure**: an import error, a missing dependency, an exploding `setup()`, or a crashing `process()` is recorded on the report while the rest of the pipeline keeps running.

Bundled sample plugins ship in `plugins/` (`echo`, `upper`, `stats`, `faulty`, `orphan`) with a config in `data/plugins.json` — the demo deliberately exercises a missing dependency, a process-time crash, teardown-after-failure, and a deterministic re-run. **No network, no API keys.**

---

# ✨ Features

- `discover_plugins()` — sorted, underscore-skipping file discovery (deterministic)
- `load_plugins()` — `importlib` registration of `Plugin` subclasses; per-file failures recorded, never fatal
- `plan_execution()` — Kahn topological sort; missing/disabled dependencies skipped with reasons; cycles detected
- `Plugin` ABC — `name`, `dependencies`, `setup/process/teardown` lifecycle hooks
- `execute()` — sandboxed init/setup/process/teardown; poisoned dependencies skip dependents
- `load_config()` — strict JSON config validation with indexed error messages
- `ExecutionReport` — order, skipped map, failures, lifecycle hook trace, output records
- CLI: `--demo`, `--config`, `--plugins DIR`
- Bundled data: 5 plugins + 4-record pipeline config
- 44 passing pytest tests

---

# 📂 Folder Structure

```text
Plugin_Architecture/
│
├── src/
│   ├── main.py        # CLI: --demo, --config, --plugins, --quiet
│   └── plugin_core.py # discovery, planning, execution, config, demo
│
├── plugins/           # runtime-discovered sample plugins
│   ├── echo_plugin.py    # root: marks records, seeds context events
│   ├── upper_plugin.py   # deps (echo): upper-cases text
│   ├── stats_plugin.py   # deps (echo): aggregates into context
│   ├── faulty_plugin.py  # always raises in process() — sandbox proof
│   └── orphan_plugin.py  # deps (missing) — planner skip proof
│
├── tests/
│   └── test_plugins.py
│
├── data/
│   └── plugins.json   # input records + enable/disable lists
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 25_Software_Engineering/Plugin_Architecture

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: full bundled pipeline with self-checks
python src/main.py --demo

# Run your own config through the bundled plugins
python src/main.py --config data/plugins.json

# Point at a different plugin directory
python src/main.py --config my.json --plugins my_plugins/
```

Input schema (config JSON):

```json
{
  "input": [{"id": "R-1", "text": "alpha", "qty": 3}],
  "enable": ["echo", "upper"],
  "disable": []
}
```

(`id` non-empty string; `text` string; `qty` integer ≥ 1. `enable` defaults to all discovered plugins minus `disable`; a name in both lists is an error; unknown `enable` names fail fast.)

**Exit codes:** `0` = success · `2` = missing file/dir, invalid config, unknown plugin, structural plugin error · `2` (argparse) = no action or conflicting actions.

---

# 🧠 How It Works

```text
plugins/*.py ──► discover (sorted) ──► importlib exec ──► find Plugin subclasses
                        │                    │
                        │              import error ──► LoadFailure (sandboxed)
                        ▼
data/plugins.json ──► load_config (validate input/enable/disable, fast-fail)
                        │
                        ▼
              plan_execution: Kahn topological sort
                 orphan ── missing dep ──► skipped (reason recorded)
                        │
                        ▼  order: echo -> faulty -> stats -> upper
              execute (per plugin, sandboxed):
                 init ──► setup ──► process ──► teardown
                          │          │             │
                          └── any exception ──► PluginFailure recorded,
                                poison dependents ► skipped, pipeline continues
                        │
                        ▼
        ExecutionReport {order, skipped, failures, hooks, data, context}
                        │
                        ▼  deterministic re-run asserted
                 "Cross-checks OK" / "Demo completed successfully."
```

Details worth knowing:

- **Discovery order is sorted**, and Kahn's algorithm scans the ready set in sorted order — the plan is byte-for-byte reproducible every run.
- **Failures poison dependents, not the pipeline**: `c` depending on a crashed `b` is skipped with `dependency 'b' failed at runtime`, while independent plugins continue.
- **`teardown` runs after a failed `process`** (setup had succeeded), but never after a failed `setup` — the hook trace proves it.
- **Config validation happens before any plugin is imported**, so a bad config fails in milliseconds.

---

# 🛠 Technologies

- Python 3 (100 % standard library)
- `importlib.util` (file-based module loading), `abc.ABC`, `dataclasses`
- `json` / `pathlib` / `sys` / `argparse` / `logging`
- pytest

---

# 📚 Concepts Covered

- Plugin/extension architecture: discovery, registration, activation
- Runtime module loading with `spec_from_file_location`
- Abstract base classes as plugin contracts
- Lifecycle hooks and resource-cleanup guarantees
- Topological sorting (Kahn) with deterministic tie-breaking
- Failure isolation: record-and-continue sandboxing
- Poison propagation vs pipeline abort
- Declarative enable/disable configuration
- Defensive validation of external config at the boundary

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**44 tests passed** covering discovery rules (missing/empty/underscore dirs), sandboxed loading (import errors, no-subclass modules, duplicate/missing names), plan semantics (topological order, disabled/missing skips, dependent skips, cycle detection, determinism), config validation (shape, indexed record errors, enable/disable conflicts, unknown plugins), execution sandboxing (process/setup/init failures, non-list results, dependents poisoned, input immutability), report formatting, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
