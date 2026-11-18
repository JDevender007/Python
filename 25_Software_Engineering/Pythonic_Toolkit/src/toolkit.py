"""Pythonic toolkit: decorators, context managers, generators, class idioms.

Decorators      - @timed, @retry, @cached, @validate (signature-aware)
Context managers- timed_block, temp_directory, capture_stdout
Generators      - chunked, flatten, sliding_window (lazy iterators)
Class idioms    - frozen/slots dataclasses, __post_init__ validation,
                  a manual __slots__ class with an AttributeError contract

Everything is stdlib-only and deterministic: bundled records ship in
data/records.json, nothing is downloaded at runtime. No network, no keys.
"""

from __future__ import annotations

import functools
import inspect
import io
import json
import shutil
import tempfile
import time
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence, TypeVar

RECORDS = Path(__file__).resolve().parents[1] / "data" / "records.json"
RECIPE_NAMES = ("decorators", "context-managers", "generators", "dataclasses")

T = TypeVar("T")

# Runtime spec used by @validate and by the record loader.
RECORD_SPEC: dict[str, dict[str, Any]] = {
    "name": {"type": str},
    "age": {"type": int, "min": 0, "max": 150},
    "score": {"type": (int, float), "min": 0, "max": 100},
}


class ToolkitError(RuntimeError):
    """Raised for bad configuration, bad recipes, and bad input data."""


class ValidationError(ToolkitError):
    """Raised when a value violates its runtime spec."""


# --------------------------------------------------------------------------- #
# Runtime validation core (shared by @validate and record loading)
# --------------------------------------------------------------------------- #
def _describe(types: Any) -> str:
    if isinstance(types, tuple):
        return " or ".join(t.__name__ for t in types)
    return types.__name__


def check_value(name: str, value: Any, spec: Any) -> None:
    """Check one value against a type or a {'type','min','max','choices'}."""
    if isinstance(spec, dict):
        expected = spec.get("type", object)
        if isinstance(expected, type) and expected is int \
                and isinstance(value, bool):
            raise ValidationError(f"{name} must be int")
        if not isinstance(value, expected):
            raise ValidationError(f"{name} must be {_describe(expected)}")
        if "min" in spec and value < spec["min"]:
            raise ValidationError(f"{name} must be >= {spec['min']}")
        if "max" in spec and value > spec["max"]:
            raise ValidationError(f"{name} must be <= {spec['max']}")
        if "choices" in spec and value not in spec["choices"]:
            raise ValidationError(
                f"{name} must be one of {sorted(spec['choices'])}")
        return
    if isinstance(spec, type) or isinstance(spec, tuple):
        if spec is int and isinstance(value, bool):
            raise ValidationError(f"{name} must be int")
        if not isinstance(value, spec):
            raise ValidationError(f"{name} must be {_describe(spec)}")
        return
    raise ToolkitError(f"unsupported spec for {name!r}: {spec!r}")


def check_record(record: Any, spec: dict[str, Any]) -> None:
    """Validate one record: structure first, then each field."""
    if not isinstance(record, dict):
        raise ValidationError("record must be a dict")
    missing = [key for key in spec if key not in record]
    if missing:
        raise ValidationError(
            f"missing field(s): {', '.join(missing)}")
    for key, field_spec in spec.items():
        check_value(key, record[key], field_spec)


# --------------------------------------------------------------------------- #
# Decorator 1: timing
# --------------------------------------------------------------------------- #
def timed(fn: Callable[..., T]) -> Callable[..., T]:
    """Record wall-clock duration on ``fn.last_elapsed`` after each call."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            wrapper.last_elapsed = time.perf_counter() - start

    wrapper.last_elapsed: float = 0.0
    return wrapper


# --------------------------------------------------------------------------- #
# Decorator 2: retry
# --------------------------------------------------------------------------- #
def retry(times: int = 3, delay: float = 0.0,
          exceptions: type[BaseException] | tuple[type[BaseException], ...]
          = Exception) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry a failing callable; give up after ``times`` attempts."""
    if isinstance(exceptions, type):
        exceptions = (exceptions,)
    if not exceptions or not all(
            isinstance(e, type) and issubclass(e, BaseException)
            for e in exceptions):
        raise ToolkitError("exceptions must be an exception class or tuple")
    if not isinstance(times, int) or isinstance(times, bool) or times < 1:
        raise ToolkitError("retry times must be an int >= 1")
    if delay < 0:
        raise ToolkitError("retry delay must be >= 0")

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            wrapper.attempts = 0
            last: BaseException | None = None
            for attempt in range(1, times + 1):
                wrapper.attempts = attempt
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last = exc
                    if attempt < times and delay:
                        time.sleep(delay)
            assert last is not None
            raise last

        wrapper.attempts: int = 0
        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# Decorator 3: caching
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CacheInfo:
    hits: int
    misses: int
    maxsize: int | None


