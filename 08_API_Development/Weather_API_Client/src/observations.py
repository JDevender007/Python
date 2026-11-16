"""A JSON value has a shape, a type and a unit -- and `0.0` is a temperature.

The legacy reader of a weather response was three lines:

    def get_temperature(payload):
        try:
            return payload["main"]["temp"] - 273.15
        except (KeyError, TypeError):
            return 0.0

Everything about that is a decision the code never admitted to making.

**1. The fallback is a reading.** `0.0` is a temperature. When the server sends
no `main` object, or a `null`, or a quoted string, the legacy reader does not
report "I could not read this" -- it reports **0.0 degrees**, which a dashboard
draws as freezing point. A missing value and a measured value are the same
value, and the measured one is the wrong one.

**2. `- 273.15` is a unit conversion, not arithmetic.** The response says
`"units": "metric"` and the temperature is already Celsius. Subtracting 273.15
turns 21.555 C into **-251.595 C** -- a number so cold that its only warning is
that it is absurd, and a dashboard has no absurdity check.

**3. A JSON float is not the number the server sent.** The body says `21.555`.
`json.loads` turns that into the nearest binary double, whose value is
21.55499999999999971578290569595992565155029296875. Multiply by 100 and the
product lands on **2155.4999999999995**, which truncates to 2155 and which
rounds *down* to 2155 as well, because it is below the tie -- one hundredth
short, silently, and the tie itself is invisible. Decoding with
`parse_float=Decimal` keeps the digits the server actually sent: `21.555` is
2155.5 hundredths, and a half rounds up to **2156**. Only then does the number
mean what it says.

**4. `KeyError` is not the only shape of "no value".** Three different bodies
reach the same `except`: a missing key, an explicit `null`, and a string. They
are three different failures and they deserve three different sentences, not
one `0.0`.

**5. A temperature has a floor.** Absolute zero is -273.15 C, and a body that
reports -300 C is not cold, it is broken. The legacy reader accepts it happily
and returns -573.15.

So this module keeps a temperature as **whole hundredths of a degree**, together
with the unit it was printed in, converts in integers only, records the unit the
response named instead of assuming one, keeps a missing humidity as `None`
rather than 0 %, and refuses every one of the five broken shapes with the
sentence that says which it is.

The demonstration is offline: one bundled file of nine response bodies exactly as
a server would send them, and no network. Standard library only: no requests, no
http client, no API key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
READINGS_FILE = DATA_DIR / "readings.txt"

#: The legacy three lines, transcribed: unreadable means 0.0 degrees.
LEGACY_TEMPERATURE = ('try:\n'
                      '    return payload["main"]["temp"] - 273.15\n'
                      'except (KeyError, TypeError):\n'
                      '    return 0.0')

#: The units a response may name, and the letter each prints with.
UNITS = ("celsius", "kelvin", "fahrenheit")

#: OpenWeather's own unit names, and the unit each one means.
NAMED_UNITS = {"metric": "celsius", "standard": "kelvin",
               "imperial": "fahrenheit"}

#: A temperature is stored in hundredths of a degree of its unit.
PER_DEGREE = 100

#: Absolute zero, in hundredths of a degree Celsius.
ABSOLUTE_ZERO = -27_315

#: Celsius to kelvin, in hundredths of a degree.
KELVIN_OFFSET = 27_315

#: The freezing point of water in Fahrenheit, in hundredths of a degree.
FAHRENHEIT_OFFSET = 3_200


class ObservationError(Exception):
    """A body that cannot be read, with the sentence that says why."""


# --------------------------------------------------------------------------- #
# Integer arithmetic
# --------------------------------------------------------------------------- #
def divide_half_up(numerator: int, denominator: int) -> int:
    """Whole division, rounding a half away from zero, in integers only.

    `round()` is not this function: it rounds a half to the even neighbour, so
    `round(2.5)` is 2 and `round(3.5)` is 4. Half-up is what a measurement
    sheet means by rounding, and writing it out is the only way to be sure of
    it -- for negatives as well as positives.
    """
    if not isinstance(numerator, int) or isinstance(numerator, bool):
        raise ObservationError(f"a numerator is a whole number, got "
                               f"{numerator!r}")
    if not isinstance(denominator, int) or isinstance(denominator, bool):
        raise ObservationError(f"a divisor is a whole number, got "
                               f"{denominator!r}")
    if denominator <= 0:
        raise ObservationError(f"a divisor must be positive, got "
                               f"{denominator}")
    sign = -1 if numerator < 0 else 1
    magnitude = abs(numerator)
    return sign * ((magnitude * 2 + denominator) // (2 * denominator))


def to_hundredths(value: Decimal) -> int:
    """A decimal number of degrees as whole hundredths, half-up."""
    if not isinstance(value, Decimal):
        raise ObservationError(f"a decimal is needed, got {type(value).__name__}")
    try:
        scaled = (value * PER_DEGREE).quantize(Decimal(1),
                                               rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ObservationError(f"{value!r} cannot be scaled") from None
    return int(scaled)


def decode(text: str) -> object:
    """`json.loads` that keeps the digits the server sent.

    A JSON number is a decimal literal, and `json.loads` converts it to the
    nearest binary double before anyone can look at it. `parse_float=Decimal`
    keeps `21.55` as the four characters the server wrote, so the hundredths
    are exact and a comparison of two readings cannot invent a difference.
    """
    return json.loads(text, parse_float=Decimal)


def plain_decode(text: str) -> object:
    """`json.loads` as it normally behaves, for the legacy comparison."""
    return json.loads(text)


# --------------------------------------------------------------------------- #
# A temperature
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=True)
class Temperature:
    """One temperature, in whole hundredths of a degree Celsius.

    One field, because a temperature is one number. The unit it arrived in is
    how it was written down, not part of it: 21.5 C, 294.65 K and 70.7 F are
    one `Temperature`, and none of the three can be added to the others by
    accident.
    """

    hundredths: int

    def __post_init__(self) -> None:
        if not isinstance(self.hundredths, int) or \
                isinstance(self.hundredths, bool):
            raise ObservationError(f"a temperature is a whole number of "
                                   f"hundredths of a degree, got "
                                   f"{self.hundredths!r}")
        if self.hundredths < ABSOLUTE_ZERO:
            raise ObservationError(
                f"{self.text('celsius')} is colder than absolute zero "
                f"(-273.15 C), so it is not a temperature")

    def in_unit(self, unit: str) -> int:
        """This temperature's value in `unit`, in hundredths of its degree."""
        if unit not in UNITS:
            raise ObservationError(f"{unit!r} is not a temperature unit: "
                                   f"expected one of {', '.join(UNITS)}")
        if unit == "celsius":
            return self.hundredths
        if unit == "kelvin":
            return self.hundredths + KELVIN_OFFSET
        scaled = divide_half_up(self.hundredths * 9, 5)
        return scaled + FAHRENHEIT_OFFSET

    def text(self, unit: str = "celsius") -> str:
        """`21.55 C`, `294.70 K`, `70.70 F` -- always two decimals."""
        scaled = self.in_unit(unit)
        sign = "-" if scaled < 0 else ""
        magnitude = abs(scaled)
        letter = unit[0].upper()
        return (f"{sign}{magnitude // PER_DEGREE}.{magnitude % PER_DEGREE:02d} "
                f"{letter}")

    def celsius_text(self) -> str:
        return self.text("celsius")

    def __str__(self) -> str:
        return self.text("celsius")


