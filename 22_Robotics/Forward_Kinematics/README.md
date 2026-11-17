<div align="center">

# 🦾 Forward Kinematics

### Joint angles → end-effector pose for DH-parameter serial arms — 2D planar and 3D spatial chains, joint-space vs task-space reports, reachability annulus checks. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-Linear%20Algebra-DD0031?style=for-the-badge&logo=numpy&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Forward Kinematics computes where a robot's end-effector is: you give it joint angles, it gives you a pose. This project implements the standard **Denavit-Hartenberg (DH)** convention for serial chains — each link contributes `T_i = Rz(θ)·Tz(d)·Tx(a)·Rx(α)` — with support for **revolute and prismatic joints**, **2D planar arms** (x, y, yaw in the plane) and **3D spatial arms** (x, y, z plus ZYX roll/pitch/yaw).

Every run reports the answer twice: once in **joint space** (angles against per-joint limits, with margin and OUT-of-range flags) and once in **task space** (position, orientation, and where the pose sits inside the arm's reachable annulus — `[2·L_max − L_total, L_total]` for planar chains). Arm definitions ship as bundled JSON, scenario joint tables as bundled CSV — nothing is downloaded at runtime. **No network, no API keys, no ROS, no hardware.**

---

# ✨ Features

- Standard DH transform builder for revolute (`θ = offset + q`) and prismatic (`d = offset + q`) joints
- `forward_kinematics(arm, q)` → 4×4 base-to-effector transform; `end_effector` → `(x, y, z, roll, pitch, yaw)`
- ZYX Euler extraction with domain-safe `arcsin` clipping (no NaNs from round-off)
- Joint-space vs task-space report: limits, margins, OUT flags, reach annulus, distance %
- Reachability checks: exact annulus for planar revolute chains, triangle-inequality bound for spatial/prismatic chains
- Strict validation: JSON schema (keys, joint types, finite values, `a ≥ 0`, `min ≤ max`), CSV scenario schema (arm exists, angle count, duplicates)
- `--angles "45,-90"` with fast-fail parsing **before** any file is touched; `--json` pose export
- Deterministic bundled scenarios: 4 arms × 8 configurations, identical output every run
- 51 passing pytest tests

---

# 📂 Folder Structure

```text
Forward_Kinematics/
│
├── src/
│   ├── main.py    # CLI: --demo, --file, --arm, --angles, --json, --quiet
│   └── fk.py      # DH maths, validation, reports, offline demo
│
├── tests/
│   └── test_fk.py
│
├── data/
│   ├── arms.json       # 4 arm definitions: 2R/3R planar, 3R spatial, R+P
│   └── scenarios.csv   # 8 deterministic joint-space configurations
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 22_Robotics/Forward_Kinematics

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: 8 scenarios, table + joint/task reports, cross-checks
python src/main.py --demo

# Default (first) arm from the bundled arms.json
python src/main.py --angles "45,-90"

# A specific arm from your own JSON
python src/main.py --file data/arms.json --arm planar3 --angles "20,-40,30"

# Pose report as JSON
python src/main.py --file data/arms.json --arm planar2 --angles "10,20" --json pose.json
```

Input schema — arm definitions (`data/arms.json`, one or more arms):

```json
{
  "planar2": {
    "description": "2R planar arm, links 1.00 + 0.80 m",
    "joints": ["R", "R"],
    "dh": [
      {"theta_offset": 0.0, "d": 0.0, "a": 1.0, "alpha": 0.0},
      {"theta_offset": 0.0, "d": 0.0, "a": 0.8, "alpha": 0.0}
    ],
    "limits": [[-180.0, 180.0], [-180.0, 180.0]]
  }
}
```

(`joints`: `R` = revolute, `P` = prismatic; `theta_offset`/`alpha` in degrees, `d`/`a` in metres; `limits` = `[min, max]` per joint — degrees for `R`, metres for `P`.)

Scenario CSV (`data/scenarios.csv`, blank `q` cells allowed for shorter arms):

```csv
scenario,arm,q0,q1,q2
home,planar2,0,0,
lift,prism2,45,0.35,
```

**Exit codes:** `0` = success · `2` = usage/schema/angle/arm error.

---

# 🧠 How It Works

```text
data/arms.json ──► validate (keys, R/P types, finite, a >= 0, min <= max)
                          │
                          ▼
   q = (q0 … qn) ──► per-link DH matrix (4×4)
        R: θ = offset + q (deg)        P: d = offset + q (m)
                          │
                          ▼  T = T0 @ T1 @ … @ Tn   (chain product)
                  4×4 base → effector transform
                          │
              ┌───────────┴────────────┐
              ▼                        ▼
      JOINT SPACE                 TASK SPACE
      q vs limits (ok/OUT)        x, y, z (m)
      revolute |q| total          roll, pitch, yaw (deg)
                                   reach annulus + distance %
```

Details worth knowing:

- **One matrix per link, multiplied in order** — the chain product *is* the kinematics; the demo cross-checks it against the closed-form 2R solution `x = a₁cos q₁ + a₂cos(q₁+q₂)`.
- **Planar arms fall out of the geometry**: all `alpha = 0` and `d = 0` means every z-axis stays parallel, so `z ≡ 0` and end-effector yaw equals the sum of joint angles — both asserted in the demo.
- **Reach annulus**: a planar chain of links `L_i` can reach exactly the annulus `[max(0, 2·L_max − ΣL), ΣL]`; spatial and prismatic chains use the triangle-inequality outer bound `Σ hypot(a, d)` (prismatic limits count their full travel).
- **Out-of-limit angles are computed, not rejected** — the report flags them `OUT` with the margin, so you can see how far past the stop a configuration goes (the Robot Arm Simulator, by contrast, hard-fails on limit violations).

---

# 🛠 Technologies

- Python 3
- NumPy (homogeneous transforms, Euler extraction, seeded cross-checks)
- pandas (scenario CSV loading and validation)
- argparse / json / logging / dataclasses
- pytest

---

# 📚 Concepts Covered

- Denavit-Hartenberg convention and the standard transform product
- Revolute vs prismatic joint variables
- Homogeneous transformation matrices and frame chaining
- ZYX Euler angles from a rotation matrix (and `arcsin` domain safety)
- Joint-space vs task-space representations of the same state
- Reachable-workspace annulus for planar chains; bound checks for spatial chains
- Per-joint limit margins and OUT-of-range reporting
- Deterministic offline demos: bundled JSON/CSV, fixed scenarios, idempotent output
- Fast-fail CLI validation before expensive work

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**51 tests passed** covering every validation rule (JSON keys, joint types, finite values, link lengths, limit pairs, CSV columns, angle counts, duplicate scenarios), analytic-vs-matrix agreement on seeded random angles, orthonormal rotations, planar yaw/zero-z identities, prismatic lift arithmetic, reach bounds, limit statuses, report/table rendering, demo idempotency and byte-identical re-runs, and every CLI path (demo, angles, file/arm, JSON export, fast-fail ordering, usage errors) — all offline. Extra cases pin the Euclidean pose distance and the `to_dict` key set on a real arm.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
