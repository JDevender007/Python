<div align="center">

# 🤖 Robotics Projects

### Five robotics projects where the geometry is the easy half. A pose is a matrix product you can check analytically; an inverse solution is a set, not a point; a filter estimate without a covariance is a guess; "shortest path" and "fastest planner" are different claims; and a trajectory is a timing problem sitting on top of a geometry one.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-Linear%20Algebra-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)

</div>

---

# 📖 About

Five projects covering the classic robotics stack — kinematics, estimation, planning and control — with
every arm, map and scenario shipped as a small JSON/CSV file in `data/`. There is no simulator to
install and no ROS: the maths is `numpy`, the geometry is written out, and each demo verifies its own
numbers against an independent formulation.

**The lesson of each project is different, on purpose.** Five variations on "multiply some matrices"
would teach nothing; five different ways a robotics result can look right and be wrong is the subject.

- **Forward_Kinematics** — *a pose is a matrix product, so there is always a second way to compute it.*
  A Denavit–Hartenberg chain can be coded correctly and still be wrong about joint order, angle
  convention, or the units of `d`. The rebuild builds the DH transforms explicitly, composes them to a
  pose, and cross-checks every scenario against an **independent analytic 2R solution** — then verifies
  the rotation block is **orthonormal**, that the planar arm produces **zero z and pure yaw**, that the
  prismatic lift moves only in z, and that limits and reach are reported per joint —
  **8 scenarios verified**.
- **Inverse_Kinematics** — *an inverse solution is a set, and the elbow branch is part of the answer.*
  A single returned joint vector hides the fact that a 2-link arm has two solutions, that joint limits
  can delete one of them, and that an iterative solver can converge to a pose that is not the target.
  The rebuild solves the closed form for both branches, runs damped least squares with seeded
  restarts, verifies the **Jacobian against finite differences**, requires the iterative and analytic
  solvers to **agree**, honours yaw when the target has one, and refuses unreachable targets by name —
  **9 targets, both elbow branches, limits held**.
- **Kalman_Filter_Localizer** — *an estimate without a covariance is a guess.* Reporting "the robot is
  here" is not a claim anyone can check; reporting a mean **and** a covariance that brackets the true
  error is. The rebuild implements the EKF with an arc motion model verified against **RK4
  integration**, checks **both Jacobians against finite differences**, gates innovations by
  Mahalanobis distance so **injected outliers are rejected**, asserts the covariance stays **positive
  definite**, verifies the **mean NEES is consistent**, and shows the filter **beating odometry** —
  plus a scalar filter checked against the closed-form gain.
- **Path_Planner** — *optimality and speed are different claims, and both need a witness.* A* with an
  inadmissible heuristic still returns a path; that path is just not the shortest. The rebuild runs
  **A* and Dijkstra on the same grid** and requires their costs to agree, requires A* to **expand fewer
  nodes**, verifies every path is **legal and contiguous**, makes smoothing **never lengthen** a path,
  keeps RRT **deterministic** under a seed, and refuses blocked maps and unknown symbols by name.
- **Robot_Arm_Simulator** — *a trajectory is a timing problem on top of a geometry one.* Reaching a
  waypoint is not enough: the motion must start and end at rest, respect joint and speed limits, and
  not pass through an obstacle between samples. The rebuild plans with **minimum-jerk** profiles,
  verifies **rest-to-rest** boundaries, checks **continuous samples** and straight Cartesian lines,
  reports the bundled mission as **collision-free**, detects a **blocked move**, and refuses
  impossible poses — with every limit checked per joint.

**Every claim is checkable.** Each demo prints `Cross-checks OK: ...` with the numbers it verified,
then `Demo completed successfully.`; run it twice and the bytes match, run it with `--quiet` and it
writes nothing at all.

The dependency list is `numpy` and `pandas`; no physics engine, no plotting requirement, no ROS.

---

# 🎓 Learning Objectives