def from_unit(unit: str, value: int) -> Temperature:
    """A value in `unit`, in hundredths of its degree, as a `Temperature`."""
    if unit not in UNITS:
        raise ObservationError(f"{unit!r} is not a temperature unit: "
                               f"expected one of {', '.join(UNITS)}")
    if unit == "celsius":
        return Temperature(value)
    if unit == "kelvin":
        return Temperature(value - KELVIN_OFFSET)
    return Temperature(divide_half_up((value - FAHRENHEIT_OFFSET) * 5, 9))


def parse_temperature(raw) -> Temperature:
    """Read the `temp` field of a body, refusing every shape but a number.

    * `None` is a missing reading, not 0 degrees.
    * a string is typing: the server sent text where a number belongs.
    * a `float` is accepted, but it is the **binary** value, so a body that
      said `21.555` decodes to 2155 hundredths, a hundredth below the tie.
      That is exactly the difference `parse_float=Decimal` removes, and the
      reader does not hide it.
    """
    if raw is None:
        raise ObservationError("the temperature is null: a missing reading is "
                               "not 0.0 degrees")
    if isinstance(raw, bool):
        raise ObservationError(f"a temperature is a number, got {raw!r}")
    if isinstance(raw, int):
        return Temperature(raw * PER_DEGREE)
    if isinstance(raw, Decimal):
        return Temperature(to_hundredths(raw))
    if isinstance(raw, float):
        return Temperature(to_hundredths(Decimal(raw)))
    raise ObservationError(f"a temperature is a number, got "
                           f"{type(raw).__name__} {raw!r}")


