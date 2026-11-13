"""A 2R-plus-wrist robot arm simulator: IK, trajectories and missions.

The arm has two position links plus an optional wrist joint that only
changes the tool orientation.  That decoupling keeps the inverse
kinematics exact: solve the position with the closed-form 2R formula,
then set the wrist so the tool yaw is what the mission asked for.

Motion is generated in two layers:

* a **joint path** (a list of configurations) - either two endpoints for
  a joint move, or the IK solutions along a straight Cartesian line;
* **time parameterisation** - a minimum-jerk profile ``s(u)`` with zero
  velocity at both ends, scaled so no joint ever exceeds its speed limit.

Every trajectory ships its samples: time, joint values, tool pose and
joint speeds.  Missions chain Cartesian moves, add dwells, and are
checked for joint limits, speed limits and collisions between the links
and circular obstacles.

Fully offline: the arm and mission live in ``data/``.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger("arm")

DEG = math.pi / 180.0
EPS = 1e-9
PEAK_FACTOR = 1.875
JOINT_NAMES = ("q0", "q1", "q2")
ARM_FILE = Path(__file__).resolve().parent.parent / "data" / "arm.json"
MISSION_FILE = Path(__file__).resolve().parent.parent / "data" / "mission.json"


class ArmError(RuntimeError):
    """Raised for invalid models, unreachable poses and bad missions."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def wrap_deg(angle: float) -> float:
    """Wrap an angle in degrees into [-180, 180]."""
    return (float(angle) + 180.0) % 360.0 - 180.0