def cached(maxsize: int = 128) -> Callable[[Callable[..., T]],
                                           Callable[..., T]]:
    """Memoise hashable-argument calls; exposes cache_info/cache_clear."""
    if not isinstance(maxsize, int) or isinstance(maxsize, bool) \
            or maxsize < 1:
        raise ToolkitError("cached maxsize must be an int >= 1")

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        store: dict[Any, T] = {}
        hits = 0
        misses = 0

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            nonlocal hits, misses
            key = (args, tuple(sorted(kwargs.items())))
            try:
                hash(key)
            except TypeError:          # unhashable args: bypass the cache
                return fn(*args, **kwargs)
            if key in store:
                hits += 1
                return store[key]
            misses += 1
            value = fn(*args, **kwargs)
            if len(store) >= maxsize:
                store.pop(next(iter(store)))   # oldest entry first
            store[key] = value
            return value

        def cache_info() -> CacheInfo:
            return CacheInfo(hits=hits, misses=misses, maxsize=maxsize)

        def cache_clear() -> None:
            nonlocal hits, misses
            store.clear()
            hits = 0
            misses = 0

        wrapper.cache_info = cache_info   # type: ignore[attr-defined]
        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# Decorator 4: validation
# --------------------------------------------------------------------------- #
def validate(**specs: Any) -> Callable[[Callable[..., T]],
                                        Callable[..., T]]:
    """Check named arguments against specs before the function runs."""

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        signature = inspect.signature(fn)
        unknown = [name for name in specs if name not in signature.parameters]
        if unknown:
            raise ToolkitError(
                f"validate: unknown parameter(s): {', '.join(unknown)}")

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            for name, spec in specs.items():
                if name in bound.arguments:
                    check_value(name, bound.arguments[name], spec)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# Context managers
# --------------------------------------------------------------------------- #
@dataclass
class BlockStats:
    label: str
    elapsed: float = 0.0


@contextmanager
def timed_block(label: str = "block") -> Iterator[BlockStats]:
    """Measure how long the block takes; stats.elapsed set on exit."""
    stats = BlockStats(label=label)
    start = time.perf_counter()
    try:
        yield stats
    finally:
        stats.elapsed = time.perf_counter() - start


@contextmanager
def temp_directory(prefix: str = "pytoolkit_") -> Iterator[Path]:
    """Yield a scratch directory that is always removed on exit."""
    path = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@contextmanager