def parse_humidity(raw) -> int | None:
    """Read the optional `humidity` field: `None` stays `None`, never 0 %."""
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ObservationError(f"a humidity is a whole percentage, got "
                               f"{raw!r}")
    if not 0 <= raw <= 100:
        raise ObservationError(f"{raw}% is not a humidity: a percentage is "
                               f"between 0 and 100")
    return raw


# --------------------------------------------------------------------------- #
# The legacy reader, executable
# --------------------------------------------------------------------------- #
def legacy_temperature(payload) -> float:
    """The legacy reader, rewritten faithfully: unreadable means 0.0.

    It is called with the payload `json.loads` returns -- binary floats -- so
    the subtraction never meets a `Decimal`, which is what the original met.
    """
    try:
        return payload["main"]["temp"] - 273.15
    except (KeyError, TypeError):
        return 0.0


# --------------------------------------------------------------------------- #
# An observation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Observation:
    """One body: the station it came from, what was read, and why not."""

    station: str
    temperature: Temperature | None
    humidity: int | None
    note: str

    def ok(self) -> bool:
        return self.temperature is not None

    def line(self) -> str:
        if self.temperature is None:
            return (f"{self.station:<12} {'refused':>10} {'-':>7}   {self.note}")
        humidity = "-" if self.humidity is None else f"{self.humidity}%"
        return (f"{self.station:<12} {self.temperature.celsius_text():>10} "
                f"{humidity:>7}   {self.note}")

    def note_line(self) -> str:
        return f"{self.station:<12} {self.note}"


def _read_fields(payload) -> tuple[Temperature, int | None, str]:
    """The temperature, the humidity and the unit, from a decoded payload."""
    if not isinstance(payload, dict):
        raise ObservationError(f"a response is a JSON object, got "
                               f"{type(payload).__name__}")
    code = payload.get("cod")
    if code is not None and str(code) != "200":
        message = payload.get("message", "no message")
        raise ObservationError(f"the response is an error, cod {code!r}: "
                               f"{message}")
    named = payload.get("units", "metric")
    if named not in NAMED_UNITS:
        raise ObservationError(f"the response names units {named!r}, which "
                               f"this lab does not convert")
    unit = NAMED_UNITS[named]
    if "main" not in payload:
        raise ObservationError("the response has no 'main' object, so it "
                               "carries no reading")
    main = payload["main"]
    if not isinstance(main, dict):
        raise ObservationError(f"'main' is a JSON object, got "
                               f"{type(main).__name__}")
    if "temp" not in main:
        raise ObservationError("'main' carries no 'temp' field")
    reading = parse_temperature(main["temp"])
    humidity = parse_humidity(main.get("humidity"))
    return from_unit(unit, reading.hundredths), humidity, unit


def read_observation(station: str, body: str, loads=None) -> Observation:
    """Read one body, keeping a refusal as a sentence rather than an exception."""
    if not isinstance(station, str) or not station.strip():
        raise ObservationError("a station needs a name")
    if not isinstance(body, str):
        raise ObservationError(f"a body is text, got {type(body).__name__}")
    reader = decode if loads is None else loads
    try:
        payload = reader(body)
    except json.JSONDecodeError as error:
        return Observation(station.strip(), None, None,
                           f"the body is not JSON at character {error.pos}: "
                           f"{error.msg}")
    try:
        temperature, humidity, unit = _read_fields(payload)
    except ObservationError as error:
        return Observation(station.strip(), None, None, str(error))
    return Observation(station.strip(), temperature, humidity,
                       f"read as {unit}")


# --------------------------------------------------------------------------- #
# A table of bodies
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Table:
    """Every body in one bundle, in the order the bundle holds them."""

    observations: tuple[Observation, ...]

    def __post_init__(self) -> None:
        if not self.observations:
            raise ObservationError("a table needs at least one body")
        names = [observation.station for observation in self.observations]
        if len(set(names)) != len(names):
            raise ObservationError("two bodies share a station name")

    def __len__(self) -> int:
        return len(self.observations)

    def readings(self) -> tuple[Observation, ...]:
        return tuple(item for item in self.observations if item.ok())

    def refusals(self) -> tuple[Observation, ...]:
        return tuple(item for item in self.observations if not item.ok())

    def by_name(self, station: str) -> Observation:
        for observation in self.observations:
            if observation.station == station:
                return observation
        raise ObservationError(f"no body named {station!r} in this table")

    def warmest(self) -> Observation | None:
        known = self.readings()
        if not known:
            return None
        return max(known, key=lambda item: item.temperature.hundredths)

    def coldest(self) -> Observation | None:
        known = self.readings()
        if not known:
            return None
        return min(known, key=lambda item: item.temperature.hundredths)

    def lines(self) -> tuple[str, ...]:
        return tuple(observation.line() for observation in self.observations)


