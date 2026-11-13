"""2D extended Kalman filter localisation - fully offline.

A differential-drive robot moves through a room with known landmarks.  It
only knows its own wheel odometry (noisy) and range/bearing sightings of
the landmarks (noisy).  This module fuses the two:

* ``motion_model`` / ``motion_jacobian`` - exact arc integration of a
  differential drive over one time step, plus its 3x3 Jacobian;
* ``measurement`` / ``measurement_jacobian`` - range and bearing from a
  pose to a landmark, plus its 2x3 Jacobian;
* ``ExtendedKalmanFilter`` - predict / update with Joseph-form covariance
  updates, innovation gating (chi-square) and innovation reporting;
* ``KalmanFilter1D`` - the scalar filter, kept as the teaching baseline;
* ``simulate`` - deterministic ground truth, noisy odometry and noisy
  landmark sightings from a scenario file and a seed;
* ``run_ekf`` - replay a simulation through the filter;
* ``dead_reckon`` - integrate odometry alone, for comparison.

Angles are radians internally and degrees in reports.  Everything is
local: landmarks in a CSV, the scenario in a JSON file.  No network, no
API keys, no ROS, no hardware.
"""

from __future__ import annotations

import csv
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

LOG = logging.getLogger("localizer")

EPS = 1e-12
TWO_PI = 2.0 * math.pi
CHI2_2DOF_95 = 5.991
CHI2_2DOF_99 = 9.210
DEG = 180.0 / math.pi
STATE_LABELS = ("x", "y", "theta")

LANDMARK_FILE = Path(__file__).resolve().parent.parent / "data" / "landmarks.csv"
SCENARIO_FILE = Path(__file__).resolve().parent.parent / "data" / "scenario.json"

# Sentinel: "use scenario.gate" for run_ekf(gate=...).
USE_SCENARIO_GATE = object()


class LocalizerError(RuntimeError):
    """Raised for invalid data files, bad flags and degenerate geometry."""


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def wrap_angle(angle: float) -> float:
    """Wrap an angle into [-pi, pi)."""
    return (float(angle) + math.pi) % TWO_PI - math.pi


