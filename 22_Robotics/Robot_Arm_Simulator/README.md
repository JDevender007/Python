<div align="center">

# 🦿 Robot Arm Simulator

### A planar 2R-plus-wrist arm: exact inverse kinematics, minimum-jerk trajectories, joint speed limits, Cartesian straight-line moves, collision checks and multi-waypoint pick-and-place missions. Fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Stdlib](https://img.shields.io/badge/Dependencies-Standard%20Library-blue?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Three questions decide whether a robot arm can do useful work: **can it reach the point, how does it get there, and does it hit anything on the way?** This project answers all three for a bench arm with two position links plus a wrist joint that only changes the tool orientation.

**The kinematics stay exact.** The two position links place the tool, so the closed form from the 2R planar arm applies directly. The wrist joint then absorbs whatever orientation is left:

```text
q2 = yaw − q0 − q1          (wrapped into [-180, 180])
```

Because the position and orientation are decoupled, IK has a closed-form answer — no iteration, no tolerance to tune. Every waypoint in the demo is reached to `~1e-16` m and the requested yaw to `1e-9` degrees.

**Motion is minimum-jerk.** A joint path is just a list of configurations. Timing them with a straight interpolation would snap the motors at both ends, so each leg uses the quintic minimum-jerk profile

```text
s(u) = 10u³ − 15u⁴ + 6u⁵        s(0) = 0, s(1) = 1
s'(u) = 30u² − 60u³ + 30u⁴      s'(0) = s'(1) = 0
```

whose derivative peaks at exactly `1.875` at `u = 0.5`. That number sets the duration: for the joint with the largest required rate, `duration = 1.875 · rate / max_speed`. Every other joint then automatically stays under its own limit, and each trajectory starts and ends at rest.

**Cartesian moves are compiled down to joint moves.** For a straight-line tool move the code walks `steps` points along the line, solves IK at each one (keeping the elbow branch nearest the previous solution), and hands the resulting joint path to the same time parameteriser. Interpolating in joint space between dense waypoints means the tool path is not *mathematically* straight — it bulges by `O(h²)`, about `3.4e-5` m over a half-metre move in the bundled mission, which is well below any real accuracy requirement.

**Collisions are geometric.** Each link is a line segment, each obstacle a circle. The check is the point-to-segment distance, and anything with `radius − distance > 0` is reported with its sample time, link index and penetration depth. The bundled mission clears its three obstacles; a deliberately blocked mission (the demo builds one) produces 18 collision samples instead of being silently accepted.

**Missions chain it all.** A mission is a home pose, an ordered list of waypoints with optional yaw, a dwell time, a waypoint count, and obstacles. Running it plans every Cartesian leg, appends a return-home leg, and reports per-leg samples, durations, end poses, waypoint error, total time and peak joint speeds.

The bundled arm is `bench3`: links `0.60 + 0.50 m` plus a massless tool, joint limits of ±180°, and speed caps of 120 / 140 / 200 deg/s. The bundled mission is a six-waypoint pick-and-place that returns home in 5.21 s, moving for 3.41 s.

No network, no API keys, no ROS, no hardware: the arm and mission are local JSON files.

---

# ✨ Features

- Exact closed-form IK for a 2R position chain plus a wrist joint
- Two elbow branches with nearest-configuration selection
- Joint limits enforced everywhere (IK, trajectories, missions)
- Minimum-jerk time parameterisation with rest-to-rest endpoints
- Automatic duration from the tightest joint speed limit
- Joint-space moves and Cartesian straight-line moves
- Per-sample joint values, tool pose and joint speeds
- Circular-obstacle collision detection against every link
- Multi-waypoint missions with dwell, return-home leg and per-leg timing
- Strict validation of arm JSON and mission JSON (types, finiteness, duplicates, limits)
- `--pose`, `--move` / `--to`, `--cartesian`, `--mission`, `--steps`, `--dt`, `--speed-scale`, `--json`, `--quiet`
- Fast-fail flag validation before any file is read
- Deterministic bundled data: 1 arm, 6 waypoints, 3 obstacles
- 146 passing pytest tests

---

# 📂 Folder Structure

