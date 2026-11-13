"""Tests for the Forward Kinematics project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fk import (  # noqa: E402
    DEMO_ARMS,
    DEMO_SCENARIOS,
    Arm,
    FkError,
    Pose,
    arm_from_dict,
    check_angles,
    dh_transform,
    end_effector,
    forward_kinematics,
    limit_statuses,
    load_arms,
    load_scenarios,
    parse_angles,
    reach_status,
    render_report,
    render_scenario_table,
    run_demo,
    select_arm,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def arms() -> dict[str, Arm]:
    return load_arms(DEMO_ARMS)


def _row(theta_offset=0.0, d=0.0, a=1.0, alpha=0.0) -> dict:
    return {"theta_offset": theta_offset, "d": d, "a": a, "alpha": alpha}


def _payload(**overrides) -> dict:
    payload = {
        "joints": ["R", "R"],
        "dh": [_row(), _row(a=0.5)],
        "limits": [[-180.0, 180.0], [-180.0, 180.0]],
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_arms(arms):
    assert set(arms) == {"planar2", "planar3", "spatial3", "prism2"}
    assert arms["planar2"].n_joints == 2
    assert arms["planar3"].n_joints == 3
    assert arms["planar2"].is_planar
    assert not arms["spatial3"].is_planar
    assert arms["prism2"].joints == ("R", "P")


def test_load_missing_file(tmp_path):
    with pytest.raises(FkError, match="file not found"):
        load_arms(tmp_path / "nope.json")


def test_load_json_errors(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(FkError, match="could not parse"):
        load_arms(bad)

    listing = tmp_path / "list.json"
    listing.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(FkError, match="JSON object of arm definitions"):
        load_arms(listing)

    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    with pytest.raises(FkError, match="no arm definitions"):
        load_arms(empty)


def test_arm_missing_key():
    with pytest.raises(FkError, match="missing key"):
        arm_from_dict("x", {"joints": ["R"]})


def test_arm_empty_joints():
    with pytest.raises(FkError, match="non-empty list"):
        arm_from_dict("x", _payload(joints=[]))


def test_arm_bad_joint_type():
    with pytest.raises(FkError, match="joint type must be R or P"):
        arm_from_dict("x", _payload(joints=["R", "S"]))


def test_arm_dh_row_errors():
    with pytest.raises(FkError, match="dh must have exactly 2 row"):
        arm_from_dict("x", _payload(dh=[_row()]))

    missing = _row()
    del missing["alpha"]
    with pytest.raises(FkError, match="dh row 0 missing key"):
        arm_from_dict("x", _payload(dh=[missing, _row()]))

    with pytest.raises(FkError, match="value 'a' must be numeric"):
        arm_from_dict("x", _payload(dh=[_row(a="long"), _row()]))

    with pytest.raises(FkError, match="value 'd' must be finite"):
        arm_from_dict("x",
                      _payload(dh=[_row(d=float("inf")), _row()]))

    with pytest.raises(FkError, match="link length a must be >= 0"):
        arm_from_dict("x", _payload(dh=[_row(a=-0.1), _row()]))


def test_arm_limit_errors():
    with pytest.raises(FkError, match="limits must have exactly 2"):
        arm_from_dict("x", _payload(limits=[[-1, 1]]))

    with pytest.raises(FkError, match="limit 1 must be \\[min, max\\]"):
        arm_from_dict("x", _payload(limits=[[-1, 1], [0, 1, 2]]))

    with pytest.raises(FkError, match="limit 0 min must be <= max"):
        arm_from_dict("x", _payload(limits=[[10, -10], [-1, 1]]))

    with pytest.raises(FkError, match="limit 1 must be finite"):
        arm_from_dict("x",
                      _payload(limits=[[-1, 1], [0, float("nan")]]))


def test_select_arm_default_and_named(arms):
    assert select_arm(arms).name == "planar2"
    assert select_arm(arms, "spatial3").name == "spatial3"


def test_select_arm_unknown(arms):
    with pytest.raises(FkError, match="unknown arm 'nope'"):
        select_arm(arms, "nope")


# --------------------------------------------------------------------------- #
# Core maths
# --------------------------------------------------------------------------- #
def test_2r_zero_config(arms):
    pose = end_effector(arms["planar2"], [0.0, 0.0])
    assert np.isclose(pose.x, 1.8, atol=1e-12)
    assert np.isclose(pose.y, 0.0, atol=1e-12)
    assert np.isclose(pose.z, 0.0, atol=1e-12)
    assert np.isclose(pose.yaw, 0.0, atol=1e-12)


def test_2r_quarter_turn(arms):
    pose = end_effector(arms["planar2"], [90.0, 0.0])
    assert np.isclose(pose.x, 0.0, atol=1e-12)
    assert np.isclose(pose.y, 1.8, atol=1e-12)
    assert np.isclose(pose.yaw, 90.0, atol=1e-9)


def test_analytic_vs_matrix_seeded(arms):
    arm = arms["planar2"]
    rng = np.random.default_rng(7)
    for q0, q1 in rng.uniform(-180, 180, size=(12, 2)):
        pose = end_effector(arm, [q0, q1])
        x = (np.cos(np.deg2rad(q0))
             + 0.8 * np.cos(np.deg2rad(q0 + q1)))
        y = (np.sin(np.deg2rad(q0))
             + 0.8 * np.sin(np.deg2rad(q0 + q1)))
        assert np.isclose(pose.x, x, atol=1e-9)
        assert np.isclose(pose.y, y, atol=1e-9)


def test_planar_yaw_is_joint_sum(arms):
    pose = end_effector(arms["planar3"], [20.0, -40.0, 30.0])
    wrapped = abs((pose.yaw - 10.0 + 180.0) % 360.0 - 180.0)
    assert wrapped < 1e-9
    assert abs(pose.z) < 1e-12


def test_rotation_orthonormal_spatial(arms):
    rotation = forward_kinematics(arms["spatial3"], [30, 45, -45])[:3, :3]
    assert np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-9)
    assert np.isclose(np.linalg.det(rotation), 1.0, atol=1e-9)


def test_chain_equals_manual_product(arms):
    arm = arms["planar2"]
    q = [30.0, -60.0]
    expected = (dh_transform(arm.rows[0], "R", q[0])
                @ dh_transform(arm.rows[1], "R", q[1]))
    assert np.allclose(forward_kinematics(arm, q), expected, atol=1e-12)


def test_prismatic_lift(arms):
    pose = end_effector(arms["prism2"], [45.0, 0.35])
    assert np.isclose(pose.z, 0.2 + 0.35, atol=1e-12)
    assert np.isclose(pose.x, 0.5 * np.cos(np.deg2rad(45)), atol=1e-12)
    assert np.isclose(pose.y, 0.5 * np.sin(np.deg2rad(45)), atol=1e-12)


def test_reach_bounds_planar(arms):
    arm = arms["planar2"]
    assert np.isclose(arm.max_reach, 1.8, atol=1e-12)
    assert np.isclose(arm.min_reach, 0.2, atol=1e-12)


def test_max_reach_counts_prismatic_travel(arms):
    arm = arms["prism2"]
    expected = np.hypot(0.5, 0.2) + 0.6
    assert np.isclose(arm.max_reach, expected, atol=1e-12)


def test_reach_status_within_and_beyond(arms):
    pose = end_effector(arms["planar2"], [45.0, -90.0])
    status, distance, inner, outer = reach_status(arms["planar2"], pose)
    assert status == "within reach"
    assert inner <= distance <= outer

    far = Pose(x=5.0, y=0.0, z=0.0, roll=0.0, pitch=0.0, yaw=0.0)
    status, distance, _, _ = reach_status(arms["planar2"], far)
    assert status == "beyond workspace"
    assert np.isclose(distance, 5.0)


def test_check_angles_errors(arms):
    with pytest.raises(FkError, match="expected 2 joint value"):
        check_angles(arms["planar2"], [0.0, 0.0, 0.0])
    with pytest.raises(FkError, match="must be finite"):
        check_angles(arms["planar2"], [0.0, float("nan")])


def test_parse_angles():
    assert parse_angles("45, -90, 0.5") == [45.0, -90.0, 0.5]
    with pytest.raises(FkError, match="not a number for joint 1"):
        parse_angles("1,abc")
    with pytest.raises(FkError, match="at least one joint value"):
        parse_angles(" , , ")


def test_limit_statuses_ok_and_out(arms):
    ok = limit_statuses(arms["planar2"], [0.0, 179.0])
    assert [state for _, state, _ in ok] == ["ok", "ok"]
    out = limit_statuses(arms["prism2"], [0.0, 0.9])
    assert [state for _, state, _ in out] == ["ok", "OUT"]


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #
def test_load_bundled_scenarios(arms):
    scenarios = load_scenarios(DEMO_SCENARIOS, arms)
    assert len(scenarios) == 8
    assert scenarios[0].name == "home"
    assert scenarios[0].q == (0.0, 0.0)
    lift = next(s for s in scenarios if s.name == "lift")
    assert lift.q == (45.0, 0.35)


def test_scenarios_missing_file(arms, tmp_path):
    with pytest.raises(FkError, match="file not found"):
        load_scenarios(tmp_path / "nope.csv", arms)


def test_scenarios_schema_errors(arms, tmp_path):
    missing = tmp_path / "a.csv"
    missing.write_text("name,arm,q0\nhome,planar2,0\n", encoding="utf-8")
    with pytest.raises(FkError, match="missing column 'scenario'"):
        load_scenarios(missing, arms)

    no_q = tmp_path / "b.csv"
    no_q.write_text("scenario,arm\nhome,planar2\n", encoding="utf-8")
    with pytest.raises(FkError, match="at least one q column"):
        load_scenarios(no_q, arms)

    empty = tmp_path / "c.csv"
    empty.write_text("scenario,arm,q0,q1\n", encoding="utf-8")
    with pytest.raises(FkError, match="no rows"):
        load_scenarios(empty, arms)


def test_scenarios_unknown_arm(arms, tmp_path):
    path = tmp_path / "s.csv"
    path.write_text("scenario,arm,q0,q1\nhome,ghost,0,0\n",
                    encoding="utf-8")
    with pytest.raises(FkError, match="unknown arm 'ghost'"):
        load_scenarios(path, arms)


def test_scenarios_count_mismatch(arms, tmp_path):
    path = tmp_path / "s.csv"
    path.write_text("scenario,arm,q0,q1,q2\nhome,planar2,0,0,0\n",
                    encoding="utf-8")
    with pytest.raises(FkError, match="expected 2 joint value"):
        load_scenarios(path, arms)


def test_scenarios_duplicate_name(arms, tmp_path):
    path = tmp_path / "s.csv"
    path.write_text("scenario,arm,q0,q1\nhome,planar2,0,0\n"
                    "home,planar2,10,10\n", encoding="utf-8")
    with pytest.raises(FkError, match="duplicate scenario name 'home'"):
        load_scenarios(path, arms)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def test_render_report_sections(arms):
    arm = arms["planar2"]
    pose = end_effector(arm, [0.0, 0.0])
    text = render_report(arm, [0.0, 0.0], pose)
    assert "arm 'planar2'" in text
    assert "Joint space" in text
    assert "Task space" in text
    assert "revolute |q| total" in text
    assert "within reach" in text
    assert "q0 (R)" in text and "q1 (R)" in text


def test_render_report_flags_out_of_limit(arms):
    arm = arms["prism2"]
    text = render_report(arm, [0.0, 0.9],
                         end_effector(arm, [0.0, 0.9]))
    assert "OUT" in text
    assert "beyond workspace" in text


def test_render_scenario_table_headers(arms):
    scenarios = load_scenarios(DEMO_SCENARIOS, arms)
    rows = [(s, arms[s.arm], end_effector(arms[s.arm], s.q))
            for s in scenarios]
    text = render_scenario_table(rows)
    lines = text.splitlines()
    assert lines[0].startswith("SCENARIO")
    assert "reach%" in lines[0]
    assert len(lines) == len(scenarios) + 2
    assert "lift" in text and "prism2" in text


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out
    assert "SCENARIO" in out and "Joint space" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert out.count("Demo completed successfully.") == 2
    assert out.count("Cross-checks OK") == 2


def test_run_demo_deterministic_output(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    second = capsys.readouterr().out
    assert first == second


def test_run_demo_missing_files(tmp_path):
    with pytest.raises(FkError, match="bundled arm file not found"):
        run_demo(arms_path=tmp_path / "nope.json")
    with pytest.raises(FkError, match="bundled scenarios not found"):
        run_demo(scenarios_path=tmp_path / "nope.csv")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out


def test_cli_angles_default_arm(capsys):
    assert main(["--angles", "45,-90", "--quiet"]) == 0
    assert "not a number" not in capsys.readouterr().err


def test_cli_file_arm_angles(capsys):
    assert main(["--file", str(DEMO_ARMS), "--arm", "planar3",
                 "--angles", "0,0,0"]) == 0
    out = capsys.readouterr().out
    assert "Task space" in out and "Done." in out


def test_cli_file_without_angles_uses_zero_config(capsys):
    assert main(["--file", str(DEMO_ARMS), "--arm", "planar2",
                 "--quiet"]) == 0


def test_cli_requires_action():
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_cli_bad_angles_fast_fails_before_file(tmp_path, capsys):
    # angle syntax is validated before the (missing) file is touched
    assert main(["--file", str(tmp_path / "nope.json"),
                 "--angles", "abc"]) == 2
    err = capsys.readouterr().err
    assert "not a number" in err
    assert "file not found" not in err


def test_cli_angle_count_mismatch(capsys):
    assert main(["--angles", "1,2,3"]) == 2
    assert "expected 2 joint value" in capsys.readouterr().err


def test_cli_missing_file(capsys, tmp_path):
    assert main(["--file", str(tmp_path / "nope.json")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_unknown_arm(capsys):
    assert main(["--file", str(DEMO_ARMS), "--arm", "ghost"]) == 2
    assert "unknown arm 'ghost'" in capsys.readouterr().err


def test_cli_json_output(tmp_path, capsys):
    payload_path = tmp_path / "pose.json"
    assert main(["--file", str(DEMO_ARMS), "--arm", "planar2",
                 "--angles", "10,20", "--json", str(payload_path),
                 "--quiet"]) == 0
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["arm"] == "planar2"
    assert payload["angles"] == [10.0, 20.0]
    assert np.isclose(payload["pose"]["yaw"], 30.0, atol=1e-6)
    assert payload["limit_statuses"] == ["ok", "ok"]
    assert payload["reach"]["status"] == "within reach"


def test_cli_demo_and_file_mutually_exclusive(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--demo", "--file", str(DEMO_ARMS)])
    assert excinfo.value.code == 2


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
def test_project_has_sample_data():
    assert DEMO_ARMS.is_file()
    assert DEMO_SCENARIOS.is_file()
    assert DEMO_ARMS.parent == PROJECT_ROOT / "data"
    assert DEMO_SCENARIOS.parent == PROJECT_ROOT / "data"


def test_bundled_scenarios_valid_against_arms(arms):
    scenarios = load_scenarios(DEMO_SCENARIOS, arms)
    for scenario in scenarios:
        arm = arms[scenario.arm]
        states = [s for _, s, _ in limit_statuses(arm, scenario.q)]
        assert states == ["ok"] * arm.n_joints
        assert reach_status(arm, end_effector(arm, scenario.q))[0] == \
            "within reach"
