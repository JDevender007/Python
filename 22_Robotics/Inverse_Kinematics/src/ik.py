"""Inverse kinematics for planar serial arms - fully offline.

Two solvers:

* **analytic** - the 2-link closed form with both elbow branches
  (elbow-up / elbow-down), exact reachability annulus check;
* **dls** - damped least squares (Levenberg-Marquardt style) on the
  analytic Jacobian for 3-link arms, optional end-effector yaw target.

Every solution reports its residual (task-space error after a forward-
kinematics round-trip), iteration count, and convergence flag.  Arm
definitions ship as bundled JSON, target tables as bundled CSV.  No
network, no API keys, no ROS, no hardware.

Internal maths runs in radians; joint values are reported in degrees.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

LOG = logging.getLogger("ik")

DEG = np.pi / 180.0
REACH_TOL = 1e-9
METHODS = ("auto", "analytic", "dls")
ELBOWS = ("up", "down")


class IkError(RuntimeError):
    """Raised for missing files, bad schemas, and failed solves."""


# --------------------------------------------------------------------------- #
# Arm and target models
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ArmIk:
    """A planar chain: link lengths (m) and per-joint limits (deg)."""

    name: str
    links: tuple[float, ...]
    limits: tuple[tuple[float, float], ...]

    @property
    def n_joints(self) -> int:
        return len(self.links)

    @property
    def inner_reach(self) -> float:
        return max(0.0, 2.0 * max(self.links) - sum(self.links))

    @property
    def outer_reach(self) -> float:
        return float(sum(self.links))


@dataclass(frozen=True)
class Target:
    """One task-space target: metres, optional yaw in degrees."""

    name: str
    arm: str
    x: float
    y: float
    yaw: float | None = None

    @property
    def values(self) -> tuple[float, ...]:
        return (self.x, self.y) if self.yaw is None else (
            self.x, self.y, self.yaw)


@dataclass(frozen=True)
class IkSolution:
    """Solved joint values plus residual reporting."""

    method: str
    arm: str
    target: tuple[float, ...]
    q: tuple[float, ...]          # degrees
    residual: float               # task-space error norm (m / rad)
    position_error: float         # metres
    yaw_error: float              # degrees (0.0 without a yaw target)
    iterations: int
    converged: bool
    extra: str = ""               # e.g. "elbow up"

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "arm": self.arm,
            "target": [round(v, 6) for v in self.target],
            "q_deg": [round(v, 6) for v in self.q],
            "residual": float(f"{self.residual:.3e}"),
            "position_error": float(f"{self.position_error:.3e}"),
            "yaw_error_deg": round(self.yaw_error, 9),
            "iterations": self.iterations,
            "converged": self.converged,
            "extra": self.extra,
        }


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def arm_from_dict(name: str, payload: object) -> ArmIk:
    """Build and validate one ArmIk from its JSON payload."""
    if not isinstance(payload, dict):
        raise IkError(f"arm {name!r} must be a JSON object")
    missing = [k for k in ("links", "limits") if k not in payload]
    if missing:
        raise IkError(f"arm {name!r} missing key(s): {', '.join(missing)}")

    links_raw = payload["links"]
    if not isinstance(links_raw, list) or not links_raw:
        raise IkError(f"arm {name!r} links must be a non-empty list")
    links: list[float] = []
    for i, value in enumerate(links_raw):
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise IkError(
                f"arm {name!r} link {i} must be numeric") from exc
        if not np.isfinite(number):
            raise IkError(f"arm {name!r} link {i} must be finite")
        if number <= 0.0:
            raise IkError(f"arm {name!r} link {i} must be > 0")
        links.append(number)

    limits_raw = payload["limits"]
    if not isinstance(limits_raw, list) or len(limits_raw) != len(links):
        raise IkError(
            f"arm {name!r} limits must have exactly {len(links)} "
            f"entr(ies)")
    limits: list[tuple[float, float]] = []
    for i, entry in enumerate(limits_raw):
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            raise IkError(f"arm {name!r} limit {i} must be [min, max]")
        try:
            low, high = float(entry[0]), float(entry[1])
        except (TypeError, ValueError) as exc:
            raise IkError(
                f"arm {name!r} limit {i} must be numeric") from exc
        if not np.isfinite(low) or not np.isfinite(high):
            raise IkError(f"arm {name!r} limit {i} must be finite")
        if low > high:
            raise IkError(f"arm {name!r} limit {i} min must be <= max")
        limits.append((low, high))

    return ArmIk(name=name, links=tuple(links), limits=tuple(limits))


def load_arms(path: str | Path) -> dict[str, ArmIk]:
    """Load and validate an arms JSON file -> {name: ArmIk}."""
    source = Path(path)
    if not source.is_file():
        raise IkError(f"file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise IkError(f"could not parse {source.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise IkError(
            f"expected a JSON object of arm definitions in {source.name}")
    if not payload:
        raise IkError(f"no arm definitions in {source.name}")
    arms = {name: arm_from_dict(name, entry)
            for name, entry in payload.items()}
    LOG.info("loaded %d arm(s) from %s", len(arms), source.name)
    return arms


def select_arm(arms: dict[str, ArmIk],
               name: str | None = None) -> ArmIk:
    """Pick an arm by name (default: first definition, JSON order)."""
    if not arms:
        raise IkError("no arms loaded")
    if name is None:
        return next(iter(arms.values()))
    if name not in arms:
        raise IkError(f"unknown arm {name!r}; available: {', '.join(arms)}")
    return arms[name]


def load_targets(path: str | Path,
                 arms: dict[str, ArmIk]) -> list[Target]:
    """Load and validate the bundled target CSV against the arms."""
    source = Path(path)
    if not source.is_file():
        raise IkError(f"file not found: {source}")
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        raise IkError(f"could not parse {source.name}: {exc}") from exc
    for column in ("target", "arm", "x", "y"):
        if column not in frame.columns:
            raise IkError(f"missing column {column!r} in {source.name}")
    if frame.empty:
        raise IkError(f"no rows in {source.name}")

    targets: list[Target] = []
    seen: set[str] = set()
    for _, row in frame.iterrows():
        name = str(row["target"]).strip()
        if not name or name == "nan":
            raise IkError("target names must be non-empty")
        if name in seen:
            raise IkError(f"duplicate target name {name!r}")
        seen.add(name)
        arm_name = str(row["arm"]).strip()
        if arm_name not in arms:
            raise IkError(
                f"unknown arm {arm_name!r} in target {name!r}; "
                f"available: {', '.join(arms)}")
        values: dict[str, float] = {}
        for column in ("x", "y"):
            values[column] = _finite(row[column], name, column)
        yaw: float | None = None
        if "yaw" in frame.columns and not pd.isna(row["yaw"]):
            yaw = _finite(row["yaw"], name, "yaw")
        targets.append(Target(name=name, arm=arm_name,
                              x=values["x"], y=values["y"], yaw=yaw))
    LOG.info("loaded %d targets from %s", len(targets), source.name)
    return targets


def _finite(value, target: str, column: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise IkError(
            f"target {target!r} column {column!r} must be numeric"
        ) from exc
    if not np.isfinite(number):
        raise IkError(f"target {target!r} column {column!r} must be finite")
    return number


def parse_values(text: str) -> tuple[float, ...]:
    """Parse a comma-separated list of finite numbers."""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        raise IkError("expected at least one numeric value")
    values: list[float] = []
    for index, part in enumerate(parts):
        try:
            number = float(part)
        except ValueError as exc:
            raise IkError(f"not a number at position {index}: {part!r}"
                          ) from exc
        if not np.isfinite(number):
            raise IkError(f"value {index} must be finite")
        values.append(number)
    return tuple(values)


def parse_target(text: str) -> tuple[float, ...]:
    """Parse 'x,y' or 'x,y,yaw' into a target tuple."""
    values = parse_values(text)
    if len(values) not in (2, 3):
        raise IkError(
            f"target must be 'x,y' or 'x,y,yaw', got {len(values)} "
            f"value(s)")
    return values


# --------------------------------------------------------------------------- #
# Planar forward kinematics and Jacobian (radians)
# --------------------------------------------------------------------------- #
def planar_fk(links, q_rad, with_yaw: bool = False) -> np.ndarray:
    """End-effector (x, y[, yaw]) of a planar chain; q in radians."""
    theta = np.cumsum(np.asarray(q_rad, dtype=float))
    x = float(np.sum(np.asarray(links) * np.cos(theta)))
    y = float(np.sum(np.asarray(links) * np.sin(theta)))
    if with_yaw:
        return np.array([x, y, float(theta[-1])])
    return np.array([x, y])


def planar_jacobian(links, q_rad, with_yaw: bool = False) -> np.ndarray:
    """Analytic Jacobian d(x, y[, yaw]) / d(q); q in radians."""
    q = np.asarray(q_rad, dtype=float)
    links = np.asarray(links, dtype=float)
    theta = np.cumsum(q)
    rows = 3 if with_yaw else 2
    jacobian = np.zeros((rows, q.size))
    for k in range(q.size):
        jacobian[0, k] = float(-np.sum(links[k:] * np.sin(theta[k:])))
        jacobian[1, k] = float(np.sum(links[k:] * np.cos(theta[k:])))
        if with_yaw:
            jacobian[2, k] = 1.0
    return jacobian


def workspace_annulus(links) -> tuple[float, float]:
    """Exact reachable annulus [inner, outer] of a planar chain."""
    inner = max(0.0, 2.0 * max(links) - sum(links))
    return inner, float(sum(links))


def check_reachable(arm: ArmIk, target) -> tuple[float, ...]:
    """Validate target shape/finiteness, then annulus + yaw reach."""
    values = np.asarray(target, dtype=float).ravel()
    if values.size not in (2, 3):
        raise IkError(
            f"target must be x,y or x,y,yaw, got {values.size} value(s)")
    if not np.isfinite(values).all():
        raise IkError("target must be finite")
    inner, outer = workspace_annulus(arm.links)
    radius = float(np.hypot(values[0], values[1]))
    if radius > outer + REACH_TOL or radius < inner - REACH_TOL:
        raise IkError(
            f"target unreachable: distance {radius:.4f} m outside "
            f"reachable annulus [{inner:.4f}, {outer:.4f}] m")
    if values.size == 3:
        yaw_rad = float(np.deg2rad(values[2]))
        low = float(np.deg2rad(sum(lo for lo, _ in arm.limits)))
        high = float(np.deg2rad(sum(hi for _, hi in arm.limits)))
        if yaw_rad < low - 1e-12 or yaw_rad > high + 1e-12:
            raise IkError(
                f"target unreachable: yaw {values[2]:.3f} deg outside "
                f"[{np.rad2deg(low):.1f}, {np.rad2deg(high):.1f}] deg")
        # with the last link's orientation pinned, the wrist point must
        # still fall inside the remaining chain's annulus
        wrist_x = values[0] - arm.links[-1] * np.cos(yaw_rad)
        wrist_y = values[1] - arm.links[-1] * np.sin(yaw_rad)
        w_inner, w_outer = workspace_annulus(arm.links[:-1])
        wrist_radius = float(np.hypot(wrist_x, wrist_y))
        if (wrist_radius > w_outer + REACH_TOL
                or wrist_radius < w_inner - REACH_TOL):
            raise IkError(
                f"target unreachable: with yaw {values[2]:.3f} deg the "
                f"wrist point sits at radius {wrist_radius:.4f} m, outside "
                f"the remaining chain's annulus "
                f"[{w_inner:.4f}, {w_outer:.4f}] m")
    return tuple(float(v) for v in values)


def within_limits(arm: ArmIk, q) -> bool:
    """True when every joint value lies inside the arm's limits."""
    values = np.asarray(q, dtype=float).ravel()
    if values.size != arm.n_joints:
        return False
    return all(float(low) - 1e-9 <= float(value) <= float(high) + 1e-9
               for value, (low, high) in zip(values, arm.limits))