- Build Denavit–Hartenberg transforms and compose them into an end-effector pose
- Cross-check a general chain against a closed-form solution you derived separately
- Verify that a rotation block is orthonormal and that a planar arm has no out-of-plane motion
- Read Euler angles back out of a rotation matrix with a stated convention (ZYX)
- Distinguish revolute and prismatic joints in both the maths and the data
- Recognise that a 2-link inverse problem has two solutions and name the branch
- Solve inverse kinematics in closed form and with damped least squares, then compare
- Check a Jacobian against finite differences before trusting it
- Enforce joint limits and refuse unreachable targets by name
- Write a motion model and validate it against a higher-order integrator
- Linearise a nonlinear model into Jacobians and check each one numerically
- Implement an EKF predict/update cycle with a covariance you can inspect
- Gate measurements by Mahalanobis distance so outliers cannot corrupt the state
- Interpret NEES as a consistency check rather than a score
- Compare a filter against dead reckoning on the same trajectory
- Implement A* and Dijkstra on one grid and compare cost and expansion count
- Prove a path is contiguous, legal and collision-free
- Smooth a path without making it longer
- Keep a sampling-based planner deterministic with a seed
- Time-parameterise a path with minimum-jerk profiles
- Enforce joint and speed limits across a trajectory, sample by sample
- Detect collisions between a moving arm and static obstacles
- Report motion evidence as numbers, not as an animation that "looks smooth"

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Forward_Kinematics | DH chains, analytic 2R cross-check, orthonormal rotations, limits and reach. | 51 | ✅
02 | Inverse_Kinematics | Closed-form 2-link with both elbow branches, damped least squares, Jacobian checks. | 109 | ✅
03 | Kalman_Filter_Localizer | EKF with arc motion model, numeric Jacobians, gating, NEES and covariance checks. | 150 | ✅
04 | Path_Planner | A* vs Dijkstra on one grid, legality and smoothing checks, seeded RRT. | 113 | ✅
05 | Robot_Arm_Simulator | Minimum-jerk trajectories, limit and speed enforcement, collision checking. | 146 | ✅

**Total: 569 tests.**

---

# 🧠 Concepts Covered

- Homogeneous transforms and the DH parameter convention
- Revolute and prismatic joints, and their different effect on a chain
- Rotation matrices, orthonormality, determinants, and Euler extraction (ZYX)
- Workspace reach: annulus bounds, maximum extension, and per-joint limits
- Closed-form inverse kinematics for a 2-link planar arm
- The elbow-up / elbow-down solution set and limit-based feasibility
- Damped least squares, pseudo-inverse behaviour, and restart seeding
- Jacobians by analytic differentiation and by finite differences
- Joint-limit clamping and unreachable-target refusal
- Differential-drive arc motion models and RK4 integration
- Linearisation and the EKF predict/update cycle
- Innovation covariance, Mahalanobis gating, and outlier rejection
- Covariance positive-definiteness and numerical symmetry
- NEES as a filter-consistency diagnostic
- Dead reckoning vs filtered estimates on the same ground truth
- Grid maps, 4- and 8-connectivity, and diagonal cost
- Dijkstra, A* and admissible heuristics
- Node-expansion counts as a measure of search efficiency
- Line-of-sight checks and Bresenham traversal
- Path smoothing that preserves or shortens cost
- Rapidly-exploring random trees and seeded determinism
- Minimum-jerk position and velocity profiles
- Rest-to-rest boundary conditions and speed scaling
- Cartesian-space straight lines vs joint-space interpolation
- Collision checking between moving links and static obstacles
- Determinism: seeded planning, byte-identical demo re-runs

---

# 📁 Repository Structure

```text
22_Robotics/
│
├── Forward_Kinematics/
│   ├── src/    fk.py, main.py
│   ├── tests/  test_fk.py
│   └── data/   arms.json, scenarios.csv
│
├── Inverse_Kinematics/
│   ├── src/    ik.py, main.py
│   ├── tests/  test_ik.py
│   └── data/   arms.json, targets.csv
│
├── Kalman_Filter_Localizer/
│   ├── src/    localizer.py, main.py
│   ├── tests/  test_localizer.py
│   └── data/   scenario.json, landmarks.csv
│
├── Path_Planner/
│   ├── src/    planner.py, main.py
│   ├── tests/  test_planner.py
│   └── data/   map.txt
│
└── Robot_Arm_Simulator/
    ├── src/    arm.py, main.py
    ├── tests/  test_arm.py
    └── data/   arm.json, mission.json
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI, a
`tests/` suite, deterministic data in `data/`, a pinned `requirements.txt`, a `.gitignore`, and a
`README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 22_Robotics/Forward_Kinematics

