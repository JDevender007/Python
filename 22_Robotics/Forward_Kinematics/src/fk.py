"""Forward kinematics for DH-parameter serial arms - fully offline.

Standard Denavit-Hartenberg convention: each link contributes

    T_i = Rz(theta) * Tz(d) * Tx(a) * Rx(alpha)

where theta is the joint variable for revolute joints (degrees) and d is
the joint variable for prismatic joints (metres).  Joint angles go in,
the end-effector pose comes out: position (x, y, z) plus ZYX Euler
angles (roll, pitch, yaw in degrees).

Everything is local: arm definitions live in a JSON file, scenario
joint-angle tables in a CSV.  No ROS, no hardware, no network.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

LOG = logging.getLogger("fk")

JOINT_TYPES = ("R", "P")
DH_KEYS = ("theta_offset", "d", "a", "alpha")
ARM_KEYS = ("joints", "dh", "limits")
DEG = np.pi / 180.0
REACH_TOL = 1e-9


class FkError(RuntimeError):
    """Raised for missing files, bad schemas, and invalid arm data."""


# --------------------------------------------------------------------------- #
# Arm model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DHRow:
    """One Denavit-Hartenberg link row (angles in degrees, lengths in m)."""

    theta_offset: float
    d: float
    a: float
    alpha: float


@dataclass(frozen=True)
class Arm:
    """A serial chain: joint types, DH rows, and per-joint limits."""

    name: str
    joints: tuple[str, ...]
    rows: tuple[DHRow, ...]
    limits: tuple[tuple[float, float], ...]
    description: str = ""

    @property
    def n_joints(self) -> int:
        return len(self.joints)

    @property
    def is_planar(self) -> bool:
        """All revolute with parallel axes and no base offset."""
        return (all(j == "R" for j in self.joints)
                and all(r.alpha == 0.0 and r.d == 0.0 for r in self.rows))

    @property
    def max_reach(self) -> float:
        """Upper bound on end-effector distance (triangle inequality)."""
        total = 0.0
        for row, joint, (low, high) in zip(self.rows, self.joints,
                                           self.limits):
            if joint == "P":
                # prismatic travel extends the chain: worst endpoint
                total += float(max(np.hypot(row.a, row.d + low),
                                   np.hypot(row.a, row.d + high)))
            else:
                total += float(np.hypot(row.a, row.d))
        return total

    @property
    def min_reach(self) -> float:
        """Inner radius of a planar revolute chain's reachable annulus."""
        if not self.is_planar:
            return 0.0
        lengths = [r.a for r in self.rows]
        return max(0.0, 2.0 * max(lengths) - sum(lengths))


@dataclass(frozen=True)
class Pose:
    """End-effector pose: metres + ZYX Euler angles in degrees."""

    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float

    @property
    def distance(self) -> float:
        return float(np.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2))

    def to_dict(self) -> dict:
        return {"x": round(self.x, 6), "y": round(self.y, 6),
                "z": round(self.z, 6), "roll": round(self.roll, 4),
                "pitch": round(self.pitch, 4), "yaw": round(self.yaw, 4)}


