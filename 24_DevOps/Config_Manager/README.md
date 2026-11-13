<div align="center">

# ⚙️ Config Manager

### Layered YAML/JSON configuration (defaults → file → environment) with schema validation, type coercion, and a per-key provenance report. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyYAML](https://img.shields.io/badge/YAML-Config-cb171e?style=for-the-badge&logo=yaml&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Config Manager implements the layering rule most real services need: **defaults → file → environment**, where later layers win and every final key remembers *exactly which layer set it*. The bundled sample layers `data/defaults.yaml` (base values) under `data/settings.yaml` (file overrides) under three `APP_*` environment variables from `data/env.json`.

A declarative `data/schema.yaml` validates every key after merging: type (`str` / `int` / `number` / `bool`) with **string-to-type coercion** (env vars are always strings — `"9090"` becomes the integer `9090`, `"true"` becomes `True`), `required` flags, `min`/`max` bounds, and `choices` lists. The **provenance report** prints each key's final value and its source (`defaults`, `file:settings.yaml`, or `env:APP_PORT`), and the demo asserts the full layer split (3 default / 3 file / 3 env), the coercion results, and that all three failure classes — unknown key, bad type, out-of-range — are rejected. **No network, no remote config servers, no secrets fetched at runtime.**

---

# ✨ Features

- Three-layer merge with deterministic precedence: `defaults -> file -> env`
- YAML **and** JSON config files (dispatch by extension), nested mappings flattened to dotted keys (`db.host`)
- Declarative schema: `type`, `required`, `min`, `max`, `choices` — schema itself is validated
- Type coercion: `"9090" → 9090`, `"0.25" → 0.25`, `"true"/"yes"/"0" → bool` — with strict rejection of bad values (`"abc"`, `"80.5"` for an int, `"maybe"` for a bool)
- Validation order is general → specific: unknown keys, missing required keys, coercion, then choices/bounds — each with a precise error
- Environment layer via `APP_` prefix (`APP_DB__HOST` → `db.host`), prefix is configurable
- Per-key **provenance** (`env:APP_PORT`, `file:settings.yaml`, `defaults`) + layer-count summary
- `--json` export of values, provenance, and layer counts; `flatten`/`unflatten` round-trip
- Deterministic: pure local-file parsing, identical output every run
- 53 passing pytest tests

---

# 📂 Folder Structure

```text
Config_Manager/
│
├── src/
│   ├── main.py           # CLI: --demo, --file, --defaults, --schema, --env-file, --json
│   └── configmanager.py  # layers, coercion, schema validation, provenance, demo
│
├── tests/
│   └── test_configmanager.py
│
├── data/
│   ├── defaults.yaml     # lowest layer: 9 keys (nested db.* included)
│   ├── settings.yaml     # file layer: overrides 5 keys
│   ├── schema.yaml       # type/required/min/max/choices per key
│   └── env.json          # env layer: APP_PORT, APP_DEBUG, APP_DB__HOST
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 24_DevOps/Config_Manager

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: layer the bundled configs, provenance report, cross-checks
python src/main.py --demo

# Layer your own file over the bundled defaults + schema
python src/main.py --file data/settings.yaml

# Add an environment layer from a JSON file of APP_* variables
python src/main.py --file data/settings.yaml --env-file data/env.json

# Values + provenance as JSON
python src/main.py --file data/settings.yaml --json cfg.json
```

Input schema — a config file is a (possibly nested) YAML/JSON mapping; every key must exist in the schema:

```yaml
# settings.yaml            # schema.yaml entry
port: 8000                 # port: {type: int, min: 1, max: 65535}
log_level: WARNING         # log_level: {type: str, choices: [DEBUG, …]}
retries: 5
db:
  host: 127.0.0.1          # db.host: {type: str, required: true}
```

Environment layer (prefix configurable, `__` → `.`):

```text
APP_PORT=9090        → port          (int coercion)
APP_DEBUG=true       → debug         (bool coercion)
APP_DB__HOST=10.0.0.5 → db.host
```

**Exit codes:** `0` = success · `2` = usage/file/schema/validation error.

---

# 🧠 How It Works

```text
defaults.yaml ─┐
               ├─► flatten() ─► {'port': 8080, 'db.host': 'localhost', ...}
settings.yaml ─┤
               │        merge: later layer wins, provenance recorded per key
env (APP_*)  ──┘
        │
        ▼  validate(merged, schema)      general ──────────────► specific
   1. unknown keys?      → ConfigError: unknown key(s): …
   2. missing required?  → ConfigError: missing required key(s): …
   3. coerce each value  → str | int | number | bool  ("9090" → 9090)
   4. choices / min / max → ConfigError: … above maximum 65535
        │
        ▼
   ConfigResult(values, provenance) ──► report table  ──► (optional) --json
```

Details worth knowing:

- **Provenance is recorded during the merge, not inferred afterwards** — so `port` correctly reports `env:APP_PORT` even though the file layer also set it.
- **Coercion only ever happens where it's safe**: an `int` schema field accepts `9090` and `"9090"` but rejects `9090.5`, `"80.5"`, and `true` (a `bool` is never a valid `int` here).
- **Validation order is fixed and tested**: unknown keys are reported before missing keys, and both before any value problem — so one error message always points at the most structural issue first.
- **Demo cross-checks**: 9 keys, split `defaults 3 / file 3 / env 3`, `port=9090` (env), `log_level=WARNING` (file), `app_name=devops-demo` (defaults), flatten round-trip, deterministic re-run, plus proof that unknown-key, coercion, and bounds validation all fire.

---

# 🛠 Technologies

- Python 3
- PyYAML (`yaml.safe_load` for YAML layers and the schema)
- json (env layer, `--json` export)
- dataclasses / argparse / logging / pathlib
- pytest

---

# 📚 Concepts Covered

- Layered configuration and precedence (defaults < file < env)
- Provenance tracking: recording *where* each value came from during the merge
- Schema-on-read validation with declarative field specs
- Type coercion from strings (the env-var reality) with strict failure modes
- Flattening/unflattening nested mappings to dotted keys
- Designing validation order: structural errors before value errors
- Self-asserting deterministic demos
- Fast-fail CLI flag validation before expensive work

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**53 tests passed** covering YAML/JSON loading errors (missing, malformed, non-mapping, bad extension), flatten/unflatten round-trips, schema validation (bad type, unknown field, bad choices), every coercion rule (int/number/bool/str, bool-vs-int pitfalls), every validation rule in the correct order (unknown → missing → coercion → choices → bounds), environment-prefix mapping rules, layer precedence and provenance, report contents, demo idempotency, and every CLI path — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