python src/main.py --demo                              # offline, deterministic, exit 0
python src/main.py --demo --quiet                       # prints nothing at all
python src/main.py --arm planar2 --angles 30,-45
python src/main.py --file data/scenarios.csv --json out.json
python -m pytest tests -q                               # the suite
```

Every project supports `--demo` (plus `--quiet`) and `--json <path>`, and adds its own flags
(`--file`, `--arm`, `--angles`, `--targets`, `--target`, `--method`, `--elbow`, `--q0`, `--damping`,
`--scenario`, `--landmarks`, `--gate`/`--no-gate`, `--map`, `--algorithm`, `--heuristic`, `--start`,
`--goal`, `--smooth`, `--seed`, `--pose`, `--mission`, `--move`, `--to`, `--cartesian`, `--steps`,
`--dt`, `--speed-scale`). No demo writes into the repository: JSON goes only where you point it.

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

- Why a kinematic chain needs a second, independent formulation before you trust it
- Why an orthonormal rotation block is a cheap and decisive test
- Why Euler extraction needs its convention stated, not implied
- Why an inverse solution is a set, and joint limits choose from it
- Why an iterative solver must be checked against a closed form where one exists
- Why a Jacobian checked by finite differences is the only Jacobian you can trust
- Why a motion model deserves an integrator comparison
- Why an estimate without covariance cannot be evaluated
- Why gating is what keeps one bad measurement from destroying a filter
- Why NEES detects an over-confident filter that looks accurate
- Why "beats odometry" is the baseline claim for any localiser
- Why an inadmissible heuristic still returns a path, just not the best one
- Why node expansions are the honest measure of planner speed
- Why smoothing a path can silently make it illegal, and how to test it
- Why a trajectory must be rest-to-rest to be executable
- Why collision checking must sample along the whole path, not at its endpoints
- How to make a robotics demo reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `load_arms`, `load_targets`, `load_scenario`, `load_landmarks`, `load_map`, `load_mission`
Values — `DHRow`, `Arm`, `Pose`, `Scenario`, `ArmIk`, `Target`, `IkSolution`, `Estimate`, `Plan`,
`Sample`, `Trajectory`, `MissionResult`
Kinematics — `dh_transform`, `forward_kinematics`, `end_effector`, `_euler_zyx`, `_analytic_planar2`,
`planar_fk`, `planar_jacobian`, `pose`, `link_points`
Inverse — `check_reachable`, `within_limits`, `solve_2link`, `solve_dls`, `_seed_patterns`, `solve`,
`solve_ik`
Estimation — `motion_model`, `motion_jacobian`, `integrate_rk4`, `measurement`, `measurement_jacobian`,
`ExtendedKalmanFilter`, `KalmanFilter1D`, `run_ekf`, `dead_reckon`, `mean_nees`, `rmse_position`
Planning — `parse_map`, `neighbours`, `astar`, `dijkstra`, `rrt`, `heuristic`, `line_of_sight`,
`smooth_path`, `path_cost`, `path_turns`
Control — `minjerk`, `minjerk_derivative`, `time_parameterize`, `plan_joint_move`,
`plan_cartesian_move`, `check_collisions`, `run_mission`
Rendering — `render_report`, `render_map`, `render_solution`, `render_table`, `render_scenario_table`
Refusal — `FkError`, `IkError`, `LocalizerError`, `PlannerError`, `ArmError`
Testing — analytic cross-checks, orthonormality, numeric Jacobians, NEES consistency, planner cost
agreement, rest-to-rest boundaries, collision samples, seeded determinism, CLI paths, quiet-mode
silence

---

# 🚀 Future Improvements

- A shared kinematics kernel, so FK and IK cannot disagree about the same arm file
- Redundant 3-link arms, where the inverse solution becomes a one-parameter family
- Unscented Kalman filter beside the EKF, on the same scenario
- Multi-hypothesis tracking for ambiguous landmark associations
- Anytime planners and a cost-versus-time curve for A*, RRT and RRT*
- Velocity and acceleration limits from a real datasheet, enforced and tested
- Trajectory scaling in time as a separate, testable step
- A category-wide `audit` harness comparing all five evidence tables in one shape

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
