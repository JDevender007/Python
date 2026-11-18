"""A software GPIO simulator: pin modes, pulls, edges, PWM and debouncing.

No hardware, no kernel driver, no network. A board holds a small set of
pins, each with a mode (input or output), a pull resistor, a logic level
and optional PWM settings. Writing an output pin or driving an input pin
records an edge event, and optional listeners see every transition.

The PWM model is analytic rather than time-stepped: a pin with frequency
``f`` and duty ``d`` percent is high during the first ``d / 100`` of each
period, so ``pwm_sample(pin, t)`` is a pure function of the clock. That
makes the simulation deterministic and testable to the last bit.

Public API
----------
Debouncer            remove contact bounce from a noisy input
Pin                  one simulated GPIO pin
Board                a set of pins with edge logging and listeners
Led                  an output pin treated as an indicator
Button               an input pin with active-low semantics
load_scenario        read a JSON pin/step scenario
run_scenario         replay a scenario and return a transcript
render_report        human-readable board summary
run_demo             offline demo with self-checks
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIO_FILE = DATA_DIR / "scenario.json"

MODES = ("input", "output")
PULLS = ("none", "up", "down")
EDGES = ("rising", "falling", "both")
OPS = ("write", "read", "set_input", "pwm", "clear_pwm", "advance")

MIN_PIN = 0
MAX_PIN = 53
DEFAULT_DEBOUNCE = 3
MAX_DUTY = 100.0


class GpioError(RuntimeError):
    """Raised for invalid pins, modes, levels or scenarios."""


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def check_pin(number: object) -> int:
    if isinstance(number, bool) or not isinstance(number, int):
        raise GpioError(f"pin number must be an integer, got {number!r}")
    if not MIN_PIN <= number <= MAX_PIN:
        raise GpioError(f"pin {number} is out of range "
                        f"{MIN_PIN}-{MAX_PIN}")
    return number


def check_mode(mode: object) -> str:
    if not isinstance(mode, str) or mode.strip().lower() not in MODES:
        raise GpioError(f"invalid mode {mode!r} "
                        f"(choose from {', '.join(MODES)})")
    return mode.strip().lower()


def check_pull(pull: object) -> str:
    if not isinstance(pull, str) or pull.strip().lower() not in PULLS:
        raise GpioError(f"invalid pull {pull!r} "
                        f"(choose from {', '.join(PULLS)})")
    return pull.strip().lower()


def check_level(level: object) -> int:
    if isinstance(level, bool):
        return int(level)
    if not isinstance(level, int) or level not in (0, 1):
        raise GpioError(f"level must be 0 or 1, got {level!r}")
    return level


def check_edge(edge: object) -> str:
    if not isinstance(edge, str) or edge.strip().lower() not in EDGES:
        raise GpioError(f"invalid edge {edge!r} "
                        f"(choose from {', '.join(EDGES)})")
    return edge.strip().lower()


def check_tick(ms: object) -> int:
    if isinstance(ms, bool) or not isinstance(ms, int) or ms < 0:
        raise GpioError(f"advance must be a non-negative integer, got {ms!r}")
    return ms


# --------------------------------------------------------------------------- #
# Debouncing
# --------------------------------------------------------------------------- #
class Debouncer:
    """Collapse contact bounce: a level must persist before it is accepted.

    ``feed`` returns the new stable level when one is accepted, otherwise
    ``None``. The first fed level is only adopted immediately when no
    ``initial`` value was supplied.
    """

    def __init__(self, min_stable: int = DEFAULT_DEBOUNCE,
                 initial: int | None = None) -> None:
        if isinstance(min_stable, bool) or not isinstance(min_stable, int):
            raise GpioError("min_stable must be an integer")
        if min_stable < 1:
            raise GpioError(f"min_stable must be >= 1, got {min_stable}")
        self.min_stable = min_stable
        self.stable = None if initial is None else check_level(initial)
        self._candidate = self.stable
        self._count = 0

    def feed(self, level: object) -> int | None:
        value = check_level(level)
        if self.stable is None:
            self.stable = value
            self._candidate = value
            self._count = 0
            return value
        if value == self.stable:
            self._candidate = value
            self._count = 0
            return None
        if value == self._candidate:
            self._count += 1
        else:
            self._candidate = value
            self._count = 1
        if self._count >= self.min_stable:
            self.stable = value
            self._candidate = value
            self._count = 0
            return value
        return None

    def to_dict(self) -> dict:
        return {"min_stable": self.min_stable, "stable": self.stable,
                "candidate": self._candidate, "count": self._count}


# --------------------------------------------------------------------------- #
# Pins and edges
# --------------------------------------------------------------------------- #
@dataclass
class EdgeEvent:
    tick: int
    pin: int
    edge: str
    level: int

    def to_dict(self) -> dict:
        return {"tick": self.tick, "pin": self.pin, "edge": self.edge,
                "level": self.level}


@dataclass
class Pin:
    number: int
    mode: str = "input"
    pull: str = "up"
    level: int = 1
    pwm_frequency: float = 0.0
    pwm_duty: float = 0.0
    events: list[EdgeEvent] = field(default_factory=list)

    @property
    def has_pwm(self) -> bool:
        return self.pwm_frequency > 0.0

    def rest_level(self) -> int:
        """Level an un-driven input settles at under its pull resistor."""
        if self.pull == "up":
            return 1
        if self.pull == "down":
            return 0
        return 0

    def to_dict(self) -> dict:
        payload = {"number": self.number, "mode": self.mode,
                   "pull": self.pull, "level": self.level,
                   "events": len(self.events)}
        if self.has_pwm:
            payload["pwm"] = {"frequency": self.pwm_frequency,
                              "duty": self.pwm_duty}
        return payload


# --------------------------------------------------------------------------- #
# Board
# --------------------------------------------------------------------------- #
class Board:
    """A deterministic set of GPIO pins with an integer clock in ms."""

    def __init__(self, name: str = "gpio-sim") -> None:
        if not isinstance(name, str) or not name.strip():
            raise GpioError("board name must be a non-empty string")
        self.name = name.strip()
        self.tick = 0
        self._pins: dict[int, Pin] = {}
        self._listeners: dict[int, list[tuple[str, object]]] = {}
        self._debouncers: dict[int, Debouncer] = {}

    # -- pin lifecycle ---------------------------------------------------- #
    def add_pin(self, number: int, mode: str = "input",
                pull: str = "up") -> Pin:
        target = check_pin(number)
        if target in self._pins:
            raise GpioError(f"pin {target} is already claimed")
        wanted = check_mode(mode)
        if wanted == "output":
            pin = Pin(number=target, mode="output", pull="none", level=0)
        else:
            chosen = check_pull(pull)
            pin = Pin(number=target, mode="input", pull=chosen,
                      level=1 if chosen == "up" else 0)
        self._pins[target] = pin
        return pin

    def pin(self, number: int) -> Pin:
        target = check_pin(number)
        if target not in self._pins:
            raise GpioError(f"pin {target} is not claimed")
        return self._pins[target]

    def release(self, number: int) -> Pin:
        target = check_pin(number)
        pin = self.pin(target)
        self._pins.pop(target)
        self._listeners.pop(target, None)
        self._debouncers.pop(target, None)
        return pin

    @property
    def pins(self) -> list[Pin]:
        return [self._pins[key] for key in sorted(self._pins)]

    # -- configuration ---------------------------------------------------- #
    def set_mode(self, number: int, mode: str, pull: str | None = None) -> Pin:
        pin = self.pin(number)
        wanted = check_mode(mode)
        if wanted == "output":
            pin.mode = "output"
            pin.pull = "none"
            pin.level = 0
            pin.pwm_frequency = 0.0
            pin.pwm_duty = 0.0
            self._debouncers.pop(pin.number, None)
        else:
            chosen = check_pull(pin.pull if pull is None else pull)
            pin.mode = "input"
            pin.pull = chosen
            pin.level = 1 if chosen == "up" else 0
            pin.pwm_frequency = 0.0
            pin.pwm_duty = 0.0
        return pin

    def attach_debouncer(self, number: int,
                         min_stable: int = DEFAULT_DEBOUNCE) -> Debouncer:
        pin = self.pin(number)
        if pin.mode != "input":
            raise GpioError(f"pin {pin.number} is an output; debouncing "
                            f"only applies to inputs")
        debouncer = Debouncer(min_stable, initial=pin.level)
        self._debouncers[pin.number] = debouncer
        return debouncer

    # -- clocks ----------------------------------------------------------- #
    def advance(self, ms: int = 1) -> int:
        self.tick += check_tick(ms)
        return self.tick

    # -- driving pins ----------------------------------------------------- #
    def _emit(self, pin: Pin, edge: str) -> None:
        if edge not in ("rising", "falling"):
            raise GpioError(f"cannot emit edge {edge!r}")
        event = EdgeEvent(tick=self.tick, pin=pin.number, edge=edge,
                          level=pin.level)
        pin.events.append(event)
        for wanted, callback in self._listeners.get(pin.number, []):
            if wanted in ("both", edge):
                callback(event)

    def write(self, number: int, level: int) -> int:
        pin = self.pin(number)
        if pin.mode != "output":
            raise GpioError(f"pin {pin.number} is an input; cannot write")
        value = check_level(level)
        if value == pin.level:
            return pin.level
        pin.level = value
        self._emit(pin, "rising" if value else "falling")
        return pin.level

    def read(self, number: int) -> int:
        return self.pin(number).level

    def set_input(self, number: int, level: int) -> int:
        pin = self.pin(number)
        if pin.mode != "input":
            raise GpioError(f"pin {pin.number} is an output; cannot drive "
                            f"it as an input")
        value = check_level(level)
        debouncer = self._debouncers.get(pin.number)
        if debouncer is not None:
            stable = debouncer.feed(value)
            if stable is None:
                return pin.level
            value = stable
        if value == pin.level:
            return pin.level
        pin.level = value
        self._emit(pin, "rising" if value else "falling")
        return pin.level

    def add_listener(self, number: int, callback, edge: str = "both") -> None:
        pin = self.pin(number)
        if not callable(callback):
            raise GpioError("listener must be callable")
        wanted = check_edge(edge)
        self._listeners.setdefault(pin.number, []).append((wanted, callback))

    def edges(self, number: int, edge: str | None = None) -> list[EdgeEvent]:
        pin = self.pin(number)
        if edge is None:
            return list(pin.events)
        wanted = check_edge(edge)
        if wanted == "both":
            return list(pin.events)
        return [event for event in pin.events if event.edge == wanted]

    # -- PWM -------------------------------------------------------------- #
    def pwm(self, number: int, frequency: float, duty: float) -> Pin:
        pin = self.pin(number)
        if pin.mode != "output":
            raise GpioError(f"pin {pin.number} is an input; PWM needs an "
                            f"output")
        if isinstance(frequency, bool) or not isinstance(frequency,
                                                        (int, float)):
            raise GpioError(f"frequency must be a number, got {frequency!r}")
        if not math.isfinite(frequency) or frequency <= 0:
            raise GpioError(f"frequency must be > 0, got {frequency}")
        if isinstance(duty, bool) or not isinstance(duty, (int, float)):
            raise GpioError(f"duty must be a number, got {duty!r}")
        if not math.isfinite(duty) or not 0.0 <= duty <= MAX_DUTY:
            raise GpioError(f"duty must be in 0..{MAX_DUTY:g}, got {duty}")
        pin.pwm_frequency = float(frequency)
        pin.pwm_duty = float(duty)
        return pin

    def clear_pwm(self, number: int) -> Pin:
        pin = self.pin(number)
        pin.pwm_frequency = 0.0
        pin.pwm_duty = 0.0
        return pin

    def pwm_sample(self, number: int, elapsed: float) -> int:
        """Level of a PWM pin ``elapsed`` seconds after the waveform starts."""
        pin = self.pin(number)
        if not pin.has_pwm:
            raise GpioError(f"pin {pin.number} has no PWM configured")
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)):
            raise GpioError(f"elapsed must be a number, got {elapsed!r}")
        if not math.isfinite(elapsed) or elapsed < 0:
            raise GpioError(f"elapsed must be >= 0, got {elapsed}")
        if pin.pwm_duty <= 0.0:
            return 0
        if pin.pwm_duty >= MAX_DUTY:
            return 1
        phase = (elapsed * pin.pwm_frequency) % 1.0
        return 1 if phase < pin.pwm_duty / MAX_DUTY else 0

    def pwm_average(self, number: int) -> float:
        pin = self.pin(number)
        if not pin.has_pwm:
            raise GpioError(f"pin {pin.number} has no PWM configured")
        return pin.pwm_duty / MAX_DUTY

    # -- reporting -------------------------------------------------------- #
    def snapshot(self) -> dict:
        return {"name": self.name, "tick": self.tick,
                "pins": [pin.to_dict() for pin in self.pins],
                "edges": sum(len(pin.events) for pin in self.pins)}

    def to_dict(self, keep_events: bool = False) -> dict:
        payload = self.snapshot()
        if keep_events:
            payload["events"] = [
                event.to_dict() for pin in self.pins for event in pin.events]
        return payload


# --------------------------------------------------------------------------- #
# Device helpers
# --------------------------------------------------------------------------- #
def _ensure(board: Board, number: int, mode: str, pull: str = "up") -> Pin:
    try:
        pin = board.pin(number)
    except GpioError:
        return board.add_pin(number, mode=mode, pull=pull)
    if pin.mode != mode:
        board.set_mode(number, mode, pull if mode == "input" else None)
    return board.pin(number)


class Led:
    """An output pin used as an indicator, optionally active-low."""

    def __init__(self, board: Board, number: int, active_high: bool = True
                 ) -> None:
        self.board = board
        self.number = check_pin(number)
        self.active_high = bool(active_high)
        self.pin = _ensure(board, self.number, "output")
        self.pin.level = 0 if self.active_high else 1

    @property
    def is_on(self) -> bool:
        return bool(self.pin.level) == self.active_high

    def on(self) -> None:
        self.board.write(self.number, 1 if self.active_high else 0)

    def off(self) -> None:
        self.board.write(self.number, 0 if self.active_high else 1)

    def toggle(self) -> bool:
        if self.is_on:
            self.off()
        else:
            self.on()
        return self.is_on

    def to_dict(self) -> dict:
        return {"pin": self.number, "on": self.is_on,
                "active_high": self.active_high}


class Button:
    """An input pin with a pull resistor, active-low by default."""

    def __init__(self, board: Board, number: int, pull: str = "up",
                 active_low: bool = True) -> None:
        self.board = board
        self.number = check_pin(number)
        self.active_low = bool(active_low)
        self.pin = _ensure(board, self.number, "input", pull)
        self.pin.pull = check_pull(pull)
        self.pin.level = self.pin.rest_level()

    @property
    def is_pressed(self) -> bool:
        level = self.board.read(self.number)
        return level == 0 if self.active_low else level == 1

    def press(self) -> None:
        self.board.set_input(self.number, 0 if self.active_low else 1)

    def release(self) -> None:
        self.board.set_input(self.number, 1 if self.active_low else 0)

    def to_dict(self) -> dict:
        return {"pin": self.number, "pressed": self.is_pressed,
                "pull": self.pin.pull, "active_low": self.active_low}


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #
def _scenario_step(step: object, index: int) -> dict:
    if not isinstance(step, dict):
        raise GpioError(f"step {index} is not an object")
    op = step.get("op")
    if not isinstance(op, str) or op not in OPS:
        raise GpioError(f"step {index} has invalid op {op!r} "
                        f"(choose from {', '.join(OPS)})")
    if op == "advance":
        if "ms" not in step:
            raise GpioError(f"step {index} (advance) needs 'ms'")
        return {"op": op, "ms": check_tick(step["ms"])}
    if "pin" not in step:
        raise GpioError(f"step {index} ({op}) needs 'pin'")
    payload = {"op": op, "pin": check_pin(step["pin"])}
    if op == "pwm":
        missing = {"frequency", "duty"} - set(step)
        if missing:
            raise GpioError(f"step {index} (pwm) is missing "
                            f"{sorted(missing)}")
        payload["frequency"] = step["frequency"]
        payload["duty"] = step["duty"]
    if op in ("write", "set_input"):
        if "level" not in step:
            raise GpioError(f"step {index} ({op}) needs 'level'")
        payload["level"] = check_level(step["level"])
    return payload


def load_scenario(path: Path | str | None = None) -> dict:
    target = Path(path) if path is not None else SCENARIO_FILE
    if not target.is_file():
        raise GpioError(f"scenario not found: {target}")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GpioError(f"scenario is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GpioError("scenario must be a JSON object")
    if "pins" not in payload or "steps" not in payload:
        raise GpioError("scenario needs 'pins' and 'steps'")

    raw_pins = payload["pins"]
    if not isinstance(raw_pins, list) or not raw_pins:
        raise GpioError("'pins' must be a non-empty list")
    pins: list[dict] = []
    seen: set[int] = set()
    for index, entry in enumerate(raw_pins, start=1):
        if not isinstance(entry, dict) or "number" not in entry:
            raise GpioError(f"pin entry {index} needs a 'number'")
        number = check_pin(entry["number"])
        if number in seen:
            raise GpioError(f"duplicate pin {number} in scenario")
        seen.add(number)
        pins.append({"number": number,
                     "mode": check_mode(entry.get("mode", "input")),
                     "pull": check_pull(entry.get("pull", "up"))})

    raw_steps = payload["steps"]
    if not isinstance(raw_steps, list):
        raise GpioError("'steps' must be a list")
    steps = [_scenario_step(step, index)
             for index, step in enumerate(raw_steps, start=1)]
    return {"name": str(payload.get("name", "scenario")), "pins": pins,
            "steps": steps}


def run_scenario(scenario: dict) -> dict:
    """Replay a validated scenario, returning a transcript and snapshot."""
    if not isinstance(scenario, dict) or "pins" not in scenario:
        raise GpioError("run_scenario needs a scenario dict")
    board = Board(str(scenario.get("name", "scenario")))
    for entry in scenario["pins"]:
        board.add_pin(entry["number"], entry.get("mode", "input"),
                      entry.get("pull", "up"))

    transcript: list[str] = []
    for step in scenario["steps"]:
        op = step["op"]
        if op == "advance":
            tick = board.advance(step["ms"])
            transcript.append(f"advance {step['ms']} ms (tick {tick})")
        elif op == "write":
            level = board.write(step["pin"], step["level"])
            transcript.append(f"write pin {step['pin']} -> {level}")
        elif op == "read":
            level = board.read(step["pin"])
            transcript.append(f"read pin {step['pin']} -> {level}")
        elif op == "set_input":
            level = board.set_input(step["pin"], step["level"])
            transcript.append(f"set_input pin {step['pin']} -> {level}")
        elif op == "pwm":
            pin = board.pwm(step["pin"], step["frequency"], step["duty"])
            transcript.append(f"pwm pin {pin.number} {pin.pwm_frequency:g} Hz "
                              f"{pin.pwm_duty:g}%")
        else:
            pin = board.clear_pwm(step["pin"])
            transcript.append(f"clear_pwm pin {pin.number}")

    return {"transcript": transcript, "snapshot": board.snapshot(),
            "board": board}


def render_report(board: Board) -> str:
    snapshot = board.snapshot()
    lines = [
        "GPIO BOARD",
        "=" * 74,
        f"Board: {snapshot['name']}    Pins: {len(snapshot['pins'])}    "
        f"Tick: {snapshot['tick']} ms    Edges: {snapshot['edges']}",
        "",
        f"{'pin':>4} {'mode':<8} {'pull':<6} {'level':>5} {'events':>6}  pwm",
        "-" * 74,
    ]
    for pin in board.pins:
        pwm = (f"{pin.pwm_frequency:g} Hz {pin.pwm_duty:g}%"
               if pin.has_pwm else "-")
        lines.append(f"{pin.number:>4} {pin.mode:<8} {pin.pull:<6} "
                     f"{pin.level:>5} {len(pin.events):>6}  {pwm}")
    if snapshot["edges"]:
        lines += ["", "Recent edges:"]
        every = sorted((event for pin in board.pins for event in pin.events),
                       key=lambda event: event.tick)[-6:]
        for event in every:
            lines.append(f"  tick {event.tick:>5}  pin {event.pin:>2}  "
                         f"{event.edge:<7} -> {event.level}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo(data_dir: Path | None = None) -> int:
    root = data_dir or DATA_DIR
    print("=" * 74)
    print(" GPIO PINS SIMULATOR - offline demo")
    print(" Modes, pulls, edges, PWM and debouncing with no hardware.")
    print("=" * 74)

    board = Board("demo")
    led = Led(board, 17)
    button = Button(board, 18, pull="up")
    print(f"\nBoard           : {board.name}, pins 17 (led) and 18 (button)")
    assert board.read(17) == 0, "an output must start low"
    assert board.read(18) == 1, "a pulled-up input must idle high"

    # --- a lamp driven through the public API -------------------------- #
    led.on()
    assert board.read(17) == 1 and led.is_on
    board.advance(250)
    led.off()
    assert board.read(17) == 0 and not led.is_on
    board.advance(250)
    board.write(17, 1)
    assert led.toggle() is False
    assert len(board.edges(17, "rising")) == 2
    assert len(board.edges(17, "falling")) == 2
    print(f"Led             : 2 rising + 2 falling edges, "
          f"level {board.read(17)}")

    # --- a button with a pull resistor --------------------------------- #
    seen: list[tuple[int, str]] = []
    board.add_listener(18, lambda event: seen.append((event.tick,
                                                      event.edge)))
    board.advance(100)
    button.press()
    assert button.is_pressed and board.read(18) == 0
    board.advance(100)
    button.release()
    assert not button.is_pressed and board.read(18) == 1
    assert [edge for _, edge in seen] == ["falling", "rising"]
    assert [tick for tick, _ in seen] == [600, 700]
    print(f"Button          : pressed at tick 600, released at 700 "
          f"({len(seen)} listener calls)")

    # --- contact bounce must not produce extra edges -------------------- #
    noisy = Board("bounce")
    noisy.add_pin(5, mode="input", pull="up")
    noisy.attach_debouncer(5, min_stable=3)
    for level in (0, 1, 0, 0, 0, 1, 0, 0, 0):
        noisy.set_input(5, level)
        noisy.advance(1)
    bounced = noisy.edges(5)
    assert len(bounced) == 1, [event.to_dict() for event in bounced]
    assert bounced[0].edge == "falling" and bounced[0].level == 0
    plain = Board("raw")
    plain.add_pin(5, mode="input", pull="up")
    for level in (0, 1, 0, 0, 0, 1, 0, 0, 0):
        plain.set_input(5, level)
    print(f"Debounce        : 9 noisy samples -> {len(bounced)} edge "
          f"(raw: {len(plain.edges(5))} edges)")

    # --- analytic PWM -------------------------------------------------- #
    board.add_pin(22, mode="output")
    board.pwm(22, frequency=4.0, duty=25.0)
    pattern = [board.pwm_sample(22, index / 16.0) for index in range(8)]
    assert pattern == [1, 0, 0, 0, 1, 0, 0, 0], pattern
    assert sum(pattern) / len(pattern) == board.pwm_average(22) == 0.25
    board.pwm(22, 4.0, 0.0)
    assert all(board.pwm_sample(22, index / 8.0) == 0 for index in range(8))
    board.pwm(22, 4.0, 100.0)
    assert all(board.pwm_sample(22, index / 8.0) == 1 for index in range(8))
    board.pwm(22, 4.0, 25.0)
    print(f"PWM pin 22      : 4 Hz 25% -> {''.join(map(str, pattern))} "
          f"(average {board.pwm_average(22):.2f})")

    # --- the bundled scenario replays deterministically ---------------- #
    scenario = load_scenario(root / "scenario.json")
    first = run_scenario(scenario)
    second = run_scenario(load_scenario(root / "scenario.json"))
    assert first["transcript"] == second["transcript"], "replay is unstable"
    assert first["snapshot"] == second["snapshot"]
    assert len(first["transcript"]) == len(scenario["steps"])
    print(f"Scenario        : {scenario['name']} replayed "
          f"{len(scenario['steps'])} steps over "
          f"{len(scenario['pins'])} pins (identical twice)")

    # --- guard rails ---------------------------------------------------- #
    checks = [
        (lambda: board.write(18, 1), "input"),
        (lambda: board.set_input(17, 1), "output"),
        (lambda: board.add_pin(17), "already claimed"),
        (lambda: board.pin(99), "out of range"),
        (lambda: board.write(17, 2), "level must be 0 or 1"),
        (lambda: board.pwm(18, 4.0, 25.0), "input"),
        (lambda: board.pwm(17, 0.0, 25.0), "frequency must be > 0"),
        (lambda: board.pwm(17, 4.0, 120.0), "duty must be in"),
        (lambda: board.pwm_sample(17, 0.0), "no PWM"),
        (lambda: Board("x").add_pin(1, mode="tri"), "invalid mode"),
        (lambda: Board("x").add_pin(1, pull="sideways"), "invalid pull"),
    ]
    for action, needle in checks:
        try:
            action()
        except GpioError as exc:
            assert needle in str(exc), (needle, str(exc))
        else:
            raise GpioError(f"guard rail did not fire for {needle!r}")

    print()
    print(render_report(board))
    print()
    print(render_report(first["board"]))

    print("\nCross-checks OK: led edges match the writes, the button "
          "reports press/release in order, three-sample debouncing "
          "collapses nine noisy readings to one edge, PWM samples match "
          "the configured duty exactly, the bundled scenario replays "
          "identically, and every guard rail fires")
    print("Demo completed successfully.")
    return 0
