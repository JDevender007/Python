"""Tests for the exit-status lab: declared codes, quoting and verdicts."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import main as cli  # noqa: E402
import ssh_tool  # noqa: E402
from ssh_tool import (  # noqa: E402
    LEGACY_FAILURE_CHECK,
    LEGACY_SERVICE_CHECK,
    Outcome,
    Result,
    SshError,
    Task,
    audit,
    build_command,
    evaluate,
    first_line,
    legacy_failed,
    legacy_service_ok,
    legacy_split,
    load_results,
    load_tasks,
    measure,
    pair_up,
    parse_ok_codes,
    quote_arg,
    render_outcomes,
    report,
    run_demo,
    split_argv,
    verdict,
)


def task(task_id: int = 1, command: str = "true", ok_codes: tuple[int, ...] = (0,)) -> Task:
    return Task(task_id=task_id, command=command, ok_codes=ok_codes, note="note")


def result(task_id: int = 1, command: str = "true", exit_code: int = 0,
           output: tuple[str, ...] = ()) -> Result:
    return Result(task_id=task_id, command=command, output=output, exit_code=exit_code)


def session(body: str) -> str:
    return body


# --------------------------------------------------------------------------- #
# quoting one argument
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw", ["nginx", "/var/log/app.log", "/", "0", "a-b_c.d:e=f@g%h+i,j", "-q"]
)
def test_safe_arguments_are_left_alone(raw):
    assert quote_arg(raw) == raw


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/srv/app data", "'/srv/app data'"),
        ("/tmp; rm -rf /", "'/tmp; rm -rf /'"),
        ("$(whoami)", "'$(whoami)'"),
        ("a*b", "'a*b'"),
    ],
)
def test_unsafe_arguments_are_single_quoted(raw, expected):
    assert quote_arg(raw) == expected


def test_a_single_quote_is_escaped_by_leaving_the_quote():
    assert quote_arg("it's") == "'it'\\''s'"


def test_a_quoted_argument_round_trips():
    for raw in ["/srv/app data", "it's", "a;b", "$x", "two words here"]:
        assert split_argv(quote_arg(raw)) == [raw]


@pytest.mark.parametrize("bad", ["a\nb", "a\rb", "a\0b"])
def test_an_argument_with_a_control_character_is_refused(bad):
    with pytest.raises(SshError, match="newline or a NUL"):
        quote_arg(bad)


@pytest.mark.parametrize("bad", ["", "   "])
def test_an_empty_argument_is_refused(bad):
    with pytest.raises(SshError, match="must not be empty"):
        quote_arg(bad)


def test_a_non_text_argument_is_refused():
    with pytest.raises(SshError, match="must be text"):
        quote_arg(22)


# --------------------------------------------------------------------------- #
# building a command line
# --------------------------------------------------------------------------- #
def test_build_command_joins_the_vector():
    assert build_command(["df", "-h", "/"]) == "df -h /"


def test_build_command_quotes_only_what_needs_it():
    assert build_command(["test", "-d", "/srv/app data"]) == "test -d '/srv/app data'"


def test_build_command_of_one_word_is_that_word():
    assert build_command(["uptime"]) == "uptime"


def test_build_command_refuses_an_empty_vector():
    with pytest.raises(SshError, match="at least one argument"):
        build_command([])


def test_build_command_refuses_a_bad_argument_inside_the_vector():
    with pytest.raises(SshError, match="newline or a NUL"):
        build_command(["ls", "a\nb"])


# --------------------------------------------------------------------------- #
# splitting a command line
# --------------------------------------------------------------------------- #
def test_split_argv_splits_on_whitespace():
    assert split_argv("df -h /") == ["df", "-h", "/"]


def test_split_argv_collapses_repeated_spaces():
    assert split_argv("  df    -h   /  ") == ["df", "-h", "/"]


def test_split_argv_keeps_a_quoted_path_whole():
    assert split_argv("test -d '/srv/app data'") == ["test", "-d", "/srv/app data"]


def test_split_argv_honours_a_backslash_escape():
    assert split_argv("test -d /srv/app\\ data") == ["test", "-d", "/srv/app data"]


def test_split_argv_keeps_an_empty_quoted_word():
    assert split_argv("printf ''") == ["printf", ""]


def test_split_argv_treats_quotes_inside_a_word_as_literal():
    assert split_argv("echo a'b'c") == ["echo", "abc"]


def test_split_argv_does_not_expand_a_dollar_sign():
    assert split_argv("echo '$(whoami)'") == ["echo", "$(whoami)"]


@pytest.mark.parametrize("bad", ["test -d '/srv/app", "echo 'unterminated"])
def test_split_argv_refuses_an_unterminated_quote(bad):
    with pytest.raises(SshError, match="unterminated single quote"):
        split_argv(bad)


def test_split_argv_refuses_a_trailing_backslash():
    with pytest.raises(SshError, match="may not end"):
        split_argv("echo a\\")


@pytest.mark.parametrize("bad", ["echo a\nb", "echo a\0b"])
def test_split_argv_refuses_a_control_character(bad):
    with pytest.raises(SshError, match="newline or a NUL"):
        split_argv(bad)


@pytest.mark.parametrize("bad", ["", "   "])
def test_split_argv_refuses_an_empty_line(bad):
    with pytest.raises(SshError, match="at least one word|must not be empty"):
        split_argv(bad)


def test_split_argv_refuses_non_text():
    with pytest.raises(SshError, match="must be text"):
        split_argv(None)


def test_legacy_split_ignores_quotes():
    assert legacy_split("test -d '/srv/app data'") == ["test", "-d", "'/srv/app", "data'"]


def test_the_legacy_split_turns_three_words_into_four():
    argv = split_argv("test -d '/srv/app data'")
    assert len(argv) == 3
    assert len(legacy_split("test -d '/srv/app data'")) == 4


# --------------------------------------------------------------------------- #
# declared success codes
# --------------------------------------------------------------------------- #
def test_parse_ok_codes_reads_one_code():
    assert parse_ok_codes("0") == (0,)


def test_parse_ok_codes_reads_two_codes():
    assert parse_ok_codes("0;1") == (0, 1)


def test_parse_ok_codes_tolerates_spaces():
    assert parse_ok_codes(" 0 ; 1 ") == (0, 1)


def test_parse_ok_codes_reads_a_high_code():
    assert parse_ok_codes("255") == (255,)


def test_parse_ok_codes_refuses_a_non_number():
    with pytest.raises(SshError, match="whole numbers"):
        parse_ok_codes("0;ok")


def test_parse_ok_codes_refuses_an_out_of_range_code():
    with pytest.raises(SshError, match="0\\.\\.255"):
        parse_ok_codes("256")


def test_parse_ok_codes_refuses_a_negative_code():
    with pytest.raises(SshError, match="0\\.\\.255"):
        parse_ok_codes("-1")


def test_parse_ok_codes_refuses_a_duplicate():
    with pytest.raises(SshError, match="repeats a code"):
        parse_ok_codes("0;0;1")


def test_parse_ok_codes_refuses_an_empty_entry():
    with pytest.raises(SshError, match="empty entry"):
        parse_ok_codes("0;;1")


def test_parse_ok_codes_refuses_an_empty_string():
    with pytest.raises(SshError, match="must not be empty"):
        parse_ok_codes("   ")


# --------------------------------------------------------------------------- #
# tasks
# --------------------------------------------------------------------------- #
def test_load_tasks_reads_the_bundled_file():
    tasks = load_tasks()
    assert len(tasks) == 5
    assert [row.task_id for row in tasks] == [1, 2, 3, 4, 5]


def test_load_tasks_pins_the_declared_codes():
    tasks = {row.task_id: row for row in load_tasks()}
    assert tasks[1].ok_codes == (0,)
    assert tasks[2].ok_codes == (0, 1)
    assert tasks[3].ok_codes == (0,)
    assert tasks[4].ok_codes == (0,)
    assert tasks[5].ok_codes == (0,)


def test_load_tasks_keeps_the_command_text():
    tasks = {row.task_id: row for row in load_tasks()}
    assert tasks[2].command == "grep -q ERROR /var/log/app.log"
    assert tasks[4].command == "test -d '/srv/app data'"


def test_a_task_exposes_its_argument_vector():
    tasks = {row.task_id: row for row in load_tasks()}
    assert tasks[4].argv == ["test", "-d", "/srv/app data"]


def test_load_tasks_refuses_a_missing_file(tmp_path):
    with pytest.raises(SshError, match="file not found"):
        load_tasks(tmp_path / "nope.csv")


def test_load_tasks_refuses_an_empty_file(tmp_path):
    path = tmp_path / "tasks.csv"
    path.write_text("task_id,command,ok_codes,note\n", encoding="utf-8")
    with pytest.raises(SshError, match="holds no tasks"):
        load_tasks(path)


def test_load_tasks_refuses_a_missing_column(tmp_path):
    path = tmp_path / "tasks.csv"
    path.write_text("task_id,command\n1,true\n", encoding="utf-8")
    with pytest.raises(SshError, match="missing column"):
        load_tasks(path)


def test_load_tasks_refuses_a_duplicate_id(tmp_path):
    path = tmp_path / "tasks.csv"
    path.write_text(
        "task_id,command,ok_codes,note\n1,true,0,a\n1,false,0,b\n", encoding="utf-8"
    )
    with pytest.raises(SshError, match="must be unique"):
        load_tasks(path)


def test_load_tasks_refuses_a_non_numeric_id(tmp_path):
    path = tmp_path / "tasks.csv"
    path.write_text("task_id,command,ok_codes,note\none,true,0,a\n", encoding="utf-8")
    with pytest.raises(SshError, match="whole number"):
        load_tasks(path)


def test_load_tasks_refuses_a_zero_id(tmp_path):
    path = tmp_path / "tasks.csv"
    path.write_text("task_id,command,ok_codes,note\n0,true,0,a\n", encoding="utf-8")
    with pytest.raises(SshError, match="must be positive"):
        load_tasks(path)


def test_load_tasks_refuses_a_command_copy_that_does_not_split(tmp_path):
    path = tmp_path / "tasks.csv"
    path.write_text(
        "task_id,command,ok_codes,note\n1,echo 'oops,0,a\n", encoding="utf-8"
    )
    with pytest.raises(SshError, match="unterminated single quote"):
        load_tasks(path)


def test_load_tasks_refuses_a_task_with_no_command(tmp_path):
    path = tmp_path / "tasks.csv"
    path.write_text("task_id,command,ok_codes,note\n1,  ,0,a\n", encoding="utf-8")
    with pytest.raises(SshError, match="must not be empty"):
        load_tasks(path)


# --------------------------------------------------------------------------- #
# results
# --------------------------------------------------------------------------- #
def test_load_results_reads_the_bundled_session():
    results = load_results()
    assert len(results) == 5
    assert [row.exit_code for row in results] == [3, 1, 0, 1, 0]


def test_load_results_keeps_the_output_lines():
    results = {row.task_id: row for row in load_results()}
    assert results[1].output == ("inactive",)
    assert results[2].output == ()
    assert results[3].output[0].startswith("Filesystem")


def test_load_results_keeps_the_recorded_command():
    results = {row.task_id: row for row in load_results()}
    assert results[4].command == "test -d '/srv/app data'"


def test_load_results_refuses_a_missing_file(tmp_path):
    with pytest.raises(SshError, match="file not found"):
        load_results(tmp_path / "nope.log")


def test_load_results_refuses_non_ascii_bytes(tmp_path):
    path = tmp_path / "session.log"
    path.write_bytes(b"# task_id=1\n$ true\n\xff\n? 0\n")
    with pytest.raises(SshError, match="not ASCII text"):
        load_results(path)


def test_load_results_refuses_an_empty_file(tmp_path):
    path = tmp_path / "session.log"
    path.write_text("\n\n", encoding="ascii")
    with pytest.raises(SshError, match="holds no results"):
        load_results(path)


def test_load_results_refuses_a_line_before_a_header(tmp_path):
    path = tmp_path / "session.log"
    path.write_text("$ true\n? 0\n", encoding="ascii")
    with pytest.raises(SshError, match="before any '# task_id=' header"):
        load_results(path)


def test_load_results_refuses_a_block_without_an_exit(tmp_path):
    path = tmp_path / "session.log"
    path.write_text("# task_id=1\n$ true\n", encoding="ascii")
    with pytest.raises(SshError, match="no exit line"):
        load_results(path)


def test_load_results_refuses_a_missing_exit_on_an_earlier_block(tmp_path):
    path = tmp_path / "session.log"
    path.write_text("# task_id=1\n$ true\n# task_id=2\n$ true\n? 0\n", encoding="ascii")
    with pytest.raises(SshError, match="block for task 1 has no exit line"):
        load_results(path)


def test_load_results_refuses_two_commands(tmp_path):
    path = tmp_path / "session.log"
    path.write_text("# task_id=1\n$ true\n$ false\n? 0\n", encoding="ascii")
    with pytest.raises(SshError, match="two command lines"):
        load_results(path)


def test_load_results_refuses_an_exit_before_the_command(tmp_path):
    path = tmp_path / "session.log"
    path.write_text("# task_id=1\n? 0\n", encoding="ascii")
    with pytest.raises(SshError, match="exit line before its command"):
        load_results(path)


def test_load_results_refuses_output_before_the_command(tmp_path):
    path = tmp_path / "session.log"
    path.write_text("# task_id=1\nhello\n? 0\n", encoding="ascii")
    with pytest.raises(SshError, match="output before the command"):
        load_results(path)


def test_load_results_refuses_a_line_after_the_exit(tmp_path):
    path = tmp_path / "session.log"
    path.write_text("# task_id=1\n$ true\n? 0\nextra\n", encoding="ascii")
    with pytest.raises(SshError, match="follows the exit line"):
        load_results(path)


def test_load_results_refuses_an_exit_code_above_255(tmp_path):
    path = tmp_path / "session.log"
    path.write_text("# task_id=1\n$ true\n? 256\n", encoding="ascii")
    with pytest.raises(SshError, match="0\\.\\.255"):
        load_results(path)


def test_load_results_skips_blank_lines(tmp_path):
    path = tmp_path / "session.log"
    path.write_text("# task_id=1\n\n$ true\n\n? 0\n", encoding="ascii")
    assert len(load_results(path)) == 1


# --------------------------------------------------------------------------- #
# pairing
# --------------------------------------------------------------------------- #
def test_pair_up_matches_every_task():
    pairs = pair_up(load_tasks(), load_results())
    assert len(pairs) == 5
    assert [task.task_id for task, _ in pairs] == [1, 2, 3, 4, 5]


def test_pair_up_refuses_a_missing_result():
    with pytest.raises(SshError, match="task 2 has no result"):
        pair_up([task(1), task(2)], [result(1)])


def test_pair_up_refuses_an_unknown_result():
    with pytest.raises(SshError, match="unknown task"):
        pair_up([task(1)], [result(1), result(9)])


def test_pair_up_refuses_a_repeated_result_id():
    with pytest.raises(SshError, match="repeats a task_id"):
        pair_up([task(1)], [result(1), result(1)])


def test_pair_up_refuses_a_different_recorded_command():
    with pytest.raises(SshError, match="was recorded as"):
        pair_up([task(1, "true")], [result(1, "false")])


# --------------------------------------------------------------------------- #
# verdicts
# --------------------------------------------------------------------------- #
def test_a_declared_code_is_success():
    outcome = verdict(task(1, "true", (0,)), result(1, "true", 0))
    assert outcome.ok is True
    assert "is one of [0]" in outcome.reason


def test_a_nonzero_declared_code_is_success():
    outcome = verdict(task(2, "grep -q x f", (0, 1)), result(2, "grep -q x f", 1))
    assert outcome.ok is True
    assert "is one of [0, 1]" in outcome.reason


def test_a_code_outside_the_declaration_is_a_failure():
    outcome = verdict(task(1, "true", (0,)), result(1, "true", 3))
    assert outcome.ok is False
    assert "is not one of [0]" in outcome.reason


def test_a_zero_outside_the_declaration_is_a_failure():
    outcome = verdict(task(1, "true", (1,)), result(1, "true", 0))
    assert outcome.ok is False


def test_evaluate_returns_one_outcome_per_pair():
    pairs = pair_up(load_tasks(), load_results())
    outcomes = evaluate(pairs)
    assert len(outcomes) == 5
    assert all(isinstance(outcome, Outcome) for outcome in outcomes)


def test_evaluate_pins_the_bundled_verdicts():
    outcomes = {outcome.task_id: outcome.ok for outcome in evaluate(pair_up(load_tasks(), load_results()))}
    assert outcomes == {1: False, 2: True, 3: True, 4: False, 5: True}


def test_legacy_rule_fails_every_nonzero_exit():
    assert legacy_failed(load_results()) == [1, 2, 4]


def test_the_two_rules_differ_on_exactly_the_grep():
    results = load_results()
    declared = {outcome.task_id for outcome in evaluate(pair_up(load_tasks(), results)) if not outcome.ok}
    assert set(legacy_failed(results)) - declared == {2}


def test_legacy_service_check_reads_inactive_as_active():
    assert legacy_service_ok(("inactive",)) is True


def test_legacy_service_check_is_false_without_the_word():
    assert legacy_service_ok(("failed",)) is False


def test_legacy_service_check_matches_a_mention():
    assert legacy_service_ok(("the unit is not active",)) is True


def test_first_line_of_an_empty_output_is_empty():
    assert first_line(result(1, "true", 0, ())) == ""


def test_first_line_of_a_multi_line_output():
    assert first_line(result(1, "df -h /", 0, ("Filesystem", "/dev/sda1"))) == "Filesystem"


# --------------------------------------------------------------------------- #
# measure and report
# --------------------------------------------------------------------------- #
def test_measure_pins_the_seed():
    measured = measure()
    assert len(measured["tasks"]) == 5
    assert len(measured["results"]) == 5
    assert measured["ok"] == [2, 3, 5]
    assert measured["failed"] == [1, 4]
    assert measured["legacy_failed"] == [1, 2, 4]


def test_measure_pins_the_service_contradiction():
    measured = measure()
    assert measured["service_output"] == "inactive"
    assert measured["service_exit"] == 3
    assert measured["service_ok"] is False
    assert measured["legacy_service_ok"] is True


def test_measure_pins_the_quoting_gap():
    measured = measure()
    assert measured["naive_argv"] == ["test", "-d", "'/srv/app", "data'"]
    assert measured["argv"] == ["test", "-d", "/srv/app data"]
    assert measured["round_trip"] == "test -d '/srv/app data'"


def test_measure_reads_the_session_beside_the_tasks(tmp_path):
    (tmp_path / "tasks.csv").write_text(
        "task_id,command,ok_codes,note\n1,true,0,a\n", encoding="utf-8"
    )
    (tmp_path / "session.log").write_text(
        "# task_id=1\n$ true\n? 3\n", encoding="ascii"
    )
    measured = measure(tmp_path / "tasks.csv")
    assert measured["failed"] == [1]
    assert measured["legacy_failed"] == [1]


def test_measure_accepts_an_explicit_session_path(tmp_path):
    (tmp_path / "tasks.csv").write_text(
        "task_id,command,ok_codes,note\n1,true,0,a\n", encoding="utf-8"
    )
    other = tmp_path / "other.log"
    other.write_text("# task_id=1\n$ true\n? 0\n", encoding="ascii")
    measured = measure(tmp_path / "tasks.csv", session_path=other)
    assert measured["ok"] == [1]


def test_measure_refuses_a_session_for_an_unknown_task(tmp_path):
    (tmp_path / "tasks.csv").write_text(
        "task_id,command,ok_codes,note\n1,true,0,a\n", encoding="utf-8"
    )
    (tmp_path / "session.log").write_text(
        "# task_id=1\n$ true\n? 0\n# task_id=2\n$ true\n? 0\n", encoding="ascii"
    )
    with pytest.raises(SshError, match="unknown task"):
        measure(tmp_path / "tasks.csv")


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "Task(" not in text
    assert payload["tasks"] == 5
    assert payload["ok"] == [2, 3, 5]
    assert payload["failed"] == [1, 4]
    assert payload["legacy_failed"] == [1, 2, 4]
    assert payload["service_output"] == "inactive"
    assert payload["argv"] == ["test", "-d", "/srv/app data"]
    assert payload["outcomes"][0] == {
        "task_id": 1, "ok": False, "reason": "exit 3 is not one of [0]"
    }


def test_report_keeps_the_transcript_plain():
    payload = report(measure())
    assert payload["results"][0] == {
        "task_id": 1,
        "command": "systemctl is-active nginx",
        "exit_code": 3,
        "output": ["inactive"],
    }


def test_render_outcomes_marks_the_failures():
    rendered = render_outcomes(measure())
    assert "FAILED" in rendered
    assert "ok" in rendered
    assert rendered.count("\n") == 5


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_audit_passes_every_check():
    results = audit(measure())
    assert len(results) == 18
    assert all(ok for _, ok in results)


def test_audit_names_are_unique():
    names = [name for name, _ in audit(measure())]
    assert len(names) == len(set(names))


def test_audit_negative_control_reader_that_fails_everything():
    def pessimistic(pairs):
        return [Outcome(task.task_id, False, "no") for task, _ in pairs]

    results = dict(audit(measure(), read_outcomes=pessimistic))
    assert results["the_verdicts_are_pinned"] is True
    assert results["verdicts_match_an_independent_comparison"] is False
    assert results["rebuild_is_deterministic"] is False


def test_audit_negative_control_reader_that_raises():
    def broken(pairs):
        raise SshError("boom")

    results = dict(audit(measure(), read_outcomes=broken))
    assert results["verdicts_match_an_independent_comparison"] is False
    assert results["rebuild_is_deterministic"] is False


def test_audit_negative_control_reader_that_drops_one():
    def short(pairs):
        return evaluate(pairs)[:-1]

    results = dict(audit(measure(), read_outcomes=short))
    assert results["verdicts_match_an_independent_comparison"] is False


def test_audit_detects_a_tampered_ok_list():
    measured = measure()
    measured["ok"] = [1, 2, 3, 5]
    results = dict(audit(measured))
    assert results["the_verdicts_are_pinned"] is False
    assert results["the_legacy_rule_fails_every_nonzero_exit"] is True


def test_audit_detects_a_tampered_legacy_failure_list():
    measured = measure()
    measured["legacy_failed"] = [1, 4]
    results = dict(audit(measured))
    assert results["the_legacy_rule_fails_every_nonzero_exit"] is False
    assert results["the_two_rules_differ_only_on_the_declared_grep"] is False


def test_audit_detects_a_tampered_service_output():
    measured = measure()
    measured["service_output"] = "active"
    assert dict(audit(measured))["the_service_check_is_wrong_about_a_stopped_unit"] is False


def test_audit_detects_a_tampered_naive_split():
    measured = measure()
    measured["naive_argv"] = ["test", "-d", "/srv/app data"]
    results = dict(audit(measured))
    assert results["the_naive_split_breaks_the_quoted_path"] is False
    assert results["the_quote_aware_split_keeps_one_path_argument"] is True


def test_audit_detects_a_tampered_round_trip():
    measured = measure()
    measured["round_trip"] = "test -d /srv/app data"
    assert dict(audit(measured))["a_command_round_trips_through_its_own_quoting"] is False


# --------------------------------------------------------------------------- #
# demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_returns_zero_and_ends_with_the_contract(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    second = capsys.readouterr().out
    assert first == second


def test_demo_prints_the_pinned_numbers(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "so the legacy check says running (True)" in out
    assert "legacy fails [1, 2, 4]; the declared codes fail [1, 4]" in out
    assert "naive split:  ['test', '-d', \"'/srv/app\", \"data'\"]" in out
    assert "18/18 checks pass" in out
    assert "FAIL " not in out.replace("FAILED", "")


def test_demo_output_is_ascii_and_silent_on_stderr(capsys):
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        run_demo()
    assert err.getvalue() == ""


def test_demo_output_is_ascii(capsys):
    run_demo()
    assert capsys.readouterr().out.isascii()


def test_the_legacy_snippets_are_kept_as_text():
    assert 'in output' in LEGACY_SERVICE_CHECK
    assert "exit_code != 0" in LEGACY_FAILURE_CHECK


def test_cli_demo_exits_zero():
    assert cli.main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_json_writes_a_report(tmp_path):
    target = tmp_path / "report.json"
    assert cli.main(["--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["ok"] == [2, 3, 5]
    assert payload["failed"] == [1, 4]


def test_cli_json_creates_the_parent_folder(tmp_path):
    target = tmp_path / "nested" / "deep" / "report.json"
    assert cli.main(["--json", str(target)]) == 0
    assert target.is_file()


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such/tasks.csv"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_bad_declared_code_exits_two(tmp_path, capsys):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "tasks.csv").write_text(
        "task_id,command,ok_codes,note\n1,true,ok,a\n", encoding="utf-8"
    )
    (folder / "session.log").write_text("# task_id=1\n$ true\n? 0\n", encoding="ascii")
    assert cli.main(["--file", str(folder / "tasks.csv")]) == 2
    assert "whole numbers" in capsys.readouterr().err


def test_cli_prints_the_summary(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "accepted [2, 3, 5], failed [1, 4]; the exit != 0 rule fails [1, 2, 4]" in out


def test_cli_quiet_json_still_writes(tmp_path):
    target = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(target)]) == 0
    assert target.is_file()


def test_module_audit_is_exposed():
    assert ssh_tool.audit is audit
