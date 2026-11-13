"""Five classic Gang-of-Four design patterns - runnable, testable, offline.

Singleton   - a metaclass-guaranteed single instance per class
Factory     - builds order objects by kind from a pluggable registry
Observer    - a pub/sub event bus with ordered, isolated notification
Strategy    - interchangeable pricing algorithms behind one interface
Decorator   - composable wrappers around a text-source component

Each pattern is deliberately tiny: the value is the *contract* the pattern
promises (single instance, pluggable construction, ordered broadcast,
swappable algorithm, order-sensitive composition) and the test suite proves
each contract. Bundled order records ship in data/orders.json - no network,
no downloads, fully deterministic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

DEMO_ORDERS = Path(__file__).resolve().parents[1] / "data" / "orders.json"

PATTERN_NAMES = ("singleton", "factory", "observer", "strategy", "decorator")
ORDER_KINDS = ("standard", "express", "digital")
REQUIRED_ORDER_FIELDS = ("id", "kind", "weight_kg", "distance_km", "items")


class PatternError(RuntimeError):
    """Raised for bad data, unknown kinds, and broken pattern contracts."""


# --------------------------------------------------------------------------- #
# Data: bundled order records
# --------------------------------------------------------------------------- #
def load_orders(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load and validate the bundled order records (JSON list of dicts)."""
    source = Path(path) if path is not None else DEMO_ORDERS
    if not source.is_file():
        raise PatternError(f"file not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PatternError(f"could not parse {source.name}: {exc}") from exc

    if not isinstance(payload, list):
        raise PatternError("orders file must contain a JSON array")
    if not payload:
        raise PatternError("orders file contains no records")
    for index, record in enumerate(payload):
        _validate_record(record, index)
    return payload


def _validate_record(record: Any, index: int) -> None:
    if not isinstance(record, dict):
        raise PatternError(f"record {index} must be a JSON object")
    missing = [f for f in REQUIRED_ORDER_FIELDS if f not in record]
    if missing:
        raise PatternError(
            f"record {index} missing field(s): {', '.join(missing)}")
    kind = record["kind"]
    if kind not in ORDER_KINDS:
        raise PatternError(
            f"record {index}: unknown order kind {kind!r} "
            f"(expected one of {', '.join(ORDER_KINDS)})")
    for name in ("weight_kg", "distance_km"):
        value = record[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PatternError(f"record {index}: {name} must be a number")
        if value < 0:
            raise PatternError(f"record {index}: {name} must be >= 0")
    if isinstance(record["items"], bool) or not isinstance(record["items"], int):
        raise PatternError(f"record {index}: items must be an integer")
    if record["items"] < 1:
        raise PatternError(f"record {index}: items must be >= 1")


# --------------------------------------------------------------------------- #
# Pattern 1: Singleton (metaclass)
# --------------------------------------------------------------------------- #
class SingletonMeta(type):
    """Metaclass that guarantees one instance per concrete class."""

    _instances: dict[type, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


def reset_singletons() -> None:
    """Forget every cached instance (test isolation / demo repeatability)."""
    SingletonMeta._instances.clear()


class AppConfig(metaclass=SingletonMeta):
    """The singleton: one shared configuration store per process."""

    def __init__(self) -> None:
        # only runs the first time; later calls return the cached instance
        self._settings: dict[str, Any] = {"env": "offline", "retries": 3}

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._settings)


# --------------------------------------------------------------------------- #
# Pattern 2: Factory (registry of builders)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Order:
    """Immutable order product built by the factory."""

    id: str
    kind: str
    weight_kg: float
    distance_km: float
    items: int

    @property
    def is_digital(self) -> bool:
        return self.kind == "digital"


class OrderFactory:
    """Registers a builder per order kind and constructs records by kind."""

    def __init__(self) -> None:
        self._builders: dict[str, Callable[[dict[str, Any]], Order]] = {}

    def register(self, kind: str, builder: Callable[[dict[str, Any]], Order]
                 ) -> None:
        if not kind:
            raise PatternError("order kind must be a non-empty string")
        self._builders[kind] = builder

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._builders))

    def create(self, record: dict[str, Any]) -> Order:
        if not isinstance(record, dict):
            raise PatternError("order record must be a dict")
        kind = record.get("kind")
        if kind not in self._builders:
            raise PatternError(
                f"unknown order kind {kind!r} "
                f"(registered: {', '.join(self.kinds) or 'none'})")
        try:
            return self._builders[kind](record)
        except KeyError as exc:
            raise PatternError(
                f"record for {kind} order missing field: {exc}") from exc

    def create_many(self, records: list[dict[str, Any]]) -> list[Order]:
        return [self.create(record) for record in records]