def _finite(value, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise LocalizerError(f"{label} must be numeric, got {value!r}") from exc
    if not math.isfinite(number):
        raise LocalizerError(f"{label} must be finite, got {value!r}")
    return number


def _positive(value, label: str) -> float:
    number = _finite(value, label)
    if number <= 0:
        raise LocalizerError(f"{label} must be > 0, got {number}")
    return number


def _non_negative(value, label: str) -> float:
    number = _finite(value, label)
    if number < 0:
        raise LocalizerError(f"{label} must be >= 0, got {number}")
    return number


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Pose:
    """Planar pose; ``theta`` is in radians."""

    x: float
    y: float
    theta: float

    @property
    def position(self) -> np.ndarray:
        return np.array([self.x, self.y], dtype=float)

    @property
    def state(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.theta)

    def to_dict(self) -> dict:
        return {"x": round(self.x, 6), "y": round(self.y, 6),
                "theta_deg": round(wrap_angle(self.theta) * DEG, 4)}


@dataclass(frozen=True)
class Landmark:
    """A known point feature in the room."""

    name: str
    x: float
    y: float

    @property
    def position(self) -> np.ndarray:
        return np.array([self.x, self.y], dtype=float)


@dataclass(frozen=True)
class Measurement:
    """One range/bearing sighting of a landmark."""

    step: int
    t: float
    landmark: str
    range: float
    bearing: float
    outlier: bool = False

    def to_dict(self) -> dict:
        return {"step": self.step, "t": round(self.t, 6),
                "landmark": self.landmark,
                "range": round(self.range, 6),
                "bearing_deg": round(wrap_angle(self.bearing) * DEG, 4),
                "outlier": self.outlier}


# --------------------------------------------------------------------------- #
# Motion model
# --------------------------------------------------------------------------- #
def motion_model(state, v: float, w: float, dt: float) -> np.ndarray:
    """Exact differential-drive arc over ``dt`` seconds."""
    x, y, theta = (float(value) for value in state)
    v = float(v)
    w = float(w)
    dt = float(dt)
    if dt <= 0:
        raise LocalizerError(f"dt must be > 0, got {dt}")
    if abs(w) < 1e-9:
        return np.array([x + v * dt * math.cos(theta),
                         y + v * dt * math.sin(theta),
                         wrap_angle(theta)], dtype=float)
    radius = v / w
    turned = theta + w * dt
    return np.array([x + radius * (math.sin(turned) - math.sin(theta)),
                     y - radius * (math.cos(turned) - math.cos(theta)),
                     wrap_angle(turned)], dtype=float)


def motion_jacobian(state, v: float, w: float, dt: float) -> np.ndarray:
    """d(state_{k+1}) / d(state_k) for the exact arc model."""
    _, _, theta = (float(value) for value in state)
    v = float(v)
    w = float(w)
    dt = float(dt)
    if dt <= 0:
        raise LocalizerError(f"dt must be > 0, got {dt}")
    jacobian = np.eye(3)
    if abs(w) < 1e-9:
        jacobian[0, 2] = -v * dt * math.sin(theta)
        jacobian[1, 2] = v * dt * math.cos(theta)
        return jacobian
    radius = v / w
    turned = theta + w * dt
    jacobian[0, 2] = radius * (math.cos(turned) - math.cos(theta))
    jacobian[1, 2] = radius * (math.sin(turned) - math.sin(theta))
    return jacobian


def integrate_rk4(state, v: float, w: float, dt: float,
                  substeps: int = 100) -> np.ndarray:
    """Integrate the differential-drive ODE with classic RK4.

    Used to check that ``motion_model``'s closed-form arc is exact rather
    than a first-order approximation.
    """
    state = np.asarray(state, dtype=float).ravel().copy()
    if state.size != 3:
        raise LocalizerError(f"state must have 3 values, got {state.size}")
    if dt <= 0:
        raise LocalizerError(f"dt must be > 0, got {dt}")
    if isinstance(substeps, bool) or not isinstance(substeps, int) \
            or substeps < 1:
        raise LocalizerError(
            f"substeps must be an integer >= 1, got {substeps!r}")
    h = dt / substeps

    def dynamics(point: np.ndarray) -> np.ndarray:
        return np.array([v * math.cos(point[2]), v * math.sin(point[2]), w])

    for _ in range(substeps):
        k1 = dynamics(state)
        k2 = dynamics(state + 0.5 * h * k1)
        k3 = dynamics(state + 0.5 * h * k2)
        k4 = dynamics(state + h * k3)
        state = state + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        state[2] = wrap_angle(state[2])
    return state


def measurement(state, landmark: Landmark) -> np.ndarray:
    """Expected (range, bearing) sighting of a landmark from a pose."""
    x, y, theta = (float(value) for value in state)
    dx = landmark.x - x
    dy = landmark.y - y
    distance = math.hypot(dx, dy)
    if distance <= EPS:
        raise LocalizerError(
            f"landmark {landmark.name!r} coincides with the robot")
    return np.array([distance, wrap_angle(math.atan2(dy, dx) - theta)],
                    dtype=float)


def measurement_jacobian(state, landmark: Landmark) -> np.ndarray:
    """d(range, bearing) / d(x, y, theta)."""
    x, y = float(state[0]), float(state[1])
    dx = landmark.x - x
    dy = landmark.y - y
    squared = dx * dx + dy * dy
    if squared <= EPS * EPS:
        raise LocalizerError(
            f"landmark {landmark.name!r} coincides with the robot")
    distance = math.sqrt(squared)
    return np.array([
        [-dx / distance, -dy / distance, 0.0],
        [dy / squared, -dx / squared, -1.0],
    ], dtype=float)


# --------------------------------------------------------------------------- #
# Scalar Kalman filter (teaching baseline)
# --------------------------------------------------------------------------- #
@dataclass
class KalmanFilter1D:
    """One-dimensional Kalman filter with a scalar state."""

    state: float = 0.0
    variance: float = 1.0
    gain: float = 0.0
    updates: int = 0

    def __post_init__(self) -> None:
        self.state = _finite(self.state, "state")
        self.variance = _non_negative(self.variance, "variance")

    def predict(self, delta: float = 0.0, process_var: float = 0.0) -> float:
        """Add a known ``delta`` and grow the variance."""
        self.state += _finite(delta, "delta")
        self.variance += _non_negative(process_var, "process_var")
        return self.state

    def update(self, measurement_value: float, meas_var: float) -> float:
        """Fuse one measurement and return the posterior state."""
        measurement_value = _finite(measurement_value, "measurement")
        meas_var = _positive(meas_var, "meas_var")
        innovation = measurement_value - self.state
        gain = self.variance / (self.variance + meas_var)
        self.state += gain * innovation
        self.variance = (1.0 - gain) * self.variance
        self.gain = gain
        self.updates += 1
        return self.state


def filter_scalar(values, process_var: float, meas_var: float,
                  initial: float | None = None
                  ) -> list[tuple[float, float, float]]:
    """Run the scalar filter over a sequence: (estimate, variance, gain)."""
    values = list(values)
    if not values:
        raise LocalizerError("filter_scalar needs at least one value")
    start = values[0] if initial is None else _finite(initial, "initial")
    filt = KalmanFilter1D(state=start, variance=max(1e-6, meas_var))
    trace: list[tuple[float, float, float]] = []
    for index, value in enumerate(values):
        if index:
            filt.predict(process_var=process_var)
        filt.update(value, meas_var)
        trace.append((filt.state, filt.variance, filt.gain))
    return trace


# --------------------------------------------------------------------------- #
# Extended Kalman filter
# --------------------------------------------------------------------------- #
class ExtendedKalmanFilter:
    """EKF over the planar pose ``[x, y, theta]``."""

    def __init__(self, state, covariance=None,
                 process_sigmas=(0.02, 0.02, 0.01),
                 motion_scaling=(0.05, 0.05),
                 range_sigma: float = 0.10,
                 bearing_sigma: float = 0.03):
        values = np.asarray(state, dtype=float).ravel()
        if values.size != 3:
            raise LocalizerError(
                f"state must have 3 values, got {values.size}")
        if not np.isfinite(values).all():
            raise LocalizerError("state must be finite")
        self.state = np.array([values[0], values[1], wrap_angle(values[2])])
        if covariance is None:
            covariance = np.diag([0.09, 0.09, 0.01])
        matrix = np.asarray(covariance, dtype=float)
        if matrix.shape != (3, 3):
            raise LocalizerError(
                f"covariance must be 3x3, got {matrix.shape}")
        if not np.isfinite(matrix).all():
            raise LocalizerError("covariance must be finite")
        self.covariance = matrix.copy()
        sigmas = tuple(_non_negative(value, "process sigma")
                       for value in process_sigmas)
        if len(sigmas) != 3:
            raise LocalizerError("process_sigmas needs 3 values")
        self.process_sigmas = sigmas
        self.motion_scaling = (
            _non_negative(motion_scaling[0], "motion scaling"),
            _non_negative(motion_scaling[1], "motion scaling"))
        self.range_sigma = _positive(range_sigma, "range_sigma")
        self.bearing_sigma = _positive(bearing_sigma, "bearing_sigma")
        self.gate: float | None = CHI2_2DOF_95
        self.last_nis = 0.0
        self.last_accepted = True
        self.updates = 0
        self.rejections = 0

    # -- prediction ------------------------------------------------------- #
    def predict(self, v: float, w: float, dt: float) -> np.ndarray:
        """Propagate the state and covariance through one motion step."""
        jacobian = motion_jacobian(self.state, v, w, dt)
        self.state = motion_model(self.state, v, w, dt)
        distance = abs(float(v)) * float(dt)
        turned = abs(float(w)) * float(dt)
        q_xy = (self.process_sigmas[0] ** 2
                + self.motion_scaling[0] * distance ** 2)
        q_th = (self.process_sigmas[2] ** 2
                + self.motion_scaling[1] * turned ** 2)
        process = np.diag([q_xy, q_xy, q_th])
        self.covariance = jacobian @ self.covariance @ jacobian.T + process
        return self.state

    # -- correction ------------------------------------------------------- #
    def update(self, landmark: Landmark, z_range: float, z_bearing: float,
               gate: float | None = None) -> float:
        """Fuse one range/bearing measurement; returns the innovation NIS."""
        z_range = _positive(z_range, "measurement range")
        z_bearing = _finite(z_bearing, "measurement bearing")
        predicted = measurement(self.state, landmark)
        innovation = np.array([
            z_range - predicted[0],
            wrap_angle(z_bearing - predicted[1]),
        ])
        jacobian = measurement_jacobian(self.state, landmark)
        noise = np.diag([self.range_sigma ** 2, self.bearing_sigma ** 2])
        innovation_cov = jacobian @ self.covariance @ jacobian.T + noise
        nis = float(innovation @ np.linalg.solve(innovation_cov, innovation))
        self.last_nis = nis

        threshold = self.gate if gate is None else gate
        if threshold is not None and nis > threshold:
            self.last_accepted = False
            self.rejections += 1
            return nis

        gain = (self.covariance @ jacobian.T
                @ np.linalg.inv(innovation_cov))
        self.state = self.state + gain @ innovation
        self.state[2] = wrap_angle(self.state[2])
        identity = np.eye(3)
        factor = identity - gain @ jacobian
        self.covariance = (factor @ self.covariance @ factor.T
                           + gain @ noise @ gain.T)
        self.last_accepted = True
        self.updates += 1
        return nis

    # -- convenience ------------------------------------------------------ #
    @property
    def pose(self) -> Pose:
        return Pose(float(self.state[0]), float(self.state[1]),
                    float(self.state[2]))

    @property
    def sigma_xy(self) -> float:
        return math.sqrt(max(0.0, self.covariance[0, 0]
                             + self.covariance[1, 1]))

    @property
    def sigma_theta(self) -> float:
        return math.sqrt(max(0.0, self.covariance[2, 2]))

    def nees(self, truth: Pose) -> float:
        """Normalised estimation error squared against a known pose."""
        error = np.array([
            truth.x - self.state[0],
            truth.y - self.state[1],
            wrap_angle(truth.theta - self.state[2]),
        ])
        return float(error @ np.linalg.solve(self.covariance, error))

    def to_dict(self) -> dict:
        return {"state": [round(float(value), 6) for value in self.state],
                "covariance": [[round(float(value), 9) for value in row]
                               for row in self.covariance],
                "updates": self.updates, "rejections": self.rejections}


# --------------------------------------------------------------------------- #
# Scenario model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Segment:
    """A constant (v, w) command held for a number of steps."""

    v: float
    w: float
    steps: int


@dataclass(frozen=True)
class Scenario:
    """Everything needed to simulate and filter one run."""

    name: str
    seed: int
    dt: float
    initial: tuple[float, float, float]
    segments: tuple[Segment, ...]
    odom_sigma: tuple[float, float]
    meas_sigma: tuple[float, float]
    gate: float = CHI2_2DOF_95
    range_limit: float = 6.0
    outlier_every: int = 0
    outlier_bias: float = 0.0

    @property
    def total_steps(self) -> int:
        return sum(segment.steps for segment in self.segments)

    @property
    def duration(self) -> float:
        return self.total_steps * self.dt

    def commands(self) -> tuple[tuple[float, float], ...]:
        """Flatten the segments into one (v, w) pair per step."""
        return tuple((segment.v, segment.w)
                     for segment in self.segments
                     for _ in range(segment.steps))


def _segment_from_dict(index: int, payload: object) -> Segment:
    if not isinstance(payload, dict):
        raise LocalizerError(f"segment {index} must be an object")
    v = _finite(payload.get("v"), f"segment {index} v")
    w = _finite(payload.get("w"), f"segment {index} w")
    steps = payload.get("steps")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise LocalizerError(
            f"segment {index} steps must be an integer >= 1, got {steps!r}")
    return Segment(v=v, w=w, steps=steps)


def scenario_from_dict(payload: object) -> Scenario:
    """Validate a scenario definition."""
    if not isinstance(payload, dict):
        raise LocalizerError("scenario must be a JSON object")
    name = payload.get("name", "scenario")
    if not isinstance(name, str) or not name.strip():
        raise LocalizerError("scenario name must be a non-empty string")
    seed = payload.get("seed", 0)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise LocalizerError(
            f"seed must be an integer >= 0, got {seed!r}")
    dt = _positive(payload.get("dt", 0.1), "dt")

    initial = payload.get("initial_state")
    if not isinstance(initial, (list, tuple)) or len(initial) != 3:
        raise LocalizerError("initial_state must be [x, y, theta]")
    start = tuple(_finite(value, f"initial_state {i}")
                  for i, value in enumerate(initial))
    start = (start[0], start[1], wrap_angle(start[2]))

    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise LocalizerError("scenario needs a non-empty segment list")
    segments = tuple(_segment_from_dict(index, entry)
                     for index, entry in enumerate(raw_segments))

    odom = payload.get("odom_noise", {})
    if not isinstance(odom, dict):
        raise LocalizerError("odom_noise must be an object")
    odom_sigma = (_non_negative(odom.get("distance", 0.0),
                                "odom distance noise"),
                  _non_negative(odom.get("rotation", 0.0),
                                "odom rotation noise"))

    meas = payload.get("meas_noise", {})
    if not isinstance(meas, dict):
        raise LocalizerError("meas_noise must be an object")
    meas_sigma = (_non_negative(meas.get("range", 0.0), "range noise"),
                  _non_negative(meas.get("bearing", 0.0), "bearing noise"))

    gate = _positive(payload.get("gate", CHI2_2DOF_95), "gate")
    range_limit = _positive(payload.get("range_limit", 6.0), "range_limit")
    outlier_every = payload.get("outlier_every", 0)
    if (isinstance(outlier_every, bool)
            or not isinstance(outlier_every, int) or outlier_every < 0):
        raise LocalizerError(
            f"outlier_every must be an integer >= 0, got {outlier_every!r}")
    outlier_bias = _non_negative(payload.get("outlier_bias", 0.0),
                                 "outlier_bias")

    return Scenario(name=name.strip(), seed=seed, dt=dt, initial=start,
                    segments=segments, odom_sigma=odom_sigma,
                    meas_sigma=meas_sigma, gate=gate,
                    range_limit=range_limit, outlier_every=outlier_every,
                    outlier_bias=outlier_bias)


def load_scenario(path: str | Path | None = None) -> Scenario:
    """Load a scenario JSON file."""
    source = Path(path) if path is not None else SCENARIO_FILE
    if not source.is_file():
        raise LocalizerError(f"scenario file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise LocalizerError(
            f"could not parse {source.name}: {exc}") from exc
    scenario = scenario_from_dict(payload)
    LOG.info("loaded scenario %s from %s", scenario.name, source.name)
    return scenario


def load_landmarks(path: str | Path | None = None) -> dict[str, Landmark]:
    """Load landmarks from a CSV with columns ``id,x,y``."""
    source = Path(path) if path is not None else LANDMARK_FILE
    if not source.is_file():
        raise LocalizerError(f"landmark file not found: {source}")
    try:
        with source.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise LocalizerError(
            f"could not read {source.name}: {exc}") from exc
    if not rows:
        raise LocalizerError(f"{source.name} has no landmark rows")
    if "id" not in rows[0]:
        raise LocalizerError(f"{source.name} is missing column 'id'")
    for column in ("x", "y"):
        if column not in rows[0]:
            raise LocalizerError(
                f"{source.name} is missing column {column!r}")

    landmarks: dict[str, Landmark] = {}
    for index, row in enumerate(rows):
        name = (row.get("id") or "").strip()
        if not name:
            raise LocalizerError(f"landmark row {index} has a blank id")
        if name in landmarks:
            raise LocalizerError(f"duplicate landmark id {name!r}")
        landmarks[name] = Landmark(
            name=name,
            x=_finite(row.get("x"), f"landmark {name!r} x"),
            y=_finite(row.get("y"), f"landmark {name!r} y"))
    LOG.info("loaded %d landmark(s) from %s", len(landmarks), source.name)
    return landmarks


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Simulation:
    """Ground truth, noisy odometry and landmark sightings for one run."""

    scenario: str
    dt: float
    truth: tuple[Pose, ...]
    odometry: tuple[Pose, ...]
    controls: tuple[tuple[float, float], ...]
    measurements: tuple[Measurement, ...]
    outlier_steps: frozenset[int] = frozenset()

    @property
    def steps(self) -> int:
        return len(self.controls)


def simulate(scenario: Scenario,
             landmarks: dict[str, Landmark]) -> Simulation:
    """Generate ground truth, odometry and measurements deterministically."""
    if not landmarks:
        raise LocalizerError("no landmarks available for simulation")
    rng = np.random.default_rng(scenario.seed)
    dt = scenario.dt
    truth: list[Pose] = [Pose(*scenario.initial)]
    odometry: list[Pose] = [Pose(*scenario.initial)]
    controls: list[tuple[float, float]] = []
    measurements: list[Measurement] = []
    outliers: set[int] = set()

    command_index = 0
    for command in scenario.commands():
        command_index += 1
        v_cmd, w_cmd = command
        truth_pose = motion_model(truth[-1].state, v_cmd, w_cmd, dt)
        truth.append(Pose(float(truth_pose[0]), float(truth_pose[1]),
                          float(truth_pose[2])))

        v_meas = v_cmd * (1.0 + rng.normal(0.0, scenario.odom_sigma[0]))
        w_meas = w_cmd + rng.normal(0.0, scenario.odom_sigma[1])
        controls.append((float(v_meas), float(w_meas)))
        odometry_pose = motion_model(odometry[-1].state, v_meas, w_meas, dt)
        odometry.append(Pose(float(odometry_pose[0]),
                             float(odometry_pose[1]),
                             float(odometry_pose[2])))

        current = truth[-1]
        visible = [(math.hypot(landmark.x - current.x,
                               landmark.y - current.y), name, landmark)
                   for name, landmark in landmarks.items()]
        visible = [entry for entry in visible
                   if entry[0] <= scenario.range_limit and entry[0] > 1e-6]
        if not visible:
            continue
        visible.sort(key=lambda entry: (entry[0], entry[1]))
        _, name, landmark = visible[0]
        expected = measurement(np.array([current.x, current.y,
                                         current.theta]), landmark)
        noisy_range = expected[0] + rng.normal(0.0, scenario.meas_sigma[0])
        noisy_bearing = wrap_angle(
            expected[1] + rng.normal(0.0, scenario.meas_sigma[1]))
        outlier = (scenario.outlier_every > 0
                   and command_index % scenario.outlier_every == 0)
        if outlier:
            noisy_range += scenario.outlier_bias
            outliers.add(command_index)
        measurements.append(Measurement(
            step=command_index, t=command_index * dt, landmark=name,
            range=float(noisy_range), bearing=float(noisy_bearing),
            outlier=outlier))

    return Simulation(scenario=scenario.name, dt=dt, truth=tuple(truth),
                      odometry=tuple(odometry), controls=tuple(controls),
                      measurements=tuple(measurements),
                      outlier_steps=frozenset(outliers))


def dead_reckon(controls, dt: float,
                initial=(0.0, 0.0, 0.0)) -> tuple[Pose, ...]:
    """Integrate odometry alone, with no landmark corrections."""
    pose = Pose(*initial)
    poses = [pose]
    for v, w in controls:
        values = motion_model(pose.state, v, w, dt)
        pose = Pose(float(values[0]), float(values[1]), float(values[2]))
        poses.append(pose)
    return tuple(poses)


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Estimate:
    """Filter output after one predict/update cycle."""

    step: int
    t: float
    x: float
    y: float
    theta: float
    covariance: tuple[float, ...]
    nis: float | None = None
    accepted: bool | None = None

    @property
    def pose(self) -> Pose:
        return Pose(self.x, self.y, self.theta)

    @property
    def matrix(self) -> np.ndarray:
        return np.asarray(self.covariance, dtype=float).reshape(3, 3)

    @property
    def sigma_xy(self) -> float:
        matrix = self.matrix
        return math.sqrt(max(0.0, matrix[0, 0] + matrix[1, 1]))

    @property
    def sigma_theta(self) -> float:
        return math.sqrt(max(0.0, self.matrix[2, 2]))

    def to_dict(self) -> dict:
        return {"step": self.step, "t": round(self.t, 6),
                "x": round(self.x, 6), "y": round(self.y, 6),
                "theta_deg": round(wrap_angle(self.theta) * DEG, 4),
                "sigma_xy": round(self.sigma_xy, 6),
                "sigma_theta_deg": round(self.sigma_theta * DEG, 4),
                "nis": None if self.nis is None else round(self.nis, 6),
                "accepted": self.accepted}


def run_ekf(scenario: Scenario, simulation: Simulation,
            landmarks: dict[str, Landmark],
            gate: float | None | object = USE_SCENARIO_GATE,
            initial_covariance=None) -> tuple[Estimate, ...]:
    """Replay a simulation through the extended Kalman filter.

    ``gate`` may be a positive number (use that threshold), ``None``
    (disable gating, accept every measurement) or left at the default
    sentinel (use ``scenario.gate``).
    """
    if len(simulation.controls) != scenario.total_steps:
        raise LocalizerError(
            f"simulation has {len(simulation.controls)} step(s), scenario "
            f"expects {scenario.total_steps}")
    if gate is USE_SCENARIO_GATE:
        gate = scenario.gate
    elif gate is not None:
        gate = _positive(gate, "gate")

    filter_ = ExtendedKalmanFilter(
        scenario.initial, covariance=initial_covariance,
        process_sigmas=(0.02, 0.02,
                        max(1e-3, scenario.odom_sigma[1])),
        motion_scaling=(0.05, 0.05),
        range_sigma=scenario.meas_sigma[0] or 1e-6,
        bearing_sigma=scenario.meas_sigma[1] or 1e-6)
    filter_.gate = gate

    by_step: dict[int, list[Measurement]] = {}
    for entry in simulation.measurements:
        by_step.setdefault(entry.step, []).append(entry)

    estimates: list[Estimate] = []
    for step, (v, w) in enumerate(simulation.controls, start=1):
        filter_.predict(v, w, scenario.dt)
        nis = None
        accepted = None
        for entry in by_step.get(step, []):
            landmark = landmarks.get(entry.landmark)
            if landmark is None:
                raise LocalizerError(
                    f"measurement references unknown landmark "
                    f"{entry.landmark!r}")
            nis = filter_.update(landmark, entry.range, entry.bearing,
                                 gate=gate)
            accepted = filter_.last_accepted
        estimates.append(Estimate(
            step=step, t=step * scenario.dt, x=float(filter_.state[0]),
            y=float(filter_.state[1]), theta=float(filter_.state[2]),
            covariance=tuple(float(value)
                             for value in filter_.covariance.ravel()),
            nis=nis, accepted=accepted))
    return tuple(estimates)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def position_errors(poses, truth) -> tuple[float, ...]:
    """Per-step Euclidean position error."""
    if len(poses) != len(truth):
        raise LocalizerError(
            f"cannot compare {len(poses)} pose(s) with {len(truth)} truth "
            "pose(s)")
    return tuple(math.hypot(pose.x - real.x, pose.y - real.y)
                 for pose, real in zip(poses, truth))


def rmse_position(poses, truth) -> float:
    """Root-mean-square position error."""
    errors = position_errors(poses, truth)
    return math.sqrt(sum(error ** 2 for error in errors) / len(errors))


def heading_errors(poses, truth) -> tuple[float, ...]:
    """Per-step absolute heading error in degrees."""
    if len(poses) != len(truth):
        raise LocalizerError(
            f"cannot compare {len(poses)} pose(s) with {len(truth)} truth "
            "pose(s)")
    return tuple(abs(wrap_angle(pose.theta - real.theta)) * DEG
                 for pose, real in zip(poses, truth))


def mean_nees(estimates: tuple[Estimate, ...] | list[Estimate],
              truth: tuple[Pose, ...] | list[Pose]) -> float:
    """Average normalised estimation error squared."""
    if not estimates:
        raise LocalizerError("mean_nees needs at least one estimate")
    if len(estimates) > len(truth) - 1:
        raise LocalizerError("not enough truth poses for every estimate")
    values = []
    for estimate in estimates:
        real = truth[estimate.step]
        error = np.array([real.x - estimate.x, real.y - estimate.y,
                          wrap_angle(real.theta - estimate.theta)])
        values.append(float(error @ np.linalg.solve(estimate.matrix, error)))
    return sum(values) / len(values)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def render_map(landmarks: dict[str, Landmark], simulation: Simulation,
               estimates=(), width: int = 41, height: int = 19) -> str:
    """ASCII map of the room with truth, odometry and estimates."""
    xs = [landmark.x for landmark in landmarks.values()]
    ys = [landmark.y for landmark in landmarks.values()]
    for pose in simulation.truth:
        xs.append(pose.x)
        ys.append(pose.y)
    for estimate in estimates:
        xs.append(estimate.x)
        ys.append(estimate.y)
    x_min, x_max = min(xs) - 0.5, max(xs) + 0.5
    y_min, y_max = min(ys) - 0.5, max(ys) + 0.5
    x_span = max(1e-6, x_max - x_min)
    y_span = max(1e-6, y_max - y_min)

    grid = [[" "] * width for _ in range(height)]

    def cell(x: float, y: float) -> tuple[int, int]:
        column = int((x - x_min) / x_span * (width - 1))
        row = int((y - y_min) / y_span * (height - 1))
        return max(0, min(height - 1, height - 1 - row)), \
            max(0, min(width - 1, column))

    for pose in simulation.odometry:
        row, column = cell(pose.x, pose.y)
        grid[row][column] = "."
    for pose in simulation.truth:
        row, column = cell(pose.x, pose.y)
        grid[row][column] = "#"
    for estimate in estimates:
        row, column = cell(estimate.x, estimate.y)
        grid[row][column] = "e"
    for landmark in landmarks.values():
        row, column = cell(landmark.x, landmark.y)
        grid[row][column] = "L"

    return "\n".join("".join(row) for row in grid)


def render_report(simulation: Simulation, estimates: tuple[Estimate, ...],
                  odometry_rmse: float, ekf_rmse: float) -> str:
    """Text summary of a localisation run."""
    accepted = sum(1 for estimate in estimates if estimate.accepted)
    rejected = sum(1 for estimate in estimates if estimate.accepted is False)
    last = estimates[-1]
    return "\n".join([
        f"LOCALISATION - {simulation.scenario}",
        "=" * 70,
        f"  steps           : {simulation.steps}",
        f"  measurements    : {len(simulation.measurements)}",
        f"  updates         : {accepted}",
        f"  rejected (gate) : {rejected}",
        f"  outlier steps   : {len(simulation.outlier_steps)}",
        f"  odometry RMSE   : {odometry_rmse:.4f} m",
        f"  EKF RMSE        : {ekf_rmse:.4f} m",
        f"  final sigma xy  : {last.sigma_xy:.4f} m",
        f"  final sigma th  : {last.sigma_theta * DEG:.3f} deg",
        f"  final error     : "
        f"{math.hypot(last.x - simulation.truth[-1].x, last.y - simulation.truth[-1].y):.4f} m",
    ])


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    """Run the bundled localisation demo - fully offline."""
    print("=" * 70)
    print(" KALMAN FILTER LOCALIZER - offline demo")
    print(" EKF fuses wheel odometry with landmark range/bearing sightings.")
    print("=" * 70)

    scenario = load_scenario()
    landmarks = load_landmarks()
    simulation = simulate(scenario, landmarks)
    estimates = run_ekf(scenario, simulation, landmarks)

    print(f"\nScenario : {scenario.name} - {scenario.total_steps} steps "
          f"at dt={scenario.dt} s ({scenario.duration:.1f} s)")
    print(f"Landmarks: {', '.join(sorted(landmarks))}")
    print(f"Noise    : odometry {scenario.odom_sigma}, "
          f"measurement {scenario.meas_sigma}")

    ekf_poses = tuple(estimate.pose for estimate in estimates)
    truth = simulation.truth
    odometry_rmse = rmse_position(simulation.odometry[1:], truth[1:])
    ekf_rmse = rmse_position(ekf_poses, truth[1:])

    print()
    print(render_report(simulation, estimates, odometry_rmse, ekf_rmse))

    header = (f"{'STEP':>6}{'t':>7}{'true x':>9}{'true y':>9}"
              f"{'est x':>9}{'est y':>9}{'err m':>9}"
              f"{'sig xy':>9}{'NIS':>8}  gate")
    print()
    print(header)
    print("-" * len(header))
    stride = max(1, len(estimates) // 8)
    for estimate in estimates[stride - 1::stride]:
        real = truth[estimate.step]
        error = math.hypot(estimate.x - real.x, estimate.y - real.y)
        nis = "-" if estimate.nis is None else f"{estimate.nis:.2f}"
        verdict = ("-" if estimate.accepted is None
                   else ("accept" if estimate.accepted else "REJECT"))
        print(f"{estimate.step:>6}{estimate.t:>7.2f}"
              f"{real.x:>9.3f}{real.y:>9.3f}{estimate.x:>9.3f}"
              f"{estimate.y:>9.3f}{error:>9.4f}{estimate.sigma_xy:>9.4f}"
              f"{nis:>8}  {verdict}")

    # --- cross-checks the demo asserts ------------------------------------- #
    # 1. the filter beats dead reckoning by a wide margin
    assert ekf_rmse < 0.5 * odometry_rmse, (
        f"EKF RMSE {ekf_rmse:.4f} not well below "
        f"odometry {odometry_rmse:.4f}")
    assert ekf_rmse < 0.15, "EKF RMSE is not below 1.5x the range noise"
    final_odom = math.hypot(
        simulation.odometry[-1].x - truth[-1].x,
        simulation.odometry[-1].y - truth[-1].y)
    final_ekf = math.hypot(ekf_poses[-1].x - truth[-1].x,
                           ekf_poses[-1].y - truth[-1].y)
    assert final_ekf < final_odom, "EKF final error is not smaller"

    # 2. every accepted innovation passes the gate
    for estimate in estimates:
        if estimate.accepted:
            assert estimate.nis is not None
            assert estimate.nis <= scenario.gate + 1e-9, (
                f"accepted NIS {estimate.nis:.3f} above gate")

    # 3. the gate rejects every injected outlier, without rejecting
    #    much of the honest data
    rejected_steps = {estimate.step for estimate in estimates
                      if estimate.accepted is False}
    for step in simulation.outlier_steps:
        assert step in rejected_steps, f"outlier at step {step} accepted"
    assert rejected_steps
    assert len(rejected_steps) <= 0.1 * len(simulation.measurements), (
        "the gate rejected too much honest data")

    # 4. the covariance stays positive definite, bounded, and the
    #    reported sigma is a sane bracket for the real error
    for estimate in estimates:
        assert np.linalg.eigvalsh(estimate.matrix).min() > 0.0, (
            "covariance lost positive definiteness")
        assert estimate.sigma_xy < 1.0, "position sigma is unbounded"
        assert estimate.sigma_theta * DEG < 20.0, "heading sigma is unbounded"
    errors = position_errors(ekf_poses, truth[1:])
    mean_sigma = sum(estimate.sigma_xy for estimate in estimates) / len(estimates)
    mean_error = sum(errors) / len(errors)
    assert mean_error < mean_sigma < 10.0 * mean_error, (
        f"sigma {mean_sigma:.4f} is not a sane bracket for the mean error "
        f"{mean_error:.4f}")

    # 5. the filter is statistically consistent (NEES near the 3-dof mean)
    nees_value = mean_nees(estimates, truth)
    assert 0.2 < nees_value < 12.0, f"NEES {nees_value:.2f} is inconsistent"

    # 6. the exact arc model agrees with RK4 integration of the ODE
    for v, w in ((0.3, 0.0), (0.3, 0.4), (0.2, -0.7)):
        arc = motion_model((1.0, 2.0, 0.3), v, w, 0.1)
        numeric = integrate_rk4((1.0, 2.0, 0.3), v, w, 0.1, substeps=400)
        assert np.allclose(arc[:2], numeric[:2], atol=1e-8), (
            "arc model disagrees with RK4 integration")

    # 7. both Jacobians match finite differences
    state = np.array([1.2, 0.7, 0.4])
    for v, w in ((0.25, 0.5), (0.3, 0.0)):
        analytic = motion_jacobian(state, v, w, 0.1)
        numeric = np.zeros((3, 3))
        for index in range(3):
            plus, minus = state.copy(), state.copy()
            plus[index] += 1e-7
            minus[index] -= 1e-7
            numeric[:, index] = (motion_model(plus, v, w, 0.1)
                                 - motion_model(minus, v, w, 0.1)) / 2e-7
        assert np.allclose(analytic, numeric, atol=1e-6), (
            "motion Jacobian mismatch")

    landmark = landmarks[sorted(landmarks)[0]]
    analytic = measurement_jacobian(state, landmark)
    numeric = np.zeros((2, 3))
    for index in range(3):
        plus, minus = state.copy(), state.copy()
        plus[index] += 1e-7
        minus[index] -= 1e-7
        numeric[:, index] = (measurement(plus, landmark)
                             - measurement(minus, landmark)) / 2e-7
    assert np.allclose(analytic, numeric, atol=1e-6), (
        "measurement Jacobian mismatch")

    # 8. a gross outlier is rejected by the gate in one shot
    probe = ExtendedKalmanFilter((simulation.truth[1].x,
                                  simulation.truth[1].y,
                                  simulation.truth[1].theta))
    expected = measurement(probe.state, landmark)
    nis = probe.update(landmark, expected[0] + 999.0, expected[1])
    assert nis > scenario.gate and probe.last_accepted is False

    # 9. the scalar filter matches the closed-form gain
    filt = KalmanFilter1D(state=0.0, variance=1.0)
    gain = filt.update(1.0, 1.0)
    assert filt.gain == 0.5 and gain == 0.5
    assert filt.variance == 0.5

    # 10. determinism: identical samples on a second run
    again = run_ekf(scenario, simulate(scenario, landmarks), landmarks)
    assert again[-1].covariance == estimates[-1].covariance
    assert again[-1].x == estimates[-1].x

    print()
    print(render_map(landmarks, simulation, estimates))
    print("\nMap legend: # truth, . odometry, e estimate, L landmark")
    print(f"\nOdometry drift: {final_odom:.3f} m   "
          f"EKF: {final_ekf:.3f} m   "
          f"ratio {final_odom / max(final_ekf, 1e-9):.1f}x")
    print(f"Mean NEES      : {mean_nees(estimates, truth):.3f}")
    print(f"Rejected steps : {sorted(rejected_steps)}")

    print("\nCross-checks OK: EKF beats odometry, accepted innovations pass "
          "the gate, injected outliers are rejected, the covariance stays "
          "positive definite and brackets the real error, mean NEES is "
          "consistent, the arc model matches RK4 integration, both "
          "Jacobians match finite differences, gross outliers are gated, "
          "the scalar filter matches the closed-form gain, deterministic "
          "re-run")
    print("\nDemo completed successfully.")
    return 0
