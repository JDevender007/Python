<div align="center">

# 📡 IoT Projects

### Five device-side projects where the interesting failure is never the sensor. State lives in a database, so the schema is the contract; a pin is a state machine with time in it; a rule is a function of a clock; a reading is only as good as its sample rate; and a simulator is only useful if its faults are reproducible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Device%20State-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)

</div>

---

# 📖 About

Five projects that sit on the device side of an IoT stack, with **no network anywhere**: no MQTT
broker, no HTTP client, no cloud SDK. The state that a real deployment would put in a message queue
lives in SQLite, a JSON scenario file, or a CSV log — which makes every one of them runnable and
inspectable on a laptop.

**The lesson of each project is different, on purpose.** Five variations on "read a sensor and print
it" would teach nothing; five different ways a device pipeline can be confidently wrong is the
subject.

- **Device_Registry** — *when state lives in a database, the schema is the contract.* A registry that
  accepts any string as a device id, or lets a delete orphan its history, is a registry you cannot
  trust after the first bad write. The rebuild puts the schema in SQLite with `CHECK`-style validation
  in Python, validates every field by name before it reaches the database, logs a status history row
  on every transition, makes delete cascade to the history, and then proves the reads: **12 seeded
  devices**, schema-valid rows, filters matching independent recounts, invalid input rejected, history
  logged, delete cascading — all with **no network**.
- **Gpio_Pins_Simulator** — *hardware is a state machine, and time is one of its inputs.* A button
  "pressed" is not one event; it is a burst of noisy samples that must be collapsed into one edge, and
  a PWM signal is a duty cycle you can measure, not an intention. The rebuild models pins, modes,
  pulls, edges and a debouncer as explicit objects, then verifies **LED edges against the writes**,
  the button reporting press/release **in order**, **nine noisy readings collapsing to one edge** at
  three samples, PWM samples matching the configured duty **exactly**, an identical replay of the
  bundled scenario, and every guard rail firing on bad input.
- **Home_Automation_Rules** — *a rule is a function of a clock, so the clock is part of the test.*
  `IF motion AND dark THEN lights` is not a rule until it says *for how long*, *after how long*, and
  *when it should stop*. The rebuild parses rules from JSON with typed validation, evaluates them
  over a CSV event stream with explicit time, supports **delay rules that fire at +120 s and +180 s**
  and **hysteresis that keeps the cool rule armed** past the off threshold, counts the actuator
  events it actually emitted (**14**), and round-trips the actuator log through CSV so the run is
  inspectable afterwards.
- **Sensor_Data_Analyzer** — *a reading is only meaningful with its sampling interval.* Detecting a
  "gap" requires knowing what a normal interval is; a flatline is a run of identical values, not a low
  variance; and resampling must conserve rows or the count is a lie. The rebuild generates a seeded
  multi-sensor series, injects a **spike and a drop**, injects a **5-sample gap and a 7-sample
  flatline**, and then requires the detector to find each one by name — while verifying that the
  bundled CSV matches the generator exactly, that resampling conserves rows, and that correlation is
  symmetric.
- **Sensor_Simulator** — *a simulator without a fault model is a random number generator with a
  schema.* The useful question is not "does it produce numbers" but "does a spike land where I asked,
  and does a dropout remove exactly the rows I asked for". The rebuild builds a seeded fleet of typed
  sensors, a `--fault sensor:kind:start:length` spec, and log/replay round-trips, then verifies the
  bundled sample **matches exactly**, a spike is **+15 °C** at the requested tick, a dropout removes
  **3 rows**, humidity stays in **0–100**, the CSV round-trip is exact, and the summary totals match.

**Every claim is checkable.** Each demo prints `Cross-checks OK: ...` with the numbers it verified,
then `Demo completed successfully.`; run it twice and the bytes match, run it with `--quiet` and it
writes nothing at all.

Dependencies stay small: `numpy` and `pandas` where the maths is tabular, PyYAML nowhere, and the
standard library's `sqlite3`, `csv` and `json` everywhere else.

---

# 🎓 Learning Objectives