def _build_order(record: dict[str, Any]) -> Order:
    """Shared builder: validates fields defensively, then builds."""
    order_id = record["id"]
    if not isinstance(order_id, str) or not order_id:
        raise PatternError("order id must be a non-empty string")
    weight = record["weight_kg"]
    distance = record["distance_km"]
    items = record["items"]
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) \
            or weight < 0:
        raise PatternError("weight_kg must be a number >= 0")
    if isinstance(distance, bool) or not isinstance(distance, (int, float)) \
            or distance < 0:
        raise PatternError("distance_km must be a number >= 0")
    if isinstance(items, bool) or not isinstance(items, int) or items < 1:
        raise PatternError("items must be an integer >= 1")
    return Order(id=order_id, kind=str(record["kind"]),
                 weight_kg=float(weight), distance_km=float(distance),
                 items=items)


def default_factory() -> OrderFactory:
    """A factory pre-registered for every bundled order kind."""
    factory = OrderFactory()
    for kind in ORDER_KINDS:
        factory.register(kind, _build_order)
    return factory


# --------------------------------------------------------------------------- #
# Pattern 3: Observer (event bus)
# --------------------------------------------------------------------------- #
class EventBus:
    """Publish/subscribe bus: ordered delivery, isolated handler failures."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[Any], None]]] = {}
        self.errors: list[tuple[str, Exception]] = []

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        if not topic:
            raise PatternError("topic must be a non-empty string")
        if not callable(handler):
            raise PatternError("handler must be callable")
        handlers = self._subscribers.setdefault(topic, [])
        if handler not in handlers:
            handlers.append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[Any], None]) -> bool:
        handlers = self._subscribers.get(topic, [])
        if handler in handlers:
            handlers.remove(handler)
            return True
        return False

    def subscriber_count(self, topic: str) -> int:
        return len(self._subscribers.get(topic, []))

    def publish(self, topic: str, payload: Any) -> int:
        """Notify every handler in subscription order; return deliveries.

        A handler that raises is recorded in ``self.errors`` and does not
        stop delivery to the remaining handlers.
        """
        delivered = 0
        for handler in list(self._subscribers.get(topic, [])):
            try:
                handler(payload)
                delivered += 1
            except Exception as exc:  # sandbox: one bad observer, no cascade
                self.errors.append((topic, exc))
        return delivered


# --------------------------------------------------------------------------- #
# Pattern 4: Strategy (interchangeable algorithms)
# --------------------------------------------------------------------------- #
class PricingStrategy:
    """Base strategy: subclasses implement quote()."""

    name = "base"

    def quote(self, order: Order) -> float:
        raise NotImplementedError


class StandardShipping(PricingStrategy):
    """Flat handling + per-kg + per-km rates."""

    name = "standard"

    def quote(self, order: Order) -> float:
        if order.is_digital:
            return 0.0
        return round(5.0 + 0.10 * order.weight_kg
                     + 0.05 * order.distance_km, 2)


class ExpressShipping(PricingStrategy):
    """Premium handling with steeper distance pricing."""

    name = "express"

    def quote(self, order: Order) -> float:
        if order.is_digital:
            return 0.0
        return round(15.0 + 0.20 * order.weight_kg
                     + 0.12 * order.distance_km, 2)


class BulkShipping(PricingStrategy):
    """Wholesale: cheap on light orders, per-kg after the first 10 items."""

    name = "bulk"

    def quote(self, order: Order) -> float:
        if order.is_digital:
            return 0.0
        extra_kg = max(order.weight_kg - 10.0, 0.0)
        base = 3.0 if order.items >= 10 else 6.0
        return round(base + 0.06 * extra_kg + 0.02 * order.distance_km, 2)


STRATEGY_REGISTRY: dict[str, type[PricingStrategy]] = {
    StandardShipping.name: StandardShipping,
    ExpressShipping.name: ExpressShipping,
    BulkShipping.name: BulkShipping,
}


class PricingService:
    """Context that prices orders with a swappable strategy."""

    def __init__(self, strategy: PricingStrategy | str) -> None:
        self._strategy: PricingStrategy | None = None
        self.strategy = strategy

    @property
    def strategy(self) -> PricingStrategy:
        assert self._strategy is not None
        return self._strategy

    @strategy.setter
    def strategy(self, value: PricingStrategy | str) -> None:
        if isinstance(value, str):
            if value not in STRATEGY_REGISTRY:
                raise PatternError(
                    f"unknown strategy {value!r} "
                    f"(expected one of {', '.join(sorted(STRATEGY_REGISTRY))})")
            value = STRATEGY_REGISTRY[value]()
        if not isinstance(value, PricingStrategy):
            raise PatternError("strategy must be a PricingStrategy or name")
        self._strategy = value

    def price(self, order: Order) -> float:
        return self.strategy.quote(order)


# --------------------------------------------------------------------------- #
# Pattern 5: Decorator (composition of wrappers)
# --------------------------------------------------------------------------- #
class TextSource:
    """Component interface: anything that can render() to a string."""

    def render(self) -> str:
        raise NotImplementedError


class PlainText(TextSource):
    """Concrete component."""

    def __init__(self, text: str) -> None:
        if not isinstance(text, str):
            raise PatternError("text must be a string")
        self._text = text

    def render(self) -> str:
        return self._text


class TextDecorator(TextSource):
    """Base decorator: forwards render() to the wrapped component."""

    def __init__(self, inner: TextSource) -> None:
        if not isinstance(inner, TextSource):
            raise PatternError("decorator must wrap a TextSource")
        self._inner = inner

    def render(self) -> str:
        return self._inner.render()


class UpperCase(TextDecorator):
    def render(self) -> str:
        return self._inner.render().upper()


class Truncate(TextDecorator):
    def __init__(self, inner: TextSource, length: int) -> None:
        super().__init__(inner)
        if length < 1:
            raise PatternError("truncate length must be >= 1")
        self._length = length

    def render(self) -> str:
        return self._inner.render()[: self._length]


class Prefix(TextDecorator):
    def __init__(self, inner: TextSource, prefix: str) -> None:
        super().__init__(inner)
        if not prefix:
            raise PatternError("prefix must be a non-empty string")
        self._prefix = prefix

    def render(self) -> str:
        return self._prefix + self._inner.render()


# --------------------------------------------------------------------------- #
# Demo sections (each runs its own deterministic self-assertions)
# --------------------------------------------------------------------------- #
def section_singleton() -> str:
    reset_singletons()
    first = AppConfig()
    second = AppConfig()
    assert first is second, "singleton contract broken: two instances"
    first.set("feature_x", True)
    assert second.get("feature_x") is True, "state not shared between refs"
    other = SingletonMeta._instances
    assert len(other) == 1, "expected exactly one cached instance"
    text = f"AppConfig() is AppConfig(): {first is second}; " \
           f"shared state: {second.as_dict()}"
    reset_singletons()
    return f"  Singleton  -> {text}"


def section_factory(orders: list[Order]) -> str:
    factory = default_factory()
    assert factory.kinds == tuple(sorted(ORDER_KINDS))
    rebuilt = factory.create({"id": "ORD-X1", "kind": "standard",
                              "weight_kg": 1.0, "distance_km": 10.0,
                              "items": 1})
    assert rebuilt.kind == "standard" and rebuilt.id == "ORD-X1"
    try:
        factory.create({"id": "ORD-BAD", "kind": "drone",
                        "weight_kg": 1.0, "distance_km": 10.0, "items": 1})
    except PatternError:
        unknown_rejected = True
    else:
        unknown_rejected = False
    assert unknown_rejected, "factory accepted an unknown kind"
    kinds = sorted({o.kind for o in orders})
    return f"  Factory    -> {len(orders)} orders built, kinds: " \
           f"{', '.join(kinds)}; unknown kind rejected"


def section_observer() -> str:
    bus = EventBus()
    log: list[str] = []

    def handler_a(payload: Any) -> None:
        log.append(f"a:{payload}")

    def handler_b(payload: Any) -> None:
        log.append(f"b:{payload}")

    def handler_boom(_payload: Any) -> None:
        raise ValueError("boom")

    bus.subscribe("order.created", handler_a)
    bus.subscribe("order.created", handler_b)
    bus.subscribe("order.created", handler_boom)

    delivered = bus.publish("order.created", "ORD-1001")
    assert log == ["a:ORD-1001", "b:ORD-1001"], "delivery order changed"
    assert delivered == 2, "failing handler must not count as delivered"
    assert len(bus.errors) == 1 and isinstance(bus.errors[0][1], ValueError)

    assert bus.unsubscribe("order.created", handler_a) is True
    log.clear()
    bus.publish("order.created", "ORD-1002")
    assert log == ["b:ORD-1002"], "first handler should be gone"
    return (f"  Observer   -> {delivered} deliveries kept order, "
            f"1 failing handler sandboxed, unsubscribe works")


def section_strategy(orders: list[Order]) -> str:
    sample = next(o for o in orders if o.kind == "standard")
    service = PricingService("standard")
    standard = service.price(sample)
    service.strategy = "express"
    express = service.price(sample)
    service.strategy = "bulk"
    bulk = service.price(sample)
    assert express > standard > 0, "express must cost more than standard"
    assert bulk < standard, "bulk must undercut standard on large orders"
    service.strategy = ExpressShipping()          # swap in an instance too
    assert service.price(sample) == express, "instance swap must be equal"
    try:
        service.strategy = "teleport"
    except PatternError:
        unknown_rejected = True
    else:
        unknown_rejected = False
    assert unknown_rejected, "unknown strategy accepted"
    return (f"  Strategy   -> standard ${standard:.2f}, express "
            f"${express:.2f}, bulk ${bulk:.2f} for {sample.id}")


def section_decorator() -> str:
    base = PlainText("ship it")
    assert base.render() == "ship it"
    upper = UpperCase(base)
    assert upper.render() == "SHIP IT"
    pipeline = Prefix(Truncate(upper, 4), ">> ")
    assert pipeline.render() == ">> SHIP", "decoration order matters"
    reversed_pipeline = Truncate(Prefix(upper, ">> "), 4)
    assert reversed_pipeline.render() == ">> S", "wrapping order changes output"
    return (f"  Decorator  -> 'ship it' -> upper -> truncate(4) -> "
            f"prefix: {pipeline.render()!r} (order-sensitive)")


def run_pattern(name: str) -> str:
    """Run one pattern section by name (validated first) and return it."""
    key = str(name).strip().lower()
    if key not in PATTERN_NAMES:
        raise PatternError(
            f"unknown pattern {name!r} "
            f"(expected one of {', '.join(PATTERN_NAMES)})")
    if key in ("factory", "strategy"):
        orders = default_factory().create_many(load_orders())
    else:
        orders = []
    if key == "singleton":
        return section_singleton()
    if key == "factory":
        return section_factory(orders)
    if key == "observer":
        return section_observer()
    if key == "strategy":
        return section_strategy(orders)
    return section_decorator()


def run_demo() -> int:
    """Run every pattern with self-assertions; always returns 0."""
    print("=" * 68)
    print(" DESIGN PATTERNS SHOWCASE")
    print(" 5 GoF patterns; bundled JSON; fully offline.")
    print("=" * 68)

    records = load_orders()
    orders = default_factory().create_many(records)
    print(f"\nLoaded {len(records)} order records from {DEMO_ORDERS.name}\n")

    sections = (
        section_singleton(),
        section_factory(orders),
        section_observer(),
        section_strategy(orders),
        section_decorator(),
    )
    for line in sections:
        print(line)

    # --- cross-checks the demo asserts ----------------------------------- #
    assert len(sections) == len(PATTERN_NAMES), "missing pattern section"
    assert len({id(s) for s in sections}) == len(sections)

    # factory round-trip: rebuilding every record gives identical orders
    rebuilt = default_factory().create_many(load_orders())
    assert rebuilt == orders, "factory rebuild is not deterministic"

    # strategy quotes are pure functions of the order
    service = PricingService("standard")
    first_quotes = [service.price(o) for o in orders]
    service.strategy = "standard"
    second_quotes = [service.price(o) for o in orders]
    assert first_quotes == second_quotes, "quotes are not deterministic"
    assert all(isinstance(q, float) and q >= 0 for q in first_quotes)

    # observer bus: order of a fresh bus is reproducible
    bus_a, bus_b = EventBus(), EventBus()
    seen_a: list[str] = []
    seen_b: list[str] = []
    for bus, seen in ((bus_a, seen_a), (bus_b, seen_b)):
        for tag in ("x", "y", "z"):
            bus.subscribe("t", lambda p, tag=tag, seen=seen:
                          seen.append(f"{tag}:{p}"))
        bus.publish("t", "evt")
    assert seen_a == seen_b, "observer delivery is not deterministic"

    print(f"\nCross-checks OK: {len(PATTERN_NAMES)} patterns, "
          f"{len(orders)} orders, {len(first_quotes)} deterministic quotes, "
          f"ordered + sandboxed observer delivery")
    print("\nDemo completed successfully.")
    return 0
