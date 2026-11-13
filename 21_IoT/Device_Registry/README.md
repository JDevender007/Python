<div align="center">

# 🗂️ Device Registry

### A local IoT inventory in SQLite — validated device rows, kind/room/status filters, an auditable status-change history, and delete-cascades. No broker, no cloud, no network.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Every IoT platform needs an inventory before it needs anything else: which devices exist, where they are, what firmware they run, and whether they are reachable right now. This project implements that inventory as a single SQLite file with two tables.

```sql
CREATE TABLE devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('gateway','sensor','actuator','camera')),
    room TEXT NOT NULL,
    firmware TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('online','offline','error','maintenance')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE device_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    changed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```

Validation happens in Python *and* in the schema. Python gives clear error messages (`invalid device id 'Bad Id'`), the `CHECK` constraints and `PRIMARY KEY` guarantee the file cannot be corrupted by a second writer or a manual `INSERT`. `PRAGMA foreign_keys = ON` makes the cascade real rather than decorative.

Status changes are append-only: a device's current status is a column, and every transition is also a row in `device_events`. Repeating the current status deliberately logs nothing, so the history contains only actual transitions.

The bundled seed of 12 devices spans four kinds, seven rooms and every firmware pattern the validator accepts. The demo loads it into an in-memory database, asserts the row counts, independently recounts the sensor filter, and proves that invalid input, duplicate ids and unknown devices are all rejected.

No network, no API keys: `data/devices.json` ships with the project.

---

# ✨ Features

- SQLite schema with `CHECK` constraints and a foreign-key cascade
- Strict validation: id pattern, kind enum, firmware `MAJOR.MINOR.PATCH`, status enum
- Filtering by kind, room and status (combinable)
- Append-only status history per device
- Idempotent seeding from a JSON file
- Registry statistics by kind, status and room
- `--demo`, `--db`, `--list`, `--add`, `--status`, `--remove`, `--history`, `--stats`, `--seed`, `--json`
- 73 passing pytest tests

---

# 📂 Folder Structure

```text
Device_Registry/
│
├── src/
│   ├── main.py      # CLI: seed, add, list, status, history, remove, stats
│   └── registry.py  # schema, validation, CRUD, statistics, demo
│
├── tests/
│   └── test_registry.py
│
├── data/
│   └── devices.json   # 12 seed devices
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 21_IoT/Device_Registry

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

No runtime dependencies — `requirements.txt` only pins pytest.

---

# ▶️ Run

```bash
# Offline demo on an in-memory database
python src/main.py --demo

# Create a database and load the seed devices
python src/main.py --db registry.db --seed

# Query and modify
python src/main.py --db registry.db --list --kind sensor
python src/main.py --db registry.db --add "fan-attic:Attic Fan:actuator:attic:1.0.0"
python src/main.py --db registry.db --status "fan-attic:online"
python src/main.py --db registry.db --history fan-attic
python src/main.py --db registry.db --remove fan-attic
```

**Input:** a local SQLite path (created if missing) or an in-memory database for `--demo`.

**Exit codes:** `0` = success · `2` = usage/validation/database error.

---

# 🧠 How It Works

```text
devices.json ──► load_seed (validate every row)
                     │
                     ▼
              INSERT OR SKIP duplicates
                     │
                     ▼
  ┌────────────── devices ───────────────┐
  │ id | name | kind | room | firmware   │
  │ status | created_at                  │
  └───────────────┬──────────────────────┘
                  │ 1:N
                  ▼
        device_events (status, changed_at)
                  │
   ┌──────────────┼───────────────┐
   ▼              ▼               ▼
 filter        update_status    remove_device
 kind/room     UPDATE + INSERT  DELETE events,
 /status       (only on change) then device
```

Every read returns plain dicts, so the same functions feed the CLI, the JSON export and the tests without an ORM.

---

# 🛠 Technologies

- Python 3
- SQLite via the standard-library `sqlite3` module
- Standard library (`json`, `re`, `dataclasses`, `argparse`)
- pytest

---

# 📚 Concepts Covered

- Relational schema design with constraints
- Primary keys, foreign keys and `ON DELETE CASCADE`
- `PRAGMA foreign_keys` and why SQLite needs it explicitly
- Row factories and dict-based access
- Input validation at the boundary vs. constraints in the schema
- Append-only event history and idempotent updates
- Idempotent seeding
- Aggregate queries (`GROUP BY`, `COUNT DISTINCT`)
- Parameterised SQL and injection safety
- Testing a database layer with in-memory fixtures

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**73 tests passed** covering schema creation, directory creation, file persistence, all device validations (ids, names, kinds, rooms, firmware, statuses), duplicates, every read/filter combination, status transitions and history ordering, no-op updates, removal with cascade, seed loading and validation errors, idempotent seeding, statistics, report rendering, JSON export, demo idempotency, quiet mode, and every CLI error path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