@dataclass(frozen=True)
class Scenario:
    """One bundled joint-space configuration."""

    name: str
    arm: str
    q: tuple[float, ...]


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def arm_from_dict(name: str, payload: object) -> Arm:
    """Build and validate one Arm from its JSON payload."""
    if not isinstance(payload, dict):
        raise FkError(f"arm {name!r} must be a JSON object")
    missing = [k for k in ARM_KEYS if k not in payload]
    if missing:
        raise FkError(f"arm {name!r} missing key(s): {', '.join(missing)}")

    joints_raw = payload["joints"]
    if not isinstance(joints_raw, list) or not joints_raw:
        raise FkError(f"arm {name!r} joints must be a non-empty list")
    joints: list[str] = []
    for joint in joints_raw:
        if joint not in JOINT_TYPES:
            raise FkError(
                f"joint type must be R or P (got {joint!r}) for arm {name!r}")
        joints.append(joint)

    dh_raw = payload["dh"]
    if not isinstance(dh_raw, list) or len(dh_raw) != len(joints):
        raise FkError(
            f"arm {name!r} dh must have exactly {len(joints)} row(s)")
    rows: list[DHRow] = []
    for i, entry in enumerate(dh_raw):
        if not isinstance(entry, dict):
            raise FkError(f"arm {name!r} dh row {i} must be an object")
        missing_row = [k for k in DH_KEYS if k not in entry]
        if missing_row:
            raise FkError(
                f"arm {name!r} dh row {i} missing key(s): "
                f"{', '.join(missing_row)}")
        values = []
        for key in DH_KEYS:
            try:
                number = float(entry[key])
            except (TypeError, ValueError) as exc:
                raise FkError(
                    f"arm {name!r} dh row {i} value {key!r} "
                    f"must be numeric") from exc
            if not np.isfinite(number):
                raise FkError(
                    f"arm {name!r} dh row {i} value {key!r} must be finite")
            values.append(number)
        if values[2] < 0.0:
            raise FkError(
                f"arm {name!r} dh row {i} link length a must be >= 0")
        rows.append(DHRow(*values))

    limits_raw = payload["limits"]
    if not isinstance(limits_raw, list) or len(limits_raw) != len(joints):
        raise FkError(
            f"arm {name!r} limits must have exactly {len(joints)} "
            f"entr(ies)")
    limits: list[tuple[float, float]] = []
    for i, entry in enumerate(limits_raw):
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            raise FkError(f"arm {name!r} limit {i} must be [min, max]")
        try:
            low, high = float(entry[0]), float(entry[1])
        except (TypeError, ValueError) as exc:
            raise FkError(
                f"arm {name!r} limit {i} must be numeric") from exc
        if not np.isfinite(low) or not np.isfinite(high):
            raise FkError(f"arm {name!r} limit {i} must be finite")
        if low > high:
            raise FkError(
                f"arm {name!r} limit {i} min must be <= max")
        limits.append((low, high))

    description = payload.get("description", "")
    if not isinstance(description, str):
        raise FkError(f"arm {name!r} description must be a string")

    return Arm(name=name, joints=tuple(joints), rows=tuple(rows),
               limits=tuple(limits), description=description)


