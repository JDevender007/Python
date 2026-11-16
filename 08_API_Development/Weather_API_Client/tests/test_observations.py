"""Tests for Weather_API_Client: a JSON value has a shape, a type and a unit,
and a missing reading is not 0.0 degrees."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                           # noqa: E402
import observations as module                               # noqa: E402
from observations import (                                  # noqa: E402
    ABSOLUTE_ZERO,
    LEGACY_TEMPERATURE,
    NAMED_UNITS,
    READINGS_FILE,
    SAMPLE_BODY,
    UNITS,
    Observation,
    ObservationError,
    Table,
    Temperature,
    audit,
    decode,
    divide_half_up,
    from_unit,
    legacy_temperature,
    parse_blocks,
    parse_humidity,
    parse_temperature,
    plain_decode,
    problems,
    read_observation,
    read_table,
    run_demo,
    to_hundredths,
)


def a_table() -> Table:
    return read_table()


def a_temperature(hundredths: int = 2_156) -> Temperature:
    return Temperature(hundredths)


def raw_temperature(hundredths) -> Temperature:
    """A Temperature with the validation bypassed, so an audit can disagree."""
    temperature = object.__new__(Temperature)
    object.__setattr__(temperature, "hundredths", hundredths)
    return temperature


class Drifting(Temperature):
    """A temperature that converts to kelvin one hundredth out."""

    def in_unit(self, unit: str) -> int:
        scaled = super().in_unit(unit)
        return scaled + 1 if unit == "kelvin" else scaled


def an_observation(station: str = "metric",
                   temperature: Temperature | None = None,
                   humidity: int | None = 61,
                   note: str = "read as celsius") -> Observation:
    return Observation(station, temperature, humidity, note)


def a_refusal(station: str = "null-temp",
              note: str = "the temperature is null") -> Observation:
    return Observation(station, None, None, note)


# --------------------------------------------------------------------------- #
# Integer arithmetic
# --------------------------------------------------------------------------- #
def test_half_up_rounds_a_half_away_from_zero():
    assert divide_half_up(5, 2) == 3


def test_half_up_rounds_the_other_half_up_too():
    assert divide_half_up(7, 2) == 4


def test_half_up_rounds_a_negative_half_away_from_zero():
    assert divide_half_up(-5, 2) == -3


def test_half_up_leaves_an_exact_division_alone():
    assert divide_half_up(4, 2) == 2


def test_half_up_rounds_a_third_down():
    assert divide_half_up(1, 3) == 0


def test_half_up_rounds_two_thirds_up():
    assert divide_half_up(2, 3) == 1


def test_half_up_of_zero_is_zero():
    assert divide_half_up(0, 7) == 0


def test_round_is_not_half_up():
    assert round(2.5) == 2 and divide_half_up(5, 2) == 3


def test_round_is_even_where_half_up_is_up():
    assert round(3.5) == 4 and divide_half_up(7, 2) == 4


def test_a_divisor_of_zero_is_refused():
    with pytest.raises(ObservationError, match="must be positive"):
        divide_half_up(1, 0)


def test_a_negative_divisor_is_refused():
    with pytest.raises(ObservationError, match="must be positive"):
        divide_half_up(1, -2)


def test_a_numerator_that_is_not_a_whole_number_is_refused():
    with pytest.raises(ObservationError, match="a numerator is a whole"):
        divide_half_up(1.5, 2)


def test_a_bool_numerator_is_refused():
    with pytest.raises(ObservationError, match="a numerator is a whole"):
        divide_half_up(True, 2)


def test_a_divisor_that_is_not_a_whole_number_is_refused():
    with pytest.raises(ObservationError, match="a divisor is a whole"):
        divide_half_up(4, 2.0)


def test_a_decimal_of_three_places_rounds_half_up():
    assert to_hundredths(Decimal("21.555")) == 2_156


def test_a_decimal_below_the_half_rounds_down():
    assert to_hundredths(Decimal("21.554")) == 2_155


def test_a_decimal_with_two_places_is_exact():
    assert to_hundredths(Decimal("21.55")) == 2_155


def test_a_negative_decimal_rounds_away_from_zero():
    assert to_hundredths(Decimal("-0.005")) == -1


def test_to_hundredths_refuses_a_float():
    with pytest.raises(ObservationError, match="a decimal is needed"):
        to_hundredths(21.555)


def test_decode_keeps_a_decimal():
    assert isinstance(decode('{"temp": 21.555}')["temp"], Decimal)


def test_decode_keeps_the_digits_the_server_sent():
    assert decode('{"temp": 21.555}')["temp"] == Decimal("21.555")


def test_plain_decode_gives_a_float():
    assert isinstance(plain_decode('{"temp": 21.555}')["temp"], float)


def test_the_double_is_not_the_literal():
    assert Decimal(plain_decode('{"temp": 21.555}')["temp"]) != \
        Decimal("21.555")


def test_the_double_is_below_the_tie():
    value = Decimal(plain_decode('{"temp": 21.555}')["temp"]) * 100
    assert value < Decimal("2155.5")


def test_an_integer_in_a_body_stays_an_integer():
    assert decode('{"temp": 21}')["temp"] == 21


def test_decode_refuses_text_that_is_not_json():
    with pytest.raises(json.JSONDecodeError):
        decode("{nope}")


# --------------------------------------------------------------------------- #
# A temperature
# --------------------------------------------------------------------------- #
def test_a_temperature_holds_hundredths():
    assert a_temperature().hundredths == 2_156


def test_a_temperature_prints_itself_in_celsius():
    assert a_temperature().celsius_text() == "21.56 C"


def test_str_of_a_temperature_is_celsius():
    assert str(a_temperature()) == "21.56 C"


def test_a_negative_temperature_keeps_its_sign():
    assert a_temperature(-25_160).celsius_text() == "-251.60 C"


def test_zero_prints_with_two_decimals():
    assert a_temperature(0).celsius_text() == "0.00 C"


def test_a_temperature_prints_in_kelvin():
    assert a_temperature().text("kelvin") == "294.71 K"


def test_a_temperature_prints_in_fahrenheit():
    assert a_temperature().text("fahrenheit") == "70.81 F"


def test_a_temperature_orders_by_its_value():
    assert a_temperature(2_150) < a_temperature(2_156)


def test_two_temperatures_at_one_value_are_equal():
    assert a_temperature(2_150) == from_unit("fahrenheit", 7_070)


def test_a_temperature_refuses_a_float_value():
    with pytest.raises(ObservationError, match="whole number of hundredths"):
        Temperature(21.5)


def test_a_temperature_refuses_a_bool_value():
    with pytest.raises(ObservationError, match="whole number of hundredths"):
        Temperature(True)


def test_absolute_zero_itself_is_allowed():
    assert Temperature(ABSOLUTE_ZERO).celsius_text() == "-273.15 C"


def test_colder_than_absolute_zero_is_refused():
    with pytest.raises(ObservationError, match="colder than absolute zero"):
        Temperature(ABSOLUTE_ZERO - 1)


def test_an_absurd_temperature_is_refused_by_reading_it():
    with pytest.raises(ObservationError, match="-300.00 C is colder"):
        a_temperature(-30_000)


def test_a_temperature_refuses_an_unknown_unit():
    with pytest.raises(ObservationError, match="not a temperature unit"):
        a_temperature().text("rankine")


def test_in_unit_refuses_an_unknown_unit():
    with pytest.raises(ObservationError, match="not a temperature unit"):
        a_temperature().in_unit("rankine")


def test_the_units_are_three():
    assert UNITS == ("celsius", "kelvin", "fahrenheit")


def test_celsius_to_kelvin_adds_the_offset():
    assert a_temperature(0).in_unit("kelvin") == 27_315


def test_celsius_to_fahrenheit_scales_and_offsets():
    assert a_temperature(10_000).in_unit("fahrenheit") == 21_200


def test_fahrenheit_freezing_is_zero_celsius():
    assert from_unit("fahrenheit", 3_200).hundredths == 0


def test_kelvin_freezing_is_zero_celsius():
    assert from_unit("kelvin", 27_315).hundredths == 0


def test_every_unit_round_trips_through_from_unit():
    for value in (ABSOLUTE_ZERO, -10_000, 0, 2_150, 2_156, 10_000):
        for unit in UNITS:
            scaled = Temperature(value).in_unit(unit)
            assert from_unit(unit, scaled).hundredths == value


def test_from_unit_refuses_an_unknown_unit():
    with pytest.raises(ObservationError, match="not a temperature unit"):
        from_unit("rankine", 100)


# --------------------------------------------------------------------------- #
# Reading the fields
# --------------------------------------------------------------------------- #
def test_an_integer_temperature_reads_as_degrees():
    assert parse_temperature(21).hundredths == 2_100


def test_a_decimal_temperature_reads_exactly():
    assert parse_temperature(Decimal("21.555")).hundredths == 2_156


def test_a_float_temperature_reads_the_binary_value():
    assert parse_temperature(21.555).hundredths == 2_155


def test_a_null_temperature_is_refused_by_name():
    with pytest.raises(ObservationError, match="the temperature is null"):
        parse_temperature(None)


def test_a_string_temperature_is_refused_as_typing():
    with pytest.raises(ObservationError, match="a temperature is a number"):
        parse_temperature("21.555")


def test_a_bool_temperature_is_refused():
    with pytest.raises(ObservationError, match="a temperature is a number"):
        parse_temperature(True)


def test_a_list_temperature_is_refused():
    with pytest.raises(ObservationError, match="a temperature is a number"):
        parse_temperature([21])


def test_a_missing_humidity_is_none():
    assert parse_humidity(None) is None


def test_zero_humidity_is_a_reading():
    assert parse_humidity(0) == 0


def test_full_humidity_is_a_reading():
    assert parse_humidity(100) == 100


def test_a_humidity_above_a_percentage_is_refused():
    with pytest.raises(ObservationError, match="between 0 and 100"):
        parse_humidity(120)


def test_a_negative_humidity_is_refused():
    with pytest.raises(ObservationError, match="between 0 and 100"):
        parse_humidity(-1)


def test_a_string_humidity_is_refused():
    with pytest.raises(ObservationError, match="a whole percentage"):
        parse_humidity("61")


def test_a_fractional_humidity_is_refused():
    with pytest.raises(ObservationError, match="a whole percentage"):
        parse_humidity(61.5)


def test_a_bool_humidity_is_refused():
    with pytest.raises(ObservationError, match="a whole percentage"):
        parse_humidity(True)


# --------------------------------------------------------------------------- #
# The legacy reader
# --------------------------------------------------------------------------- #
def test_the_legacy_reader_subtracts_kelvin_from_a_metric_body():
    payload = plain_decode('{"main": {"temp": 21.555}}')
    assert legacy_temperature(payload) == pytest.approx(-251.595)


def test_the_legacy_reader_reads_a_kelvin_body_correctly():
    payload = plain_decode('{"main": {"temp": 294.65}}')
    assert legacy_temperature(payload) == pytest.approx(21.5)


def test_the_legacy_reader_answers_zero_for_a_null():
    assert legacy_temperature(plain_decode('{"main": {"temp": null}}')) == 0.0


def test_the_legacy_reader_answers_zero_for_a_string():
    assert legacy_temperature(plain_decode('{"main": {"temp": "21"}}')) == 0.0


def test_the_legacy_reader_answers_zero_for_a_missing_key():
    assert legacy_temperature(plain_decode('{"main": {}}')) == 0.0


def test_the_legacy_reader_answers_zero_for_a_missing_main():
    assert legacy_temperature(plain_decode('{"cod": "404"}')) == 0.0


def test_the_legacy_reader_answers_zero_for_a_list():
    assert legacy_temperature([1, 2, 3]) == 0.0


def test_the_legacy_reader_accepts_a_temperature_below_absolute_zero():
    payload = plain_decode('{"main": {"temp": -300.0}}')
    assert legacy_temperature(payload) == pytest.approx(-573.15)


def test_the_legacy_lines_are_pinned():
    assert LEGACY_TEMPERATURE.startswith("try:")
    assert "- 273.15" in LEGACY_TEMPERATURE
    assert "return 0.0" in LEGACY_TEMPERATURE


# --------------------------------------------------------------------------- #
# An observation
# --------------------------------------------------------------------------- #
def test_a_reading_is_ok():
    assert an_observation(temperature=a_temperature()).ok() is True


def test_a_refusal_is_not_ok():
    assert a_refusal().ok() is False


def test_a_reading_line_names_the_station_and_the_temperature():
    line = an_observation(temperature=a_temperature()).line()
    assert line.startswith("metric") and "21.56 C" in line


def test_a_reading_line_shows_the_humidity():
    assert "61%" in an_observation(temperature=a_temperature()).line()


def test_a_missing_humidity_prints_a_dash():
    line = an_observation(temperature=a_temperature(), humidity=None).line()
    assert "61%" not in line and "-" in line


def test_a_refusal_line_says_refused_and_why():
    line = a_refusal(note="the temperature is null").line()
    assert line.startswith("null-temp") and "refused" in line
    assert "the temperature is null" in line


def test_a_note_line_is_the_station_and_the_sentence():
    assert a_refusal().note_line() == \
        "null-temp    the temperature is null"


# --------------------------------------------------------------------------- #
# Reading one body
# --------------------------------------------------------------------------- #
def test_the_sample_body_reads_as_celsius():
    read = read_observation("metric", SAMPLE_BODY)
    assert read.temperature.celsius_text() == "21.56 C"


def test_the_sample_body_keeps_its_humidity():
    assert read_observation("metric", SAMPLE_BODY).humidity == 61


def test_the_note_names_the_unit_the_body_used():
    assert "read as celsius" in read_observation("metric", SAMPLE_BODY).note


def test_a_kelvin_body_reads_as_celsius():
    body = '{"units": "standard", "main": {"temp": 294.65}}'
    assert read_observation("k", body).temperature.celsius_text() == "21.50 C"


def test_an_imperial_body_reads_as_celsius():
    body = '{"units": "imperial", "main": {"temp": 70.7}}'
    assert read_observation("f", body).temperature.celsius_text() == "21.50 C"


def test_a_body_with_no_units_is_read_as_metric():
    body = '{"main": {"temp": 21.5}}'
    assert read_observation("m", body).temperature.celsius_text() == "21.50 C"


def test_a_body_that_is_not_json_becomes_a_note():
    read = read_observation("bad", "{nope}")
    assert read.temperature is None and "not JSON" in read.note


def test_a_truncated_body_names_where_it_stopped():
    read = read_observation("bad", '{"main": {"temp": 21.5')
    assert "not JSON at character" in read.note


def test_a_truncated_body_does_not_raise():
    assert read_observation("bad", "{").temperature is None


def test_an_error_body_is_refused_with_its_code_and_message():
    body = '{"cod": "404", "message": "city not found"}'
    read = read_observation("bad", body)
    assert "cod '404'" in read.note and "city not found" in read.note


def test_a_numeric_code_that_is_not_200_is_an_error():
    body = '{"cod": 401, "message": "no key"}'
    assert "cod 401" in read_observation("bad", body).note


def test_a_code_of_200_is_not_an_error():
    body = '{"cod": 200, "units": "metric", "main": {"temp": 21.5}}'
    assert read_observation("ok", body).ok() is True


def test_a_body_that_is_a_list_is_refused():
    assert "a response is a JSON object" in read_observation("bad", "[]").note


def test_a_body_with_no_main_is_refused():
    read = read_observation("bad", '{"units": "metric"}')
    assert "no 'main' object" in read.note


def test_a_main_that_is_not_an_object_is_refused():
    read = read_observation("bad", '{"main": 21.5}')
    assert "'main' is a JSON object" in read.note


def test_a_main_with_no_temp_is_refused():
    read = read_observation("bad", '{"main": {"humidity": 61}}')
    assert "no 'temp' field" in read.note


def test_an_unknown_unit_name_is_refused():
    read = read_observation("bad", '{"units": "rankine", "main": {"temp": 21}}')
    assert "names units 'rankine'" in read.note


def test_a_humidity_of_120_is_refused_by_reading_the_body():
    body = '{"units": "metric", "main": {"temp": 21.5, "humidity": 120}}'
    read = read_observation("bad", body)
    assert read.temperature is None and "between 0 and 100" in read.note


def test_reading_with_a_plain_decoder_reads_a_double():
    read = read_observation("metric", SAMPLE_BODY, loads=plain_decode)
    assert read.temperature.celsius_text() == "21.55 C"


def test_the_two_decoders_disagree_by_one_hundredth():
    exact = read_observation("metric", SAMPLE_BODY)
    binary = read_observation("metric", SAMPLE_BODY, loads=plain_decode)
    assert exact.temperature.hundredths - binary.temperature.hundredths == 1


def test_an_empty_station_name_is_refused():
    with pytest.raises(ObservationError, match="a station needs a name"):
        read_observation("   ", SAMPLE_BODY)


def test_a_body_that_is_not_text_is_refused():
    with pytest.raises(ObservationError, match="a body is text"):
        read_observation("metric", {"main": {}})


def test_the_station_name_is_trimmed():
    assert read_observation("  metric  ", SAMPLE_BODY).station == "metric"


def test_the_named_units_table_covers_three_names():
    assert NAMED_UNITS == {"metric": "celsius", "standard": "kelvin",
                           "imperial": "fahrenheit"}


# --------------------------------------------------------------------------- #
# A table
# --------------------------------------------------------------------------- #
def test_the_table_holds_nine_bodies():
    assert len(a_table()) == 9


def test_four_bodies_are_readings():
    assert len(a_table().readings()) == 4


def test_five_bodies_are_refusals():
    assert len(a_table().refusals()) == 5


def test_the_refused_stations_are_the_broken_ones():
    assert [item.station for item in a_table().refusals()] == [
        "null-temp", "string-temp", "no-main", "cold", "truncated"]


def test_the_warmest_reading_is_the_metric_body():
    assert a_table().warmest().station == "metric"


def test_the_coldest_reading_is_the_kelvin_body():
    assert a_table().coldest().station == "kelvin"


def test_the_two_readings_at_21_50_stay_equal():
    table = a_table()
    assert table.by_name("kelvin").temperature == \
        table.by_name("imperial").temperature


def test_by_name_finds_a_body():
    assert a_table().by_name("metric").station == "metric"


def test_by_name_refuses_a_name_that_is_not_there():
    with pytest.raises(ObservationError, match="no body named 'nope'"):
        a_table().by_name("nope")


def test_a_table_needs_a_body():
    with pytest.raises(ObservationError, match="at least one body"):
        Table(())


def test_a_table_refuses_two_bodies_with_one_name():
    with pytest.raises(ObservationError, match="share a station name"):
        Table((a_refusal("x"), a_refusal("x")))


def test_a_table_of_only_refusals_has_no_warmest():
    table = Table((a_refusal(),))
    assert table.warmest() is None and table.coldest() is None


def test_the_table_lines_are_one_per_body():
    assert len(a_table().lines()) == 9


def test_the_metric_row_shows_21_56_degrees():
    assert "21.56 C" in a_table().lines()[0]


def test_the_no_humidity_row_prints_a_dash():
    row = a_table().lines()[7]
    assert row.startswith("no-humidity") and "%" not in row


# --------------------------------------------------------------------------- #
# Reading the file
# --------------------------------------------------------------------------- #
def test_parse_blocks_reads_one_body():
    assert parse_blocks("--- a\n{}\n") == (("a", "{}"),)


def test_parse_blocks_reads_two_bodies():
    assert len(parse_blocks("--- a\n{}\n--- b\n[]\n")) == 2


def test_parse_blocks_keeps_a_multiline_body():
    blocks = parse_blocks("--- a\n{\n  \"x\": 1\n}\n")
    assert "\n" in blocks[0][1]


def test_parse_blocks_skips_a_comment():
    assert parse_blocks("; note\n--- a\n{}\n") == (("a", "{}"),)


def test_parse_blocks_skips_a_blank_line():
    assert len(parse_blocks("\n\n--- a\n{}\n\n")) == 1


def test_parse_blocks_reads_windows_line_endings():
    assert len(parse_blocks("--- a\r\n{}\r\n--- b\r\n{}\r\n")) == 2


def test_parse_blocks_refuses_a_body_before_a_header():
    with pytest.raises(ObservationError, match="before the first"):
        parse_blocks("{}\n")


def test_parse_blocks_refuses_a_header_with_no_name():
    with pytest.raises(ObservationError, match="needs a name"):
        parse_blocks("---\n{}\n")


def test_parse_blocks_refuses_an_empty_block():
    with pytest.raises(ObservationError, match="is empty"):
        parse_blocks("--- a\n\n--- b\n{}\n")


def test_parse_blocks_refuses_a_bundle_with_no_bodies():
    with pytest.raises(ObservationError, match="holds no bodies"):
        parse_blocks("; nothing\n")


def test_the_bundled_file_holds_nine_headers():
    text = READINGS_FILE.read_text(encoding="utf-8")
    assert len([line for line in text.split("\n")
                if line.startswith("---")]) == 9


def test_a_missing_bundle_is_refused(tmp_path):
    with pytest.raises(ObservationError, match="file not found"):
        module.read_table(tmp_path / "nope.txt")


def test_read_table_accepts_its_own_bundle(tmp_path):
    path = tmp_path / "readings.txt"
    path.write_bytes(b'--- only\n{"main": {"temp": 21.5}}\n')
    table = read_table(path)
    assert len(table) == 1 and table.readings()[0].temperature.hundredths == 2_150


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every temperature is a whole number of hundredths",
    "every temperature prints in each unit and reads back",
    "the digits of the body survive the decoder",
    "the legacy conversion treats a Celsius reading as Kelvin",
    "the legacy fallback answers 0.0 for three broken bodies",
    "the legacy reader accepts a temperature below absolute zero",
    "a missing humidity is None, not zero",
    "a humidity outside a percentage is refused",
    "every refusal carries the sentence that says why",
]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(a_table())] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_bodies():
    assert problems(audit(a_table())) == []


def test_the_audit_is_repeatable():
    assert audit(a_table()) == audit(a_table())


def test_the_audit_catches_a_fractional_hundredth():
    table = Table((an_observation(temperature=raw_temperature(21.5)),))
    assert CHECK_NAMES[0] in problems(audit(table))


def test_the_audit_does_not_raise_on_a_fractional_hundredth():
    table = Table((an_observation(temperature=raw_temperature("x")),))
    assert len(audit(table)) == 9


def test_the_audit_catches_a_unit_conversion_that_does_not_come_back():
    table = Table((an_observation(temperature=Drifting(2_156)),))
    assert CHECK_NAMES[1] in problems(audit(table))


def test_the_audit_catches_a_decoder_that_gives_doubles():
    assert CHECK_NAMES[2] in problems(audit(a_table(), loads=plain_decode))


def test_the_audit_catches_a_table_with_no_metric_row():
    table = Table((read_observation("other", SAMPLE_BODY),))
    assert CHECK_NAMES[3] in problems(audit(table))


def test_the_audit_catches_a_cold_row_that_was_read():
    body = '{"units": "metric", "main": {"temp": -20.0}}'
    table = Table((read_observation("cold", body),))
    assert CHECK_NAMES[5] in problems(audit(table))


def test_the_audit_catches_a_missing_humidity_read_as_zero():
    table = Table((an_observation("no-humidity", a_temperature(), 0),
                   an_observation("metric", a_temperature(), 61)))
    assert CHECK_NAMES[6] in problems(audit(table))


def test_the_audit_catches_a_reader_that_never_refuses_a_humidity():
    broken = lambda text: json.loads("{nope}")               # noqa: E731
    assert CHECK_NAMES[7] in problems(audit(a_table(), loads=broken))


def test_the_audit_catches_a_refusal_with_no_sentence():
    table = Table((a_refusal(note=""),))
    assert CHECK_NAMES[8] in problems(audit(table))


def test_the_audit_catches_a_table_with_no_refusal_at_all():
    table = Table((an_observation(temperature=a_temperature()),))
    assert CHECK_NAMES[8] in problems(audit(table))


def test_eight_of_the_nine_checks_have_a_negative_control():
    """Check 5 pins the transcribed legacy line; it cannot be broken."""
    body = '{"units": "metric", "main": {"temp": -20.0}}'
    broken = [
        audit(Table((an_observation(temperature=raw_temperature(21.5)),))),
        audit(Table((an_observation(temperature=Drifting(2_156)),))),
        audit(a_table(), loads=plain_decode),
        audit(Table((read_observation("other", SAMPLE_BODY),))),
        audit(Table((read_observation("cold", body),))),
        audit(Table((an_observation("no-humidity", a_temperature(), 0),
                     an_observation("metric", a_temperature(), 61)))),
        audit(a_table(), loads=lambda text: json.loads("{nope}")),
        audit(Table((a_refusal(note=""),))),
    ]
    caught = {name for checks in broken for name in problems(checks)}
    assert len(caught) == 8


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out and "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_legacy_reader(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert 'payload["main"]["temp"] - 273.15' in out
    assert "return 0.0" in out


def test_demo_shows_the_two_decoders_disagreeing(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "float    21.555" in out
    assert "Decimal  21.555" in out
    assert "2156 from the digits, 2155 from the double" in out


def test_demo_shows_the_metric_row(capsys):
    run_demo()
    assert "metric          21.56 C     61%   read as celsius" in \
        capsys.readouterr().out


def test_demo_shows_the_counts(capsys):
    run_demo()
    assert "4 reading(s), 5 refusal(s)" in capsys.readouterr().out


def test_demo_shows_the_legacy_zero_count(capsys):
    run_demo()
    assert "3 of 9 bodies come back as exactly 0.00 C" in capsys.readouterr().out


def test_demo_shows_the_warmest_and_coldest(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "warmest  metric          21.56 C  (294.71 K)" in out
    assert "coldest  kelvin          21.50 C  (70.70 F)" in out


def test_demo_shows_all_nine_checks(capsys):
    run_demo()
    assert "9/9 checks pass" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_reads_the_bundled_bodies(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "9 body(s): 4 reading(s), 5 refusal(s)" in out
    assert "21.56 C" in out


def test_cli_reads_one_body(capsys):
    assert cli.main(["--body", SAMPLE_BODY]) == 0
    out = capsys.readouterr().out
    assert "21.56 C" in out and "the legacy reader answers" in out


def test_cli_a_body_it_cannot_read_exits_two(capsys):
    assert cli.main(["--body", '{"main": {"temp": null}}']) == 2
    assert "the temperature is null" in capsys.readouterr().err


def test_cli_a_body_that_is_not_json_exits_two(capsys):
    assert cli.main(["--body", "{nope}"]) == 2
    assert "not JSON" in capsys.readouterr().err


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_writes_the_reading_as_json(tmp_path, capsys):
    target = tmp_path / "reading.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["readings"] == 4 and payload["refusals"] == 5
    assert payload["observations"][0]["celsius"] == "21.56 C"
    assert payload["observations"][0]["hundredths"] == 2_156
    assert payload["observations"][0]["kelvin"] == "294.71 K"
    assert payload["observations"][3]["celsius"] is None
    assert payload["observations"][7]["humidity"] is None
    assert "null" in payload["observations"][3]["note"]


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_missing_bundle_exits_two(tmp_path, capsys):
    assert cli.main(["--readings", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_malformed_bundle_exits_two(tmp_path, capsys):
    path = tmp_path / "readings.txt"
    path.write_bytes(b"{\"main\": {}}\n")
    assert cli.main(["--readings", str(path)]) == 2
    assert "before the first" in capsys.readouterr().err