def capture_stdout() -> Iterator[io.StringIO]:
    """Capture whatever the block prints into a StringIO buffer."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        yield buffer


# --------------------------------------------------------------------------- #
# Generators / iterators
# --------------------------------------------------------------------------- #
def chunked(iterable: Sequence[T] | Iterable[T],
            size: int) -> Iterator[list[T]]:
    """Yield consecutive fixed-size chunks (last chunk may be short)."""
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ToolkitError("chunk size must be an int >= 1")
    chunk: list[T] = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def flatten(nested: Any) -> Iterator[Any]:
    """Depth-first generator that flattens arbitrarily nested sequences."""
    if isinstance(nested, (list, tuple)):
        for item in nested:
            yield from flatten(item)
    else:
        yield nested


def sliding_window(sequence: Sequence[T], width: int) -> Iterator[tuple[T, ...]]:
    """Yield every contiguous window of ``width`` items."""
    if not isinstance(width, int) or isinstance(width, bool) or width < 1:
        raise ToolkitError("window width must be an int >= 1")
    items = tuple(sequence)
    for index in range(len(items) - width + 1):
        yield items[index:index + width]


# --------------------------------------------------------------------------- #
# Class idioms: dataclasses and __slots__
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Point:
    """Immutable, slot-backed value object."""

    x: float
    y: float

    def distance_to(self, other: Point) -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


@dataclass(slots=True)
class Reading:
    """Mutable record validated in __post_init__."""

    name: str
    value: float
    unit: str = "count"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValidationError("reading name must be a non-empty string")
        if isinstance(self.value, bool) or not isinstance(
                self.value, (int, float)):
            raise ValidationError("reading value must be a number")
        self.value = float(self.value)

    def scaled(self, factor: float) -> float:
        return self.value * factor


class Tally:
    """Manual __slots__: undeclared attributes raise AttributeError."""

    __slots__ = ("_count",)

    def __init__(self) -> None:
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    def bump(self, step: int = 1) -> int:
        if not isinstance(step, int) or isinstance(step, bool) or step < 1:
            raise ValidationError("step must be an int >= 1")
        self._count += step
        return self._count

    def reset(self) -> None:
        self._count = 0


# --------------------------------------------------------------------------- #
# Bundled records
# --------------------------------------------------------------------------- #
def load_records(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load and spec-validate the bundled records JSON."""
    source = Path(path) if path is not None else RECORDS
    if not source.is_file():
        raise ToolkitError(f"file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolkitError(f"could not parse {source.name}: {exc}") from exc
    if not isinstance(payload, list):
        raise ToolkitError("records file must contain a JSON array")
    if not payload:
        raise ToolkitError("records file contains no records")
    for index, record in enumerate(payload):
        try:
            check_record(record, RECORD_SPEC)
        except ValidationError as exc:
            raise ValidationError(f"record {index}: {exc}") from exc
    return payload


def record_summary(records: list[dict[str, Any]]) -> dict[str, float]:
    """Deterministic aggregate over validated records."""
    ages = [record["age"] for record in records]
    scores = [float(record["score"]) for record in records]
    return {
        "count": len(records),
        "mean_age": round(sum(ages) / len(ages), 4),
        "mean_score": round(sum(scores) / len(scores), 4),
        "max_score": max(scores),
    }


# --------------------------------------------------------------------------- #
# Recipes (one per idiom family) - used by --run and asserted by the demo
# --------------------------------------------------------------------------- #
def _recipe_decorators() -> str:
    @timed
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5 and add.last_elapsed >= 0.0

    attempts_used: list[int] = []

    @retry(times=4, exceptions=RuntimeError)
    def flaky() -> str:
        attempts_used.append(1)
        if len(attempts_used) < 3:
            raise RuntimeError("transient")
        return "ok"

    assert flaky() == "ok" and flaky.attempts == 3

    @cached(maxsize=8)
    def square(n: int) -> int:
        return n * n

    assert square(7) == 49 and square(7) == 49
    info = square.cache_info()
    assert info.hits == 1 and info.misses == 1

    @validate(age={"type": int, "min": 0, "max": 150})
    def voter(age: int) -> bool:
        return age >= 18

    assert voter(30) is True
    try:
        voter(-1)
    except ValidationError:
        rejected = True
    else:
        rejected = False
    assert rejected, "validate must reject out-of-range input"
    return (f"  decorators     -> timed elapsed recorded "
            f"({add.last_elapsed >= 0.0}), "
            f"retry attempts={flaky.attempts}, cache "
            f"hits={info.hits}/misses={info.misses}, "
            f"validate rejects age=-1")


def _recipe_context() -> str:
    with temp_directory() as tmp:
        probe = tmp / "probe.txt"
        probe.write_text("scratch", encoding="utf-8")
        assert probe.is_file()
    assert not tmp.exists(), "temp directory must be cleaned up"

    with capture_stdout() as buffer:
        print("captured line")
    assert buffer.getvalue().strip() == "captured line"

    with timed_block("demo") as stats:
        sum(range(1000))
    assert stats.elapsed >= 0.0 and stats.label == "demo"
    return (f"  context-managers -> temp dir removed={not tmp.exists()}, "
            f"captured {len(buffer.getvalue().strip())} chars, "
            f"block {stats.label} elapsed recorded "
            f"({stats.elapsed >= 0.0})")


def _recipe_generators() -> str:
    chunks = list(chunked(range(10), 4))
    assert chunks == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]]
    flat = list(flatten([1, [2, [3, [4]]], 5]))
    assert flat == [1, 2, 3, 4, 5]
    windows = list(sliding_window("abcde", 3))
    assert len(windows) == 3 and windows[0] == ("a", "b", "c")
    lazy = chunked(range(1_000_000), 2)
    assert next(lazy) == [0, 1]          # nothing materialised up front
    return (f"  generators      -> {len(chunks)} chunks cover 10 items, "
            f"flatten depth 4 -> {len(flat)} items, "
            f"{len(windows)} windows (lazy)")