- Model device state in a relational schema and treat the schema as the contract
- Validate every field before it reaches the database, and refuse by name
- Append to a history table on every state transition instead of overwriting
- Make deletes cascade, and prove the orphan rows are gone
- Model a GPIO pin as an explicit state machine: mode, pull, level, edge
- Debounce a noisy input and show the reduction in edge count
- Measure a PWM duty cycle from samples instead of asserting it
- Replay a recorded scenario and get identical results
- Parse declarative rules with typed validation and per-rule error messages
- Evaluate rules over an event stream where time is an explicit input
- Implement delayed actions and hysteresis, and test both edges of the threshold
- Round-trip an actuator log through CSV so a run is reproducible
- Recognise that gap detection depends on the expected sampling interval
- Distinguish a spike, a dropout, a flatline and ordinary noise
- Resample a series and prove the row count is conserved
- Build a fault model with an explicit spec and a seeded RNG
- Verify a simulator against its own bundled output, byte for byte
- Keep every project offline: no broker, no socket, no clock dependency

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Device_Registry | SQLite registry with field validation, status history, cascading delete and filters. | 73 | ✅
02 | Gpio_Pins_Simulator | Pins, pulls, edges, debouncing, LED/button wiring and PWM duty measurement. | 123 | ✅
03 | Home_Automation_Rules | Declarative rules, delays, hysteresis, event-stream evaluation, CSV actuator log. | 75 | ✅
04 | Sensor_Data_Analyzer | Rolling stats, z-score anomalies, gap and flatline detection, resampling, correlation. | 66 | ✅
05 | Sensor_Simulator | Seeded sensor fleet, fault specs, CSV logging, replay and summary reconciliation. | 55 | ✅

**Total: 392 tests.**

---

# 🧠 Concepts Covered

- Relational modelling for device state: identity, kind, room, firmware, status
- Input validation at the boundary, with errors that name the field
- Audit tables and append-only status history
- Referential integrity and `ON DELETE CASCADE`
- Filtered queries that can be re-derived independently
- GPIO modes: input, output, input with pull-up/pull-down
- Rising and falling edges as events rather than levels
- Debouncing as time-domain filtering, and the sample count as a parameter
- PWM duty cycle, and measuring it back from samples
- Recording and replaying a hardware scenario deterministically
- Declarative rule formats and schema validation with helpful messages
- Event-time evaluation versus wall-clock evaluation
- Delayed actuation and why `time` must be a parameter
- Hysteresis, deadbands, and the difference between "on" and "stay on"
- Actuator logs as data, and round-tripping them through CSV
- Rolling windows and their edge effects
- Z-score anomaly detection and the assumption of stationarity
- Gap detection from an expected sampling interval
- Flatline detection as a run-length problem
- Resampling and conservation of rows
- Correlation between sensor channels and its symmetry
- Synthetic data generation with a seeded RNG
- Fault injection with an explicit, parseable specification
- CSV as a lossless round-trip format for typed readings
- Offline-by-construction design: no broker, no socket, no clock reads

---

# 📁 Repository Structure

```text
21_IoT/
│
├── Device_Registry/
│   ├── src/    registry.py, main.py
│   ├── tests/  test_registry.py
│   └── data/   devices.json
│
├── Gpio_Pins_Simulator/
│   ├── src/    gpio.py, main.py
│   ├── tests/  test_gpio.py
│   └── data/   scenario.json
│
├── Home_Automation_Rules/
│   ├── src/    rules.py, main.py
│   ├── tests/  test_rules.py
│   └── data/   rules.json, events.csv
│
├── Sensor_Data_Analyzer/
│   ├── src/    analysis.py, main.py
│   ├── tests/  test_analysis.py
│   └── data/   readings.csv
│
└── Sensor_Simulator/
    ├── src/    sensors.py, main.py
    ├── tests/  test_sensors.py
    └── data/   sensor_sample.csv
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI, a
`tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a `.gitignore`, and a
`README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 21_IoT/Sensor_Simulator

python src/main.py --demo                                   # offline, deterministic, exit 0
python src/main.py --demo --quiet                            # prints nothing at all
python src/main.py --log out/sensors.csv --ticks 48 --seed 7
python src/main.py --replay --log out/sensors.csv --json out/summary.json
python src/main.py --log out/spiked.csv --fault living_room_temp:spike:10:3
python -m pytest tests -q                                    # the suite
```

