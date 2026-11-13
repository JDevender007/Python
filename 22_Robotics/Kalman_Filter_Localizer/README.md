<div align="center">

# 🧭 Kalman Filter Localizer

### A differential-drive robot localises itself from noisy wheel odometry and noisy landmark range/bearing sightings, fused by an extended Kalman filter with innovation gating. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-2.5.2-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Wheel odometry is cheap and continuous, but it drifts: every small error in wheel radius, slip or heading is integrated forever. A landmark sighting is absolute, but it only arrives now and then, and it is noisy too. **This project fuses the two.**

The state is the planar pose `[x, y, θ]`. Prediction runs the robot's motion model, correction uses range/bearing sightings of known landmarks.

**The motion model is exact, not Euler.** A differential drive with constant `(v, ω)` over `dt` traces an arc of radius `R = v/ω`:

```text
x' = x + R · (sin(θ + ω·dt) − sin θ)
y' = y − R · (cos(θ + ω·dt) − cos θ)
θ' = θ + ω·dt
```

with the straight-line limit taken when `|ω|` is tiny. `integrate_rk4` in the same module integrates the underlying ODE numerically, and the demo asserts that the two agree to `1e-8` — so the closed form is not a first-order approximation that quietly biases the filter.

**The filter is an EKF over that model.** The Jacobian `d(state')/d(state)` is analytic and is checked against central finite differences. Covariance updates use the Joseph form, `P ← (I−KH)P(I−KH)ᵀ + KRKᵀ`, which stays positive semi-definite even when the gain is ill-conditioned. The measurement model

```text
range   = ‖L − p‖
bearing = atan2(Ly − y, Lx − x) − θ        (wrapped)
```

likewise has an analytic `2×3` Jacobian, also checked against finite differences.

**Gating throws away the bad sightings.** Each innovation `ν = z − h(x)` has covariance `S = HPHᵀ + R`, so the normalised innovation squared `NIS = νᵀS⁻¹ν` is chi-square with two degrees of freedom. Anything above the 95% threshold (`5.991`) is rejected instead of being allowed to yank the estimate. In the bundled run the gate rejects every injected outlier and only 1 extra sighting out of 200.

**A scalar filter keeps the arithmetic honest.** `KalmanFilter1D` is the one-dimensional textbook filter, used as a baseline so the matrix algebra has something simple to be checked against: with unit prior variance and unit measurement variance the gain must be exactly `0.5`, and the demo asserts that.

**Every claim in the demo is measured, not assumed.** This project deliberately does not claim "the EKF beats odometry on every seed" — sometimes a lucky odometry realisation is unusually good. The bundled scenario pins one deterministic seed where the drift is meaningful (`0.397 m` final, `0.182 m` RMSE) and the filter cuts it to `0.097 m` final and `0.049 m` RMSE — a 4.1× improvement — while reporting a mean NEES of `1.34`, close to the consistency value of 3 for a three-dimensional state.

The bundled room has five landmarks (`nw`, `ne`, `se`, `sw`, `centre` on a 1–9 m square) and a six-segment survey drive at `dt = 0.1 s`, 200 steps, 20 s.

No network, no API keys, no ROS, no hardware: landmarks are a CSV and the scenario a JSON file.

---

# ✨ Features

- Exact closed-form differential-drive arc model plus its analytic Jacobian
- RK4 integrator kept as an independent check of the motion model
- Analytic range/bearing measurement model and Jacobian
- Extended Kalman filter with Joseph-form covariance updates
- Chi-square innovation gating (NIS) with configurable threshold
- Scalar `KalmanFilter1D` baseline and a `filter_scalar` trace helper
- Deterministic simulation: ground truth, noisy odometry, noisy sightings, injected outliers
- Dead reckoning for comparison
- Metrics: position RMSE, per-step error, heading error, NEES
- ASCII map of truth / odometry / estimate / landmarks
- Strict validation of scenario JSON and landmark CSV (types, finiteness, duplicates, ranges)
- `--scenario`, `--landmarks`, `--gate`, `--no-gate`, `--map`, `--json`, `--quiet`
- Fast-fail flag validation before any file is read
- Deterministic bundled data: 5 landmarks, 6 segments, 200 steps
- 150 passing pytest tests