def _recipe_dataclasses() -> str:
    origin, target = Point(0.0, 0.0), Point(3.0, 4.0)
    assert origin.distance_to(target) == 5.0
    try:
        origin.x = 9.0
    except Exception:
        frozen = True
    else:
        frozen = False
    assert frozen, "frozen dataclass must reject assignment"

    reading = Reading(name="latency", value=12)
    assert reading.value == 12.0 and isinstance(reading.value, float)
    try:
        Reading(name="", value=1.0)
    except ValidationError:
        invalid_rejected = True
    else:
        invalid_rejected = False
    assert invalid_rejected

    tally = Tally()
    tally.bump(2)
    tally.bump(3)
    try:
        tally.extra = "nope"
    except AttributeError:
        slots_enforced = True
    else:
        slots_enforced = False
    assert slots_enforced and tally.count == 5
    return (f"  dataclasses     -> frozen Point dist={origin.distance_to(target)}, "
            f"__post_init__ rejects empty name, __slots__ blocks new "
            f"attributes, Tally count={tally.count}")


def run_recipe(name: str) -> str:
    """Run one idiom recipe by name (validated first) and return it."""
    key = str(name).strip().lower()
    if key not in RECIPE_NAMES:
        raise ToolkitError(
            f"unknown recipe {name!r} "
            f"(expected one of {', '.join(RECIPE_NAMES)})")
    if key == "decorators":
        return _recipe_decorators()
    if key == "context-managers":
        return _recipe_context()
    if key == "generators":
        return _recipe_generators()
    return _recipe_dataclasses()


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    """Exercise every idiom with self-assertions; always returns 0."""
    print("=" * 68)
    print(" PYTHONIC TOOLKIT")
    print(" Decorators, context managers, generators, class idioms.")
    print(" Stdlib only; bundled records; fully offline.")
    print("=" * 68)

    records = load_records()
    summary = record_summary(records)
    print(f"\nLoaded {len(records)} records from {RECORDS.name}; "
          f"mean age {summary['mean_age']}, "
          f"mean score {summary['mean_score']}")

    sections = [run_recipe(name) for name in RECIPE_NAMES]
    print()
    for line in sections:
        print(line)

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(sections) == len(RECIPE_NAMES), "missing recipe section"

    # records validate identically on a second pass (idempotent loader)
    assert load_records() == records, "loader is not deterministic"
    assert summary["count"] == len(records)
    assert 0 <= summary["max_score"] <= 100

    # generators partition exactly: every item appears exactly once
    items = list(range(17))
    reassembled = [item for chunk in chunked(items, 5) for item in chunk]
    assert reassembled == items, "chunking lost or duplicated items"
    width = 4
    window_total = sum(len(w) for w in sliding_window(items, width))
    assert window_total == width * (len(items) - width + 1), \
        "window arithmetic wrong"

    # decorator contracts are stable across calls
    @cached()
    def cube(n: int) -> int:
        return n ** 3

    first = [cube(n) for n in range(5)]
    again = [cube(n) for n in range(5)]
    assert first == again, "cached results diverged"
    info = cube.cache_info()
    assert info.misses == 5 and info.hits == 5

    print(f"\nCross-checks OK: {len(RECIPE_NAMES)} recipes, "
          f"{len(records)} records re-validated, chunk/window arithmetic, "
          f"cache hits={info.hits}")
    print("Demo completed successfully.")
    return 0