# --------------------------------------------------------------------------- #
# Solvers
# --------------------------------------------------------------------------- #
def solve_2link(arm: ArmIk, target, elbow: str = "up") -> IkSolution:
    """Closed-form 2-link IK; elbow 'up' = positive q2, 'down' = negative."""
    if arm.n_joints != 2:
        raise IkError(
            f"analytic solver needs exactly 2 links, arm {arm.name!r} "
            f"has {arm.n_joints}")
    if elbow not in ELBOWS:
        raise IkError(f"elbow must be 'up' or 'down' (got {elbow!r})")
    values = np.asarray(target, dtype=float).ravel()
    if values.size not in (2, 3):
        raise IkError(
            f"target must be x,y or x,y,yaw, got {values.size} value(s)")
    if not np.isfinite(values).all():
        raise IkError("target must be finite")
    if values.size == 3:
        raise IkError(
            "analytic solver accepts x,y only; use method 'dls' for "
            "yaw targets")
    x, y = float(values[0]), float(values[1])
    inner, outer = workspace_annulus(arm.links)
    radius = float(np.hypot(x, y))
    if radius > outer + REACH_TOL or radius < inner - REACH_TOL:
        raise IkError(
            f"target unreachable: distance {radius:.4f} m outside "
            f"reachable annulus [{inner:.4f}, {outer:.4f}] m")

    a1, a2 = arm.links
    cos_q2 = (radius ** 2 - a1 ** 2 - a2 ** 2) / (2.0 * a1 * a2)
    cos_q2 = float(np.clip(cos_q2, -1.0, 1.0))
    q2_mag = float(np.arccos(cos_q2))
    q2 = q2_mag if elbow == "up" else -q2_mag
    q1 = float(np.arctan2(y, x) - np.arctan2(a2 * np.sin(q2),
                                            a1 + a2 * np.cos(q2)))
    q_rad = np.array([q1, q2])
    q_deg = tuple(float(v) for v in np.rad2deg(q_rad))

    achieved = planar_fk(arm.links, q_rad)
    residual = float(np.linalg.norm(achieved - np.array([x, y])))
    return IkSolution(
        method="analytic", arm=arm.name, target=(x, y), q=q_deg,
        residual=residual, position_error=residual, yaw_error=0.0,
        iterations=0, converged=residual < 1e-9, extra=f"elbow {elbow}")


