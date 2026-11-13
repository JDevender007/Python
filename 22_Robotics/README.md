<div align="center">

# 🦾 Robotics Projects

### Five offline robotics simulations: forward kinematics, analytic inverse kinematics, A*/RRT path planning, a full motion-planned arm, and an extended Kalman filter that localises a robot from odometry and landmarks.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Robotics is a chain of questions asked in order: **where is the tool, can it reach that point, how does the arm or the vehicle get there, and where does it actually think it is?** Get one link wrong and everything downstream is subtly off — a base that is 2 mm out becomes a 3 cm miss at the gripper, and an unmodelled heading error becomes a kilometre of drift.

This category builds that chain in miniature, one project per link:

- **Forward_Kinematics** composes joint angles into tool poses for 2R, 3R and 4-joint arms, and checks the analytic result against a hand-rolled transform chain.
- **Inverse_Kinematics** solves the same arms backwards in closed form (plus damped least squares for the unreachable cases), picking the reachable elbow branch and respecting joint limits.
- **Path_Planner** searches a grid maze with A*, smooths the route, and plans in continuous space with an RRT that must actually reach the goal.
- **Robot_Arm_Simulator** chains IK, minimum-jerk timing, speed limits and circular-obstacle collision checks into multi-waypoint pick-and-place missions.
- **Kalman_Filter_Localizer** fuses drifting wheel odometry with noisy landmark range/bearing sightings using an EKF with chi-square gating.

Every project runs on bundled data, finishes its demo in a few seconds, and **asserts its own numerical claims** — exact IK residuals, arc-vs-RK4 agreement, finite-difference Jacobians, gate rejections — instead of printing numbers for a human to squint at.

---

# 🎯 Learning Objectives

- Compose 2D rigid transforms and predict tool poses from joint angles
- Solve planar inverse kinematics in closed form with both elbow branches
- Handle joint limits, reach annuli and infeasible targets honestly
- Fall back to damped least squares when the closed form cannot be used
- Implement A* correctly (heap ordering, admissible heuristic, tie-breaking)
- Smooth a grid path and cost the smoothed route rather than the raw one
- Plan in continuous space with a sampling-based planner that provably reaches the goal
- Time parameterise a joint path under velocity limits with rest-to-rest motion
- Compile Cartesian straight-line motion down to a joint trajectory
- Detect collisions between link segments and circular keep-out zones
- Integrate an exact differential-drive motion model and verify it against RK4
- Derive and verify analytic Jacobians against finite differences
- Fuse noisy sensors with an EKF using Joseph-form covariance updates
- Gate innovations with the chi-square / NIS test and reject outliers
- Judge a filter with RMSE and NEES rather than a single lucky run

---

# 📂 Projects

No. | Project | Description | Status
--: | --- | --- | :---:
01 | Forward_Kinematics | 2R/3R/4-joint arms, tool poses, analytic vs transform-chain cross-check, workspace sampling. | ✅
02 | Inverse_Kinematics | Closed-form IK, both elbow branches, joint limits, damped least squares fallback. | ✅
03 | Path_Planner | A* on a 15x21 maze, Bresenham smoothing, RRT in continuous space, cost accounting. | ✅
04 | Robot_Arm_Simulator | Exact IK + minimum-jerk timing + speed limits + collision checks over 6-waypoint missions. | ✅
05 | Kalman_Filter_Localizer | EKF over odometry + landmark range/bearing, NIS gating, NEES consistency, ASCII map. | ✅

---

# 💡 Concepts Covered

- Homogeneous 2D transforms and rotation composition
- Analytic forward kinematics and elbow-up / elbow-down solutions
- Reach annulus (`inner <= |p| <= outer`) and wrist decoupling
- Joint-limit feasibility and nearest-branch selection
- Damped least squares (Levenberg-Marquardt style) iteration
- Grid search with A*: admissible heuristics, `g`-score bookkeeping, tie-breaking
- Line-of-sight smoothing and Bresenham rasterisation
- Sampling-based planning with Rapidly-exploring Random Trees
- Minimum-jerk quintic profiles and the `1.875` peak-rate factor
- Time parameterisation under velocity limits and Cartesian resampling
- Point-to-segment distance for circular obstacle clearance
- Exact differential-drive arc integration vs RK4 integration of the ODE
- Extended Kalman filtering with analytic Jacobians
- Joseph-form covariance updates and positive definiteness
- Normalised innovation squared and chi-square gating for outlier rejection
- RMSE, per-step error and NEES as consistency diagnostics
- Deterministic seeded simulation as a testable property

---

# 📁 Repository Structure

```text
22_Robotics/
│
├── Forward_Kinematics/
├── Inverse_Kinematics/
├── Path_Planner/
├── Robot_Arm_Simulator/
├── Kalman_Filter_Localizer/
│
└── README.md
```

Each project contains:

```text
Project_Name/
├── src/              # main.py + library modules
├── tests/            # pytest test suite
├── data/             # bundled arms / mazes / landmarks / scenarios
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠 Technologies

- Python 3
- NumPy (Kalman_Filter_Localizer)
- Standard library (`math`, `json`, `csv`, `heapq`, `random`, `dataclasses`, `argparse`)
- pytest

---

# 📈 Progress

| Project | Status |
| --- | :---: |
| Forward Kinematics | ✅ |
| Inverse Kinematics | ✅ |
| Path Planner | ✅ |
| Robot Arm Simulator | ✅ |
| Kalman Filter Localizer | ✅ |

**Completed:** **5 / 5 Projects** · 567 passing tests

---

# ▶️ Quick Start

```bash
cd 22_Robotics/Path_Planner

python src/main.py --demo     # offline demo
python -m pytest tests/ -q    # run the tests
```

Each project follows the same shape: `python src/main.py --demo` for a self-checking offline run, `python -m pytest tests/ -q` for the suite.

---

# 📚 Skills Developed

- Deriving closed-form kinematics and validating them numerically
- Writing planners that are correct about ordering, costs and goal reachability
- Turning declarative robot descriptions (JSON arms, missions) into validated specs
- Building trajectory generators that respect physical limits by construction
- Implementing state estimators and testing them for consistency, not just accuracy
- Verifying analytic derivatives against finite differences
- Writing honest statistical claims: pinning a seed, bounding an RMSE, checking a NEES band
- Writing 49–150 pytest cases per project, including every error path and CLI flag

---

# 🚀 Key Learning Outcomes

- Compute tool poses for planar arms and check them two independent ways
- Solve IK in closed form, choose a branch, and know when a target is infeasible
- Plan a collision-free path on a grid and in continuous space
- Drive a simulated arm through a multi-waypoint mission with timing and collisions
- Localise a robot by fusing odometry with landmark sightings under an EKF

---

# 🔮 Future Enhancements

- 3D kinematics with quaternion orientation
- Dynamic programming planners (D*, RRT*) with anytime replanning
- Velocity and acceleration limits with jerk-bounded profiles
- Multi-hypothesis tracking for ambiguous landmark associations
- A small SLAM loop that estimates landmark positions alongside the pose

---

# 🤝 Contributions

Contributions, issues and feature requests are welcome. Feel free to open an issue or submit a pull request.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this category useful, consider giving this repository a star.

</div>
