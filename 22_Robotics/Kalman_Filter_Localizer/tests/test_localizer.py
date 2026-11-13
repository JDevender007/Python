"""Tests for the Kalman Filter Localizer project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from localizer import (  # noqa: E402
    CHI2_2DOF_95,
    DEG,
    LANDMARK_FILE,
    SCENARIO_FILE,
    USE_SCENARIO_GATE,
    Estimate,
    ExtendedKalmanFilter,
    KalmanFilter1D,
    Landmark,
    LocalizerError,
    Measurement,
    Pose,
    Scenario,
    Segment,
    Simulation,
    dead_reckon,
    filter_scalar,
    heading_errors,
    integrate_rk4,
    load_landmarks,
    load_scenario,
    mean_nees,
    measurement,
    measurement_jacobian,
    motion_jacobian,
    motion_model,
    position_errors,
    render_map,
    render_report,
    rmse_position,
    run_demo,
    run_ekf,
    scenario_from_dict,
    simulate,
    wrap_angle,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TWO_PI = 2.0 * math.pi


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #
def _scenario_payload(**overrides) -> dict:
    payload = {
        "name": "test",
        "seed": 1,
        "dt": 0.1,
        "initial_state": [0.0, 0.0, 0.0],
        "segments": [{"v": 0.5, "w": 0.0, "steps": 4}],
        "odom_noise": {"distance": 0.01, "rotation": 0.01},
        "meas_noise": {"range": 0.05, "bearing": 0.02},
        "gate": 5.991,
        "range_limit": 6.0,
        "outlier_every": 0,
        "outlier_bias": 0.0,
    }
    payload.update(overrides)
    return payload


def _scenario(**overrides) -> Scenario:
    return scenario_from_dict(_scenario_payload(**overrides))


def _simulation(steps: int = 4, measurements=(), dt: float = 0.1,
                controls=None) -> Simulation:
    if controls is None:
        controls = tuple((0.5, 0.0) for _ in range(steps))
    truth = tuple(Pose(index * 0.05, 0.0, 0.0)
                  for index in range(len(controls) + 1))
    return Simulation(scenario="manual", dt=dt, truth=truth, odometry=truth,
                      controls=controls, measurements=tuple(measurements))


@pytest.fixture(scope="module")
def scenario():
    return load_scenario(SCENARIO_FILE)


@pytest.fixture(scope="module")
def landmarks():
    return load_landmarks(LANDMARK_FILE)


@pytest.fixture(scope="module")
def simulation(scenario, landmarks):
    return simulate(scenario, landmarks)


@pytest.fixture(scope="module")
def estimates(scenario, simulation, landmarks):
    return run_ekf(scenario, simulation, landmarks)


@pytest.fixture(scope="module")
def square():
    return Landmark("corner", 3.0, 4.0)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def test_wrap_angle_keeps_small_angles():
    assert wrap_angle(0.4) == pytest.approx(0.4)


def test_wrap_angle_wraps_both_ways():
    assert wrap_angle(math.pi + 0.5) == pytest.approx(-math.pi + 0.5)
    assert wrap_angle(-math.pi - 0.5) == pytest.approx(math.pi - 0.5)
    assert wrap_angle(TWO_PI) == pytest.approx(0.0, abs=1e-12)


def test_wrap_angle_stays_in_range_for_many_values():
    values = [(index - 40) * 0.7 for index in range(80)]
    assert all(-math.pi <= wrap_angle(value) < math.pi for value in values)


# --------------------------------------------------------------------------- #
# Motion model
# --------------------------------------------------------------------------- #
def test_motion_model_straight_line():
    result = motion_model((0.0, 0.0, 0.0), 1.0, 0.0, 1.0)
    assert result[0] == pytest.approx(1.0)
    assert result[1] == pytest.approx(0.0)
    assert result[2] == pytest.approx(0.0)


def test_motion_model_quarter_circle_is_exact():
    # v = 1, w = pi/2 -> radius 2/pi, a quarter turn
    result = motion_model((0.0, 0.0, 0.0), 1.0, math.pi / 2.0, 1.0)
    radius = 2.0 / math.pi
    assert result[0] == pytest.approx(radius)
    assert result[1] == pytest.approx(radius)
    assert result[2] == pytest.approx(math.pi / 2.0)


def test_motion_model_rotates_in_place():
    result = motion_model((1.0, 2.0, 0.0), 0.0, 1.0, 1.0)
    assert result[0] == pytest.approx(1.0)
    assert result[1] == pytest.approx(2.0)
    assert result[2] == pytest.approx(1.0)


def test_motion_model_wraps_heading():
    result = motion_model((0.0, 0.0, 3.0), 0.0, 1.0, 1.0)
    assert -math.pi <= result[2] < math.pi


def test_motion_model_rejects_bad_dt():
    with pytest.raises(LocalizerError, match="dt must be > 0"):
        motion_model((0.0, 0.0, 0.0), 1.0, 0.0, 0.0)


def test_motion_jacobian_straight_line():
    jacobian = motion_jacobian((0.0, 0.0, 0.0), 1.0, 0.0, 1.0)
    assert jacobian[0, 2] == pytest.approx(0.0)
    assert jacobian[1, 2] == pytest.approx(1.0)


def test_motion_jacobian_rejects_bad_dt():
    with pytest.raises(LocalizerError, match="dt must be > 0"):
        motion_jacobian((0.0, 0.0, 0.0), 1.0, 0.0, -1.0)


@pytest.mark.parametrize("v,w", [(0.3, 0.0), (0.3, 0.4), (0.2, -0.7)])
def test_motion_jacobian_matches_finite_differences(v, w):
    state = np.array([1.2, 0.7, 0.4])
    analytic = motion_jacobian(state, v, w, 0.1)
    numeric = np.zeros((3, 3))
    for index in range(3):
        plus, minus = state.copy(), state.copy()
        plus[index] += 1e-7
        minus[index] -= 1e-7
        numeric[:, index] = (motion_model(plus, v, w, 0.1)
                             - motion_model(minus, v, w, 0.1)) / 2e-7
    assert np.allclose(analytic, numeric, atol=1e-6)


@pytest.mark.parametrize("v,w", [(0.3, 0.0), (0.3, 0.4), (0.2, -0.7)])
def test_integrate_rk4_matches_the_closed_form_arc(v, w):
    arc = motion_model((1.0, 2.0, 0.3), v, w, 0.1)
    numeric = integrate_rk4((1.0, 2.0, 0.3), v, w, 0.1, substeps=400)
    assert np.allclose(arc, numeric, atol=1e-8)


def test_integrate_rk4_rejects_a_bad_state():
    with pytest.raises(LocalizerError, match="state must have 3 values"):
        integrate_rk4((1.0, 2.0), 0.1, 0.1, 0.1)


def test_integrate_rk4_rejects_bad_dt():
    with pytest.raises(LocalizerError, match="dt must be > 0"):
        integrate_rk4((0.0, 0.0, 0.0), 0.1, 0.1, 0.0)


def test_integrate_rk4_rejects_zero_substeps():
    with pytest.raises(LocalizerError, match="substeps must be an integer >= 1"):
        integrate_rk4((0.0, 0.0, 0.0), 0.1, 0.1, 0.1, substeps=0)


def test_integrate_rk4_rejects_boolean_substeps():
    with pytest.raises(LocalizerError, match="substeps must be an integer >= 1"):
        integrate_rk4((0.0, 0.0, 0.0), 0.1, 0.1, 0.1, substeps=True)


# --------------------------------------------------------------------------- #
# Measurement model
# --------------------------------------------------------------------------- #
def test_measurement_range_and_bearing(square):
    values = measurement(np.array([0.0, 0.0, 0.0]), square)
    assert values[0] == pytest.approx(5.0)
    assert values[1] == pytest.approx(math.atan2(4.0, 3.0))


def test_measurement_subtracts_the_heading(square):
    values = measurement(np.array([0.0, 0.0, math.pi / 2.0]), square)
    assert values[1] == pytest.approx(math.atan2(4.0, 3.0) - math.pi / 2.0)


def test_measurement_wraps_a_landmark_behind(square):
    values = measurement(np.array([0.0, 0.0, math.pi - 0.1]), square)
    assert -math.pi <= values[1] < math.pi


def test_measurement_rejects_a_coincident_landmark():
    with pytest.raises(LocalizerError, match="coincides with the robot"):
        measurement(np.array([3.0, 4.0, 0.0]), Landmark("here", 3.0, 4.0))


def test_measurement_jacobian_values(square):
    jacobian = measurement_jacobian(np.array([0.0, 0.0, 0.0]), square)
    assert jacobian[0, 0] == pytest.approx(-3.0 / 5.0)
    assert jacobian[0, 1] == pytest.approx(-4.0 / 5.0)
    assert jacobian[0, 2] == pytest.approx(0.0)
    assert jacobian[1, 0] == pytest.approx(4.0 / 25.0)
    assert jacobian[1, 1] == pytest.approx(-3.0 / 25.0)
    assert jacobian[1, 2] == pytest.approx(-1.0)


def test_measurement_jacobian_matches_finite_differences(square):
    state = np.array([1.1, 0.6, 0.35])
    analytic = measurement_jacobian(state, square)
    numeric = np.zeros((2, 3))
    for index in range(3):
        plus, minus = state.copy(), state.copy()
        plus[index] += 1e-7
        minus[index] -= 1e-7
        numeric[:, index] = (measurement(plus, square)
                             - measurement(minus, square)) / 2e-7
    assert np.allclose(analytic, numeric, atol=1e-6)


def test_measurement_jacobian_rejects_a_coincident_landmark():
    with pytest.raises(LocalizerError, match="coincides with the robot"):
        measurement_jacobian(np.array([1.0, 1.0, 0.0]),
                             Landmark("here", 1.0, 1.0))


# --------------------------------------------------------------------------- #
# Scalar Kalman filter
# --------------------------------------------------------------------------- #
def test_scalar_filter_update_matches_the_closed_form_gain():
    filt = KalmanFilter1D(state=0.0, variance=1.0)
    result = filt.update(1.0, 1.0)
    assert filt.gain == pytest.approx(0.5)
    assert result == pytest.approx(0.5)
    assert filt.variance == pytest.approx(0.5)
    assert filt.updates == 1


def test_scalar_filter_predict_grows_the_variance():
    filt = KalmanFilter1D(state=1.0, variance=1.0)
    assert filt.predict(delta=2.0, process_var=3.0) == pytest.approx(3.0)
    assert filt.variance == pytest.approx(4.0)


def test_scalar_filter_rejects_a_non_finite_delta():
    with pytest.raises(LocalizerError, match="delta must be finite"):
        KalmanFilter1D().predict(delta=float("nan"))


def test_scalar_filter_rejects_negative_variance():
    with pytest.raises(LocalizerError, match="variance must be >= 0"):
        KalmanFilter1D(variance=-1.0)


def test_scalar_filter_rejects_zero_measurement_variance():
    with pytest.raises(LocalizerError, match="meas_var must be > 0"):
        KalmanFilter1D().update(1.0, 0.0)


def test_filter_scalar_converges_on_a_constant_signal():
    trace = filter_scalar([5.0] * 6, 0.01, 1.0, initial=5.0)
    assert len(trace) == 6
    assert trace[-1][0] == pytest.approx(5.0)
    assert trace[-1][1] < trace[0][1]


def test_filter_scalar_starts_from_the_first_value():
    trace = filter_scalar([3.0], 0.0, 1.0)
    assert trace[0][0] == pytest.approx(3.0)


def test_filter_scalar_honours_an_explicit_initial():
    trace = filter_scalar([1.0], 0.0, 1.0, initial=0.0)
    assert trace[0][0] == pytest.approx(0.5)


def test_filter_scalar_rejects_an_empty_sequence():
    with pytest.raises(LocalizerError, match="at least one value"):
        filter_scalar([], 0.0, 1.0)


# --------------------------------------------------------------------------- #
# Extended Kalman filter
# --------------------------------------------------------------------------- #
def test_ekf_rejects_a_bad_state_size():
    with pytest.raises(LocalizerError, match="state must have 3 values"):
        ExtendedKalmanFilter([0.0, 0.0])


def test_ekf_rejects_a_non_finite_state():
    with pytest.raises(LocalizerError, match="state must be finite"):
        ExtendedKalmanFilter([0.0, 0.0, float("inf")])


def test_ekf_rejects_a_bad_covariance_shape():
    with pytest.raises(LocalizerError, match="covariance must be 3x3"):
        ExtendedKalmanFilter([0.0, 0.0, 0.0], covariance=np.eye(2))


def test_ekf_rejects_a_non_finite_covariance():
    with pytest.raises(LocalizerError, match="covariance must be finite"):
        ExtendedKalmanFilter([0.0, 0.0, 0.0],
                             covariance=np.full((3, 3), np.nan))


def test_ekf_rejects_a_negative_process_sigma():
    with pytest.raises(LocalizerError, match="process sigma must be >= 0"):
        ExtendedKalmanFilter([0.0, 0.0, 0.0],
                             process_sigmas=(0.1, -0.1, 0.1))


def test_ekf_rejects_a_bad_process_sigma_count():
    with pytest.raises(LocalizerError, match="process_sigmas needs 3 values"):
        ExtendedKalmanFilter([0.0, 0.0, 0.0], process_sigmas=(0.1, 0.1))


def test_ekf_wraps_the_initial_heading():
    filt = ExtendedKalmanFilter([0.0, 0.0, 4.0])
    assert -math.pi <= filt.state[2] < math.pi


def test_ekf_predict_advances_the_state():
    filt = ExtendedKalmanFilter([0.0, 0.0, 0.0])
    filt.predict(1.0, 0.0, 1.0)
    assert filt.state[0] == pytest.approx(1.0)
    assert filt.pose.x == pytest.approx(1.0)


def test_ekf_predict_grows_the_covariance():
    filt = ExtendedKalmanFilter([0.0, 0.0, 0.0],
                                covariance=np.zeros((3, 3)))
    filt.predict(1.0, 0.0, 1.0)
    assert filt.sigma_xy > 0.0
    assert filt.sigma_theta > 0.0


def test_ekf_update_reduces_the_position_variance(square):
    filt = ExtendedKalmanFilter([0.0, 0.0, 0.0])
    before = filt.covariance[0, 0]
    expected = measurement(filt.state, square)
    filt.update(square, expected[0], expected[1])
    assert filt.covariance[0, 0] < before
    assert filt.last_accepted is True
    assert filt.updates == 1


def test_ekf_update_rejects_a_gross_outlier(square):
    filt = ExtendedKalmanFilter([0.0, 0.0, 0.0])
    expected = measurement(filt.state, square)
    nis = filt.update(square, expected[0] + 500.0, expected[1])
    assert nis > CHI2_2DOF_95
    assert filt.last_accepted is False
    assert filt.rejections == 1
    assert filt.updates == 0


def test_ekf_update_accepts_everything_without_a_gate(square):
    filt = ExtendedKalmanFilter([0.0, 0.0, 0.0])
    filt.gate = None
    expected = measurement(filt.state, square)
    filt.update(square, expected[0] + 500.0, expected[1])
    assert filt.last_accepted is True


def test_ekf_update_rejects_a_non_positive_range(square):
    with pytest.raises(LocalizerError, match="measurement range must be > 0"):
        ExtendedKalmanFilter([0.0, 0.0, 0.0]).update(square, 0.0, 0.0)


def test_ekf_nees_is_small_when_the_estimate_is_good(square):
    filt = ExtendedKalmanFilter([0.0, 0.0, 0.0])
    assert filt.nees(Pose(0.0, 0.0, 0.0)) == pytest.approx(0.0)


def test_ekf_nees_grows_with_the_error():
    filt = ExtendedKalmanFilter([0.0, 0.0, 0.0])
    assert filt.nees(Pose(1.0, 0.0, 0.0)) > 1.0


def test_ekf_to_dict_shape():
    payload = ExtendedKalmanFilter([1.0, 2.0, 0.0]).to_dict()
    assert payload["state"] == [1.0, 2.0, 0.0]
    assert len(payload["covariance"]) == 3
    assert payload["updates"] == 0
    assert payload["rejections"] == 0


def test_pose_state_and_to_dict():
    pose = Pose(1.0, 2.0, math.pi / 2.0)
    assert pose.state == (1.0, 2.0, math.pi / 2.0)
    assert pose.to_dict()["theta_deg"] == pytest.approx(90.0)
    assert list(pose.position) == [1.0, 2.0]


def test_pose_to_dict_wraps_half_turns():
    assert Pose(0.0, 0.0, math.pi).to_dict()["theta_deg"] \
        == pytest.approx(-180.0)


# --------------------------------------------------------------------------- #
# Scenario validation
# --------------------------------------------------------------------------- #
def test_scenario_from_dict_valid():
    scenario = _scenario(name=" hall ")
    assert scenario.name == "hall"
    assert scenario.seed == 1
    assert scenario.dt == pytest.approx(0.1)
    assert scenario.initial == (0.0, 0.0, 0.0)
    assert len(scenario.segments) == 1


def test_scenario_defaults():
    payload = _scenario_payload()
    for key in ("gate", "range_limit", "outlier_every", "outlier_bias"):
        payload.pop(key)
    scenario = scenario_from_dict(payload)
    assert scenario.gate == pytest.approx(CHI2_2DOF_95)
    assert scenario.range_limit == pytest.approx(6.0)
    assert scenario.outlier_every == 0
    assert scenario.outlier_bias == 0.0


def test_scenario_total_steps_and_duration():
    scenario = _scenario(segments=[{"v": 0.1, "w": 0.0, "steps": 3},
                                   {"v": 0.2, "w": 0.1, "steps": 5}])
    assert scenario.total_steps == 8
    assert scenario.duration == pytest.approx(0.8)


def test_scenario_commands_flatten_the_segments():
    scenario = _scenario(segments=[{"v": 0.1, "w": 0.0, "steps": 2},
                                   {"v": 0.2, "w": 0.5, "steps": 1}])
    assert scenario.commands() == ((0.1, 0.0), (0.1, 0.0), (0.2, 0.5))


def test_scenario_rejects_a_non_object():
    with pytest.raises(LocalizerError, match="must be a JSON object"):
        scenario_from_dict([])


def test_scenario_rejects_a_blank_name():
    with pytest.raises(LocalizerError, match="name must be a non-empty string"):
        _scenario(name="   ")


def test_scenario_rejects_a_negative_seed():
    with pytest.raises(LocalizerError, match="seed must be an integer >= 0"):
        _scenario(seed=-1)


def test_scenario_rejects_a_boolean_seed():
    with pytest.raises(LocalizerError, match="seed must be an integer >= 0"):
        _scenario(seed=True)


def test_scenario_rejects_a_bad_dt():
    with pytest.raises(LocalizerError, match="dt must be > 0"):
        _scenario(dt=0.0)


def test_scenario_rejects_a_short_initial_state():
    with pytest.raises(LocalizerError, match="initial_state must be"):
        _scenario(initial_state=[0.0, 0.0])


def test_scenario_rejects_a_non_finite_initial_value():
    with pytest.raises(LocalizerError, match="initial_state 1 must be finite"):
        _scenario(initial_state=[0.0, float("inf"), 0.0])


def test_scenario_rejects_an_empty_segment_list():
    with pytest.raises(LocalizerError, match="non-empty segment list"):
        _scenario(segments=[])


def test_scenario_rejects_a_non_object_segment():
    with pytest.raises(LocalizerError, match="segment 0 must be an object"):
        _scenario(segments=[3])


def test_scenario_rejects_a_non_numeric_velocity():
    with pytest.raises(LocalizerError, match="segment 0 v must be numeric"):
        _scenario(segments=[{"v": "fast", "w": 0.0, "steps": 1}])


def test_scenario_rejects_zero_steps():
    with pytest.raises(LocalizerError, match="steps must be an integer >= 1"):
        _scenario(segments=[{"v": 0.1, "w": 0.0, "steps": 0}])


def test_scenario_rejects_boolean_steps():
    with pytest.raises(LocalizerError, match="steps must be an integer >= 1"):
        _scenario(segments=[{"v": 0.1, "w": 0.0, "steps": True}])


def test_scenario_rejects_a_non_object_odom_noise():
    with pytest.raises(LocalizerError, match="odom_noise must be an object"):
        _scenario(odom_noise=0.1)


def test_scenario_rejects_a_negative_odom_noise():
    with pytest.raises(LocalizerError,
                       match="odom distance noise must be >= 0"):
        _scenario(odom_noise={"distance": -0.1})


def test_scenario_rejects_a_non_object_meas_noise():
    with pytest.raises(LocalizerError, match="meas_noise must be an object"):
        _scenario(meas_noise=[])


def test_scenario_rejects_a_negative_bearing_noise():
    with pytest.raises(LocalizerError, match="bearing noise must be >= 0"):
        _scenario(meas_noise={"range": 0.1, "bearing": -0.1})


def test_scenario_rejects_a_non_positive_gate():
    with pytest.raises(LocalizerError, match="gate must be > 0"):
        _scenario(gate=0.0)


def test_scenario_rejects_a_negative_outlier_period():
    with pytest.raises(LocalizerError,
                       match="outlier_every must be an integer >= 0"):
        _scenario(outlier_every=-5)


def test_scenario_rejects_a_negative_outlier_bias():
    with pytest.raises(LocalizerError, match="outlier_bias must be >= 0"):
        _scenario(outlier_bias=-1.0)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_load_scenario_bundled(scenario):
    assert scenario.name == "room_survey"
    assert scenario.seed == 3
    assert scenario.total_steps == 200
    assert len(scenario.segments) == 6


def test_load_scenario_missing_file(tmp_path):
    with pytest.raises(LocalizerError, match="scenario file not found"):
        load_scenario(tmp_path / "ghost.json")


def test_load_scenario_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(LocalizerError, match="could not parse"):
        load_scenario(path)


def test_load_landmarks_bundled(landmarks):
    assert sorted(landmarks) == ["centre", "ne", "nw", "se", "sw"]
    assert landmarks["nw"].x == pytest.approx(1.0)
    assert landmarks["se"].y == pytest.approx(9.0)


def test_load_landmarks_missing_file(tmp_path):
    with pytest.raises(LocalizerError, match="landmark file not found"):
        load_landmarks(tmp_path / "ghost.csv")


def test_load_landmarks_rejects_an_empty_file(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("id,x,y\n", encoding="utf-8")
    with pytest.raises(LocalizerError, match="has no landmark rows"):
        load_landmarks(path)


def test_load_landmarks_rejects_a_missing_id_column(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("name,x,y\na,1,2\n", encoding="utf-8")
    with pytest.raises(LocalizerError, match="missing column 'id'"):
        load_landmarks(path)


def test_load_landmarks_rejects_a_missing_coordinate(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,x\na,1\n", encoding="utf-8")
    with pytest.raises(LocalizerError, match="missing column 'y'"):
        load_landmarks(path)


def test_load_landmarks_rejects_a_blank_id(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,x,y\n,1,2\n", encoding="utf-8")
    with pytest.raises(LocalizerError, match="blank id"):
        load_landmarks(path)


def test_load_landmarks_rejects_a_duplicate_id(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,x,y\na,1,2\na,3,4\n", encoding="utf-8")
    with pytest.raises(LocalizerError, match="duplicate landmark id"):
        load_landmarks(path)


def test_load_landmarks_rejects_a_bad_coordinate(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("id,x,y\na,left,2\n", encoding="utf-8")
    with pytest.raises(LocalizerError, match="landmark 'a' x must be numeric"):
        load_landmarks(path)


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #
def test_simulate_rejects_an_empty_landmark_set(scenario):
    with pytest.raises(LocalizerError, match="no landmarks available"):
        simulate(scenario, {})


def test_simulate_lengths(scenario, simulation):
    assert len(simulation.truth) == scenario.total_steps + 1
    assert len(simulation.odometry) == scenario.total_steps + 1
    assert len(simulation.controls) == scenario.total_steps
    assert simulation.steps == scenario.total_steps


def test_simulate_is_deterministic(scenario, landmarks, simulation):
    again = simulate(scenario, landmarks)
    assert again.truth == simulation.truth
    assert again.odometry == simulation.odometry
    assert again.controls == simulation.controls
    assert again.measurements == simulation.measurements


def test_simulate_marks_the_injected_outliers(scenario, simulation):
    assert simulation.outlier_steps
    flagged = {entry.step for entry in simulation.measurements
               if entry.outlier}
    assert flagged == set(simulation.outlier_steps)


def test_simulate_only_sights_known_landmarks(scenario, landmarks,
                                             simulation):
    for entry in simulation.measurements:
        assert entry.landmark in landmarks


def test_simulate_measurement_times_follow_the_steps(scenario, simulation):
    for entry in simulation.measurements:
        assert entry.t == pytest.approx(entry.step * scenario.dt)


def test_simulate_bearings_are_wrapped(scenario, simulation):
    for entry in simulation.measurements:
        assert -math.pi <= entry.bearing < math.pi


def test_simulate_odometry_diverges_from_the_truth(scenario, simulation):
    error = position_errors(simulation.odometry[1:], simulation.truth[1:])
    assert max(error) > 0.01


def test_simulate_respects_zero_noise():
    scenario = _scenario(odom_noise={"distance": 0.0, "rotation": 0.0},
                         meas_noise={"range": 0.0, "bearing": 0.0},
                         outlier_every=0)
    landmarks = {"far": Landmark("far", 5.0, 5.0)}
    simulation = simulate(scenario, landmarks)
    assert simulation.odometry == simulation.truth


def test_simulation_steps_property():
    assert _simulation(steps=3).steps == 3


def test_dead_reckon_drives_straight():
    poses = dead_reckon([(0.5, 0.0)] * 10, 0.1)
    assert len(poses) == 11
    assert poses[-1].x == pytest.approx(0.5)
    assert poses[-1].y == pytest.approx(0.0)


def test_dead_reckon_honours_the_initial_pose():
    poses = dead_reckon([], 0.1, initial=(1.0, 2.0, 0.0))
    assert poses[0] == Pose(1.0, 2.0, 0.0)


# --------------------------------------------------------------------------- #
# run_ekf
# --------------------------------------------------------------------------- #
def test_run_ekf_returns_one_estimate_per_step(scenario, estimates):
    assert len(estimates) == scenario.total_steps
    assert [estimate.step for estimate in estimates] == \
        list(range(1, scenario.total_steps + 1))


def test_run_ekf_is_deterministic(scenario, landmarks, estimates):
    again = run_ekf(scenario, simulate(scenario, landmarks), landmarks)
    assert again[-1].x == estimates[-1].x
    assert again[-1].covariance == estimates[-1].covariance


def test_run_ekf_rejects_a_step_count_mismatch():
    scenario = _scenario(segments=[{"v": 0.1, "w": 0.0, "steps": 2}])
    simulation = _simulation(controls=((0.0, 0.0),))
    with pytest.raises(LocalizerError, match="scenario expects 2"):
        run_ekf(scenario, simulation, {"a": Landmark("a", 5.0, 5.0)})


def test_run_ekf_rejects_an_unknown_landmark():
    scenario = _scenario(segments=[{"v": 0.0, "w": 0.0, "steps": 1}])
    entry = Measurement(step=1, t=0.1, landmark="ghost", range=3.0,
                        bearing=0.0)
    simulation = _simulation(controls=((0.0, 0.0),), measurements=[entry])
    with pytest.raises(LocalizerError, match="unknown landmark"):
        run_ekf(scenario, simulation, {"a": Landmark("a", 5.0, 5.0)})


def test_run_ekf_no_gate_accepts_every_measurement(scenario, simulation,
                                                   landmarks):
    unguarded = run_ekf(scenario, simulation, landmarks, gate=None)
    assert all(estimate.accepted is not False for estimate in unguarded)
    rejected = sum(1 for estimate in unguarded
                   if estimate.accepted is False)
    assert rejected == 0


def test_run_ekf_loose_gate_rejects_nothing(scenario, simulation,
                                            landmarks):
    loose = run_ekf(scenario, simulation, landmarks, gate=1e9)
    assert all(estimate.accepted for estimate in loose)


def test_run_ekf_tight_gate_rejects_more(scenario, simulation, landmarks,
                                         estimates):
    tight = run_ekf(scenario, simulation, landmarks, gate=0.5)
    narrow = sum(1 for estimate in tight if estimate.accepted is False)
    wide = sum(1 for estimate in estimates if estimate.accepted is False)
    assert narrow >= wide


def test_run_ekf_rejects_a_non_positive_gate(scenario, simulation, landmarks):
    with pytest.raises(LocalizerError, match="gate must be > 0"):
        run_ekf(scenario, simulation, landmarks, gate=-1.0)


def test_run_ekf_honours_the_scenario_gate_by_default(scenario, simulation,
                                                     landmarks):
    assert run_ekf.__defaults__ is not None
    default = run_ekf(scenario, simulation, landmarks,
                      gate=USE_SCENARIO_GATE)
    assert [estimate.x for estimate in default] == \
        [estimate.x for estimate in
         run_ekf(scenario, simulate(scenario, landmarks), landmarks)]


def test_run_ekf_accepts_a_custom_initial_covariance(scenario, simulation,
                                                     landmarks):
    wide = run_ekf(scenario, simulation, landmarks,
                   initial_covariance=np.diag([4.0, 4.0, 1.0]))
    narrow = run_ekf(scenario, simulation, landmarks,
                     initial_covariance=np.diag([0.001, 0.001, 0.001]))
    assert wide[0].sigma_xy > narrow[0].sigma_xy


def test_estimate_to_dict_shape(estimates):
    payload = estimates[0].to_dict()
    assert set(payload) == {"step", "t", "x", "y", "theta_deg", "sigma_xy",
                            "sigma_theta_deg", "nis", "accepted"}
    assert payload["step"] == 1


def test_estimate_pose_and_sigmas(estimates):
    estimate = estimates[-1]
    assert estimate.pose.x == estimate.x
    assert estimate.sigma_xy > 0.0
    assert estimate.sigma_theta > 0.0
    assert estimate.matrix.shape == (3, 3)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def test_position_errors_is_zero_for_identical_poses():
    poses = (Pose(1.0, 2.0, 0.0), Pose(3.0, 4.0, 0.0))
    assert position_errors(poses, poses) == (0.0, 0.0)


def test_position_errors_computes_distances():
    assert position_errors((Pose(3.0, 4.0, 0.0),), (Pose(0.0, 0.0, 0.0),)) \
        == pytest.approx((5.0,))


def test_position_errors_rejects_a_length_mismatch():
    with pytest.raises(LocalizerError, match="cannot compare"):
        position_errors((Pose(0.0, 0.0, 0.0),), ())


def test_rmse_position_averages_the_squares():
    poses = (Pose(3.0, 0.0, 0.0), Pose(0.0, 4.0, 0.0))
    truth = (Pose(0.0, 0.0, 0.0), Pose(0.0, 0.0, 0.0))
    assert rmse_position(poses, truth) == pytest.approx(math.sqrt(12.5))


def test_heading_errors_are_in_degrees():
    assert heading_errors((Pose(0.0, 0.0, math.pi / 2.0),),
                          (Pose(0.0, 0.0, 0.0),)) == pytest.approx((90.0,))


def test_heading_errors_wrap_across_pi():
    assert heading_errors((Pose(0.0, 0.0, -math.pi + 0.01),),
                          (Pose(0.0, 0.0, math.pi - 0.01),)) \
        == pytest.approx((0.02 * DEG,))


def test_heading_errors_rejects_a_length_mismatch():
    with pytest.raises(LocalizerError, match="cannot compare"):
        heading_errors((Pose(0.0, 0.0, 0.0),), ())


def test_mean_nees_on_a_perfect_estimate():
    estimate = Estimate(step=1, t=0.1, x=0.0, y=0.0, theta=0.0,
                        covariance=tuple(np.eye(3).ravel()))
    truth = [Pose(9.0, 9.0, 0.0), Pose(0.0, 0.0, 0.0)]
    assert mean_nees([estimate], truth) == pytest.approx(0.0)


def test_mean_nees_grows_with_the_error():
    estimate = Estimate(step=1, t=0.1, x=0.0, y=0.0, theta=0.0,
                        covariance=tuple(np.eye(3).ravel()))
    truth = [Pose(9.0, 9.0, 0.0), Pose(2.0, 0.0, 0.0)]
    assert mean_nees([estimate], truth) == pytest.approx(4.0)


def test_mean_nees_rejects_an_empty_list():
    with pytest.raises(LocalizerError, match="at least one estimate"):
        mean_nees([], [Pose(0.0, 0.0, 0.0)])


def test_mean_nees_rejects_too_few_truth_poses():
    estimate = Estimate(step=5, t=0.5, x=0.0, y=0.0, theta=0.0,
                        covariance=np.eye(3).ravel())
    with pytest.raises(LocalizerError, match="not enough truth poses"):
        mean_nees([estimate], [Pose(0.0, 0.0, 0.0)])


def test_mean_nees_is_finite_on_the_bundled_run(estimates, simulation):
    value = mean_nees(estimates, simulation.truth)
    assert 0.0 < value < 15.0


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def test_render_report_contains_the_totals(simulation, estimates):
    text = render_report(simulation, estimates, 0.2, 0.05)
    for needle in ("LOCALISATION", "steps", "measurements", "updates",
                   "rejected (gate)", "odometry RMSE", "EKF RMSE",
                   "final sigma xy"):
        assert needle in text


def test_render_map_shape(landmarks, simulation):
    text = render_map(landmarks, simulation, (), width=31, height=11)
    lines = text.splitlines()
    assert len(lines) == 11
    assert all(len(line) == 31 for line in lines)


def test_render_map_marks_landmarks_and_truth(landmarks, simulation):
    text = render_map(landmarks, simulation)
    assert "L" in text
    assert "#" in text


def test_render_map_marks_estimates_only_when_given(landmarks, simulation,
                                                    estimates):
    assert "e" not in render_map(landmarks, simulation, ())
    assert "e" in render_map(landmarks, simulation, estimates)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    assert capsys.readouterr().out == first


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_demo_rejects_a_gate_flag():
    with pytest.raises(SystemExit) as exc:
        main(["--demo", "--gate", "3"])
    assert exc.value.code == 2


def test_cli_default_run(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "LOCALISATION - room_survey" in out
    assert "Done." in out


def test_cli_quiet_default_run(capsys):
    assert main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_no_gate(capsys):
    assert main(["--no-gate"]) == 0
    out = capsys.readouterr().out
    assert "rejected (gate) : 0" in out


def test_cli_tight_gate(capsys):
    assert main(["--gate", "0.5"]) == 0
    assert "rejected (gate)" in capsys.readouterr().out


def test_cli_rejects_a_non_positive_gate(capsys):
    assert main(["--gate", "0"]) == 2
    assert "gate must be > 0" in capsys.readouterr().err


def test_cli_rejects_a_non_finite_gate(capsys):
    assert main(["--gate", "nan"]) == 2
    assert "gate must be > 0" in capsys.readouterr().err


def test_cli_rejects_gate_and_no_gate_together():
    with pytest.raises(SystemExit) as exc:
        main(["--gate", "5", "--no-gate"])
    assert exc.value.code == 2


def test_cli_writes_json(tmp_path):
    out = tmp_path / "run.json"
    assert main(["--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["scenario"] == "room_survey"
    assert payload["steps"] == 200
    assert len(payload["estimates"]) == 200
    assert payload["ekf_rmse"] < payload["odometry_rmse"]
    assert set(payload["estimates"][0]) == {
        "step", "t", "x", "y", "theta_deg", "sigma_xy",
        "sigma_theta_deg", "nis", "accepted"}


def test_cli_json_records_the_rejected_steps(tmp_path):
    out = tmp_path / "run.json"
    assert main(["--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["rejected_steps"]
    assert payload["outlier_steps"]
    assert all(step in payload["rejected_steps"]
               for step in payload["outlier_steps"])


def test_cli_json_without_a_gate_has_no_rejections(tmp_path):
    out = tmp_path / "run.json"
    assert main(["--no-gate", "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["rejected_steps"] == []


def test_cli_map(capsys):
    assert main(["--map"]) == 0
    assert "Map legend" in capsys.readouterr().out


def test_cli_missing_scenario(tmp_path, capsys):
    assert main(["--scenario", str(tmp_path / "ghost.json")]) == 2
    assert "scenario file not found" in capsys.readouterr().err


def test_cli_missing_landmarks(tmp_path, capsys):
    assert main(["--landmarks", str(tmp_path / "ghost.csv")]) == 2
    assert "landmark file not found" in capsys.readouterr().err


def test_cli_reports_a_bad_scenario_file(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{oops", encoding="utf-8")
    assert main(["--scenario", str(path)]) == 2
    assert "could not parse" in capsys.readouterr().err


def test_bundled_files_exist():
    assert SCENARIO_FILE.is_file()
    assert LANDMARK_FILE.is_file()


def test_segment_dataclass_fields():
    segment = Segment(v=0.2, w=0.1, steps=7)
    assert (segment.v, segment.w, segment.steps) == (0.2, 0.1, 7)


def test_measurement_to_dict_shape():
    payload = Measurement(step=2, t=0.2, landmark="a", range=3.0,
                          bearing=0.5, outlier=True).to_dict()
    assert payload["landmark"] == "a"
    assert payload["outlier"] is True
    assert payload["bearing_deg"] == pytest.approx(0.5 * DEG, abs=1e-3)