def _dls_run(links, goal, q, with_yaw: bool, damping: float, tol: float,
             max_iters: int) -> tuple[np.ndarray, float, int]:
    """Run one damped-least-squares descent from a start configuration."""
    identity = np.eye(goal.size)
    residual = float(np.inf)
    iterations = 0
    for iterations in range(1, max_iters + 1):
        error = goal - planar_fk(links, q, with_yaw)
        residual = float(np.linalg.norm(error))
        if residual < tol:
            break
        jacobian = planar_jacobian(links, q, with_yaw)
        system = jacobian @ jacobian.T + (damping ** 2) * identity
        step = jacobian.T @ np.linalg.solve(system, error)
        q = q + step
    return q, float(residual), iterations


def _seed_patterns(n_joints: int) -> list[tuple[float, ...]]:
    """Deterministic restart seeds used when a single start stalls."""
    patterns = [
        (60.0, -60.0, -60.0, 0.0),
        (-60.0, 60.0, 60.0, 0.0),
        (120.0, -90.0, 45.0, -45.0),
        (-120.0, 90.0, -45.0, 45.0),
        (30.0, 30.0, -30.0, -30.0),
    ]
    seeds: list[tuple[float, ...]] = []
    for pattern in patterns:
        values = list(pattern[:n_joints])
        values += [0.0] * (n_joints - len(values))
        seeds.append(tuple(values))
    return seeds


