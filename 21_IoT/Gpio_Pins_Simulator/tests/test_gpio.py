"""Tests for the GPIO Pins Simulator project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main  # noqa: E402
from gpio import (  # noqa: E402
    DEFAULT_DEBOUNCE,
    EDGES,
    MAX_PIN,
    MIN_PIN,
    MODES,
    PULLS,
    SCENARIO_FILE,
    Board,
    Button,
    Debouncer,
    EdgeEvent,
    GpioError,
    Led,
    Pin,
    check_edge,
    check_level,
    check_mode,
    check_pin,
    check_pull,
    check_tick,
    load_scenario,
    render_report,
    run_demo,
    run_scenario,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENARIO = PROJECT_ROOT / "data" / "scenario.json"


@pytest.fixture()
def board() -> Board:
    return Board("test")


@pytest.fixture()
def out_pin(board):
    return board.add_pin(17, mode="output")


@pytest.fixture()
def in_pin(board):
    return board.add_pin(18, mode="input", pull="up")


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def test_check_pin_accepts_range():
    assert check_pin(MIN_PIN) == MIN_PIN
    assert check_pin(MAX_PIN) == MAX_PIN


@pytest.mark.parametrize("value", [-1, MAX_PIN + 1, 100])
def test_check_pin_rejects_out_of_range(value):
    with pytest.raises(GpioError, match="out of range"):
        check_pin(value)


@pytest.mark.parametrize("value", ["17", 17.0, None, True])
def test_check_pin_rejects_non_integer(value):
    with pytest.raises(GpioError, match="must be an integer"):
        check_pin(value)


def test_check_mode_normalises_case():
    assert check_mode("OUTPUT") == "output"


def test_check_mode_rejects_unknown():
    with pytest.raises(GpioError, match="invalid mode"):
        check_mode("analog")


def test_check_pull_accepts_all():
    assert [check_pull(pull) for pull in PULLS] == list(PULLS)


def test_check_pull_rejects_unknown():
    with pytest.raises(GpioError, match="invalid pull"):
        check_pull("sideways")


def test_check_level_accepts_bools():
    assert check_level(True) == 1
    assert check_level(False) == 0


@pytest.mark.parametrize("value", [2, -1, "1", None])
def test_check_level_rejects_bad_values(value):
    with pytest.raises(GpioError, match="level must be 0 or 1"):
        check_level(value)


def test_check_edge_accepts_all():
    assert [check_edge(edge) for edge in EDGES] == list(EDGES)


def test_check_edge_rejects_unknown():
    with pytest.raises(GpioError, match="invalid edge"):
        check_edge("sideways")


def test_check_tick_accepts_zero():
    assert check_tick(0) == 0


@pytest.mark.parametrize("value", [-5, 1.5, "10"])
def test_check_tick_rejects_bad_values(value):
    with pytest.raises(GpioError, match="non-negative integer"):
        check_tick(value)


# --------------------------------------------------------------------------- #
# Debouncer
# --------------------------------------------------------------------------- #
def test_debouncer_needs_at_least_one_sample():
    with pytest.raises(GpioError, match="min_stable must be >= 1"):
        Debouncer(0)


def test_debouncer_first_level_is_adopted_without_initial():
    debouncer = Debouncer(2)
    assert debouncer.feed(0) == 0
    assert debouncer.stable == 0


def test_debouncer_holds_initial_value():
    debouncer = Debouncer(2, initial=1)
    assert debouncer.feed(0) is None
    assert debouncer.stable == 1


def test_debouncer_accepts_a_sustained_level():
    debouncer = Debouncer(3, initial=1)
    assert debouncer.feed(0) is None
    assert debouncer.feed(0) is None
    assert debouncer.feed(0) == 0
    assert debouncer.stable == 0


def test_debouncer_resets_on_bounce():
    debouncer = Debouncer(3, initial=1)
    debouncer.feed(0)
    debouncer.feed(1)
    debouncer.feed(0)
    debouncer.feed(0)
    assert debouncer.stable == 1


def test_debouncer_ignores_repeats_of_the_stable_level():
    debouncer = Debouncer(2, initial=0)
    for level in (0, 0, 0):
        assert debouncer.feed(level) is None


def test_debouncer_to_dict_reports_state():
    debouncer = Debouncer(2, initial=1)
    debouncer.feed(0)
    payload = debouncer.to_dict()
    assert payload == {"min_stable": 2, "stable": 1, "candidate": 0,
                       "count": 1}


# --------------------------------------------------------------------------- #
# Pins
# --------------------------------------------------------------------------- #
def test_output_pin_starts_low_without_pull(board):
    pin = board.add_pin(17, mode="output", pull="up")
    assert pin.level == 0
    assert pin.pull == "none"


def test_input_pin_rests_at_the_pull_level(board):
    assert board.add_pin(5, mode="input", pull="up").level == 1
    assert board.add_pin(6, mode="input", pull="down").level == 0
    assert board.add_pin(7, mode="input", pull="none").level == 0


def test_pin_rest_level_helper():
    assert Pin(number=1, pull="up").rest_level() == 1
    assert Pin(number=1, pull="down").rest_level() == 0
    assert Pin(number=1, pull="none").rest_level() == 0


def test_pin_to_dict_without_pwm(out_pin):
    assert out_pin.to_dict() == {"number": 17, "mode": "output",
                                 "pull": "none", "level": 0, "events": 0}


def test_pin_to_dict_includes_pwm(board):
    board.add_pin(22, mode="output")
    board.pwm(22, 4.0, 25.0)
    payload = board.pin(22).to_dict()
    assert payload["pwm"] == {"frequency": 4.0, "duty": 25.0}


def test_add_pin_rejects_duplicates(board):
    board.add_pin(17, mode="output")
    with pytest.raises(GpioError, match="already claimed"):
        board.add_pin(17, mode="input")


def test_pin_lookup_of_unknown_pin(board):
    with pytest.raises(GpioError, match="not claimed"):
        board.pin(42)


def test_release_frees_the_pin(board, out_pin):
    released = board.release(17)
    assert released.number == 17
    with pytest.raises(GpioError, match="not claimed"):
        board.pin(17)


def test_release_clears_listeners_and_debouncers(board, in_pin):
    board.add_listener(18, lambda event: None)
    board.attach_debouncer(18)
    board.release(18)
    assert board._listeners == {}
    assert board._debouncers == {}


def test_pins_are_sorted_by_number(board):
    for number in (22, 5, 17):
        board.add_pin(number, mode="input", pull="down")
    assert [pin.number for pin in board.pins] == [5, 17, 22]


def test_board_name_must_not_be_blank():
    with pytest.raises(GpioError, match="board name"):
        Board("   ")


def test_board_name_is_trimmed():
    assert Board("  bench  ").name == "bench"


# --------------------------------------------------------------------------- #
# Writing and reading
# --------------------------------------------------------------------------- #
def test_write_sets_the_level(board, out_pin):
    assert board.write(17, 1) == 1
    assert board.read(17) == 1


def test_write_same_level_records_no_event(board, out_pin):
    board.write(17, 1)
    board.write(17, 1)
    assert len(board.edges(17)) == 1


def test_write_emits_rising_then_falling(board, out_pin):
    board.write(17, 1)
    board.write(17, 0)
    assert [event.edge for event in board.edges(17)] == ["rising", "falling"]


def test_write_to_input_is_rejected(board, in_pin):
    with pytest.raises(GpioError, match="is an input"):
        board.write(18, 1)


def test_read_returns_the_current_level(board, in_pin):
    assert board.read(18) == 1
    board.set_input(18, 0)
    assert board.read(18) == 0


def test_set_input_emits_a_falling_edge(board, in_pin):
    board.set_input(18, 0)
    events = board.edges(18)
    assert len(events) == 1
    assert events[0].edge == "falling"
    assert events[0].level == 0


def test_set_input_on_output_is_rejected(board, out_pin):
    with pytest.raises(GpioError, match="is an output"):
        board.set_input(17, 1)


def test_set_input_same_level_is_idempotent(board, in_pin):
    board.set_input(18, 1)
    assert board.edges(18) == []


def test_edges_filters_by_kind(board, out_pin):
    board.write(17, 1)
    board.write(17, 0)
    board.write(17, 1)
    assert len(board.edges(17, "rising")) == 2
    assert len(board.edges(17, "falling")) == 1
    assert len(board.edges(17, "both")) == 3


def test_edges_rejects_unknown_kind(board, out_pin):
    with pytest.raises(GpioError, match="invalid edge"):
        board.edges(17, "sideways")


def test_edge_event_to_dict(board, out_pin):
    board.advance(40)
    board.write(17, 1)
    payload = board.edges(17)[0].to_dict()
    assert payload == {"tick": 40, "pin": 17, "edge": "rising", "level": 1}


def test_edge_event_dataclass_defaults():
    event = EdgeEvent(tick=1, pin=2, edge="rising", level=1)
    assert event.pin == 2


# --------------------------------------------------------------------------- #
# Clocks and listeners
# --------------------------------------------------------------------------- #
def test_advance_increments_the_tick(board):
    assert board.advance(250) == 250
    assert board.advance(0) == 250
    assert board.advance(50) == 300


def test_advance_rejects_negative(board):
    with pytest.raises(GpioError, match="non-negative integer"):
        board.advance(-1)


def test_listener_sees_matching_edges(board, out_pin):
    seen: list[int] = []
    board.add_listener(17, lambda event: seen.append(event.level))
    board.write(17, 1)
    board.write(17, 0)
    assert seen == [1, 0]


def test_listener_can_filter_by_edge(board, out_pin):
    seen: list[str] = []
    board.add_listener(17, lambda event: seen.append(event.edge), edge="rising")
    board.write(17, 1)
    board.write(17, 0)
    assert seen == ["rising"]


def test_listener_requires_a_callable(board, out_pin):
    with pytest.raises(GpioError, match="must be callable"):
        board.add_listener(17, "not-callable")


def test_listener_receives_the_event_object(board, out_pin):
    captured: list[EdgeEvent] = []
    board.add_listener(17, captured.append)
    board.advance(10)
    board.write(17, 1)
    assert captured[0].tick == 10
    assert captured[0].edge == "rising"


# --------------------------------------------------------------------------- #
# Modes
# --------------------------------------------------------------------------- #
def test_set_mode_switches_to_output(board, in_pin):
    pin = board.set_mode(18, "output")
    assert pin.mode == "output"
    assert pin.level == 0
    assert pin.pull == "none"


def test_set_mode_switches_to_input_with_pull(board, out_pin):
    pin = board.set_mode(17, "input", "down")
    assert pin.mode == "input"
    assert pin.pull == "down"
    assert pin.level == 0


def test_set_mode_to_output_clears_pwm(board):
    board.add_pin(22, mode="output")
    board.pwm(22, 4.0, 25.0)
    board.set_mode(22, "output")
    assert board.pin(22).has_pwm is False


def test_attach_debouncer_requires_an_input(board, out_pin):
    with pytest.raises(GpioError, match="debouncing only applies to inputs"):
        board.attach_debouncer(17)


def test_debouncer_swallows_bounce(board, in_pin):
    board.attach_debouncer(18, min_stable=3)
    for level in (0, 1, 0, 0, 0):
        board.set_input(18, level)
    assert [event.edge for event in board.edges(18)] == ["falling"]


def test_debouncer_starts_at_the_pull_level(board, in_pin):
    debouncer = board.attach_debouncer(18, min_stable=2)
    assert debouncer.stable == 1


def test_debouncer_blocks_a_single_sample_glitch(board, in_pin):
    board.attach_debouncer(18, min_stable=2)
    board.set_input(18, 0)
    board.set_input(18, 1)
    assert board.read(18) == 1
    assert board.edges(18) == []


# --------------------------------------------------------------------------- #
# PWM
# --------------------------------------------------------------------------- #
def test_pwm_requires_an_output(board, in_pin):
    with pytest.raises(GpioError, match="PWM needs an output"):
        board.pwm(18, 4.0, 25.0)


@pytest.mark.parametrize("frequency", [0, -1, 0.0])
def test_pwm_rejects_bad_frequency(board, out_pin, frequency):
    with pytest.raises(GpioError, match="frequency must be > 0"):
        board.pwm(17, frequency, 25.0)


@pytest.mark.parametrize("duty", [-1, 101, 1000])
def test_pwm_rejects_bad_duty(board, out_pin, duty):
    with pytest.raises(GpioError, match="duty must be in"):
        board.pwm(17, 4.0, duty)


def test_pwm_rejects_non_numeric_frequency(board, out_pin):
    with pytest.raises(GpioError, match="frequency must be a number"):
        board.pwm(17, "fast", 25.0)


def test_pwm_rejects_non_numeric_duty(board, out_pin):
    with pytest.raises(GpioError, match="duty must be a number"):
        board.pwm(17, 4.0, "half")


def test_pwm_sample_pattern_for_quarter_duty(board, out_pin):
    board.pwm(17, 4.0, 25.0)
    pattern = [board.pwm_sample(17, index / 16.0) for index in range(8)]
    assert pattern == [1, 0, 0, 0, 1, 0, 0, 0]


def test_pwm_edges_hold_at_the_extremes(board, out_pin):
    board.pwm(17, 4.0, 0.0)
    assert {board.pwm_sample(17, t / 8.0) for t in range(8)} == {0}
    board.pwm(17, 4.0, 100.0)
    assert {board.pwm_sample(17, t / 8.0) for t in range(8)} == {1}


def test_pwm_average_matches_duty(board, out_pin):
    board.pwm(17, 8.0, 40.0)
    assert board.pwm_average(17) == pytest.approx(0.40)


def test_pwm_sample_requires_configuration(board, out_pin):
    with pytest.raises(GpioError, match="no PWM configured"):
        board.pwm_sample(17, 0.0)


def test_pwm_average_requires_configuration(board, out_pin):
    with pytest.raises(GpioError, match="no PWM configured"):
        board.pwm_average(17)


def test_pwm_sample_rejects_negative_elapsed(board, out_pin):
    board.pwm(17, 4.0, 25.0)
    with pytest.raises(GpioError, match="elapsed must be >= 0"):
        board.pwm_sample(17, -1.0)


def test_clear_pwm_resets_the_configuration(board, out_pin):
    board.pwm(17, 4.0, 25.0)
    board.clear_pwm(17)
    assert board.pin(17).has_pwm is False
    with pytest.raises(GpioError, match="no PWM configured"):
        board.pwm_sample(17, 0.0)


# --------------------------------------------------------------------------- #
# Device helpers
# --------------------------------------------------------------------------- #
def test_led_claims_an_output_pin(board):
    led = Led(board, 21)
    assert board.pin(21).mode == "output"
    assert not led.is_on


def test_led_on_off_and_toggle(board):
    led = Led(board, 21)
    led.on()
    assert led.is_on and board.read(21) == 1
    led.off()
    assert not led.is_on
    assert led.toggle() is True
    assert led.toggle() is False


def test_active_low_led_inverts_the_level(board):
    led = Led(board, 21, active_high=False)
    led.on()
    assert board.read(21) == 0 and led.is_on
    led.off()
    assert board.read(21) == 1


def test_led_to_dict(board):
    led = Led(board, 21)
    led.on()
    assert led.to_dict() == {"pin": 21, "on": True, "active_high": True}


def test_button_rests_released(board):
    button = Button(board, 18, pull="up")
    assert not button.is_pressed
    assert board.read(18) == 1


def test_button_press_and_release(board):
    button = Button(board, 18, pull="up")
    button.press()
    assert button.is_pressed and board.read(18) == 0
    button.release()
    assert not button.is_pressed
    assert [event.edge for event in board.edges(18)] == ["falling", "rising"]


def test_active_high_button(board):
    button = Button(board, 18, pull="down", active_low=False)
    assert not button.is_pressed
    button.press()
    assert board.read(18) == 1 and button.is_pressed


def test_button_to_dict(board):
    button = Button(board, 18, pull="up")
    button.press()
    assert button.to_dict() == {"pin": 18, "pressed": True, "pull": "up",
                                "active_low": True}


def test_helpers_reuse_an_existing_pin(board):
    board.add_pin(21, mode="input", pull="down")
    led = Led(board, 21)
    assert led.pin.mode == "output"


# --------------------------------------------------------------------------- #
# Snapshots and reports
# --------------------------------------------------------------------------- #
def test_snapshot_counts_pins_and_edges(board, out_pin, in_pin):
    board.write(17, 1)
    snapshot = board.snapshot()
    assert snapshot["pins"] and len(snapshot["pins"]) == 2
    assert snapshot["edges"] == 1
    assert snapshot["name"] == "test"


def test_to_dict_can_include_events(board, out_pin):
    board.write(17, 1)
    assert len(board.to_dict(keep_events=True)["events"]) == 1
    assert "events" not in board.to_dict()


def test_render_report_lists_pins(board, out_pin, in_pin):
    report = render_report(board)
    assert "GPIO BOARD" in report
    assert "17" in report and "18" in report
    assert "output" in report and "input" in report


def test_render_report_shows_pwm(board):
    board.add_pin(22, mode="output")
    board.pwm(22, 4.0, 25.0)
    assert "4 Hz 25%" in render_report(board)


def test_render_report_without_events(board):
    assert "Recent edges:" not in render_report(board)


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #
def test_load_scenario_bundled():
    scenario = load_scenario(SCENARIO)
    assert scenario["name"] == "status-panel"
    assert len(scenario["pins"]) == 4
    assert len(scenario["steps"]) == 16


def test_load_scenario_missing_file(tmp_path):
    with pytest.raises(GpioError, match="scenario not found"):
        load_scenario(tmp_path / "ghost.json")


def test_load_scenario_rejects_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(GpioError, match="not valid JSON"):
        load_scenario(path)


def test_load_scenario_requires_keys(tmp_path):
    path = tmp_path / "short.json"
    path.write_text(json.dumps({"pins": []}), encoding="utf-8")
    with pytest.raises(GpioError, match="needs 'pins' and 'steps'"):
        load_scenario(path)


def test_load_scenario_rejects_empty_pins(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"pins": [], "steps": []}),
                    encoding="utf-8")
    with pytest.raises(GpioError, match="non-empty list"):
        load_scenario(path)


def test_load_scenario_rejects_duplicate_pins(tmp_path):
    path = tmp_path / "dupe.json"
    path.write_text(json.dumps({"pins": [{"number": 5}, {"number": 5}],
                                "steps": []}), encoding="utf-8")
    with pytest.raises(GpioError, match="duplicate pin"):
        load_scenario(path)


def test_load_scenario_rejects_bad_op(tmp_path):
    path = tmp_path / "op.json"
    path.write_text(json.dumps({"pins": [{"number": 5}],
                                "steps": [{"op": "explode", "pin": 5}]}),
                    encoding="utf-8")
    with pytest.raises(GpioError, match="invalid op"):
        load_scenario(path)


def test_load_scenario_requires_ms_for_advance(tmp_path):
    path = tmp_path / "ms.json"
    path.write_text(json.dumps({"pins": [{"number": 5}],
                                "steps": [{"op": "advance"}]}),
                    encoding="utf-8")
    with pytest.raises(GpioError, match="needs 'ms'"):
        load_scenario(path)


def test_load_scenario_requires_level_for_writes(tmp_path):
    path = tmp_path / "level.json"
    path.write_text(json.dumps({"pins": [{"number": 5, "mode": "output"}],
                                "steps": [{"op": "write", "pin": 5}]}),
                    encoding="utf-8")
    with pytest.raises(GpioError, match="needs 'level'"):
        load_scenario(path)


def test_load_scenario_requires_pwm_fields(tmp_path):
    path = tmp_path / "pwm.json"
    path.write_text(json.dumps({"pins": [{"number": 5, "mode": "output"}],
                                "steps": [{"op": "pwm", "pin": 5,
                                           "duty": 25}]}),
                    encoding="utf-8")
    with pytest.raises(GpioError, match="missing"):
        load_scenario(path)


def test_run_scenario_transcript_length():
    result = run_scenario(load_scenario(SCENARIO))
    assert len(result["transcript"]) == 16
    assert result["snapshot"]["tick"] == 850


def test_run_scenario_is_deterministic():
    first = run_scenario(load_scenario(SCENARIO))
    second = run_scenario(load_scenario(SCENARIO))
    assert first["transcript"] == second["transcript"]
    assert first["snapshot"] == second["snapshot"]


def test_run_scenario_ends_with_the_led_off():
    snapshot = run_scenario(load_scenario(SCENARIO))["snapshot"]
    levels = {pin["number"]: pin["level"] for pin in snapshot["pins"]}
    assert levels == {17: 0, 18: 1, 22: 0, 23: 0}


def test_run_scenario_records_six_edges():
    snapshot = run_scenario(load_scenario(SCENARIO))["snapshot"]
    assert snapshot["edges"] == 6


def test_run_scenario_rejects_bad_input():
    with pytest.raises(GpioError, match="needs a scenario dict"):
        run_scenario({"steps": []})


def test_run_scenario_surfaces_pin_errors():
    scenario = {"pins": [{"number": 5, "mode": "input", "pull": "up"}],
                "steps": [{"op": "write", "pin": 5, "level": 1}]}
    with pytest.raises(GpioError, match="is an input"):
        run_scenario(scenario)


# --------------------------------------------------------------------------- #
# Demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_prints_cross_checks(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    first = capsys.readouterr().out
    assert run_demo() == 0
    assert capsys.readouterr().out == first


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


def test_cli_replays_the_bundled_scenario(capsys):
    assert main(["--scenario", str(SCENARIO)]) == 0
    out = capsys.readouterr().out
    assert "status-panel" in out
    assert "Transcript:" in out
    assert "GPIO BOARD" in out


def test_cli_validates_debounce(capsys):
    assert main(["--scenario", str(SCENARIO), "--debounce", "0"]) == 2
    assert "debounce must be >= 1" in capsys.readouterr().err


def test_cli_missing_scenario(tmp_path, capsys):
    assert main(["--scenario", str(tmp_path / "nope.json")]) == 2
    assert "scenario not found" in capsys.readouterr().err


def test_cli_json_export(tmp_path, capsys):
    out = tmp_path / "run.json"
    assert main(["--scenario", str(SCENARIO), "--json", str(out),
                 "--quiet"]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["scenario"] == "status-panel"
    assert len(payload["transcript"]) == 16
    assert payload["snapshot"]["tick"] == 850
    assert len(payload["events"]) == 6
    assert capsys.readouterr().out == ""


def test_bundled_defaults_are_sane():
    assert SCENARIO_FILE.is_file()
    assert DEFAULT_DEBOUNCE >= 1
    assert set(MODES) == {"input", "output"}
    assert set(PULLS) == {"none", "up", "down"}