def parse_blocks(text: str) -> tuple[tuple[str, str], ...]:
    """Read `--- name` blocks; the body is everything until the next header."""
    blocks: list[tuple[str, str]] = []
    name: str | None = None
    body: list[str] = []

    def flush(number: int) -> None:
        if name is None:
            return
        joined = "\n".join(body).strip()
        if not joined:
            raise ObservationError(f"block {name!r} on line {number} is empty")
        blocks.append((name, joined))

    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"),
                                  start=1):
        if line.lstrip().startswith(";"):
            continue
        if line.startswith("---"):
            flush(number)
            name = line[3:].strip()
            if not name:
                raise ObservationError(f"line {number}: a block header needs a "
                                      f"name")
            body = []
            continue
        if name is None:
            if line.strip():
                raise ObservationError(f"line {number}: a body before the first "
                                      f"'--- name' header")
            continue
        body.append(line)
    flush(len(text.split("\n")))
    if not blocks:
        raise ObservationError("the bundle holds no bodies")
    return tuple(blocks)


def read_table(path=None) -> Table:
    target = Path(READINGS_FILE if path is None else path)
    if not target.is_file():
        raise ObservationError(f"file not found: {target}")
    blocks = parse_blocks(target.read_text(encoding="utf-8"))
    return Table(tuple(read_observation(name, body) for name, body in blocks))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(table: Table, loads=None) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived from the bundled bodies.

    `loads` is injected so a negative control can hand in a decoder that turns
    every JSON number into a binary double -- the only way to show that the
    digit check is testing the decoder rather than the table.
    """
    reader = decode if loads is None else loads

    def every_temperature_is_whole_hundredths() -> bool:
        for observation in table.readings():
            value = observation.temperature.hundredths
            if not isinstance(value, int) or isinstance(value, bool):
                return False
        return True

    def every_temperature_prints_and_reads_back() -> bool:
        for observation in table.readings():
            for unit in UNITS:
                scaled = observation.temperature.in_unit(unit)
                back = from_unit(unit, scaled)
                if back.hundredths != observation.temperature.hundredths:
                    return False
        return True

    def the_digits_survive_the_decoder() -> bool:
        sample = '{"main": {"temp": 21.555}}'
        literal = reader(sample)["main"]["temp"]
        return isinstance(literal, Decimal) and \
            parse_temperature(literal).hundredths == 2_156

    def the_legacy_conversion_treats_celsius_as_kelvin() -> bool:
        metric = plain_decode('{"units": "metric", "main": {"temp": 21.555}}')
        legacy = legacy_temperature(metric)
        here = table.by_name("metric").temperature.celsius_text()
        return legacy < -200 and here == "21.56 C"

    def the_legacy_fallback_answers_zero_for_three_broken_bodies() -> bool:
        bodies = ('{"main": {}}',
                  '{"main": {"temp": null}}',
                  '{"main": {"temp": "21.555"}}')
        return all(legacy_temperature(plain_decode(body)) == 0.0
                   for body in bodies)

    def the_legacy_reader_accepts_a_temperature_below_absolute_zero() -> bool:
        cold = plain_decode('{"main": {"temp": -300.0}}')
        if legacy_temperature(cold) >= ABSOLUTE_ZERO / PER_DEGREE:
            return False
        try:
            table.by_name("cold").temperature.celsius_text()
        except AttributeError:
            return True
        return False

    def a_missing_humidity_is_none_not_zero() -> bool:
        missing = table.by_name("no-humidity")
        present = table.by_name("metric")
        return missing.humidity is None and present.humidity == 61

    def a_humidity_outside_a_percentage_is_refused() -> bool:
        body = '{"units": "metric", "main": {"temp": 21.5, "humidity": 120}}'
        read = read_observation("wet", body, loads=reader)
        return read.temperature is None and "between 0 and 100" in read.note

    def every_refusal_carries_the_sentence_that_says_why() -> bool:
        refusals = table.refusals()
        if not refusals:
            return False
        return all(item.note.strip() for item in refusals)

    checks = [
        ("every temperature is a whole number of hundredths",
         every_temperature_is_whole_hundredths),
        ("every temperature prints in each unit and reads back",
         every_temperature_prints_and_reads_back),
        ("the digits of the body survive the decoder",
         the_digits_survive_the_decoder),
        ("the legacy conversion treats a Celsius reading as Kelvin",
         the_legacy_conversion_treats_celsius_as_kelvin),
        ("the legacy fallback answers 0.0 for three broken bodies",
         the_legacy_fallback_answers_zero_for_three_broken_bodies),
        ("the legacy reader accepts a temperature below absolute zero",
         the_legacy_reader_accepts_a_temperature_below_absolute_zero),
        ("a missing humidity is None, not zero",
         a_missing_humidity_is_none_not_zero),
        ("a humidity outside a percentage is refused",
         a_humidity_outside_a_percentage_is_refused),
        ("every refusal carries the sentence that says why",
         every_refusal_carries_the_sentence_that_says_why),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
SAMPLE_BODY = '{"units": "metric", "main": {"temp": 21.555, "humidity": 61}}'


def run_demo() -> int:
    table = read_table()

    print("=" * 78)
    print(" UNITS LAB - a JSON value has a shape, a type and a unit")
    print("=" * 78)

    print("\n  the legacy reader, transcribed:")
    for line in LEGACY_TEMPERATURE.split("\n"):
        print(f"    {line}")

    as_float = plain_decode('{"temp": 21.555}')["temp"]
    as_digits = decode('{"temp": 21.555}')["temp"]
    exact = str(Decimal(as_float))
    product = str(Decimal(as_float) * 100)
    print("\n  the body says 21.555. what a decoder makes of it:")
    print(f"    json.loads            -> {type(as_float).__name__:<8} "
          f"{as_float!r}")
    print(f"    its exact value       -> {exact[:32]}...")
    print(f"    x 100, exactly        -> {product[:32]}...")
    print(f"    int(...), as many do  -> {int(Decimal(as_float) * 100)}")
    print(f"    parse_float=Decimal   -> {type(as_digits).__name__:<8} "
          f"{as_digits}")
    print(f"    x 100, rounded half-up-> {to_hundredths(as_digits)}")
    print(f"    hundredths kept: "
          f"{parse_temperature(as_digits).hundredths} from the digits, "
          f"{parse_temperature(as_float).hundredths} from the double")

    print(f"\n  the nine bundled bodies, {len(table)} in all:")
    print(f"    {'station':<12} {'here':>10} {'humidity':>7}   note")
    for line in table.lines():
        print(f"    {line}")

    print(f"\n  {len(table.readings())} reading(s), "
          f"{len(table.refusals())} refusal(s)")

    print("\n  what the legacy reader makes of the same bodies:")
    zero = 0
    for station, body in parse_blocks(READINGS_FILE.read_text(encoding="utf-8")):
        try:
            payload = plain_decode(body)
        except json.JSONDecodeError:
            print(f"    {station:<12} {'-':>10}   the body is not JSON, so the "
                  f"legacy reader never ran")
            continue
        value = legacy_temperature(payload)
        if value == 0.0:
            zero += 1
        print(f"    {station:<12} {value:>10.2f} C")
    print(f"    {zero} of {len(table)} bodies come back as exactly 0.00 C")

    warmest = table.warmest()
    coldest = table.coldest()
    print("\n  the warmest and the coldest reading:")
    print(f"    warmest  {warmest.station:<12} "
          f"{warmest.temperature.celsius_text():>10}  "
          f"({warmest.temperature.text('kelvin')})")
    print(f"    coldest  {coldest.station:<12} "
          f"{coldest.temperature.celsius_text():>10}  "
          f"({coldest.temperature.text('fahrenheit')})")

    checks = audit(table)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(table)} bodies give {len(table.readings())} reading(s) and "
          f"{len(table.refusals())} refusal(s), the legacy reader answers "
          f"exactly 0.00 C for {zero} of them and treats a metric reading as "
          f"Kelvin ({legacy_temperature(plain_decode(SAMPLE_BODY)):.2f} C "
          f"where the body says "
          f"{table.by_name('metric').temperature.celsius_text()}), "
          f"json.loads turns 21.555 into a double worth 2155 hundredths where "
          f"the digits give 2156, a missing humidity stays None, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