def solve_dls(arm: ArmIk, target, q0=None, damping: float = 0.05,
              tol: float = 1e-9, max_iters: int = 500,
              restarts: bool = True) -> IkSolution:
    """Damped least squares IK with deterministic restarts on stalls."""
    if arm.n_joints < 2:
        raise IkError(
            f"damped least squares needs at least 2 links, arm "
            f"{arm.name!r} has {arm.n_joints}")
    if any(not np.isfinite(l) or l <= 0 for l in arm.links):
        raise IkError(f"arm {arm.name!r} link lengths must be > 0")
    values = np.asarray(check_reachable(arm, target), dtype=float)
    if not np.isfinite(damping) or damping <= 0:
        raise IkError(f"damping must be > 0, got {damping}")
    if not np.isfinite(tol) or tol <= 0:
        raise IkError(f"tol must be > 0, got {tol}")
    if max_iters < 1:
        raise IkError(f"max_iters must be >= 1, got {max_iters}")

    with_yaw = values.size == 3
    goal = np.array(values[:2], dtype=float)
    if with_yaw:
        goal = np.append(goal, np.deg2rad(values[2]))
    if q0 is None:
        start = np.zeros(arm.n_joints)
    else:
        start = np.asarray(q0, dtype=float).ravel()
        if start.size != arm.n_joints:
            raise IkError(
                f"q0 must have {arm.n_joints} values, got {start.size}")
        if not np.isfinite(start).all():
            raise IkError("q0 must be finite")
        start = np.deg2rad(start)

    starts = [start]
    if restarts:
        starts += [np.deg2rad(seed) for seed in _seed_patterns(arm.n_joints)
                   if not np.allclose(np.deg2rad(seed), start)]

    best_q, best_residual, best_iters, best_seed = start, float(np.inf), 0, 0
    for index, candidate in enumerate(starts):
        q, residual, iterations = _dls_run(
            arm.links, goal, candidate.copy(), with_yaw, damping, tol,
            max_iters)
        if residual < best_residual:
            best_q, best_residual = q, residual
            best_iters, best_seed = iterations, index
        if residual < tol:
            break

    q_deg = tuple(float(v) for v in np.rad2deg(best_q))
    achieved = planar_fk(arm.links, best_q, with_yaw)
    position_error = float(np.linalg.norm(achieved[:2] - goal[:2]))
    yaw_error = 0.0
    if with_yaw:
        yaw_error = float(np.rad2deg(
            np.arctan2(np.sin(achieved[2] - goal[2]),
                       np.cos(achieved[2] - goal[2]))))
    converged = best_residual < tol
    extra = f"damping {damping:g}"
    if best_seed:
        extra += f", restart {best_seed}"
    return IkSolution(
        method="dls", arm=arm.name, target=values, q=q_deg,
        residual=best_residual, position_error=position_error,
        yaw_error=yaw_error, iterations=best_iters,
        converged=converged, extra=extra)