Every project supports `--demo` (plus `--quiet`) and `--json <path>`, and adds its own flags
(`--db`, `--list`, `--add`, `--status`, `--remove`, `--history`, `--stats`, `--seed`, `--kind`,
`--room`, `--scenario`, `--debounce`, `--rules`, `--events`, `--out`, `--readings`, `--window`, `--z`,
`--resample`, `--log`, `--replay`, `--sensor`, `--ticks`, `--interval`, `--fault`). No demo writes into
the repository: databases, CSVs and JSON go only where you point them.

---

# ✅ Verify the whole category

```powershell
Get-ChildItem -Directory | ForEach-Object {
    Push-Location $_
    python -m compileall -q src tests
    python -m pytest tests -q
    python src\main.py --demo
    python src\main.py --demo --quiet
    Pop-Location
}
```

The gates each project must pass, and does:

1. `compileall` on `src` and `tests` exits 0
2. `pytest` passes with no skips, 50+ tests
3. `--demo` exits 0 and ends with `Cross-checks OK: ...` then `Demo completed successfully.`
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing at all
5. no non-ASCII byte in `src/`, `tests/` or the text data files

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why validation at the database boundary beats validation in the caller
- Why a status column without a history table loses the only interesting data
- Why a cascading delete is a correctness property, not a convenience
- Why a button press is an interval, and a debouncer is a parameterised one
- Why measuring a duty cycle is a stronger claim than configuring one
- Why a replayed scenario must produce identical results to be a test
- Why a rule with no time semantics is a suggestion
- Why hysteresis is what stops an actuator oscillating at its threshold
- Why gap detection is impossible without an expected interval
- Why resampling that changes the row count is a bug you can assert
- Why a simulator's fault model is its specification
- Why "+15 °C at tick 10 for 3 ticks" is testable and "some noise" is not
- Why offline-by-construction is a design choice you can verify
- How to make a device pipeline reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `load_seed`, `load_scenario`, `load_rules`, `load_events`, `load_readings`, `load_log`
Values — `Pin`, `Board`, `EdgeEvent`, `Debouncer`, `Led`, `Button`
Rules — `Rule`, `RuleState`, `RuleEngine`, `_parse_rule`, `parse_rules`, `parse_ts`, `format_ts`
Registry — `connect`, `add_device`, `get_device`, `list_devices`, `update_status`, `remove_device`,
`device_events`, `seed_registry`, `registry_stats`
GPIO — `check_pin`, `check_mode`, `check_pull`, `check_edge`, `run_scenario`, `render_report`
Analysis — `add_rolling`, `detect_anomalies`, `detect_gaps`, `detect_flatlines`, `resample_metric`,
`sensor_summary`, `correlation`
Simulation — `default_fleet`, `parse_fault`, `simulate`, `log_readings`, `summarize`, `_active_fault`
Refusal — `RegistryError`, `GpioError`, `RuleError`, `AnalysisError`, `SensorError`
Testing — schema validation, cascade checks, debounce edge counts, measured PWM duty, delay and
hysteresis edges, gap/flatline by name, CSV round-trips, seeded determinism, CLI paths, quiet-mode
silence

---

# 🚀 Future Improvements

- A tiny in-process pub/sub so producers and consumers can be split without a broker
- A migration path for the registry schema, with the history preserved across versions
- A state-machine description for GPIO pins, generated from the code rather than written twice
- Rule priorities and conflict detection when two rules target one actuator
- Seasonal decomposition in the analyser, beside the z-score detector
- A fault catalogue (drift, stuck-at, quantisation) with one test per fault kind
- Shared CSV/JSON schema definitions across all five projects
- A category-wide `audit` harness that prints all five evidence tables in one shape

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a clear message.
4. Push the branch.
5. Open a Pull Request.

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