def _finite(value, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ArmError(f"{label} must be numeric, got {value!r}") from exc
    if not math.isfinite(number):
        raise ArmError(f"{label} must be finite, got {value!r}")
    return number


def minjerk(u: float) -> float:
    """Minimum-jerk position profile on [0, 1]: zero velocity at both ends."""
    return 10.0 * u ** 3 - 15.0 * u ** 4 + 6.0 * u ** 5


def minjerk_derivative(u: float) -> float:
    """d/du of the minimum-jerk profile; peak 1.875 at u = 0.5."""
    return 30.0 * u ** 2 - 60.0 * u ** 3 + 30.0 * u ** 4


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class JointSpec:
    """One joint: name, limits in degrees, top speed in degrees/second."""

    name: str
    low: float
    high: float
    max_speed: float


@dataclass(frozen=True)
class ArmSpec:
    """Serial arm: link lengths (m) and one JointSpec per joint."""

    name: str
    links: tuple[float, ...]
    joints: tuple[JointSpec, ...]
    description: str = ""

    @property
    def n_joints(self) -> int:
        return len(self.joints)

    @property
    def inner_reach(self) -> float:
        return max(0.0, 2.0 * max(self.links[:2]) - sum(self.links[:2]))

    @property
    def outer_reach(self) -> float:
        return float(sum(self.links))

    def limit_pairs(self) -> tuple[tuple[float, float], ...]:
        return tuple((joint.low, joint.high) for joint in self.joints)


@dataclass(frozen=True)
class Pose:
    """Tool pose in the plane."""

    x: float
    y: float
    yaw: float

    @property
    def distance(self) -> float:
        return math.hypot(self.x, self.y)

    def to_dict(self) -> dict:
        return {"x": round(self.x, 6), "y": round(self.y, 6),
                "yaw": round(self.yaw, 4)}


@dataclass(frozen=True)
class Obstacle:
    """A circular keep-out zone the links must not enter."""

    name: str
    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class Sample:
    """One trajectory sample."""

    t: float
    q: tuple[float, ...]
    x: float
    y: float
    yaw: float
    speeds: tuple[float, ...]

    @property
    def pose(self) -> Pose:
        return Pose(self.x, self.y, self.yaw)


@dataclass(frozen=True)
class Trajectory:
    """A sampled joint path with timing."""

    samples: tuple[Sample, ...]
    duration: float
    dt: float

    @property
    def q_start(self) -> tuple[float, ...]:
        return self.samples[0].q

    @property
    def q_end(self) -> tuple[float, ...]:
        return self.samples[-1].q

    @property
    def max_speeds(self) -> tuple[float, ...]:
        n = len(self.samples[0].q)
        return tuple(max(abs(sample.speeds[i]) for sample in self.samples)
                     for i in range(n))

    @property
    def cartesian_length(self) -> float:
        return sum(math.hypot(b.x - a.x, b.y - a.y)
                   for a, b in zip(self.samples, self.samples[1:]))

    def to_dict(self) -> dict:
        return {"duration": round(self.duration, 6),
                "dt": round(self.dt, 6),
                "samples": [
                    {"t": round(sample.t, 6),
                     "q": [round(v, 6) for v in sample.q],
                     "x": round(sample.x, 6),
                     "y": round(sample.y, 6),
                     "yaw": round(sample.yaw, 4)}
                    for sample in self.samples]}


@dataclass(frozen=True)
class Waypoint:
    """One mission target."""

    name: str
    x: float
    y: float
    yaw: float | None = None


@dataclass(frozen=True)
class Mission:
    """Home pose, ordered waypoints, dwell time and obstacles."""

    name: str
    home: tuple[float, float, float | None]
    waypoints: tuple[Waypoint, ...]
    obstacles: tuple[Obstacle, ...] = ()
    dwell: float = 0.0
    steps: int = 40


@dataclass(frozen=True)
class Segment:
    """One planned move plus its dwell."""

    name: str
    trajectory: Trajectory
    dwell: float

    @property
    def duration(self) -> float:
        return self.trajectory.duration + self.dwell


@dataclass(frozen=True)
class Collision:
    """A link that entered an obstacle's keep-out zone."""

    t: float
    link: int
    obstacle: str
    clearance: float

    def to_dict(self) -> dict:
        return {"t": round(self.t, 4), "link": self.link,
                "obstacle": self.obstacle,
                "clearance": round(self.clearance, 6)}


@dataclass(frozen=True)
class MissionResult:
    """A planned mission with its bookkeeping."""

    mission: str
    segments: tuple[Segment, ...]
    collisions: tuple[Collision, ...] = ()
    waypoint_errors: tuple[tuple[str, float], ...] = ()

    @property
    def total_time(self) -> float:
        return sum(segment.duration for segment in self.segments)

    @property
    def move_time(self) -> float:
        return sum(segment.trajectory.duration for segment in self.segments)

    @property
    def sample_count(self) -> int:
        return sum(len(segment.trajectory.samples)
                   for segment in self.segments)

    @property
    def max_speeds(self) -> tuple[float, ...]:
        n = len(self.segments[0].trajectory.samples[0].q)
        return tuple(
            max(segment.trajectory.max_speeds[i]
                for segment in self.segments if segment.trajectory.samples)
            for i in range(n))


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def joint_from_dict(index: int, payload: object) -> JointSpec:
    """Validate one joint definition."""
    if not isinstance(payload, dict):
        raise ArmError(f"joint {index} must be an object")
    name = payload.get("name", JOINT_NAMES[index])
    if not isinstance(name, str) or not name.strip():
        raise ArmError(f"joint {index} name must be a non-empty string")
    low = _finite(payload.get("low"), f"joint {index} low")
    high = _finite(payload.get("high"), f"joint {index} high")
    speed = _finite(payload.get("max_speed"), f"joint {index} max_speed")
    if low > high:
        raise ArmError(f"joint {index} low must be <= high")
    if speed <= 0:
        raise ArmError(f"joint {index} max_speed must be > 0")
    return JointSpec(name=name.strip(), low=low, high=high, max_speed=speed)


def arm_from_dict(name: str, payload: object) -> ArmSpec:
    """Validate one arm definition."""
    if not isinstance(payload, dict):
        raise ArmError(f"arm {name!r} must be an object")
    raw_links = payload.get("links")
    if not isinstance(raw_links, list) or not 2 <= len(raw_links) <= 3:
        raise ArmError(
            f"arm {name!r} needs a link list of 2 or 3 entries")
    links = tuple(_finite(value, f"arm {name!r} link {i}")
                  for i, value in enumerate(raw_links))
    if any(link < 0 for link in links):
        raise ArmError(f"arm {name!r} links must be >= 0")
    if links[0] <= 0 or links[1] <= 0:
        raise ArmError(f"arm {name!r} position links must be > 0")
    raw_joints = payload.get("joints")
    if not isinstance(raw_joints, list) or len(raw_joints) != len(links):
        raise ArmError(
            f"arm {name!r} needs {len(links)} joint definition(s)")
    joints = tuple(joint_from_dict(i, entry)
                   for i, entry in enumerate(raw_joints))
    description = payload.get("description", "")
    if not isinstance(description, str):
        raise ArmError(f"arm {name!r} description must be a string")
    return ArmSpec(name=name, links=links, joints=joints,
                   description=description)


def load_arm(path: str | Path | None = None) -> ArmSpec:
    """Load the arm JSON file (a single definition)."""
    source = Path(path) if path is not None else ARM_FILE
    if not source.is_file():
        raise ArmError(f"arm file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ArmError(f"could not parse {source.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ArmError(f"arm file {source.name} must be a JSON object")
    name = payload.pop("name", source.stem) if "name" in payload else source.stem
    arm = arm_from_dict(str(name), payload)
    LOG.info("loaded arm %s from %s", arm.name, source.name)
    return arm


def _obstacle_from_dict(index: int, payload: object) -> Obstacle:
    if not isinstance(payload, dict):
        raise ArmError(f"obstacle {index} must be an object")
    name = payload.get("name", f"obstacle{index}")
    if not isinstance(name, str) or not name.strip():
        raise ArmError(f"obstacle {index} name must be a non-empty string")
    x = _finite(payload.get("x"), f"obstacle {index} x")
    y = _finite(payload.get("y"), f"obstacle {index} y")
    radius = _finite(payload.get("radius"), f"obstacle {index} radius")
    if radius <= 0:
        raise ArmError(f"obstacle {index} radius must be > 0")
    return Obstacle(name=name.strip(), x=x, y=y, radius=radius)


def mission_from_dict(payload: object, arm: ArmSpec | None = None) -> Mission:
    """Validate a mission definition."""
    if not isinstance(payload, dict):
        raise ArmError("mission must be a JSON object")
    if arm is not None and "arm" in payload and payload["arm"] != arm.name:
        raise ArmError(
            f"mission targets arm {payload['arm']!r}, loaded {arm.name!r}")
    name = payload.get("name", "mission")
    if not isinstance(name, str) or not name.strip():
        raise ArmError("mission name must be a non-empty string")

    home = payload.get("home")
    if not isinstance(home, (list, tuple)) or len(home) not in (2, 3):
        raise ArmError("mission home must be [x, y] or [x, y, yaw]")
    home_x = _finite(home[0], "home x")
    home_y = _finite(home[1], "home y")
    home_yaw = None
    if len(home) == 3:
        home_yaw = _finite(home[2], "home yaw")

    dwell = _finite(payload.get("dwell", 0.0), "dwell")
    if dwell < 0:
        raise ArmError("dwell must be >= 0")
    steps = payload.get("steps", 40)
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 2:
        raise ArmError(f"steps must be an integer >= 2, got {steps!r}")

    raw_waypoints = payload.get("waypoints")
    if not isinstance(raw_waypoints, list) or not raw_waypoints:
        raise ArmError("mission needs a non-empty waypoint list")
    waypoints: list[Waypoint] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw_waypoints):
        if not isinstance(entry, dict):
            raise ArmError(f"waypoint {index} must be an object")
        label = entry.get("name", f"wp{index}")
        if not isinstance(label, str) or not label.strip():
            raise ArmError(f"waypoint {index} name must be a non-empty string")
        label = label.strip()
        if label in seen:
            raise ArmError(f"duplicate waypoint name {label!r}")
        seen.add(label)
        x = _finite(entry.get("x"), f"waypoint {label!r} x")
        y = _finite(entry.get("y"), f"waypoint {label!r} y")
        yaw = None
        if "yaw" in entry and entry["yaw"] is not None:
            yaw = _finite(entry["yaw"], f"waypoint {label!r} yaw")
        waypoints.append(Waypoint(name=label, x=x, y=y, yaw=yaw))

    raw_obstacles = payload.get("obstacles", [])
    if not isinstance(raw_obstacles, list):
        raise ArmError("obstacles must be a list")
    obstacles = tuple(_obstacle_from_dict(i, entry)
                      for i, entry in enumerate(raw_obstacles))

    return Mission(name=name.strip(),
                   home=(home_x, home_y, home_yaw),
                   waypoints=tuple(waypoints), obstacles=obstacles,
                   dwell=dwell, steps=steps)


def load_mission(path: str | Path | None = None,
                 arm: ArmSpec | None = None) -> Mission:
    """Load and validate a mission JSON file."""
    source = Path(path) if path is not None else MISSION_FILE
    if not source.is_file():
        raise ArmError(f"mission file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ArmError(f"could not parse {source.name}: {exc}") from exc
    mission = mission_from_dict(payload, arm)
    LOG.info("loaded mission %s from %s", mission.name, source.name)
    return mission


def parse_pose(text: str) -> tuple[float, ...]:
    """Parse 'x,y' or 'x,y,yaw'."""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) not in (2, 3):
        raise ArmError(f"pose must be 'x,y' or 'x,y,yaw', got {text!r}")
    return tuple(_finite(part, f"pose component {i}")
                 for i, part in enumerate(parts))


# --------------------------------------------------------------------------- #
# Kinematics
# --------------------------------------------------------------------------- #
def check_joints(arm: ArmSpec, q, enforce_limits: bool = True
                 ) -> tuple[float, ...]:
    """Validate a configuration's length, finiteness and limits."""
    values = tuple(float(v) for v in q)
    if len(values) != arm.n_joints:
        raise ArmError(
            f"arm {arm.name!r} needs {arm.n_joints} joint value(s), "
            f"got {len(values)}")
    if any(not math.isfinite(v) for v in values):
        raise ArmError("joint values must be finite")
    if not enforce_limits:
        return values
    for i, (value, joint) in enumerate(zip(values, arm.joints)):
        if value < joint.low - EPS or value > joint.high + EPS:
            raise ArmError(
                f"joint {joint.name} value {value:.3f} deg outside "
                f"[{joint.low:.1f}, {joint.high:.1f}]")
    return values


def link_points(arm: ArmSpec, q) -> tuple[tuple[float, float], ...]:
    """Base plus every link endpoint, in the base frame."""
    values = check_joints(arm, q, enforce_limits=False)
    points: list[tuple[float, float]] = [(0.0, 0.0)]
    angle = 0.0
    x = y = 0.0
    for length, value in zip(arm.links, values):
        angle += value
        x += length * math.cos(math.radians(angle))
        y += length * math.sin(math.radians(angle))
        points.append((x, y))
    return tuple(points)


def pose(arm: ArmSpec, q) -> Pose:
    """Tool pose from joint values."""
    values = check_joints(arm, q, enforce_limits=False)
    angle = 0.0
    x = y = 0.0
    for length, value in zip(arm.links, values):
        angle += value
        x += length * math.cos(math.radians(angle))
        y += length * math.sin(math.radians(angle))
    return Pose(x=x, y=y, yaw=wrap_deg(angle))


def _candidates_2link(arm: ArmSpec, x: float, y: float,
                      yaw: float | None) -> list[tuple[float, ...]]:
    radius = math.hypot(x, y)
    inner, outer = arm.inner_reach, arm.outer_reach
    if radius > outer + EPS or radius < inner - EPS:
        raise ArmError(
            f"pose ({x:.4f}, {y:.4f}) unreachable: distance {radius:.4f} m "
            f"outside [{inner:.4f}, {outer:.4f}] m")
    a1, a2 = arm.links[0], arm.links[1]
    cosine = (radius ** 2 - a1 ** 2 - a2 ** 2) / (2.0 * a1 * a2)
    cosine = max(-1.0, min(1.0, cosine))
    magnitude = math.degrees(math.acos(cosine))

    candidates: list[tuple[float, ...]] = []
    for sign in (1.0, -1.0):
        q1 = sign * magnitude
        q0 = math.degrees(
            math.atan2(y, x)
            - math.atan2(a2 * math.sin(math.radians(q1)),
                         a1 + a2 * math.cos(math.radians(q1))))
        values = [wrap_deg(q0), wrap_deg(q1)]
        if arm.n_joints == 3:
            if yaw is None:
                values.append(0.0)
            else:
                values.append(wrap_deg(yaw - (values[0] + values[1])))
        candidates.append(tuple(values))
    return candidates


def solve_ik(arm: ArmSpec, target, near=None) -> tuple[float, ...]:
    """Exact IK for the 2R position plus a wrist joint, honouring limits."""
    values = tuple(float(v) for v in target)
    if len(values) not in (2, 3):
        raise ArmError(f"target must be x,y or x,y,yaw, got {len(values)}")
    if any(not math.isfinite(v) for v in values):
        raise ArmError("target must be finite")
    yaw = values[2] if len(values) == 3 else None
    if yaw is not None and arm.n_joints < 3:
        raise ArmError(
            f"arm {arm.name!r} has no wrist joint; yaw is not controllable")

    feasible = [q for q in _candidates_2link(arm, values[0], values[1], yaw)
                if all(joint.low - EPS <= value <= joint.high + EPS
                       for value, joint in zip(q, arm.joints))]
    if not feasible:
        raise ArmError(
            f"no IK solution for ({values[0]:.4f}, {values[1]:.4f}) "
            f"within the joint limits")

    if near is not None:
        reference = check_joints(arm, near, enforce_limits=False)
        feasible.sort(key=lambda q: sum(
            abs(wrap_deg(a - b)) for a, b in zip(q, reference)))
    return feasible[0]


# --------------------------------------------------------------------------- #
# Trajectories
# --------------------------------------------------------------------------- #
def _sample(arm: ArmSpec, t: float, q: tuple[float, ...],
            speeds: tuple[float, ...]) -> Sample:
    tool = pose(arm, q)
    return Sample(t=t, q=q, x=tool.x, y=tool.y, yaw=tool.yaw, speeds=speeds)


def time_parameterize(arm: ArmSpec, path, dt: float = 0.05,
                      speed_scale: float = 1.0,
                      enforce_limits: bool = True) -> Trajectory:
    """Time a joint path with a minimum-jerk profile under speed limits."""
    if not isinstance(dt, (int, float)) or isinstance(dt, bool):
        raise ArmError(f"dt must be a number, got {dt!r}")
    if not math.isfinite(dt) or dt <= 0:
        raise ArmError(f"dt must be > 0, got {dt!r}")
    if not isinstance(speed_scale, (int, float)) or isinstance(
            speed_scale, bool):
        raise ArmError(f"speed_scale must be a number, got {speed_scale!r}")
    if not math.isfinite(speed_scale) or speed_scale <= 0:
        raise ArmError(f"speed_scale must be > 0, got {speed_scale!r}")

    configurations = [check_joints(arm, q, enforce_limits)
                      for q in path]
    if not configurations:
        raise ArmError("path must contain at least one configuration")
    if len(configurations) == 1:
        configurations.append(configurations[0])

    segments = len(configurations) - 1
    peak_rate = [0.0] * arm.n_joints
    for start, end in zip(configurations, configurations[1:]):
        for i in range(arm.n_joints):
            peak_rate[i] = max(peak_rate[i],
                               abs(end[i] - start[i]) * segments)

    duration = 0.0
    for rate, joint in zip(peak_rate, arm.joints):
        duration = max(duration,
                       PEAK_FACTOR * rate / (joint.max_speed * speed_scale))
    if duration <= EPS:
        only = configurations[0]
        zero = tuple(0.0 for _ in only)
        return Trajectory(samples=(_sample(arm, 0.0, only, zero),),
                          duration=0.0, dt=float(dt))

    steps = max(1, int(math.ceil(duration / dt)))
    actual_dt = duration / steps
    samples: list[Sample] = []
    for index in range(steps + 1):
        fraction = index / steps
        s = minjerk(fraction)
        u = s * segments
        low = min(int(u), segments - 1)
        local = u - low
        start = configurations[low]
        end = configurations[low + 1]
        q = tuple(a + (b - a) * local for a, b in zip(start, end))
        rate = minjerk_derivative(fraction) / duration
        speeds = tuple((b - a) * segments * rate
                       for a, b in zip(start, end))
        samples.append(_sample(arm, index * actual_dt, q, speeds))
    return Trajectory(samples=tuple(samples), duration=duration,
                      dt=actual_dt)


def plan_joint_move(arm: ArmSpec, q_start, q_end, dt: float = 0.05,
                    speed_scale: float = 1.0) -> Trajectory:
    """Move directly between two configurations."""
    return time_parameterize(arm, [q_start, q_end], dt=dt,
                             speed_scale=speed_scale)


def plan_cartesian_move(arm: ArmSpec, q_start, target, steps: int = 40,
                        dt: float = 0.05, speed_scale: float = 1.0
                        ) -> Trajectory:
    """Follow a straight Cartesian line, solving IK at every waypoint."""
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 2:
        raise ArmError(f"steps must be an integer >= 2, got {steps!r}")
    values = tuple(float(v) for v in target)
    if len(values) not in (2, 3):
        raise ArmError(f"target must be x,y or x,y,yaw, got {len(values)}")
    start = pose(arm, check_joints(arm, q_start))
    goal_yaw = start.yaw
    if len(values) == 3:
        if arm.n_joints < 3:
            raise ArmError(
                f"arm {arm.name!r} has no wrist joint; yaw is not "
                f"controllable")
        goal_yaw = wrap_deg(values[2])
    delta_yaw = wrap_deg(goal_yaw - start.yaw)

    path: list[tuple[float, ...]] = []
    previous = check_joints(arm, q_start)
    for index in range(steps + 1):
        fraction = index / steps
        x = start.x + (values[0] - start.x) * fraction
        y = start.y + (values[1] - start.y) * fraction
        yaw = start.yaw + delta_yaw * fraction
        request = (x, y, yaw) if arm.n_joints == 3 else (x, y)
        previous = solve_ik(arm, request, near=previous)
        path.append(previous)
    return time_parameterize(arm, path, dt=dt, speed_scale=speed_scale)


# --------------------------------------------------------------------------- #
# Collisions
# --------------------------------------------------------------------------- #
def point_segment_distance(point: tuple[float, float],
                           start: tuple[float, float],
                           end: tuple[float, float]) -> float:
    """Shortest distance from a point to a line segment."""
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= EPS:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def check_collisions(arm: ArmSpec, trajectory: Trajectory,
                     obstacles: tuple[Obstacle, ...] | list[Obstacle]
                     ) -> list[Collision]:
    """Every link-vs-obstacle overlap in a trajectory."""
    found: list[Collision] = []
    for sample in trajectory.samples:
        points = link_points(arm, sample.q)
        for obstacle in obstacles:
            centre = (obstacle.x, obstacle.y)
            for link, (start, end) in enumerate(
                    zip(points, points[1:])):
                distance = point_segment_distance(centre, start, end)
                clearance = obstacle.radius - distance
                if clearance > EPS:
                    found.append(Collision(
                        t=sample.t, link=link, obstacle=obstacle.name,
                        clearance=clearance))
    return found


# --------------------------------------------------------------------------- #
# Missions
# --------------------------------------------------------------------------- #
def run_mission(arm: ArmSpec, mission: Mission, dt: float = 0.05,
                speed_scale: float = 1.0) -> MissionResult:
    """Plan every leg of a mission, then check limits and collisions."""
    q = solve_ik(arm, mission.home)
    segments: list[Segment] = []
    errors: list[tuple[str, float]] = []
    collisions: list[Collision] = []

    for waypoint in mission.waypoints:
        target = ((waypoint.x, waypoint.y, waypoint.yaw)
                  if waypoint.yaw is not None
                  else (waypoint.x, waypoint.y))
        if arm.n_joints == 3 and waypoint.yaw is None:
            target = (waypoint.x, waypoint.y, pose(arm, q).yaw)
        trajectory = plan_cartesian_move(
            arm, q, target, steps=mission.steps, dt=dt,
            speed_scale=speed_scale)
        segments.append(Segment(waypoint.name, trajectory, mission.dwell))
        collisions.extend(check_collisions(arm, trajectory,
                                           mission.obstacles))
        achieved = pose(arm, trajectory.q_end)
        errors.append((waypoint.name,
                       math.hypot(achieved.x - waypoint.x,
                                  achieved.y - waypoint.y)))
        q = trajectory.q_end

    home_target = mission.home
    if arm.n_joints == 3 and mission.home[2] is None:
        home_target = (mission.home[0], mission.home[1], pose(arm, q).yaw)
    home_trajectory = plan_cartesian_move(
        arm, q, home_target, steps=mission.steps, dt=dt,
        speed_scale=speed_scale)
    segments.append(Segment("home", home_trajectory, 0.0))
    collisions.extend(check_collisions(arm, home_trajectory,
                                       mission.obstacles))

    return MissionResult(mission=mission.name, segments=tuple(segments),
                         collisions=tuple(collisions),
                         waypoint_errors=tuple(errors))


def render_report(result: MissionResult) -> str:
    """ASCII summary of a planned mission."""
    lines = [
        f"MISSION - {result.mission}",
        "=" * 70,
        f"{'LEG':<14}{'SAMPLES':>9}{'MOVE s':>9}{'DWELL s':>9}"
        f"{'END x':>9}{'END y':>9}{'END yaw':>9}",
        "-" * 70,
    ]
    for segment in result.segments:
        last = segment.trajectory.samples[-1]
        lines.append(
            f"{segment.name:<14}{len(segment.trajectory.samples):>9}"
            f"{segment.trajectory.duration:>9.2f}{segment.dwell:>9.2f}"
            f"{last.x:>9.4f}{last.y:>9.4f}{last.yaw:>9.2f}")
    lines += [
        "-" * 70,
        f"Total time   : {result.total_time:.2f} s "
        f"(moving {result.move_time:.2f} s)",
        f"Samples      : {result.sample_count}",
        f"Waypoint err : "
        + ", ".join(f"{name}={error:.2e} m"
                    for name, error in result.waypoint_errors),
        f"Collisions   : {len(result.collisions)}",
        "Max speeds   : "
        + ", ".join(f"{speed:.1f} deg/s"
                    for speed in result.max_speeds),
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    """Run the bundled pick-and-place demo - fully offline."""
    print("=" * 70)
    print(" ROBOT ARM SIMULATOR - offline demo")
    print(" Exact IK, minimum-jerk trajectories, limits and collisions.")
    print("=" * 70)

    arm = load_arm()
    mission = load_mission(arm=arm)
    print(f"\nArm     : {arm.name} - {arm.description}")
    print(f"Links   : {', '.join(f'{link:.2f} m' for link in arm.links)}")
    for joint in arm.joints:
        print(f"  {joint.name}: [{joint.low:+.0f}, {joint.high:+.0f}] deg"
              f"   max {joint.max_speed:.0f} deg/s")
    print(f"Mission : {mission.name} - {len(mission.waypoints)} waypoints, "
          f"{len(mission.obstacles)} obstacle(s)")

    result = run_mission(arm, mission)
    print()
    print(render_report(result))

    # --- cross-checks the demo asserts ------------------------------------- #
    # 1. every waypoint is reached to sub-micrometre accuracy
    for name, error in result.waypoint_errors:
        assert error < 1e-6, f"waypoint {name} missed by {error:.3e} m"

    # 2. no joint leaves its limits and no joint exceeds its speed
    for segment in result.segments:
        for sample in segment.trajectory.samples:
            check_joints(arm, sample.q)
    for speed, joint in zip(result.max_speeds, arm.joints):
        assert speed <= joint.max_speed + 1e-6, (
            f"{joint.name} exceeded {joint.max_speed} deg/s: {speed:.4f}")

    # 3. minimum-jerk profiles start and end at rest
    for segment in result.segments:
        first = segment.trajectory.samples[0]
        last = segment.trajectory.samples[-1]
        assert max(abs(v) for v in first.speeds) < 1e-9
        assert max(abs(v) for v in last.speeds) < 1e-9
        assert segment.trajectory.duration > 0.0

    # 4. trajectories are continuous: no sample jumps further than
    #    the joint speed limit allows
    for segment in result.segments:
        trajectory = segment.trajectory
        for before, after in zip(trajectory.samples,
                                 trajectory.samples[1:]):
            step = after.t - before.t
            for i, joint in enumerate(arm.joints):
                jump = abs(after.q[i] - before.q[i])
                assert jump <= joint.max_speed * step * 2.0 + 1e-6, (
                    f"discontinuity in {joint.name}")

    # 5. the tool follows the requested straight lines closely
    worst = 0.0
    for segment, waypoint in zip(result.segments, mission.waypoints):
        start = segment.trajectory.samples[0]
        end = segment.trajectory.samples[-1]
        for sample in segment.trajectory.samples:
            dx, dy = end.x - start.x, end.y - start.y
            length = math.hypot(dx, dy)
            if length <= EPS:
                continue
            cross = abs((sample.x - start.x) * dy
                        - (sample.y - start.y) * dx) / length
            worst = max(worst, cross)
    assert worst < 5e-3, f"cartesian deviation {worst:.4f} m too large"

    # 6. the bundled obstacles are clear of the whole mission
    assert not result.collisions, (
        f"{len(result.collisions)} collision(s) in the bundled mission")

    # 7. a deliberately blocked move is detected, not silently ignored
    blocked = Mission(name="blocked", home=(0.55, 0.35, 90.0),
                      waypoints=(Waypoint("crash", 0.55, 0.65, 90.0),),
                      obstacles=(Obstacle("blocker", 0.55, 0.0, 0.06),),
                      dwell=0.0, steps=20)
    blocked_result = run_mission(arm, blocked)
    assert blocked_result.collisions, "blocked move was not detected"

    # 8. impossible poses are rejected with a clear error
    for target in ((2.0, 0.0), (0.01, 0.0)):
        try:
            solve_ik(arm, target)
        except ArmError as exc:
            assert "unreachable" in str(exc)
        else:
            raise AssertionError(f"unreachable pose {target} accepted")

    # 9. deterministic re-run: identical samples
    again = run_mission(arm, mission)
    assert again.total_time == result.total_time
    assert again.segments[0].trajectory.samples == \
        result.segments[0].trajectory.samples

    print(f"\nStraight-line deviation: {worst:.2e} m")
    print(f"Blocked move detected  : "
          f"{len(blocked_result.collisions)} collision sample(s)")

    print("\nCross-checks OK: waypoints reached, joint limits and speed "
          "limits held, rest-to-rest profiles, continuous samples, "
          "straight Cartesian lines, bundled mission collision-free, "
          "blocked move detected, impossible poses rejected, "
          "deterministic re-run")
    print("\nDemo completed successfully.")
    return 0