def solve(arm: ArmIk, target, method: str = "auto",
          elbow: str = "up", **kwargs) -> IkSolution:
    """Dispatch: 'auto' picks analytic for 2-link arms, dls otherwise."""
    if method not in METHODS:
        raise IkError(f"method must be one of {METHODS} (got {method!r})")
    chosen = method
    if chosen == "auto":
        chosen = "analytic" if arm.n_joints == 2 else "dls"
    if chosen == "analytic":
        return solve_2link(arm, target, elbow=elbow)
    return solve_dls(arm, target, **kwargs)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def render_solution(solution: IkSolution, arm: ArmIk | None = None) -> str:
    """Human-readable report for one IK solution."""
    target_text = "  ".join(
        f"{name} = {value:+.4f} m"
        for name, value in zip(("x", "y"), solution.target[:2]))
    if len(solution.target) == 3:
        target_text += f"  yaw = {solution.target[2]:+.2f} deg"

    joint_text = "   ".join(
        f"q{i} = {value:+9.3f} deg"
        for i, value in enumerate(solution.q))

    lines = [
        f"IK SOLUTION - arm {solution.arm!r} ({solution.method}"
        + (f", {solution.extra}" if solution.extra else "") + ")",
        "-" * 68,
        f"  target   : {target_text}",
        f"  solution : {joint_text}",
    ]
    if arm is not None:
        achieved = planar_fk(
            arm.links, np.deg2rad(solution.q),
            with_yaw=len(solution.target) == 3)
        lines.append(
            f"  FK check : x = {achieved[0]:+.4f} m  "
            f"y = {achieved[1]:+.4f} m"
            + (f"  yaw = {np.rad2deg(achieved[2]):+.2f} deg"
               if len(solution.target) == 3 else ""))
    lines.append(
        f"  residual : {solution.residual:.3e} (position error "
        f"{solution.position_error:.3e} m, yaw error "
        f"{solution.yaw_error:.3e} deg)")
    lines.append(
        f"  iterations: {solution.iterations}   "
        f"converged: {'yes' if solution.converged else 'NO'}")
    return "\n".join(lines)


