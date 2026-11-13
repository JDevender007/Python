<div align="center">

# 🏠 Home Automation Rules

### An if-then rule engine over simulated sensor events — threshold conditions, hysteresis, minimum-duration delays, and a chronological actuator log. Replay any rule set against any event CSV, fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

A home automation hub is, at its core, a state machine that turns sensor readings into actuator commands. This project implements that state machine and nothing else — no hub, no MQTT, no devices.

Rules are declared in JSON:

```json
{
  "id": "cool_living_room",
  "sensor": "living_room",
  "metric": "temperature",
  "condition": {"op": ">", "threshold": 25.0},
  "hysteresis": 2.0,
  "min_duration_s": 180,
  "action": {"actuator": "thermostat", "command": "cool_on"},
  "release": {"command": "cool_off"}
}
```

Three details make the engine behave like a real one:

- **Minimum duration** — a condition must hold continuously for `min_duration_s` before the action fires. Any reading that breaks it resets the timer, so a one-sample spike cannot switch the heating on.
- **Hysteresis** — once active, the rule releases only after crossing back past `threshold ± hysteresis`. The bundled cooling rule stays armed across a 25.0 °C plateau and releases at 23.0 °C, which is exactly the chatter a naive `> 25` check would produce.
- **Ordering** — events are replayed chronologically, one actuator event per transition, with no re-trigger while a rule is already active.

The bundled scenario (4 rules, 111 sensor readings, 30-second resolution) produces exactly 14 actuator events: 7 triggers and 7 releases. The demo asserts each timestamp, the per-rule counts, deterministic replay, and a CSV round-trip of the actuator log.

No network, no API keys: `data/rules.json` and `data/events.csv` ship with the project.

---

# ✨ Features

- JSON rule schema with strict validation (unknown fields, bad ops, negative delays)
- Hysteresis and minimum-duration semantics
- Chronological replay with per-rule state (`active`, `since`, counters)
- Actuator event log (trigger/release) as a DataFrame and CSV
- CSV validation: columns, numeric values, monotonic timestamps
- Human-readable rules + event report
- `--demo`, `--rules`, `--events`, `--out`, `--json` CLI
- 75 passing pytest tests

---

# 📂 Folder Structure

```text
Home_Automation_Rules/
│
├── src/
│   ├── main.py   # CLI: --demo, --rules, --events, --out, --json
│   └── rules.py  # schema, engine, logging, report, demo
│
├── tests/
│   └── test_rules.py
│
├── data/
│   ├── rules.json    # 4 rules
│   └── events.csv    # 111 sensor readings (2026-03-01, 30 s grid)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 21_IoT/Home_Automation_Rules

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo on the bundled rules and events
python src/main.py --demo

# Replay your own files and save the actuator log
python src/main.py --rules data/rules.json --events data/events.csv \
                   --out actuators.csv

# Machine-readable summary
python src/main.py --rules data/rules.json --events data/events.csv \
                   --json run.json
```

**Input:** a JSON rules object (`{"rules": [...]}`) and a CSV with columns `timestamp,sensor,metric,value`.

**Exit codes:** `0` = success · `2` = usage/validation file error.

---

# 🧠 How It Works

```text
rules.json ──► parse + validate ──► Rule(id, sensor, metric, op, threshold,
                                          hysteresis, min_duration_s,
                                          actuator, command, release)

events.csv ──► validate columns, numeric values, monotonic time
                    │
                    ▼
          for each event, for each matching rule:
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
   rule inactive?           rule active?
        │                        │
   condition true?          released(value)?
        │                        │
   start/reset timer         emit release (if command)
   elapsed >= min_duration        │
        │                        ▼
   emit trigger            clear active flag
        ▼
   active = True
                    │
                    ▼
        actuator log (CSV / DataFrame)
```

The state machine is deliberately tiny: `active`, `since`, `triggers`, `releases`. Everything else is a pure function of the reading, which is why replaying the same CSV twice produces byte-identical logs.

---

# 🛠 Technologies

- Python 3
- pandas (validation, replay, CSV I/O)
- Standard library (`json`, `datetime`, `dataclasses`, `argparse`)
- pytest

---

# 📚 Concepts Covered

- Event-driven rule engines and per-rule state machines
- Threshold conditions with comparison operators
- Hysteresis as a cure for actuator chatter
- Debouncing via continuous-duration requirements
- Schema validation with unknown-field rejection
- Timestamp parsing (ISO-8601 with `Z` and offsets)
- Monotonic time validation for logs
- Deterministic replay and idempotency
- CSV round-trip integrity
- Simulating IoT without hardware

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**75 tests passed** covering timestamp formatting/parsing, all comparison operators, hysteresis release logic, the full rule schema (missing fields, unknown fields, duplicates, bad ops, negative values, empty commands), rule and event file loading errors, engine behaviour (immediate triggers, delays, timer resets, sensor filtering, no double triggers, silent releases), bundled scenario counts and exact timestamps, deterministic replay, CSV logging round-trips, report rendering, demo idempotency, JSON export, quiet mode, and every CLI error path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
