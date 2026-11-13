<div align="center">

# 📡 IoT Projects

### Five offline IoT simulations: a seeded sensor fleet with fault injection, an if-then home automation engine, a SQLite device registry, a telemetry analyzer and a GPIO pin simulator.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

IoT is mostly plumbing: sensors produce numbers, rules turn numbers into actions, a registry remembers what exists, logs answer what happened, and pins connect it all to the physical world. Getting that plumbing right needs no cloud account — only a deterministic model of each layer.

This category builds the whole stack in miniature:

- **Sensor_Simulator** generates reproducible telemetry with four fault kinds (spike, drift, stuck, dropout) and validates the CSV on the way back in.
- **Home_Automation_Rules** replays sensor events through a JSON rule set with hysteresis and minimum-duration delays, emitting an actuator log.
- **Device_Registry** keeps the inventory in SQLite with schema constraints and an auditable status history.
- **Sensor_Data_Analyzer** answers the operator's questions: what is normal, what is an outlier, where is data missing, where did a sensor freeze.
- **Gpio_Pins_Simulator** models the hardware layer — modes, pulls, edge events, analytic PWM and contact debouncing.

Every project runs on a bundled dataset, takes under three seconds for a demo, and **asserts its own behaviour** rather than printing numbers for a human to squint at.

---

# 🎯 Learning Objectives

- Generate reproducible synthetic telemetry with seeded RNGs
- Inject realistic faults and prove the downstream tooling finds them
- Validate CSV inputs strictly at the boundary
- Build an event-driven rule engine with per-rule state
- Understand hysteresis and debouncing as cures for chatter
- Model a relational schema with constraints and cascades
- Implement append-only event histories
- Detect anomalies with rolling z-scores rather than global thresholds
- Measure data completeness with gap detection
- Simulate GPIO at the level of modes, pulls, edges and PWM duty

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Sensor_Simulator | Seeded virtual temperature/humidity/motion fleet, four fault kinds, strict CSV validation. | ✅
02 | Home_Automation_Rules | JSON rules with hysteresis and delays; 111 events replay to 14 actuator events. | ✅
03 | Device_Registry | SQLite inventory of 12 devices, validated CRUD, status history, delete cascade. | ✅
04 | Sensor_Data_Analyzer | Rolling z-score anomalies, gaps, flatlines, resampling, correlation over 355 rows. | ✅
05 | Gpio_Pins_Simulator | Modes, pulls, edge events, listeners, analytic PWM and debouncing; 16-step scenario. | ✅

---

# 💡 Concepts Covered

- Seeded random processes and byte-identical reproducibility
- Fault injection: spike, drift, stuck sensor, dropped samples
- CSV schema and type validation
- Threshold rules, hysteresis and minimum-duration debouncing
- Event replay with per-rule state machines
- Relational schema design, `CHECK` constraints and `ON DELETE CASCADE`
- Append-only audit trails
- Rolling statistics and z-score anomaly detection
- Missing-data and flatline detection
- Time-based resampling and row conservation
- Cross-series correlation with pivot tables
- GPIO modes, pull-up/pull-down behaviour and active-low wiring
- Rising/falling edge detection with listener callbacks
- Analytic PWM sampling and duty-cycle averaging
- Deterministic simulation testing without hardware

---

# 📁 Repository Structure

```text
21_IoT/
│
├── Sensor_Simulator/
├── Home_Automation_Rules/
├── Device_Registry/
├── Sensor_Data_Analyzer/
├── Gpio_Pins_Simulator/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── data/             # bundled telemetry / rules / seed / scenario
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- NumPy (Sensor_Simulator, Sensor_Data_Analyzer)
- pandas (Home_Automation_Rules, Sensor_Data_Analyzer)
- SQLite via the standard-library `sqlite3` module (Device_Registry)
- Standard library (`json`, `csv`, `math`, `dataclasses`, `argparse`)
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Sensor Simulator | ✅ |
| Home Automation Rules | ✅ |
| Device Registry | ✅ |
| Sensor Data Analyzer | ✅ |
| GPIO Pins Simulator | ✅ |

**Completed:** **5 / 5 Projects** · 392 passing tests

---

# ▶️ Quick Start

```bash
cd 21_IoT/Sensor_Simulator

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

Each project follows the same shape: `python src/main.py --demo` for a self-checking offline run, `python -m pytest tests/ -q` for the suite.

---

# 📚 Skills Developed

- Designing deterministic synthetic datasets with known ground truth
- Writing detectors and asserting they find the injected fault
- Building validated data pipelines (CSV in, typed frames out)
- Implementing stateful rule engines and event replay
- Modelling and querying relational data without an ORM
- Analysing time series with rolling windows and resampling
- Simulating hardware interfaces faithfully enough to test against
- Writing 55–123 pytest cases per project, including every error path

---

# 🚀 Key Learning Outcomes

- Generate and validate reproducible sensor telemetry offline
- Turn a rule file plus an event log into an actuator log
- Keep a device inventory with history you can audit
- Find anomalies, gaps and frozen sensors in a telemetry export
- Drive and observe simulated GPIO pins with edges and PWM

---

# 🔮 Future Enhancements

- MQTT-style message bus between the simulator and the rule engine
- Rule DSL with boolean combinations and time windows
- Device registry sync against a bundled firmware catalogue
- Seasonal decomposition and forecasting in the analyzer
- I2C/SPI bus simulation on top of the pin board

---

# 🤝 Contributions

Suggestions, improvements, and feedback are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