def render_table(rows: list[tuple[str, IkSolution]]) -> str:
    """ASCII table over labelled IK solutions."""
    max_q = max(len(solution.q) for _, solution in rows)
    header = (f"{'TARGET':<12}{'ARM':<10}{'METHOD':<10}"
              + "".join(f"{'q' + str(i):>10}" for i in range(max_q))
              + f"{'residual':>12}{'iter':>7}  status")
    lines = [header, "-" * len(header)]
    for label, solution in rows:
        cells = "".join(
            f"{solution.q[i]:10.3f}" if i < len(solution.q)
            else f"{'-':>10}"
            for i in range(max_q))
        status = ("converged" if solution.converged else "FAILED")
        lines.append(
            f"{label:<12}{solution.arm:<10}{solution.method:<10}{cells}"
            f"{solution.residual:12.3e}{solution.iterations:>7}  {status}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_ARMS = Path(__file__).resolve().parent.parent / "data" / "arms.json"
DEMO_TARGETS = (Path(__file__).resolve().parent.parent / "data"
                / "targets.csv")
UNREACHABLE_OUTER = (2.5, 0.0)
UNREACHABLE_INNER = (0.1, 0.0)


def run_demo(arms_path: Path | None = None,
             targets_path: Path | None = None) -> int:
    """Run the bundled inverse-kinematics demo - fully offline."""
    print("=" * 68)
    print(" INVERSE KINEMATICS - offline demo")
    print(" 2-link analytic + 3-link damped least squares; no network.")
    print("=" * 68)

    arms_file = arms_path or DEMO_ARMS
    targets_file = targets_path or DEMO_TARGETS
    if not arms_file.is_file():
        raise IkError(f"bundled arm file not found: {arms_file}")
    if not targets_file.is_file():
        raise IkError(f"bundled targets not found: {targets_file}")

    arms = load_arms(arms_file)
    targets = load_targets(targets_file, arms)
    print(f"\nLoaded {len(arms)} arms ({', '.join(arms)}) and "
          f"{len(targets)} targets from bundled data.")

    solutions: list[tuple[Target, IkSolution]] = []
    for target in targets:
        arm = arms[target.arm]
        solution = solve(arm, target.values, method="auto")
        solutions.append((target, solution))

    print()
    print(render_table([(target.name, solution)
                        for target, solution in solutions]))

    featured = [solutions[0], next(s for s in solutions
                                   if s[1].method == "dls")]
    for target, solution in featured:
        print()
        print(render_solution(solution, arms[target.arm]))

    # --- cross-checks the demo asserts ------------------------------------- #
    # 1. analytic solutions round-trip through FK to their targets
    for target, solution in solutions:
        if solution.method != "analytic":
            continue
        arm = arms[target.arm]
        achieved = planar_fk(arm.links, np.deg2rad(solution.q))
        assert np.allclose(achieved, [target.x, target.y], atol=1e-9), \
            f"analytic round-trip failed for {target.name}"
        assert solution.residual < 1e-9, \
            f"analytic residual too large for {target.name}"

    # 2. dls solutions converge with tiny residuals
    for target, solution in solutions:
        if solution.method != "dls":
            continue
        assert solution.converged, f"dls did not converge for {target.name}"
        assert solution.residual < 1e-9, \
            f"dls residual too large for {target.name}"
        arm = arms[target.arm]
        achieved = planar_fk(arm.links, np.deg2rad(solution.q),
                             with_yaw=target.yaw is not None)
        assert np.allclose(achieved[:2], [target.x, target.y],
                           atol=1e-8), f"FK round-trip failed for {target.name}"

    # 3. both elbow branches reach the same target with different joints
    probe = next(t for t in targets if t.name == "up_left")
    arm = arms[probe.arm]
    up = solve_2link(arm, probe.values, elbow="up")
    down = solve_2link(arm, probe.values, elbow="down")
    assert not np.allclose(up.q, down.q, atol=1e-6), "branches identical"
    for branch in (up, down):
        achieved = planar_fk(arm.links, np.deg2rad(branch.q))
        assert np.allclose(achieved, [probe.x, probe.y], atol=1e-9)

    # 4. dls on the 2-link arm agrees with an analytic branch
    dls2 = solve_dls(arm, probe.values, q0=[10.0, 10.0])
    assert dls2.converged and dls2.residual < 1e-9
    matches = (np.allclose(dls2.q, up.q, atol=1e-6)
               or np.allclose(dls2.q, down.q, atol=1e-6))
    assert matches, "dls solution matches no analytic branch"

    # 5. analytic Jacobian matches central finite differences (seeded)
    rng = np.random.default_rng(11)
    links = arms["planar3"].links
    for _ in range(10):
        q = rng.uniform(-np.pi, np.pi, size=3)
        analytic = planar_jacobian(links, q, with_yaw=True)
        numeric = np.zeros_like(analytic)
        h = 1e-6
        for k in range(3):
            plus, minus = q.copy(), q.copy()
            plus[k] += h
            minus[k] -= h
            numeric[:, k] = (planar_fk(links, plus, with_yaw=True)
                             - planar_fk(links, minus, with_yaw=True)) / (2 * h)
        assert np.allclose(analytic, numeric, atol=1e-6), \
            "Jacobian mismatch vs finite differences"

    # 6. yaw target is honoured by the 3-link solver
    yaw_target = next(t for t in targets if t.yaw is not None)
    yaw_solution = next(s for t, s in solutions if t.yaw is not None)
    assert abs(yaw_solution.yaw_error) < 1e-6, "yaw target missed"
    assert yaw_target.yaw is not None

    # 7. unreachable targets are rejected with a clear error
    for label, bad in (("outer", UNREACHABLE_OUTER),
                       ("inner", UNREACHABLE_INNER)):
        try:
            solve_2link(arms["planar2"], bad)
        except IkError as exc:
            assert "target unreachable" in str(exc)
        else:
            raise AssertionError(f"{label} hole target was not rejected")

    # 8. every bundled solution respects the joint limits
    for target, solution in solutions:
        assert within_limits(arms[target.arm], solution.q), \
            f"joint limit violated for {target.name}"

    # 9. deterministic re-run: identical joint values
    repeat = solve(arms[featured[0][0].arm], featured[0][0].values)
    assert np.allclose(repeat.q, featured[0][1].q, atol=1e-12), \
        "not deterministic"

    print(f"\nCross-checks OK: {len(solutions)} targets solved, analytic "
          "round-trips, elbow branches, dls-vs-analytic agreement, "
          "Jacobian vs finite differences, yaw honoured, unreachable "
          "rejected, joint limits held, deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
