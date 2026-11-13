<div align="center">

# 🔌 GPIO Pins Simulator

### A software GPIO board — input/output modes, pull-up and pull-down resistors, rising/falling edge events, listeners, analytic PWM and contact debouncing. No hardware, no kernel driver, no network.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Stdlib](https://img.shields.io/badge/Dependencies-Standard%20Library-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Physical computing is hard to learn on real pins: a wrong mode can short a pin, and a bouncing button produces traces nobody can reproduce. This project models the parts that matter in software, with a deterministic integer clock in milliseconds.

A `Board` owns a set of `Pin` objects. Each pin has:

- a **mode** (`input` or `output`) — writing to an input, or driving an output as an input, raises instead of silently doing nothing;
- a **pull resistor** (`up`, `down`, `none`) that decides the idle level an un-driven input settles at (`1` for up, `0` otherwise);
- a **level** (0/1) and an append-only **edge log** of `(tick, pin, edge, level)`.

Every transition emits a `rising` or `falling` edge and notifies any registered listeners, optionally filtered to one edge direction. Time only moves when you call `advance(ms)`, so traces are reproducible to the millisecond.

Three details make it behave like hardware:

**PWM is analytic, not stepped.** A pin at `f` Hz and `d %` duty is high for the first `d/100` of each period, so `pwm_sample(pin, t)` is a pure function of elapsed time. Sampling a 4 Hz / 25 % signal every 62.5 ms yields exactly `1,0,0,0,1,0,0,0` — average 0.25, no drift, no accumulate-error.

**Debouncing is a state machine, not a delay.** A `Debouncer(min_stable=3)` only accepts a new level after three consecutive samples agree with it. The demo feeds nine noisy readings (`0,1,0,0,0,1,0,0,0`) at an undebounced pin and gets **5 edges**; the same sequence through a three-sample debouncer produces exactly **1**. A single-sample glitch never reaches the pin.

**Scenarios are data.** `data/scenario.json` declares four pins and sixteen steps (`read`, `write`, `set_input`, `pwm`, `clear_pwm`, `advance`). `run_scenario` replays them into a transcript, a board snapshot and an edge list, and the demo asserts the replay is byte-identical the second time.

No network, no API keys, no hardware: everything ships in `data/scenario.json`.

---

# ✨ Features

- Input/output modes with a validated state transition
- Pull-up / pull-down / floating inputs with correct rest levels
- Rising and falling edge log, with per-edge filtering
- Edge listeners with `rising`, `falling` or `both` filters
- Analytic PWM: deterministic sampling plus exact average duty
- `Debouncer` that removes contact bounce; attachable per input pin
- `Led` and `Button` helpers (including active-low wiring)
- JSON scenario loader with strict per-step validation
- `--demo`, `--scenario`, `--debounce`, `--json`, `--quiet`
- 123 passing pytest tests

---

# 📂 Folder Structure

```text
Gpio_Pins_Simulator/
│
├── src/
│   ├── main.py   # CLI: --demo, --scenario, --debounce, --json
│   └── gpio.py   # pins, board, debouncer, PWM, scenarios, demo
│
├── tests/
│   └── test_gpio.py
│
├── data/
│   └── scenario.json   # 4 pins, 16 steps
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 21_IoT/Gpio_Pins_Simulator

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

No runtime dependencies — `requirements.txt` only pins pytest.

---

# ▶️ Run

```bash
# Offline demo: LED, button, bounce, PWM, scenario, guard rails
python src/main.py --demo

# Replay the bundled scenario
python src/main.py --scenario data/scenario.json

# Replay with a stricter debounce and export the result
python src/main.py --scenario data/scenario.json --debounce 5 \
                   --json run.json
```

**Input:** a JSON object with `pins` (`number`, `mode`, `pull`) and `steps` (`op`, plus `pin`/`level`/`ms`/`frequency`/`duty` as needed).

**Exit codes:** `0` = success · `2` = usage/validation/scenario error.

---

# 🧠 How It Works

```text
scenario.json ──► load_scenario: validate pins + steps
                          │
                          ▼
                       Board(name)
        ┌─────────────────┼──────────────────┐
        ▼                 ▼                  ▼
     add_pin        step: write         step: advance
   (mode, pull)     set_input            tick += ms
        │           pwm / clear_pwm
        ▼                 │
    rest_level            ▼
    up->1, other->0    change? ──no──► nothing
                          │yes
                          ▼
                 _emit(edge, level)
                 ┌────────┴─────────┐
                 ▼                  ▼
          pin.events log      listeners
       (tick, pin, edge)   (rising/falling/both)
```

PWM sampling:

```text
phase  = (elapsed * frequency) mod 1
level  = 1 if phase < duty / 100 else 0      (duty 0 -> always 0,
                                              duty 100 -> always 1)
```

---

# 🛠 Technologies

- Python 3 standard library (`dataclasses`, `json`, `math`, `argparse`)
- pytest

No RPi.GPIO, no gpiozero, no hardware access at all.

---

# 📚 Concepts Covered

- GPIO modes, pull resistors and idle levels
- Active-low wiring and why buttons invert
- Rising/falling edge detection and event logs
- Debouncing with a persistence-count state machine
- PWM duty cycle, frequency and analytic sampling
- Aliasing: why the sample rate must exceed the waveform changes
- Listener/callback registration with edge filtering
- Declarative scenario replay and determinism
- Validation at the boundary with actionable error messages
- Testing a stateful simulation without hardware

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**123 tests passed** covering pin-number/mode/pull/level/edge/tick validation, debouncer adoption, persistence, reset and state reporting, pin lifecycle (claim, duplicate, lookup, release), output/input rest levels, write/read semantics and edge emission, listener filtering and payloads, mode switching and PWM reset, debounced bounce rejection, PWM configuration guards, exact duty patterns at 0/25/100 %, PWM averages, `Led` and `Button` helpers including active-low wiring, snapshots, reports, scenario loading (missing keys, duplicate pins, bad ops, missing fields) and replay determinism, JSON export, demo idempotency, quiet mode, and every CLI error path.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
