<div align="center">

# 🦾 Inverse Kinematics

### Task-space target → joint angles for planar arms — a closed-form 2-link solver with both elbow branches, and damped least squares with deterministic restarts for 3–4 link chains. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-Linear%20Algebra-DD0031?style=for-the-badge&logo=numpy&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Forward kinematics is a function; inverse kinematics is a search. Given a point (and optionally an orientation) the arm must reach, IK asks which joint values put the tool there. This project solves it two ways and cross-checks them against each other.

**Analytic 2-link solution.** For links `a1, a2` and target distance `r`, the law of cosines gives

```text
cos(q2) = (r² − a1² − a2²) / (2 · a1 · a2)
q1      = atan2(y, x) − atan2(a2 sin q2, a1 + a2 cos q2)
```

`q2` has two signs, so there are two **elbow branches** — `up` (positive elbow) and `down` (negative elbow). Both reach the same point with different joint values and different posture. The solver returns the residual of an FK round-trip, and for every bundled 2-link target that residual is `< 1e-9` m.

**Damped least squares** for longer chains. The analytic Jacobian `J = ∂(x, y[, yaw]) / ∂q` is built per iteration and the step is

```text
Δq = Jᵀ (J Jᵀ + λ² I)⁻¹ e
```

Damping `λ` keeps the step finite near singularities where `J Jᵀ` would be non-invertible. It solves 3-link and 4-link position problems and can also hit an end-effector yaw target.

**Restarts matter.** A single descent from `q = 0` stalls in local minima: in a 400-sample sweep of reachable random targets, 17 of 223 converged poorly from a standing start. `solve_dls` therefore retries from five fixed seeds and keeps the best attempt — the same sweep then converges on **all 223**. The seeds are constants, so the result is fully deterministic, and the returned `extra` field says which restart won.

**Reachability is checked before solving.** The workspace is an annulus `[max(0, 2·L_max − L_total), L_total]`; a target inside the outer radius but inside the inner hole is rejected. With a yaw target there is a second condition: pinning the last link's orientation means the **wrist point** — the target minus that last link — must still lie inside the remaining chain's annulus. Skipping that test is why naive IK code "fails to converge" on targets that are simply impossible.

No network, no API keys, no ROS, no hardware: arms ship in `data/arms.json`, targets in `data/targets.csv`.

---

# ✨ Features

- Closed-form 2-link IK with `up` / `down` elbow branches
- Damped least squares on the analytic Jacobian, with damping, tolerance and iteration budget
- Deterministic multi-seed restarts that escape local minima
- Yaw targets for 3+ link chains, with wrapped yaw-error reporting
- Exact annulus reachability plus the orientation-constrained wrist test
- Joint-limit reporting via `within_limits`
- Residual, position error, yaw error, iteration count and convergence flag on every solution
- Strict validation of arms JSON and targets CSV (schema, duplicates, unknown arms, finiteness)
- `--target`, `--targets`, `--arm`, `--method`, `--elbow`, `--q0`, `--damping`, `--json`, `--quiet`
- Fast-fail flag validation before any file is read
- Deterministic bundled data: 4 arms × 9 targets
- 109 passing pytest tests

---

# 📂 Folder Structure

```text
Inverse_Kinematics/
│
├── src/
│   ├── main.py   # CLI: --demo, --target(s), --method, --elbow, --q0, --json
│   └── ik.py     # FK/Jacobian, validation, solvers, reports, offline demo
│
├── tests/
│   └── test_ik.py
│
├── data/
│   ├── arms.json     # planar2, planar3, long2 (hole), wrist4
│   └── targets.csv   # 9 deterministic targets, 3 with yaw
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 22_Robotics/Inverse_Kinematics

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: solve all bundled targets, then run 9 self-checks
python src/main.py --demo

# One 2-link target, elbow-up branch
python src/main.py --target "1.0,0.8" --arm planar2

# Same target, elbow-down
python src/main.py --target "1.0,0.8" --arm planar2 --elbow down

# 3-link target with yaw, damped least squares
python src/main.py --target "1.0,0.5,45" --arm planar3 --method dls

# Batch solve and export
python src/main.py --targets data/targets.csv --json solutions.json
```

**Input:** an arms JSON object of `{name: {links: [...], limits: [[min, max], ...]}}`, and a target CSV with columns `target,arm,x,y[,yaw]`.

**Exit codes:** `0` = success · `2` = usage, validation, unreachable target or solver error.

---

# 🧠 How It Works

```text
targets.csv ──► load + validate ──► for each target
                                        │
                          ┌─────────────┴──────────────┐
                          ▼                            ▼
                   2 links, x/y only            3+ links or yaw
                          │                            │
                   closed form                  damped least squares
                   q2 = ±acos(...)              Δq = Jᵀ(JJᵀ + λ²I)⁻¹e
                   two elbow branches           restart on a stall
                          │                            │
                          └─────────────┬──────────────┘
                                        ▼
                          FK round-trip → residual
                          annulus + wrist reachability
                          joint-limit check
```

The reachable workspace of a planar chain:

```text
outer = sum(link lengths)
inner = max(0, 2 · max(link lengths) − outer)
reachable = {p : inner ≤ |p| ≤ outer}
```

With a yaw target, replace `p` by `p − L_last · (cos yaw, sin yaw)` and re-test against the annulus of the remaining links.

---

# 🛠 Technologies

- Python 3
- NumPy (matrix algebra, `linalg.solve`, `linalg.norm`)
- pandas (target CSV loading)
- Standard library (`json`, `dataclasses`, `argparse`, `math`)
- pytest

---

# 📚 Concepts Covered

- Inverse kinematics as an optimisation/search problem
- Closed-form 2R geometry and the two elbow branches
- Workspace annulus and inner "hole" reachability
- Orientation-constrained reachability (the wrist-point test)
- The analytic Jacobian of a planar chain
- Damped least squares / Levenberg-Marquardt style damping
- Local minima and deterministic multi-start restarts
- Convergence criteria: residual, tolerance, iteration budget
- Yaw error wrapping with `atan2(sin, cos)`
- Separating task-space error (metres/radians) from joint-space values (degrees)
- Strict schema validation for bundled data

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**109 tests passed** covering arm schema validation (types, finiteness, positivity, limit order), arm and target loading error paths, duplicate and unknown targets, target parsing, annulus and wrist reachability, FK and finite-difference Jacobian agreement, both elbow branches, analytic residual and round-trip accuracy, DLS convergence with and without yaw, the restart rescue on a known local minimum, determinism, iteration budgets, negative damping/tolerance/iteration validation, solver dispatch, report and table rendering, demo idempotency, and every CLI path including JSON export.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