---

# 📂 Folder Structure

```text
Kalman_Filter_Localizer/
│
├── src/
│   ├── main.py        # CLI: --demo, --scenario, --gate, --map, --json
│   └── localizer.py   # models, EKF, simulation, metrics, reports, demo
│
├── tests/
│   └── test_localizer.py
│
├── data/
│   ├── landmarks.csv   # 5 landmarks on a 1-9 m square
│   └── scenario.json   # room_survey: 6 segments, 200 steps, seed 3
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 22_Robotics/Kalman_Filter_Localizer

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

Only NumPy is required at runtime; pytest is pinned for the tests.

---

# ▶️ Run

```bash
# Offline demo: simulate, filter, then run 10 self-checks
python src/main.py --demo

# Filter the bundled scenario (default action)
python src/main.py

# Compare against a looser or a disabled gate
python src/main.py --gate 9.21
python src/main.py --no-gate

# Print the ASCII map and export every estimate
python src/main.py --map --json run.json
```

**Input:** a scenario JSON object with `dt`, `initial_state`, a `segments` list of `{v, w, steps}`, `odom_noise`, `meas_noise`, and optional `gate`, `range_limit`, `outlier_every`, `outlier_bias`; a landmark CSV with columns `id,x,y`.

**Exit codes:** `0` = success · `2` = usage or validation error.

---

# 🧠 How It Works

```text
scenario.json ──► Scenario ──┐
landmarks.csv ──► Landmarks ─┤
                             ▼
                         simulate (seeded RNG)
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   truth poses        noisy odometry      noisy sightings
        │                    │                    │
        │              dead reckon                │
        │                    │                    │
        └────────────────────┴────────► run_ekf ─┘
                                            │
                              predict: arc model + Jacobian
                                            │
                              update:  NIS gate ── reject if > 5.991
                                            │
                              Joseph form covariance update
                                            │
                                            ▼
                        estimates + RMSE + NEES + map
```

The predict step, written out:

```text
x⁻ = f(x, u, dt)
P⁻ = F P Fᵀ + Q          Q = diag(σ_xy², σ_xy², σ_θ²)
```

and the correction:

```text
ν = z − h(x⁻)
S = H P⁻ Hᵀ + R
K = P⁻ Hᵀ S⁻¹
x = x⁻ + K ν
P = (I − K H) P⁻ (I − K H)ᵀ + K R Kᵀ
```

with `NIS = νᵀ S⁻¹ ν` computed before deciding whether to apply the update at all.

---

# 🛠 Technologies

- Python 3 standard library (`math`, `json`, `csv`, `dataclasses`, `argparse`, `pathlib`)
- NumPy 2.5.2 (linear algebra, seeded RNG)
- pytest

No plotting library, no ROS, no SciPy.

---

# 📚 Concepts Covered

- Exact vs numerical integration of a differential-drive motion model
- Analytic Jacobians and their finite-difference verification
- Extended Kalman filter prediction and correction
- Joseph-form covariance updates and positive definiteness
- Normalised innovation squared and chi-square gating
- Outlier rejection in state estimation
- Dead reckoning drift vs landmark-corrected estimates
- Position RMSE, heading error and NEES consistency
- Deterministic simulation with a seeded RNG
- Validation of declarative scenario and landmark data
- Percentile thresholds (`χ²(2, 0.95) = 5.991`) as practical engineering constants

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**150 tests passed** covering angle wrapping, the exact arc model (straight, quarter-turn, in-place rotation, wrapping, bad `dt`), both Jacobians against finite differences, RK4 agreement with the closed form and its argument validation, the measurement model and its wrap/coincidence handling, the scalar filter gain and variance bookkeeping, every `ExtendedKalmanFilter` constructor and update error path, gating acceptance and rejection, NEES, scenario schema validation (name, seed, `dt`, initial state, segments, noises, gate, outlier settings), landmark CSV parsing errors, simulation determinism and outlier bookkeeping, dead reckoning, `run_ekf` overrides and failure modes, metric helpers and their length checks, map/report rendering, demo idempotency, and every CLI path including fast-fail validation.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
