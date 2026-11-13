"""Tests for the Inverse Kinematics project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ik import (  # noqa: E402
    DEMO_ARMS,
    DEMO_TARGETS,
    ArmIk,
    IkError,
    IkSolution,
    Target,
    arm_from_dict,
    check_reachable,
    load_arms,
    load_targets,
    parse_target,
    parse_values,
    planar_fk,
    planar_jacobian,
    render_solution,
    render_table,
    run_demo,
    select_arm,
    solve,
    solve_2link,
    solve_dls,
    within_limits,
    workspace_annulus,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARMS_FILE = PROJECT_ROOT / "data" / "arms.json"
TARGETS_FILE = PROJECT_ROOT / "data" / "targets.csv"

STALL_TARGET = (0.2055418935160611, -0.5207959304846969, -143.63416540065904)


@pytest.fixture(scope="module")
def arms():
    return load_arms(ARMS_FILE)


@pytest.fixture()
def planar2(arms):
    return arms["planar2"]


@pytest.fixture()
def planar3(arms):
    return arms["planar3"]


# --------------------------------------------------------------------------- #
# Arm validation
# --------------------------------------------------------------------------- #
def _payload(**overrides):
    payload = {"links": [1.0, 0.8], "limits": [[-180.0, 180.0],
                                               [-180.0, 180.0]]}
    payload.update(overrides)
    return payload


def test_arm_from_dict_valid():
    arm = arm_from_dict("two", _payload())
    assert arm.name == "two"
    assert arm.n_joints == 2
    assert arm.links == (1.0, 0.8)


def test_arm_from_dict_rejects_non_object():
    with pytest.raises(IkError, match="must be a JSON object"):
        arm_from_dict("bad", [])


def test_arm_from_dict_requires_links_and_limits():
    with pytest.raises(IkError, match="missing key"):
        arm_from_dict("bad", {"links": [1.0]})


def test_arm_from_dict_links_must_be_a_list():
    with pytest.raises(IkError, match="links must be a non-empty list"):
        arm_from_dict("bad", _payload(links="1.0"))


def test_arm_from_dict_links_must_not_be_empty():
    with pytest.raises(IkError, match="links must be a non-empty list"):
        arm_from_dict("bad", _payload(links=[]))


def test_arm_from_dict_link_must_be_numeric():
    with pytest.raises(IkError, match="link 0 must be numeric"):
        arm_from_dict("bad", _payload(links=["long", 0.8]))


def test_arm_from_dict_link_must_be_finite():
    with pytest.raises(IkError, match="link 1 must be finite"):
        arm_from_dict("bad", _payload(links=[1.0, float("inf")]))


def test_arm_from_dict_link_must_be_positive():
    with pytest.raises(IkError, match="link 1 must be > 0"):
        arm_from_dict("bad", _payload(links=[1.0, 0.0]))


def test_arm_from_dict_limit_count_must_match():
    with pytest.raises(IkError, match="limits must have exactly 2"):
        arm_from_dict("bad", _payload(limits=[[-180.0, 180.0]]))


def test_arm_from_dict_limit_must_be_a_pair():
    with pytest.raises(IkError, match="limit 0 must be"):
        arm_from_dict("bad", _payload(limits=[[-180.0], [-180.0, 180.0]]))


def test_arm_from_dict_limit_must_be_numeric():
    with pytest.raises(IkError, match="limit 0 must be numeric"):
        arm_from_dict("bad", _payload(limits=[["low", 180.0],
                                              [-180.0, 180.0]]))


def test_arm_from_dict_limit_must_be_finite():
    with pytest.raises(IkError, match="limit 1 must be finite"):
        arm_from_dict("bad", _payload(limits=[[-180.0, 180.0],
                                              [-180.0, float("nan")]]))


def test_arm_from_dict_limit_min_above_max():
    with pytest.raises(IkError, match="min must be <= max"):
        arm_from_dict("bad", _payload(limits=[[180.0, -180.0],
                                              [-180.0, 180.0]]))


# --------------------------------------------------------------------------- #
# Loading arms
# --------------------------------------------------------------------------- #
def test_load_arms_bundled(arms):
    assert list(arms) == ["planar2", "planar3", "long2", "wrist4"]
    assert arms["wrist4"].n_joints == 4


def test_load_arms_missing_file(tmp_path):
    with pytest.raises(IkError, match="file not found"):
        load_arms(tmp_path / "ghost.json")


def test_load_arms_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(IkError, match="could not parse"):
        load_arms(path)


def test_load_arms_requires_object(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(IkError, match="expected a JSON object"):
        load_arms(path)


def test_load_arms_requires_definitions(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(IkError, match="no arm definitions"):
        load_arms(path)


def test_select_arm_default(arms):
    assert select_arm(arms).name == "planar2"


def test_select_arm_by_name(arms):
    assert select_arm(arms, "wrist4").links == (0.5, 0.4, 0.3, 0.2)


def test_select_arm_unknown(arms):
    with pytest.raises(IkError, match="unknown arm"):
        select_arm(arms, "nope")


def test_select_arm_empty():
    with pytest.raises(IkError, match="no arms loaded"):
        select_arm({})


# --------------------------------------------------------------------------- #
# Targets
# --------------------------------------------------------------------------- #
def test_target_values_without_yaw():
    target = Target(name="a", arm="planar2", x=1.0, y=2.0)
    assert target.values == (1.0, 2.0)


def test_target_values_with_yaw():
    target = Target(name="a", arm="planar3", x=1.0, y=2.0, yaw=30.0)
    assert target.values == (1.0, 2.0, 30.0)


def test_load_targets_bundled(arms):
    targets = load_targets(TARGETS_FILE, arms)
    assert len(targets) == 9
    assert targets[0].name == "up_left"
    assert targets[0].yaw is None
    assert targets[4].yaw == 45.0


def test_load_targets_missing_file(arms, tmp_path):
    with pytest.raises(IkError, match="file not found"):
        load_targets(tmp_path / "ghost.csv", arms)


def test_load_targets_missing_columns(arms, tmp_path):
    path = tmp_path / "cols.csv"
    path.write_text("target,arm\nup,planar2\n", encoding="utf-8")
    with pytest.raises(IkError, match="missing column 'x'"):
        load_targets(path, arms)


def test_load_targets_rejects_empty_frame(arms, tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("target,arm,x,y\n", encoding="utf-8")
    with pytest.raises(IkError, match="no rows"):
        load_targets(path, arms)


def test_load_targets_rejects_duplicates(arms, tmp_path):
    path = tmp_path / "dupe.csv"
    path.write_text("target,arm,x,y\nup,planar2,1.0,0.8\n"
                    "up,planar2,1.0,0.8\n", encoding="utf-8")
    with pytest.raises(IkError, match="duplicate target name"):
        load_targets(path, arms)


def test_load_targets_rejects_unknown_arm(arms, tmp_path):
    path = tmp_path / "arm.csv"
    path.write_text("target,arm,x,y\nup,ghost,1.0,0.8\n", encoding="utf-8")
    with pytest.raises(IkError, match="unknown arm"):
        load_targets(path, arms)


def test_load_targets_rejects_non_numeric(arms, tmp_path):
    path = tmp_path / "text.csv"
    path.write_text("target,arm,x,y\nup,planar2,left,0.8\n",
                    encoding="utf-8")
    with pytest.raises(IkError, match="must be numeric"):
        load_targets(path, arms)


def test_load_targets_blank_yaw_is_none(arms, tmp_path):
    path = tmp_path / "yaw.csv"
    path.write_text("target,arm,x,y,yaw\nup,planar2,1.0,0.8,\n",
                    encoding="utf-8")
    assert load_targets(path, arms)[0].yaw is None


def test_parse_values_ok():
    assert parse_values(" 1.5, -2, 3 ") == (1.5, -2.0, 3.0)


def test_parse_values_rejects_empty():
    with pytest.raises(IkError, match="at least one numeric value"):
        parse_values(" , ")


def test_parse_values_rejects_text():
    with pytest.raises(IkError, match="not a number at position 1"):
        parse_values("1,many")


def test_parse_values_rejects_infinite():
    with pytest.raises(IkError, match="value 0 must be finite"):
        parse_values("inf,1")


def test_parse_target_two_values():
    assert parse_target("1.0,0.8") == (1.0, 0.8)


def test_parse_target_three_values():
    assert parse_target("1.0,0.8,45") == (1.0, 0.8, 45.0)


def test_parse_target_wrong_count():
    with pytest.raises(IkError, match="got 1 value"):
        parse_target("1.0")


# --------------------------------------------------------------------------- #
# Model properties
# --------------------------------------------------------------------------- #
def test_arm_properties(planar2):
    assert planar2.n_joints == 2
    assert planar2.inner_reach == pytest.approx(0.2)
    assert planar2.outer_reach == pytest.approx(1.8)


def test_inner_reach_is_never_negative(planar3):
    assert planar3.inner_reach == 0.0


def test_solution_to_dict_rounds():
    solution = IkSolution(method="analytic", arm="planar2",
                          target=(1.0, 0.8), q=(0.0, 90.0),
                          residual=0.0, position_error=0.0, yaw_error=0.0,
                          iterations=0, converged=True, extra="elbow up")
    payload = solution.to_dict()
    assert payload["q_deg"] == [0.0, 90.0]
    assert payload["converged"] is True
    assert payload["extra"] == "elbow up"


# --------------------------------------------------------------------------- #
# Planar FK and Jacobian
# --------------------------------------------------------------------------- #
def test_planar_fk_straight_chain():
    point = planar_fk([1.0, 0.5], np.zeros(2))
    assert point == pytest.approx([1.5, 0.0])


def test_planar_fk_uses_cumulative_angles():
    point = planar_fk([1.0, 1.0], np.deg2rad([90.0, -90.0]))
    assert point == pytest.approx([1.0, 1.0])


def test_planar_fk_with_yaw_reports_total_rotation():
    point = planar_fk([1.0, 0.5], np.deg2rad([10.0, 20.0]), with_yaw=True)
    assert point[2] == pytest.approx(np.deg2rad(30.0))


def test_jacobian_matches_finite_differences():
    links = [0.6, 0.5, 0.3]
    q = np.deg2rad([37.0, -22.0, 15.0])
    analytic = planar_jacobian(links, q, with_yaw=True)
    numeric = np.zeros_like(analytic)
    h = 1e-6
    for k in range(3):
        plus, minus = q.copy(), q.copy()
        plus[k] += h
        minus[k] -= h
        numeric[:, k] = (planar_fk(links, plus, with_yaw=True)
                         - planar_fk(links, minus, with_yaw=True)) / (2 * h)
    assert np.allclose(analytic, numeric, atol=1e-6)


def test_jacobian_yaw_row_is_one():
    jacobian = planar_jacobian([0.5, 0.4], np.zeros(2), with_yaw=True)
    assert jacobian.shape == (3, 2)
    assert list(jacobian[2]) == [1.0, 1.0]


def test_workspace_annulus_planar2():
    assert workspace_annulus([1.0, 0.8]) == pytest.approx((0.2, 1.8))


def test_workspace_annulus_with_a_hole():
    assert workspace_annulus([1.2, 0.4]) == pytest.approx((0.8, 1.6))


# --------------------------------------------------------------------------- #
# Reachability
# --------------------------------------------------------------------------- #
def test_check_reachable_accepts_a_valid_point(planar2):
    assert check_reachable(planar2, (1.0, 0.8)) == (1.0, 0.8)


def test_check_reachable_rejects_wrong_shape(planar2):
    with pytest.raises(IkError, match="target must be x,y or x,y,yaw"):
        check_reachable(planar2, (1.0,))


def test_check_reachable_rejects_non_finite(planar2):
    with pytest.raises(IkError, match="target must be finite"):
        check_reachable(planar2, (float("nan"), 0.0))


def test_check_reachable_rejects_outer(planar2):
    with pytest.raises(IkError, match="outside reachable annulus"):
        check_reachable(planar2, (2.5, 0.0))


def test_check_reachable_rejects_inner_hole(arms):
    with pytest.raises(IkError, match="outside reachable annulus"):
        check_reachable(arms["long2"], (0.1, 0.0))


def test_check_reachable_rejects_yaw_outside_limits():
    arm = ArmIk(name="narrow", links=(0.6, 0.5, 0.3),
                limits=((-90.0, 90.0), (-90.0, 90.0), (-90.0, 90.0)))
    with pytest.raises(IkError, match="yaw .* outside"):
        check_reachable(arm, (0.5, 0.3, 300.0))


def test_check_reachable_rejects_pinned_yaw_wrist(planar3):
    with pytest.raises(IkError, match="wrist point"):
        check_reachable(planar3, (0.4, 0.9, -60.0))


def test_within_limits_true(planar2):
    assert within_limits(planar2, (0.0, 90.0)) is True


def test_within_limits_false(planar2):
    assert within_limits(planar2, (0.0, 200.0)) is False


def test_within_limits_wrong_size(planar2):
    assert within_limits(planar2, (0.0,)) is False


# --------------------------------------------------------------------------- #
# Analytic solver
# --------------------------------------------------------------------------- #
def test_solve_2link_straight_reach(planar2):
    solution = solve_2link(planar2, (1.8, 0.0))
    assert solution.converged is True
    assert solution.q == pytest.approx((0.0, 0.0), abs=1e-9)
    assert solution.residual < 1e-9


def test_solve_2link_elbow_branches_differ(planar2):
    up = solve_2link(planar2, (1.0, 0.8), elbow="up")
    down = solve_2link(planar2, (1.0, 0.8), elbow="down")
    assert up.q[1] > 0.0 > down.q[1]
    assert abs(up.q[1]) == pytest.approx(abs(down.q[1]), abs=1e-6)
    assert up.extra == "elbow up"
    assert down.extra == "elbow down"


def test_solve_2link_round_trips(planar2):
    target = (0.3, 0.4)
    for elbow in ("up", "down"):
        solution = solve_2link(planar2, target, elbow=elbow)
        achieved = planar_fk(planar2.links, np.deg2rad(solution.q))
        assert achieved == pytest.approx(list(target), abs=1e-9)
        assert solution.position_error < 1e-9
        assert solution.iterations == 0


def test_solve_2link_rejects_three_link_arm(planar3):
    with pytest.raises(IkError, match="needs exactly 2 links"):
        solve_2link(planar3, (1.0, 0.5))


def test_solve_2link_rejects_unknown_elbow(planar2):
    with pytest.raises(IkError, match="elbow must be"):
        solve_2link(planar2, (1.0, 0.8), elbow="sideways")


def test_solve_2link_rejects_yaw_target(planar2):
    with pytest.raises(IkError, match="accepts x,y only"):
        solve_2link(planar2, (1.0, 0.8, 10.0))


def test_solve_2link_rejects_unreachable(planar2):
    with pytest.raises(IkError, match="target unreachable"):
        solve_2link(planar2, (2.5, 0.0))


def test_solve_2link_rejects_bad_target_shape(planar2):
    with pytest.raises(IkError, match="target must be x,y or x,y,yaw"):
        solve_2link(planar2, (1.0,))


def test_solve_2link_rejects_non_finite_target(planar2):
    with pytest.raises(IkError, match="target must be finite"):
        solve_2link(planar2, (float("inf"), 0.0))


# --------------------------------------------------------------------------- #
# Damped least squares
# --------------------------------------------------------------------------- #
def test_solve_dls_needs_two_links():
    arm = ArmIk(name="one", links=(1.0,), limits=((-180.0, 180.0),))
    with pytest.raises(IkError, match="at least 2 links"):
        solve_dls(arm, (1.0, 0.0))


def test_solve_dls_rejects_non_positive_links():
    arm = ArmIk(name="bad", links=(1.0, 0.0),
                limits=((-180.0, 180.0), (-180.0, 180.0)))
    with pytest.raises(IkError, match="link lengths must be > 0"):
        solve_dls(arm, (1.0, 0.0))


def test_solve_dls_rejects_bad_damping(planar3):
    with pytest.raises(IkError, match="damping must be > 0"):
        solve_dls(planar3, (0.9, 0.2, 0.0), damping=0.0)


def test_solve_dls_rejects_bad_tolerance(planar3):
    with pytest.raises(IkError, match="tol must be > 0"):
        solve_dls(planar3, (0.9, 0.2, 0.0), tol=-1.0)


def test_solve_dls_rejects_bad_iteration_budget(planar3):
    with pytest.raises(IkError, match="max_iters must be >= 1"):
        solve_dls(planar3, (0.9, 0.2, 0.0), max_iters=0)


def test_solve_dls_rejects_wrong_q0_size(planar3):
    with pytest.raises(IkError, match="q0 must have 3 values"):
        solve_dls(planar3, (0.9, 0.2, 0.0), q0=[1.0, 2.0])


def test_solve_dls_rejects_non_finite_q0(planar3):
    with pytest.raises(IkError, match="q0 must be finite"):
        solve_dls(planar3, (0.9, 0.2, 0.0), q0=[0.0, float("nan"), 0.0])


def test_solve_dls_converges_on_planar3(planar3):
    solution = solve_dls(planar3, (1.0, 0.5, 45.0))
    assert solution.converged is True
    assert solution.residual < 1e-9
    assert solution.position_error < 1e-8
    assert solution.method == "dls"


def test_solve_dls_honours_yaw(planar3):
    solution = solve_dls(planar3, (0.9, 0.2, 30.0))
    assert abs(solution.yaw_error) < 1e-6


def test_solve_dls_restarts_escape_a_local_minimum(planar3):
    stalled = solve_dls(planar3, STALL_TARGET, restarts=False)
    rescued = solve_dls(planar3, STALL_TARGET)
    assert stalled.converged is False
    assert rescued.converged is True
    assert rescued.residual < 1e-9
    assert "restart" in rescued.extra


def test_solve_dls_is_deterministic(planar3):
    first = solve_dls(planar3, STALL_TARGET)
    second = solve_dls(planar3, STALL_TARGET)
    assert first.q == pytest.approx(second.q, abs=1e-12)
    assert first.iterations == second.iterations


def test_solve_dls_respects_the_iteration_budget(planar3):
    solution = solve_dls(planar3, (0.9, 0.2, 0.0), max_iters=1,
                         restarts=False)
    assert solution.converged is False
    assert solution.iterations == 1
    assert solution.residual > 1e-3


def test_solve_dls_reports_damping(planar3):
    solution = solve_dls(planar3, (0.9, 0.2, 0.0), damping=0.2)
    assert "damping 0.2" in solution.extra


def test_solve_dls_accepts_a_q0_guess(planar2):
    solution = solve_dls(planar2, (1.0, 0.8), q0=[10.0, 10.0],
                         restarts=False)
    assert solution.converged is True
    assert solution.residual < 1e-9


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
def test_solve_rejects_unknown_method(planar2):
    with pytest.raises(IkError, match="method must be one of"):
        solve(planar2, (1.0, 0.8), method="magic")


def test_solve_auto_uses_analytic_for_two_links(planar2):
    assert solve(planar2, (1.0, 0.8)).method == "analytic"


def test_solve_auto_uses_dls_for_three_links(planar3):
    assert solve(planar3, (1.0, 0.5, 45.0)).method == "dls"


def test_solve_forced_analytic_on_three_links_fails(planar3):
    with pytest.raises(IkError, match="needs exactly 2 links"):
        solve(planar3, (1.0, 0.5), method="analytic")


def test_solve_elbow_is_forwarded(planar2):
    assert solve(planar2, (1.0, 0.8), elbow="down").extra == "elbow down"


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def test_render_solution_contains_the_numbers(planar2):
    solution = solve_2link(planar2, (1.0, 0.8))
    text = render_solution(solution, planar2)
    assert "IK SOLUTION" in text
    assert "target" in text and "solution" in text
    assert "residual" in text
    assert "converged: yes" in text


def test_render_solution_cross_checks_fk(planar2):
    solution = solve_2link(planar2, (1.0, 0.8))
    text = render_solution(solution, planar2)
    assert "FK check" in text
    assert "x = +1.0000 m" in text


def test_render_solution_without_arm():
    solution = solve_2link(load_arms(ARMS_FILE)["planar2"], (1.0, 0.8))
    assert "FK check" not in render_solution(solution)


def test_render_table_lists_every_row(planar2):
    rows = [("first", solve_2link(planar2, (1.0, 0.8))),
            ("second", solve_2link(planar2, (0.3, 0.4)))]
    text = render_table(rows)
    assert "TARGET" in text and "METHOD" in text
    assert "first" in text and "second" in text
    assert text.count("converged") == 2


def test_render_table_marks_failures():
    failed = IkSolution(method="dls", arm="x", target=(0.0, 0.0),
                        q=(0.0, 0.0), residual=1.0, position_error=1.0,
                        yaw_error=0.0, iterations=3, converged=False)
    assert "FAILED" in render_table([("bad", failed)])


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


def test_cli_single_target(capsys):
    assert main(["--target", "1.0,0.8", "--arm", "planar2"]) == 0
    out = capsys.readouterr().out
    assert "IK SOLUTION" in out
    assert "converged: yes" in out


def test_cli_elbow_down(capsys):
    assert main(["--target", "1.0,0.8", "--arm", "planar2",
                 "--elbow", "down"]) == 0
    assert "elbow down" in capsys.readouterr().out


def test_cli_bad_target(capsys):
    assert main(["--target", "1.0", "--arm", "planar2"]) == 2
    assert "target must be" in capsys.readouterr().err


def test_cli_bad_damping(capsys):
    assert main(["--target", "1.0,0.8", "--arm", "planar2",
                 "--damping", "0"]) == 2
    assert "damping must be > 0" in capsys.readouterr().err


def test_cli_batch(capsys):
    assert main(["--targets", str(TARGETS_FILE)]) == 0
    out = capsys.readouterr().out
    assert "up_left" in out
    assert "wrist" in out


def test_cli_batch_quiet(capsys):
    assert main(["--targets", str(TARGETS_FILE), "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_json_export(tmp_path):
    out = tmp_path / "solutions.json"
    assert main(["--targets", str(TARGETS_FILE), "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["solutions"]) == 9
    assert payload["arms"] == ["planar2", "planar3", "long2", "wrist4"]
    assert payload["solutions"][0]["method"] == "analytic"


def test_cli_missing_targets_file(tmp_path, capsys):
    assert main(["--targets", str(tmp_path / "ghost.csv")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_unknown_arm(capsys):
    assert main(["--target", "1.0,0.8", "--arm", "ghost"]) == 2
    assert "unknown arm" in capsys.readouterr().err


def test_cli_analytic_on_three_links(capsys):
    assert main(["--target", "1.0,0.5", "--arm", "planar3",
                 "--method", "analytic"]) == 2
    assert "needs exactly 2 links" in capsys.readouterr().err


def test_cli_bad_q0(capsys):
    assert main(["--target", "1.0,0.5", "--arm", "planar3",
                 "--q0", "1,2"]) == 2
    assert "q0 must have 3 values" in capsys.readouterr().err


def test_bundled_files_exist():
    assert DEMO_ARMS.is_file()
    assert DEMO_TARGETS.is_file()
