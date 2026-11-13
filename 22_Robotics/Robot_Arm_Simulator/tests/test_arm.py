"""Tests for the Robot Arm Simulator project."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arm import (  # noqa: E402
    ARM_FILE,
    MISSION_FILE,
    PEAK_FACTOR,
    ArmError,
    ArmSpec,
    Collision,
    JointSpec,
    Mission,
    MissionResult,
    Obstacle,
    Pose,
    Sample,
    Segment,
    Trajectory,
    Waypoint,
    arm_from_dict,
    check_collisions,
    check_joints,
    joint_from_dict,
    link_points,
    load_arm,
    load_mission,
    minjerk,
    minjerk_derivative,
    mission_from_dict,
    parse_pose,
    plan_cartesian_move,
    plan_joint_move,
    point_segment_distance,
    pose,
    render_report,
    run_demo,
    run_mission,
    solve_ik,
    time_parameterize,
    wrap_deg,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #
def _joint(index: int, **overrides) -> dict:
    payload = {"name": f"j{index}", "low": -180.0, "high": 180.0,
               "max_speed": 120.0}
    payload.update(overrides)
    return payload


def _arm_payload(**overrides) -> dict:
    payload = {"links": [0.6, 0.5],
               "joints": [_joint(0), _joint(1)]}
    payload.update(overrides)
    return payload


def _mission_payload(**overrides) -> dict:
    payload = {"name": "test", "home": [0.5, 0.4, 90.0],
               "waypoints": [{"name": "a", "x": 0.6, "y": 0.3,
                              "yaw": 45.0}],
               "dwell": 0.1, "steps": 10}
    payload.update(overrides)
    return payload


@pytest.fixture(scope="module")
def arm():
    return load_arm(ARM_FILE)


@pytest.fixture(scope="module")
def mission(arm):
    return load_mission(MISSION_FILE, arm=arm)


@pytest.fixture(scope="module")
def planar2():
    return arm_from_dict("planar2", _arm_payload())


@pytest.fixture(scope="module")
def result(arm, mission):
    return run_mission(arm, mission)


# --------------------------------------------------------------------------- #
# Scalar helpers
# --------------------------------------------------------------------------- #
def test_wrap_deg_keeps_small_angles():
    assert wrap_deg(37.5) == pytest.approx(37.5)


def test_wrap_deg_wraps_positive_and_negative():
    assert wrap_deg(190.0) == pytest.approx(-170.0)
    assert wrap_deg(-190.0) == pytest.approx(170.0)
    assert wrap_deg(540.0) == pytest.approx(-180.0)


def test_minjerk_endpoints_and_midpoint():
    assert minjerk(0.0) == 0.0
    assert minjerk(1.0) == 1.0
    assert minjerk(0.5) == pytest.approx(0.5)


def test_minjerk_is_monotonic():
    values = [minjerk(index / 100.0) for index in range(101)]
    assert all(b >= a for a, b in zip(values, values[1:]))


def test_minjerk_derivative_is_zero_at_the_ends():
    assert minjerk_derivative(0.0) == 0.0
    assert minjerk_derivative(1.0) == 0.0


def test_minjerk_derivative_peaks_at_the_midpoint():
    assert minjerk_derivative(0.5) == pytest.approx(PEAK_FACTOR)


# --------------------------------------------------------------------------- #
# Joint validation
# --------------------------------------------------------------------------- #
def test_joint_from_dict_valid():
    joint = joint_from_dict(2, _joint(2, name="wrist"))
    assert joint.name == "wrist"
    assert (joint.low, joint.high, joint.max_speed) == (-180.0, 180.0, 120.0)


def test_joint_from_dict_rejects_non_object():
    with pytest.raises(ArmError, match="joint 1 must be an object"):
        joint_from_dict(1, [1, 2])


def test_joint_from_dict_rejects_blank_name():
    with pytest.raises(ArmError, match="name must be a non-empty string"):
        joint_from_dict(0, _joint(0, name="  "))


def test_joint_from_dict_rejects_missing_low():
    payload = _joint(0)
    payload.pop("low")
    with pytest.raises(ArmError, match="joint 0 low must be numeric"):
        joint_from_dict(0, payload)


def test_joint_from_dict_rejects_infinite_high():
    with pytest.raises(ArmError, match="joint 0 high must be finite"):
        joint_from_dict(0, _joint(0, high=float("nan")))


def test_joint_from_dict_rejects_inverted_limits():
    with pytest.raises(ArmError, match="low must be <= high"):
        joint_from_dict(0, _joint(0, low=10.0, high=-10.0))


def test_joint_from_dict_rejects_non_positive_speed():
    with pytest.raises(ArmError, match="max_speed must be > 0"):
        joint_from_dict(0, _joint(0, max_speed=0.0))


# --------------------------------------------------------------------------- #
# Arm validation
# --------------------------------------------------------------------------- #
def test_arm_from_dict_valid():
    arm = arm_from_dict("two", _arm_payload())
    assert arm.name == "two"
    assert arm.n_joints == 2
    assert arm.links == (0.6, 0.5)


def test_arm_from_dict_accepts_three_links():
    payload = _arm_payload(links=[0.6, 0.5, 0.0],
                           joints=[_joint(0), _joint(1), _joint(2)])
    assert arm_from_dict("three", payload).n_joints == 3


def test_arm_from_dict_rejects_non_object():
    with pytest.raises(ArmError, match="must be an object"):
        arm_from_dict("bad", "text")


def test_arm_from_dict_rejects_link_count():
    with pytest.raises(ArmError, match="link list of 2 or 3"):
        arm_from_dict("bad", _arm_payload(links=[1.0]))


def test_arm_from_dict_rejects_non_numeric_link():
    with pytest.raises(ArmError, match="bend' link 1 must be numeric"):
        arm_from_dict("bend", _arm_payload(links=[1.0, "long"]))


def test_arm_from_dict_rejects_negative_link():
    with pytest.raises(ArmError, match="links must be >= 0"):
        arm_from_dict("bad", _arm_payload(links=[1.0, -0.2]))


def test_arm_from_dict_rejects_zero_position_link():
    with pytest.raises(ArmError, match="position links must be > 0"):
        arm_from_dict("bad", _arm_payload(links=[0.0, 0.5]))


def test_arm_from_dict_rejects_joint_count():
    with pytest.raises(ArmError, match="needs 2 joint definition"):
        arm_from_dict("bad", _arm_payload(joints=[_joint(0)]))


def test_arm_from_dict_rejects_non_list_joints():
    with pytest.raises(ArmError, match="needs 2 joint definition"):
        arm_from_dict("bad", _arm_payload(joints="j0"))


def test_arm_from_dict_rejects_non_string_description():
    with pytest.raises(ArmError, match="description must be a string"):
        arm_from_dict("bad", _arm_payload(description=7))


def test_arm_spec_reach_properties(arm):
    assert arm.outer_reach == pytest.approx(1.1)
    assert arm.inner_reach == pytest.approx(0.1)


def test_arm_spec_inner_reach_floors_at_zero():
    arm = arm_from_dict("equal", _arm_payload(links=[0.5, 0.5]))
    assert arm.inner_reach == 0.0


def test_arm_spec_inner_reach_has_a_hole():
    arm = arm_from_dict("long", _arm_payload(links=[1.0, 0.3]))
    assert arm.inner_reach == pytest.approx(0.7)


def test_arm_spec_limit_pairs(arm):
    assert arm.limit_pairs()[0] == (-180.0, 180.0)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_load_arm_bundled(arm):
    assert arm.name == "bench3"
    assert arm.n_joints == 3
    assert [joint.name for joint in arm.joints] == ["shoulder", "elbow",
                                                    "wrist"]


def test_load_arm_missing_file(tmp_path):
    with pytest.raises(ArmError, match="arm file not found"):
        load_arm(tmp_path / "ghost.json")


def test_load_arm_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(ArmError, match="could not parse"):
        load_arm(path)


def test_load_arm_requires_object(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ArmError, match="must be a JSON object"):
        load_arm(path)


def test_load_arm_uses_the_stem_without_a_name(tmp_path):
    path = tmp_path / "nameless.json"
    path.write_text(json.dumps(_arm_payload()), encoding="utf-8")
    assert load_arm(path).name == "nameless"


def test_load_arm_honours_an_explicit_name(tmp_path):
    path = tmp_path / "x.json"
    path.write_text(json.dumps(_arm_payload(name="custom")), encoding="utf-8")
    assert load_arm(path).name == "custom"


# --------------------------------------------------------------------------- #
# Pose parsing
# --------------------------------------------------------------------------- #
def test_parse_pose_two_values():
    assert parse_pose("0.5, 0.3") == (0.5, 0.3)


def test_parse_pose_three_values():
    assert parse_pose("0.5,0.3,45") == (0.5, 0.3, 45.0)


def test_parse_pose_rejects_one_value():
    with pytest.raises(ArmError, match="pose must be"):
        parse_pose("0.5")


def test_parse_pose_rejects_text():
    with pytest.raises(ArmError, match="pose component 1 must be numeric"):
        parse_pose("0.5,up")


def test_parse_pose_rejects_infinite():
    with pytest.raises(ArmError, match="pose component 0 must be finite"):
        parse_pose("inf,0")


# --------------------------------------------------------------------------- #
# Mission validation
# --------------------------------------------------------------------------- #
def test_mission_from_dict_valid(arm):
    mission = mission_from_dict(_mission_payload(), arm)
    assert mission.name == "test"
    assert mission.home == (0.5, 0.4, 90.0)
    assert len(mission.waypoints) == 1
    assert mission.waypoints[0].yaw == 45.0


def test_mission_from_dict_defaults(arm):
    payload = _mission_payload()
    payload.pop("dwell")
    payload.pop("steps")
    mission = mission_from_dict(payload, arm)
    assert mission.dwell == 0.0
    assert mission.steps == 40
    assert mission.obstacles == ()


def test_mission_from_dict_home_without_yaw(arm):
    mission = mission_from_dict(_mission_payload(home=[0.5, 0.4]), arm)
    assert mission.home == (0.5, 0.4, None)


def test_mission_from_dict_rejects_non_object(arm):
    with pytest.raises(ArmError, match="mission must be a JSON object"):
        mission_from_dict([], arm)


def test_mission_from_dict_rejects_arm_mismatch(arm):
    with pytest.raises(ArmError, match="mission targets arm"):
        mission_from_dict(_mission_payload(arm="other"), arm)


def test_mission_from_dict_rejects_blank_name(arm):
    with pytest.raises(ArmError, match="mission name must be"):
        mission_from_dict(_mission_payload(name=" "), arm)


def test_mission_from_dict_rejects_bad_home(arm):
    with pytest.raises(ArmError, match="home must be"):
        mission_from_dict(_mission_payload(home=[0.5]), arm)


def test_mission_from_dict_rejects_negative_dwell(arm):
    with pytest.raises(ArmError, match="dwell must be >= 0"):
        mission_from_dict(_mission_payload(dwell=-1.0), arm)


def test_mission_from_dict_rejects_boolean_steps(arm):
    with pytest.raises(ArmError, match="steps must be an integer >= 2"):
        mission_from_dict(_mission_payload(steps=True), arm)


def test_mission_from_dict_rejects_small_steps(arm):
    with pytest.raises(ArmError, match="steps must be an integer >= 2"):
        mission_from_dict(_mission_payload(steps=1), arm)


def test_mission_from_dict_rejects_empty_waypoints(arm):
    with pytest.raises(ArmError, match="non-empty waypoint list"):
        mission_from_dict(_mission_payload(waypoints=[]), arm)


def test_mission_from_dict_rejects_non_object_waypoint(arm):
    with pytest.raises(ArmError, match="waypoint 0 must be an object"):
        mission_from_dict(_mission_payload(waypoints=[3]), arm)


def test_mission_from_dict_rejects_blank_waypoint_name(arm):
    with pytest.raises(ArmError, match="waypoint 0 name must be"):
        mission_from_dict(
            _mission_payload(waypoints=[{"name": " ", "x": 0.5, "y": 0.3}]),
            arm)


def test_mission_from_dict_rejects_duplicate_waypoints(arm):
    waypoint = {"name": "a", "x": 0.5, "y": 0.3}
    with pytest.raises(ArmError, match="duplicate waypoint name"):
        mission_from_dict(
            _mission_payload(waypoints=[waypoint, dict(waypoint)]), arm)


def test_mission_from_dict_rejects_bad_waypoint_coordinate(arm):
    with pytest.raises(ArmError, match="waypoint 'a' x must be numeric"):
        mission_from_dict(
            _mission_payload(waypoints=[{"name": "a", "x": "left",
                                         "y": 0.3}]), arm)


def test_mission_from_dict_accepts_null_yaw(arm):
    mission = mission_from_dict(
        _mission_payload(waypoints=[{"name": "a", "x": 0.5, "y": 0.3,
                                     "yaw": None}]), arm)
    assert mission.waypoints[0].yaw is None


def test_mission_from_dict_rejects_obstacle_list_type(arm):
    with pytest.raises(ArmError, match="obstacles must be a list"):
        mission_from_dict(_mission_payload(obstacles="wall"), arm)


def test_mission_from_dict_rejects_non_object_obstacle(arm):
    with pytest.raises(ArmError, match="obstacle 0 must be an object"):
        mission_from_dict(_mission_payload(obstacles=[7]), arm)


def test_mission_from_dict_rejects_blank_obstacle_name(arm):
    with pytest.raises(ArmError, match="obstacle 0 name must be"):
        mission_from_dict(
            _mission_payload(obstacles=[{"name": " ", "x": 1.0, "y": 0.0,
                                         "radius": 0.1}]), arm)


def test_mission_from_dict_rejects_non_positive_obstacle_radius(arm):
    with pytest.raises(ArmError, match="radius must be > 0"):
        mission_from_dict(
            _mission_payload(obstacles=[{"name": "wall", "x": 1.0, "y": 0.0,
                                         "radius": 0.0}]), arm)


def test_load_mission_bundled(mission):
    assert mission.name == "pick_and_place"
    assert len(mission.waypoints) == 6
    assert len(mission.obstacles) == 3
    assert mission.steps == 40


def test_load_mission_missing_file(tmp_path, arm):
    with pytest.raises(ArmError, match="mission file not found"):
        load_mission(tmp_path / "ghost.json", arm=arm)


def test_load_mission_bad_json(tmp_path, arm):
    path = tmp_path / "bad.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(ArmError, match="could not parse"):
        load_mission(path, arm=arm)


# --------------------------------------------------------------------------- #
# Kinematics
# --------------------------------------------------------------------------- #
def test_check_joints_accepts_a_valid_configuration(arm):
    assert check_joints(arm, (10.0, -20.0, 30.0)) == (10.0, -20.0, 30.0)


def test_check_joints_rejects_the_wrong_count(arm):
    with pytest.raises(ArmError, match="needs 3 joint value"):
        check_joints(arm, (10.0, 20.0))


def test_check_joints_rejects_non_finite(arm):
    with pytest.raises(ArmError, match="must be finite"):
        check_joints(arm, (0.0, float("nan"), 0.0))


def test_check_joints_enforces_limits(arm):
    with pytest.raises(ArmError, match="outside"):
        check_joints(arm, (0.0, 200.0, 0.0))


def test_check_joints_can_skip_limits(arm):
    assert check_joints(arm, (0.0, 200.0, 0.0),
                        enforce_limits=False) == (0.0, 200.0, 0.0)


def test_link_points_straight_arm(arm):
    points = link_points(arm, (0.0, 0.0, 0.0))
    assert points[0] == (0.0, 0.0)
    assert points[1] == pytest.approx((0.6, 0.0))
    assert points[2] == pytest.approx((1.1, 0.0))
    assert points[3] == pytest.approx((1.1, 0.0))


def test_link_points_count_is_links_plus_base(arm):
    assert len(link_points(arm, (10.0, 20.0, 30.0))) == 4


def test_pose_straight_arm(arm):
    tool = pose(arm, (0.0, 0.0, 0.0))
    assert tool.x == pytest.approx(1.1)
    assert tool.y == pytest.approx(0.0)
    assert tool.yaw == pytest.approx(0.0)


def test_pose_reports_the_summed_yaw(arm):
    tool = pose(arm, (10.0, 20.0, 15.0))
    assert tool.yaw == pytest.approx(45.0)


def test_pose_distance_property():
    assert Pose(3.0, 4.0, 0.0).distance == pytest.approx(5.0)


def test_pose_to_dict_rounds():
    assert Pose(0.1234567, 0.5, 90.0).to_dict() == {
        "x": 0.123457, "y": 0.5, "yaw": 90.0}


def test_solve_ik_hits_the_requested_position(arm):
    q = solve_ik(arm, (0.55, 0.35, 90.0))
    tool = pose(arm, q)
    assert tool.x == pytest.approx(0.55, abs=1e-12)
    assert tool.y == pytest.approx(0.35, abs=1e-12)
    assert tool.yaw == pytest.approx(90.0, abs=1e-9)


def test_solve_ik_without_yaw_sets_a_zero_wrist(arm):
    q = solve_ik(arm, (0.7, 0.3))
    assert q[2] == pytest.approx(0.0, abs=1e-9)
    assert pose(arm, q).x == pytest.approx(0.7, abs=1e-12)


def test_solve_ik_has_two_elbow_branches(planar2):
    from arm import _candidates_2link

    branches = _candidates_2link(planar2, 0.6, 0.4, None)
    assert len(branches) == 2
    assert branches[0][1] == pytest.approx(-branches[1][1])
    for q in branches:
        assert pose(planar2, q).x == pytest.approx(0.6, abs=1e-12)
        assert pose(planar2, q).y == pytest.approx(0.4, abs=1e-12)


def test_solve_ik_prefers_the_configuration_near_a_reference(arm):
    reference = (10.0, 20.0, 0.0)
    q = solve_ik(arm, (0.7, 0.3), near=reference)
    assert sum(abs(a - b) for a, b in zip(q[:2], reference[:2])) < 180.0


def test_solve_ik_rejects_a_point_outside_reach(arm):
    with pytest.raises(ArmError, match="unreachable"):
        solve_ik(arm, (2.0, 0.0))


def test_solve_ik_rejects_a_point_inside_the_hole(arm):
    with pytest.raises(ArmError, match="unreachable"):
        solve_ik(arm, (0.01, 0.0))


def test_solve_ik_rejects_bad_target_length(arm):
    with pytest.raises(ArmError, match="target must be x,y or x,y,yaw"):
        solve_ik(arm, (0.5,))


def test_solve_ik_rejects_non_finite_target(arm):
    with pytest.raises(ArmError, match="target must be finite"):
        solve_ik(arm, (0.5, float("inf")))


def test_solve_ik_requires_a_wrist_for_yaw(planar2):
    with pytest.raises(ArmError, match="no wrist joint"):
        solve_ik(planar2, (0.6, 0.4, 45.0))


def test_solve_ik_reports_joint_limit_infeasibility():
    arm = arm_from_dict("locked", _arm_payload(
        joints=[_joint(0, low=-5.0, high=5.0),
                _joint(1, low=-5.0, high=5.0)]))
    with pytest.raises(ArmError, match="no IK solution"):
        solve_ik(arm, (0.6, 0.5))


# --------------------------------------------------------------------------- #
# Time parameterisation
# --------------------------------------------------------------------------- #
def test_time_parameterize_rest_to_rest(arm):
    trajectory = time_parameterize(arm, [(0.0, 0.0, 0.0),
                                         (30.0, -20.0, 10.0)])
    first = trajectory.samples[0]
    last = trajectory.samples[-1]
    assert first.q == pytest.approx((0.0, 0.0, 0.0))
    assert last.q == pytest.approx((30.0, -20.0, 10.0))
    assert max(abs(v) for v in first.speeds) < 1e-9
    assert max(abs(v) for v in last.speeds) < 1e-9


def test_time_parameterize_respects_speed_limits(arm):
    trajectory = time_parameterize(arm, [(0.0, 0.0, 0.0),
                                         (60.0, -40.0, 20.0)])
    for speed, joint in zip(trajectory.max_speeds, arm.joints):
        assert speed <= joint.max_speed + 1e-6


def test_time_parameterize_scales_with_speed_scale(arm):
    fast = time_parameterize(arm, [(0.0,) * 3, (30.0, 20.0, 10.0)])
    slow = time_parameterize(arm, [(0.0,) * 3, (30.0, 20.0, 10.0)],
                             speed_scale=0.5)
    assert slow.duration == pytest.approx(2.0 * fast.duration, rel=1e-9)


def test_time_parameterize_single_configuration_has_zero_duration(arm):
    trajectory = time_parameterize(arm, [(10.0, 20.0, 30.0)])
    assert trajectory.duration == 0.0
    assert len(trajectory.samples) == 1


def test_time_parameterize_rejects_an_empty_path(arm):
    with pytest.raises(ArmError, match="at least one configuration"):
        time_parameterize(arm, [])


def test_time_parameterize_rejects_bad_dt(arm):
    with pytest.raises(ArmError, match="dt must be > 0"):
        time_parameterize(arm, [(0.0,) * 3, (10.0, 0.0, 0.0)], dt=0.0)


def test_time_parameterize_rejects_non_numeric_dt(arm):
    with pytest.raises(ArmError, match="dt must be a number"):
        time_parameterize(arm, [(0.0,) * 3, (10.0, 0.0, 0.0)], dt="fast")


def test_time_parameterize_rejects_bad_speed_scale(arm):
    with pytest.raises(ArmError, match="speed_scale must be > 0"):
        time_parameterize(arm, [(0.0,) * 3, (10.0, 0.0, 0.0)],
                          speed_scale=-1.0)


def test_time_parameterize_rejects_non_numeric_speed_scale(arm):
    with pytest.raises(ArmError, match="speed_scale must be a number"):
        time_parameterize(arm, [(0.0,) * 3, (10.0, 0.0, 0.0)],
                          speed_scale="slow")


def test_time_parameterize_can_skip_limits(arm):
    trajectory = time_parameterize(arm, [(0.0,) * 3, (200.0, 0.0, 0.0)],
                                   enforce_limits=False)
    assert trajectory.samples[-1].q[0] == pytest.approx(200.0)


def test_time_parameterize_interpolates_between_waypoints(arm):
    trajectory = time_parameterize(
        arm, [(0.0,) * 3, (30.0, 0.0, 0.0), (30.0, 30.0, 0.0)], dt=0.02)
    assert trajectory.samples[0].q == pytest.approx((0.0, 0.0, 0.0))
    assert trajectory.samples[-1].q == pytest.approx((30.0, 30.0, 0.0))
    assert len(trajectory.samples) > 10


# --------------------------------------------------------------------------- #
# Trajectory properties
# --------------------------------------------------------------------------- #
def test_plan_joint_move_matches_the_endpoints(arm):
    trajectory = plan_joint_move(arm, (10.0, 20.0, 30.0),
                                 (40.0, -10.0, 0.0))
    assert trajectory.q_start == pytest.approx((10.0, 20.0, 30.0))
    assert trajectory.q_end == pytest.approx((40.0, -10.0, 0.0))


def test_trajectory_samples_are_ordered_in_time(arm):
    trajectory = plan_joint_move(arm, (0.0,) * 3, (30.0, 20.0, 10.0))
    times = [sample.t for sample in trajectory.samples]
    assert times[0] == 0.0
    assert all(b >= a for a, b in zip(times, times[1:]))
    assert times[-1] == pytest.approx(trajectory.duration)


def test_trajectory_cartesian_length_is_positive(arm):
    trajectory = plan_joint_move(arm, (0.0,) * 3, (30.0, 20.0, 10.0))
    assert trajectory.cartesian_length > 0.0


def test_trajectory_to_dict_shape(arm):
    payload = plan_joint_move(arm, (0.0,) * 3, (20.0, 10.0, 0.0)).to_dict()
    assert payload["duration"] > 0
    assert len(payload["samples"]) >= 2
    assert set(payload["samples"][0]) == {"t", "q", "x", "y", "yaw"}


def test_sample_pose_property():
    sample = Sample(t=0.0, q=(0.0,), x=0.1, y=0.2, yaw=30.0, speeds=(0.0,))
    assert sample.pose == Pose(0.1, 0.2, 30.0)


# --------------------------------------------------------------------------- #
# Cartesian moves
# --------------------------------------------------------------------------- #
def test_plan_cartesian_move_hits_the_target(arm):
    start = solve_ik(arm, (0.55, 0.35, 90.0))
    trajectory = plan_cartesian_move(arm, start, (0.70, 0.28, 60.0),
                                     steps=20)
    last = trajectory.samples[-1]
    assert last.x == pytest.approx(0.70, abs=1e-9)
    assert last.y == pytest.approx(0.28, abs=1e-9)
    assert last.yaw == pytest.approx(60.0, abs=1e-9)


def test_plan_cartesian_move_stays_on_the_line(arm):
    start = solve_ik(arm, (0.55, 0.35, 90.0))
    trajectory = plan_cartesian_move(arm, start, (0.36, 0.78, 150.0),
                                     steps=40, dt=0.01)
    first, last = trajectory.samples[0], trajectory.samples[-1]
    length = math.hypot(last.x - first.x, last.y - first.y)
    assert length > 0.4
    worst = 0.0
    for sample in trajectory.samples:
        cross = abs((sample.x - first.x) * (last.y - first.y)
                    - (sample.y - first.y) * (last.x - first.x)) / length
        worst = max(worst, cross)
    # joint-space interpolation between dense IK waypoints bulges by O(h^2)
    assert worst < 1e-4


def test_plan_cartesian_move_keeps_yaw_without_a_yaw_target(arm):
    start = solve_ik(arm, (0.55, 0.35, 90.0))
    trajectory = plan_cartesian_move(arm, start, (0.60, 0.30), steps=10)
    assert trajectory.samples[0].yaw == pytest.approx(90.0, abs=1e-9)
    assert trajectory.samples[-1].yaw == pytest.approx(90.0, abs=1e-9)


def test_plan_cartesian_move_rejects_bad_steps(arm):
    with pytest.raises(ArmError, match="steps must be an integer >= 2"):
        plan_cartesian_move(arm, (0.55, 0.35, 90.0), (0.6, 0.3), steps=1)


def test_plan_cartesian_move_rejects_a_yaw_target_without_a_wrist(planar2):
    with pytest.raises(ArmError, match="no wrist joint"):
        plan_cartesian_move(planar2, (0.6, 0.4), (0.5, 0.5, 10.0))


def test_plan_cartesian_move_rejects_unreachable_targets(arm):
    with pytest.raises(ArmError, match="unreachable"):
        plan_cartesian_move(arm, (0.55, 0.35, 90.0), (1.9, 0.0), steps=10)


# --------------------------------------------------------------------------- #
# Collisions
# --------------------------------------------------------------------------- #
def test_point_segment_distance_on_the_segment():
    assert point_segment_distance((0.5, 0.0), (0.0, 0.0),
                                  (1.0, 0.0)) == pytest.approx(0.0)


def test_point_segment_distance_beyond_the_end():
    assert point_segment_distance((2.0, 0.0), (0.0, 0.0),
                                  (1.0, 0.0)) == pytest.approx(1.0)


def test_point_segment_distance_perpendicular():
    assert point_segment_distance((0.5, 0.4), (0.0, 0.0),
                                  (1.0, 0.0)) == pytest.approx(0.4)


def test_point_segment_distance_degenerate_segment():
    assert point_segment_distance((3.0, 4.0), (0.0, 0.0),
                                  (0.0, 0.0)) == pytest.approx(5.0)


def test_check_collisions_reports_a_hit(arm):
    trajectory = plan_joint_move(arm, (0.0,) * 3, (0.0,) * 3)
    obstacle = Obstacle("post", 0.3, 0.0, 0.1)
    hits = check_collisions(arm, trajectory, (obstacle,))
    assert hits
    assert hits[0].obstacle == "post"
    assert hits[0].clearance > 0


def test_check_collisions_ignores_distant_obstacles(arm):
    trajectory = plan_joint_move(arm, (0.0,) * 3, (0.0,) * 3)
    obstacle = Obstacle("far", 2.0, 0.0, 0.1)
    assert check_collisions(arm, trajectory, (obstacle,)) == []


def test_collision_to_dict_shape():
    hit = Collision(t=0.5, link=1, obstacle="post", clearance=0.02)
    assert hit.to_dict() == {"t": 0.5, "link": 1, "obstacle": "post",
                             "clearance": 0.02}


# --------------------------------------------------------------------------- #
# Missions
# --------------------------------------------------------------------------- #
def test_run_mission_reaches_every_waypoint(result):
    assert len(result.waypoint_errors) == 6
    for _, error in result.waypoint_errors:
        assert error < 1e-6


def test_run_mission_adds_the_home_leg(result):
    assert len(result.segments) == 7
    assert result.segments[-1].name == "home"


def test_run_mission_bundled_is_collision_free(result):
    assert result.collisions == ()


def test_run_mission_timing_bookkeeping(result, mission):
    assert result.total_time == pytest.approx(
        result.move_time + len(mission.waypoints) * mission.dwell)
    assert result.sample_count == sum(
        len(segment.trajectory.samples) for segment in result.segments)


def test_run_mission_respects_speed_limits(result, arm):
    for speed, joint in zip(result.max_speeds, arm.joints):
        assert speed <= joint.max_speed + 1e-6


def test_run_mission_is_deterministic(arm, mission, result):
    again = run_mission(arm, mission)
    assert again.total_time == result.total_time
    assert again.segments[0].trajectory.samples == \
        result.segments[0].trajectory.samples


def test_run_mission_detects_a_blocked_move(arm):
    blocked = Mission(
        name="blocked", home=(0.55, 0.35, 90.0),
        waypoints=(Waypoint("crash", 0.55, 0.65, 90.0),),
        obstacles=(Obstacle("blocker", 0.55, 0.0, 0.06),),
        dwell=0.0, steps=20)
    assert run_mission(arm, blocked).collisions


def test_run_mission_keeps_yaw_when_a_waypoint_has_none(arm):
    mission = Mission(name="m", home=(0.55, 0.35, 90.0),
                      waypoints=(Waypoint("a", 0.60, 0.30),),
                      dwell=0.0, steps=10)
    result = run_mission(arm, mission)
    assert result.segments[0].trajectory.samples[-1].yaw == \
        pytest.approx(90.0, abs=1e-9)


def test_segment_duration_includes_the_dwell(arm):
    trajectory = plan_joint_move(arm, (0.0,) * 3, (10.0, 0.0, 0.0))
    segment = Segment("leg", trajectory, 0.4)
    assert segment.duration == pytest.approx(trajectory.duration + 0.4)


def test_mission_result_defaults():
    result = MissionResult(mission="empty", segments=())
    assert result.total_time == 0.0
    assert result.sample_count == 0
    assert result.collisions == ()


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def test_render_report_contains_the_totals(result):
    text = render_report(result)
    for needle in ("MISSION", "LEG", "SAMPLES", "Total time", "Samples",
                   "Waypoint err", "Collisions", "Max speeds"):
        assert needle in text


def test_render_report_lists_every_leg(result):
    text = render_report(result)
    for segment in result.segments:
        assert segment.name in text


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


def test_cli_requires_a_mode():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_pose(capsys):
    assert main(["--pose", "0.55,0.35,90"]) == 0
    out = capsys.readouterr().out
    assert "IK SOLUTION" in out
    assert "shoulder" in out


def test_cli_pose_json(tmp_path):
    out = tmp_path / "pose.json"
    assert main(["--pose", "0.55,0.35", "--json", str(out), "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["kind"] == "ik"
    assert len(payload["q_deg"]) == 3
    assert payload["pose"]["x"] == pytest.approx(0.55, abs=1e-6)


def test_cli_bad_pose(capsys):
    assert main(["--pose", "0.55"]) == 2
    assert "pose must be" in capsys.readouterr().err


def test_cli_unreachable_pose(capsys):
    assert main(["--pose", "2.0,0.0"]) == 2
    assert "unreachable" in capsys.readouterr().err


def test_cli_joint_move(capsys):
    assert main(["--move", "0,0,0", "--to", "30,20,10"]) == 0
    out = capsys.readouterr().out
    assert "TRAJECTORY - joint" in out
    assert "peak speeds" in out


def test_cli_cartesian_move(capsys):
    assert main(["--move", "0.55,0.35,90", "--to", "0.70,0.28,60",
                 "--cartesian", "--steps", "10"]) == 0
    assert "TRAJECTORY - cartesian" in capsys.readouterr().out


def test_cli_move_requires_a_goal(capsys):
    assert main(["--move", "0,0,0"]) == 2
    assert "--move requires --to" in capsys.readouterr().err


def test_cli_move_rejects_the_wrong_joint_count(capsys):
    assert main(["--move", "0,0", "--to", "0,0"]) == 2
    assert "needs 3 joint value" in capsys.readouterr().err


def test_cli_bad_dt(capsys):
    assert main(["--pose", "0.55,0.35", "--dt", "0"]) == 2
    assert "dt must be > 0" in capsys.readouterr().err


def test_cli_bad_steps(capsys):
    assert main(["--pose", "0.55,0.35", "--steps", "1"]) == 2
    assert "steps must be >= 2" in capsys.readouterr().err


def test_cli_bad_speed_scale(capsys):
    assert main(["--pose", "0.55,0.35", "--speed-scale", "-2"]) == 2
    assert "speed_scale must be > 0" in capsys.readouterr().err


def test_cli_mission(capsys):
    assert main(["--mission", str(MISSION_FILE)]) == 0
    out = capsys.readouterr().out
    assert "MISSION - pick_and_place" in out
    assert "Collisions   : 0" in out


def test_cli_mission_json(tmp_path):
    out = tmp_path / "mission.json"
    assert main(["--mission", str(MISSION_FILE), "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["segments"]) == 7
    assert payload["collisions"] == []
    assert payload["total_time"] > 0


def test_cli_mission_reports_collisions(tmp_path, capsys):
    path = tmp_path / "blocked.json"
    path.write_text(json.dumps({
        "name": "blocked", "home": [0.55, 0.35, 90.0], "dwell": 0.0,
        "steps": 20,
        "waypoints": [{"name": "crash", "x": 0.55, "y": 0.65,
                       "yaw": 90.0}],
        "obstacles": [{"name": "blocker", "x": 0.55, "y": 0.0,
                       "radius": 0.06}]}), encoding="utf-8")
    assert main(["--mission", str(path), "--quiet"]) == 3
    assert main(["--mission", str(path)]) == 3
    assert "Collisions   : 18" in capsys.readouterr().out


def test_cli_missing_mission(tmp_path, capsys):
    assert main(["--mission", str(tmp_path / "ghost.json")]) == 2
    assert "mission file not found" in capsys.readouterr().err


def test_cli_mission_arm_mismatch(tmp_path, capsys):
    path = tmp_path / "other.json"
    payload = json.loads(MISSION_FILE.read_text(encoding="utf-8"))
    payload["arm"] = "other"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["--mission", str(path)]) == 2
    assert "mission targets arm" in capsys.readouterr().err


def test_cli_quiet_with_mission_json(tmp_path, capsys):
    out = tmp_path / "m.json"
    assert main(["--mission", str(MISSION_FILE), "--json", str(out),
                 "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_bundled_files_exist():
    assert ARM_FILE.is_file()
    assert MISSION_FILE.is_file()