```text
Robot_Arm_Simulator/
│
├── src/
│   ├── main.py   # CLI: --pose, --move/--to, --mission, JSON export
│   └── arm.py    # model, IK, trajectories, collisions, missions, demo
│
├── tests/
│   └── test_arm.py
│
├── data/
│   ├── arm.json       # bench3: links 0.60 + 0.50, 3 joints, speed caps
│   └── mission.json   # pick_and_place: 6 waypoints, dwell 0.3 s, 3 obstacles
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 22_Robotics/Robot_Arm_Simulator

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

No runtime dependencies — `requirements.txt` only pins pytest.

---

# ▶️ Run

```bash
# Offline demo: plan the bundled mission, then run 9 self-checks
python src/main.py --demo

# Inverse kinematics for one pose (position + tool yaw)
python src/main.py --pose "0.55,0.35,90"

# Joint-space move between two configurations
python src/main.py --move "0,0,0" --to "30,20,10"

# Straight-line Cartesian move (position and yaw)
python src/main.py --move "0.55,0.35,90" --to "0.70,0.28,60" --cartesian

# Plan the bundled mission and export every sample
python src/main.py --mission data/mission.json --json result.json
```

**Input:** an arm JSON object with `links` (2 or 3 entries) and one `joints` entry per link (`name`, `low`, `high`, `max_speed`); a mission JSON object with `home`, `waypoints`, optional `obstacles`, `dwell` and `steps`.

**Exit codes:** `0` = success · `2` = usage, validation or solver error · `3` = mission planned but collisions detected.

---

# 🧠 How It Works

```text
arm.json ──► ArmSpec ──► mission.json ──► Mission
                              │
                    for each waypoint:
                       Cartesian line
                              │
                  ┌───────────┴────────────┐
                  ▼                        ▼
            IK at 41 points          nearest elbow
            (closed form)            branch kept
                  │                        │
                  └───────────┬────────────┘
                              ▼
                    joint path ──► minimum-jerk timing
                              │         duration from
                              │         1.875 · rate / vmax
                              ▼
                    samples: t, q, pose, speeds
                              │
                              ▼
                link segments vs circular obstacles
                              │
                              ▼
                  MissionResult + report
```

Reachability of the 2R chain is the same annulus as the Inverse Kinematics project:

```text
outer = L1 + L2
inner = max(0, 2 · max(L1, L2) − (L1 + L2))
reachable = { p : inner ≤ |p| ≤ outer }
```

The minimum-jerk peak rate is the reason duration is cheap to compute:

```text
duration = max over joints of  (1.875 · |Δq_max| / max_speed)
```

and the sampled speed of a joint is `Δq_max · s'(u) / duration`, which is guaranteed to stay under its cap because `s'(u) ≤ 1.875`.

---

# 🛠 Technologies

- Python 3 standard library (`math`, `json`, `dataclasses`, `argparse`, `pathlib`)
- pytest

No NumPy, no physics engine, no plotting library.

---

# 📚 Concepts Covered

- Decoupling position and orientation to keep IK closed-form
- Analytic inverse kinematics with elbow-branch selection
- Joint limits and speed limits as first-class constraints
- Minimum-jerk trajectory profiles and their peak-rate factor
- Time parameterisation of a joint path under velocity limits
- Cartesian straight-line motion via dense IK resampling
- Interpolation error `O(h²)` when interpolating in joint space
- Point-to-segment distance and circular keep-out zones
- Mission composition: waypoints, dwell, return-home leg
- Validation of declarative robot descriptions
- Determinism as a testable property of a simulator

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**146 tests passed** covering scalar helpers, minimum-jerk shape and peak, joint and arm schema validation (types, finiteness, link counts, limits, speeds), arm and mission loading error paths, pose parsing, mission validation (home, dwell, steps, duplicate waypoints, obstacle schemas), forward kinematics and link geometry, IK accuracy, both elbow branches, nearest-branch selection, wrist requirements, joint-limit infeasibility, time parameterisation (rest-to-rest, speed limits, scaling, single configuration, invalid flags), Cartesian moves (endpoint accuracy, straightness, yaw handling, unreachable targets), collision detection and clearance, mission planning and determinism, report rendering, demo idempotency, and every CLI path including collision exit code 3.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
