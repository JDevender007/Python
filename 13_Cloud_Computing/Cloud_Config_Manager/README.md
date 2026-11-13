<div align="center">

# 🧩 Cloud Config Manager

### Validate, overlay, and drift-check cloud infrastructure configs — YAML/JSON in, path-based errors and a masked change plan out. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyYAML](https://img.shields.io/badge/PyYAML-YAML-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Cloud Config Manager treats infrastructure configuration as files you can test like code:

1. **Validate** — a strict schema checks projects, regions, services (image tags, replica ranges, env vars), storage, budgets, and tags, reporting *every* problem with a JSON-path (`$.services[0].replicas`).
2. **Overlay** — deep-merge a base config with per-environment overrides (mappings merge, lists/scalars replace).
3. **Plan** — diff a desired config against an observed state to produce a change plan of adds, removes, and updates, keyed by service `name` where possible.
4. **Mask** — anything on a path containing `password`, `secret`, `token`, `api_key`, or `credential` is masked in the plan, including nested values inside whole blocks being added or removed.

Everything is file-based: **no cloud APIs, no network**. `--check` turns drift into exit code 1 for CI gates.

---

# ✨ Features

- YAML and JSON config loading with precise parse errors
- Strict schema validation: unknown keys, slug rules, region patterns, replica ranges, env types
- Deep-merge overlays (dicts merge, lists/scalars replace, inputs untouched)
- Drift diff: scalar/nested changes, keyed-list adds/removes, positional fallback
- Secret masking at any depth (path hints + recursive key scan)
- Change plan rendering with add/update/remove counts
- `--check`: exit 1 when drift exists (CI-friendly)
- JSON output for tooling; merged configs written back as YAML/JSON
- 56 passing pytest tests

---

# 📂 Folder Structure

```text
Cloud_Config_Manager/
│
├── src/
│   ├── main.py           # CLI: demo, --validate, --plan, --merge
│   └── config_manager.py # loading, schema, deep merge, diff, masking, demo
│
├── tests/
│   └── test_config_manager.py
│
├── data/                 # written by the demo (desired/override/observed YAML)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 13_Cloud_Computing/Cloud_Config_Manager

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: validate, break, overlay, and drift-plan sample configs
python src/main.py --demo

# Schema check (exit 2 + all errors listed when invalid)
python src/main.py --validate infra.yaml

# Drift plan between desired and observed state
python src/main.py --plan --desired base.yaml --observed live.yaml

# CI gate: exit 1 when anything drifted
python src/main.py --plan --desired base.yaml --observed live.yaml --check

# Machine-readable plan
python src/main.py --plan --desired base.yaml --observed live.yaml --json

# Environment overlay
python src/main.py --merge --base base.yaml --overlay prod.yaml --out prod.merged.yaml
```

Example config:

```yaml
project: shop-api
region: us-east-1
services:
  - name: web
    image: nginx:1.25
    replicas: 2
    env:
      LOG_LEVEL: info
storage:
  bucket: shop-api-assets
  size_gb: 500
budget: 400
tags:
  team: platform
```

---

# 🛠 Technologies

- Python
- PyYAML (`safe_load` / `safe_dump`)
- json / re / dataclasses / argparse
- pytest

---

# 📚 Concepts Covered

- Schema validation with JSON-path error reporting
- Deep-merge semantics (dicts vs. lists vs. scalars)
- Desired vs. observed state: drift detection fundamentals
- Keyed list reconciliation by `name` vs. positional fallback
- Secret redaction in diffs and plans
- Infrastructure-as-code planning (Terraform-style plan output)
- Exit-code conventions for CI (`--check`)
- Test-driven development

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**56 tests passed** covering loading/parsing, every validation rule, deep merge, all diff paths (nested, keyed lists, positional, shape changes), secret masking, plan rendering, demo idempotency, and every CLI mode — all offline.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