def load_arms(path: str | Path) -> dict[str, Arm]:
    """Load and validate an arms JSON file -> {name: Arm}."""
    source = Path(path)
    if not source.is_file():
        raise FkError(f"file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise FkError(f"could not parse {source.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FkError(
            f"expected a JSON object of arm definitions in {source.name}")
    if not payload:
        raise FkError(f"no arm definitions in {source.name}")
    arms = {name: arm_from_dict(name, entry)
            for name, entry in payload.items()}
    LOG.info("loaded %d arm(s) from %s", len(arms), source.name)
    return arms


def select_arm(arms: dict[str, Arm], name: str | None = None) -> Arm:
    """Pick an arm by name (default: first definition, JSON order)."""
    if not arms:
        raise FkError("no arms loaded")
    if name is None:
        return next(iter(arms.values()))
    if name not in arms:
        available = ", ".join(arms)
        raise FkError(f"unknown arm {name!r}; available: {available}")
    return arms[name]


def load_scenarios(path: str | Path,
                   arms: dict[str, Arm]) -> list[Scenario]:
    """Load and validate the bundled scenario CSV against the arms."""
    source = Path(path)
    if not source.is_file():
        raise FkError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise FkError(f"could not parse {source.name}: {exc}") from exc
    for column in ("scenario", "arm"):
        if column not in frame.columns:
            raise FkError(f"missing column {column!r} in {source.name}")
    q_cols = sorted((c for c in frame.columns if c.startswith("q")),
                    key=lambda c: int(c[1:]))
    if not q_cols:
        raise FkError(f"need at least one q column (q0, q1, ...) in "
                      f"{source.name}")
    if frame.empty:
        raise FkError(f"no rows in {source.name}")

    scenarios: list[Scenario] = []
    seen: set[str] = set()
    for _, row in frame.iterrows():
        name = str(row["scenario"]).strip()
        if not name or name == "nan":
            raise FkError("scenario names must be non-empty")
        if name in seen:
            raise FkError(f"duplicate scenario name {name!r}")
        seen.add(name)
        arm_name = str(row["arm"]).strip()
        if arm_name not in arms:
            available = ", ".join(arms)
            raise FkError(
                f"unknown arm {arm_name!r} in scenario {name!r}; "
                f"available: {available}")
        arm = arms[arm_name]
        values: list[float] = []
        for column in q_cols:
            value = row[column]
            if pd.isna(value):
                continue
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise FkError(
                    f"scenario {name!r} value {column!r} "
                    f"must be numeric") from exc
            if not np.isfinite(number):
                raise FkError(
                    f"scenario {name!r} value {column!r} must be finite")
            values.append(number)
        if len(values) != arm.n_joints:
            raise FkError(
                f"scenario {name!r}: expected {arm.n_joints} joint "
                f"value(s) for arm {arm_name!r}, got {len(values)}")
        scenarios.append(Scenario(name=name, arm=arm_name,
                                  q=tuple(values)))
    LOG.info("loaded %d scenarios from %s", len(scenarios), source.name)
    return scenarios


# --------------------------------------------------------------------------- #
# Kinematics maths
# --------------------------------------------------------------------------- #
def check_angles(arm: Arm, q) -> np.ndarray:
    """Validate joint values: count first, then finiteness."""
    values = np.asarray(q, dtype=float).ravel()
    if values.size != arm.n_joints:
        raise FkError(
            f"expected {arm.n_joints} joint value(s) for arm "
            f"{arm.name!r}, got {values.size}")
    if not np.isfinite(values).all():
        raise FkError("joint values must be finite")
    return values


def parse_angles(text: str) -> list[float]:
    """Parse '45,-90,...' into joint values (degrees / metres)."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        raise FkError("expected at least one joint value")
    values = []
    for i, part in enumerate(parts):
        try:
            number = float(part)
        except ValueError as exc:
            raise FkError(
                f"not a number for joint {i}: {part!r}") from exc
        if not np.isfinite(number):
            raise FkError(f"joint {i} must be finite")
        values.append(number)
    return values


def dh_transform(row: DHRow, joint: str, q: float) -> np.ndarray:
    """4x4 transform for one DH row (q in degrees for R, metres for P)."""
    if joint == "R":
        theta = np.deg2rad(row.theta_offset + q)
        d = row.d
    else:
        theta = np.deg2rad(row.theta_offset)
        d = row.d + q
    ct, st = np.cos(theta), np.sin(theta)
    ca, sa = np.cos(np.deg2rad(row.alpha)), np.sin(np.deg2rad(row.alpha))
    return np.array([
        [ct, -st * ca, st * sa, row.a * ct],
        [st, ct * ca, -ct * sa, row.a * st],
        [0.0, sa, ca, d],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=float)


def forward_kinematics(arm: Arm, q) -> np.ndarray:
    """Full chain transform: base frame -> end-effector (4x4)."""
    values = check_angles(arm, q)
    transform = np.eye(4)
    for row, joint, value in zip(arm.rows, arm.joints, values):
        transform = transform @ dh_transform(row, joint, float(value))
    return transform


def _euler_zyx(rotation: np.ndarray) -> tuple[float, float, float]:
    """Roll/pitch/yaw (degrees) from a rotation matrix (ZYX order)."""
    yaw = np.arctan2(rotation[1, 0], rotation[0, 0])
    pitch = np.arcsin(np.clip(-rotation[2, 0], -1.0, 1.0))
    roll = np.arctan2(rotation[2, 1], rotation[2, 2])
    return np.rad2deg(roll), np.rad2deg(pitch), np.rad2deg(yaw)


def end_effector(arm: Arm, q) -> Pose:
    """Joint angles -> end-effector pose (x, y, z + roll/pitch/yaw)."""
    transform = forward_kinematics(arm, q)
    x, y, z = (float(v) for v in transform[:3, 3])
    roll, pitch, yaw = _euler_zyx(transform[:3, :3])
    return Pose(x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw)


def limit_statuses(arm: Arm, q) -> list[tuple[float, str, float]]:
    """Per-joint (value, 'ok'/'OUT', limit-margin) for the report."""
    values = check_angles(arm, q)
    out: list[tuple[float, str, float]] = []
    for value, (low, high) in zip(values, arm.limits):
        if value < low - 1e-12 or value > high + 1e-12:
            status = "OUT"
        else:
            status = "ok"
        out.append((float(value), status, min(value - low, high - value)))
    return out


def reach_status(arm: Arm, pose: Pose) -> tuple[str, float, float, float]:
    """(status, distance, inner, outer) workspace annulus check."""
    inner, outer = arm.min_reach, arm.max_reach
    distance = pose.distance
    if distance <= outer + REACH_TOL and distance >= inner - REACH_TOL:
        status = "within reach"
    else:
        status = "beyond workspace"
    return status, distance, inner, outer


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def render_report(arm: Arm, q, pose: Pose) -> str:
    """Joint-space vs task-space report for one configuration."""
    values = check_angles(arm, q)
    statuses = limit_statuses(arm, values)
    status, distance, inner, outer = reach_status(arm, pose)
    unit = "deg"

    lines = [
        f"Detailed report - arm {arm.name!r}"
        + (f" ({arm.description})" if arm.description else ""),
        "-" * 68,
        "  Joint space (values vs limits):",
    ]
    for i, ((value, state, margin), joint) in enumerate(
            zip(statuses, arm.joints)):
        low, high = arm.limits[i]
        unit_i = "deg" if joint == "R" else "m"
        lines.append(
            f"    q{i} ({joint}) = {value:+9.3f} {unit_i:>3}   "
            f"[{low:+8.3f} .. {high:+8.3f}]  {state}"
            + ("" if state == "ok" else f"  (margin {margin:+.3f})"))
    revolute_total = sum(abs(v) for v, j in zip(values, arm.joints)
                         if j == "R")
    lines.append(f"    revolute |q| total = {revolute_total:.3f} {unit}")

    lines += [
        "  Task space (end-effector pose):",
        f"    x = {pose.x:+9.4f} m    y = {pose.y:+9.4f} m    "
        f"z = {pose.z:+9.4f} m",
        f"    roll = {pose.roll:+8.2f} deg  pitch = {pose.pitch:+8.2f} deg"
        f"  yaw = {pose.yaw:+8.2f} deg",
        f"    reach {distance:.4f} m  "
        f"(annulus {inner:.4f} .. {outer:.4f} m)  -> {status}",
    ]
    return "\n".join(lines)


def render_scenario_table(
        rows: list[tuple[Scenario, Arm, Pose]]) -> str:
    """ASCII table of every scenario's joint space and task space."""
    max_q = max(len(sc.q) for sc, _, _ in rows)
    header = (f"{'SCENARIO':<11}{'ARM':<10}"
              + "".join(f"{'q' + str(i):>9}" for i in range(max_q))
              + f"{'x':>10}{'y':>10}{'z':>10}{'yaw':>9}{'reach%':>9}")
    lines = [header, "-" * len(header)]
    for scenario, arm, pose in rows:
        cells = "".join(
            f"{scenario.q[i]:9.2f}" if i < len(scenario.q)
            else f"{'-':>9}"
            for i in range(max_q))
        reach_pct = 100.0 * pose.distance / arm.max_reach
        lines.append(
            f"{scenario.name:<11}{arm.name:<10}{cells}"
            f"{pose.x:10.4f}{pose.y:10.4f}{pose.z:10.4f}"
            f"{pose.yaw:9.2f}{reach_pct:9.1f}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_ARMS = Path(__file__).resolve().parent.parent / "data" / "arms.json"
DEMO_SCENARIOS = (Path(__file__).resolve().parent.parent / "data"
                  / "scenarios.csv")


def _analytic_planar2(arm: Arm, q) -> tuple[float, float]:
    """Closed-form 2R solution used as an independent cross-check."""
    a1, a2 = arm.rows[0].a, arm.rows[1].a
    q0, q1 = float(q[0]), float(q[1])
    x = a1 * np.cos(np.deg2rad(q0)) + a2 * np.cos(np.deg2rad(q0 + q1))
    y = a1 * np.sin(np.deg2rad(q0)) + a2 * np.sin(np.deg2rad(q0 + q1))
    return float(x), float(y)


def run_demo(arms_path: Path | None = None,
             scenarios_path: Path | None = None) -> int:
    """Run the bundled forward-kinematics demo - fully offline."""
    print("=" * 68)
    print(" FORWARD KINEMATICS - offline demo")
    print(" DH-parameter arms from bundled JSON + CSV; no network.")
    print("=" * 68)

    arms_file = arms_path or DEMO_ARMS
    scenarios_file = scenarios_path or DEMO_SCENARIOS
    if not arms_file.is_file():
        raise FkError(f"bundled arm file not found: {arms_file}")
    if not scenarios_file.is_file():
        raise FkError(f"bundled scenarios not found: {scenarios_file}")

    arms = load_arms(arms_file)
    scenarios = load_scenarios(scenarios_file, arms)
    print(f"\nLoaded {len(arms)} arms ({', '.join(arms)}) and "
          f"{len(scenarios)} scenarios from bundled data.")

    computed = [(scenario, arms[scenario.arm],
                 end_effector(arms[scenario.arm], scenario.q))
                for scenario in scenarios]
    print()
    print(render_scenario_table(computed))

    planar = [row for row in computed if row[1].is_planar]
    spatial = [row for row in computed if not row[1].is_planar]
    featured = ([planar[0], spatial[0]]
                if planar and spatial else computed[:2])
    for scenario, arm, pose in featured:
        print()
        print(render_report(arm, scenario.q, pose))

    # --- cross-checks the demo asserts ------------------------------------ #
    # 1. analytic 2R formula matches the DH matrix chain
    for scenario, arm, pose in computed:
        if arm.name == "planar2":
            expected_x, expected_y = _analytic_planar2(arm, scenario.q)
            assert np.isclose(pose.x, expected_x, atol=1e-9), \
                f"analytic x mismatch for {scenario.name}"
            assert np.isclose(pose.y, expected_y, atol=1e-9), \
                f"analytic y mismatch for {scenario.name}"

    # 2. every rotation matrix is orthonormal with det +1
    for scenario, arm, _ in computed:
        rotation = forward_kinematics(arm, scenario.q)[:3, :3]
        assert np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-9), \
            f"rotation not orthonormal for {scenario.name}"
        assert np.isclose(np.linalg.det(rotation), 1.0, atol=1e-9), \
            f"det(R) != 1 for {scenario.name}"

    # 3. planar arms stay in z = 0 and yaw equals the joint sum
    for scenario, arm, pose in computed:
        if not arm.is_planar:
            continue
        assert abs(pose.z) < 1e-9, f"planar z != 0 for {scenario.name}"
        total = float(np.sum(scenario.q))
        wrapped = abs((pose.yaw - total + 180.0) % 360.0 - 180.0)
        assert wrapped < 1e-9, f"yaw != sum(q) for {scenario.name}"

    # 4. the prismatic scenario lifts along z exactly
    lift = next(r for r in computed if r[0].name == "lift")
    expected_z = lift[1].rows[0].d + lift[0].q[1]
    assert np.isclose(lift[2].z, expected_z, atol=1e-9), \
        "prismatic joint did not lift along z"

    # 5. joint limits and workspace annulus hold for every scenario
    for scenario, arm, pose in computed:
        states = [state for _, state, _ in limit_statuses(arm, scenario.q)]
        assert states == ["ok"] * arm.n_joints, \
            f"limit violated in scenario {scenario.name}"
        status, distance, inner, outer = reach_status(arm, pose)
        assert status == "within reach", \
            f"scenario {scenario.name} outside workspace"
        assert inner - 1e-9 <= distance <= outer + 1e-9

    # 6. deterministic re-run: identical poses
    first = computed[0]
    again = end_effector(first[1], first[0].q)
    assert np.allclose([again.x, again.y, again.z],
                       [first[2].x, first[2].y, first[2].z],
                       atol=1e-12), "not deterministic"

    print(f"\nCross-checks OK: {len(computed)} scenarios, analytic 2R "
          "match, orthonormal rotations, planar yaw/zero-z, prismatic "
          "lift, limit + reach checks, deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
