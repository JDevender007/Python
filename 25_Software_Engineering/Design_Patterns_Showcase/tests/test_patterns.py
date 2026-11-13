"""Tests for the Design Patterns Showcase project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from patterns import (  # noqa: E402
    DEMO_ORDERS,
    ORDER_KINDS,
    PATTERN_NAMES,
    AppConfig,
    BulkShipping,
    EventBus,
    ExpressShipping,
    Order,
    PatternError,
    PlainText,
    Prefix,
    PricingService,
    StandardShipping,
    SingletonMeta,
    TextDecorator,
    Truncate,
    UpperCase,
    default_factory,
    load_orders,
    run_demo,
    run_pattern,
    reset_singletons,
)
from main import main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _write(tmp_path: Path, payload, name: str = "orders.json") -> Path:
    path = tmp_path / name
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _record(**overrides) -> dict:
    record = {"id": "ORD-1", "kind": "standard", "weight_kg": 1.0,
              "distance_km": 10.0, "items": 1}
    record.update(overrides)
    return record


# --------------------------------------------------------------------------- #
# Data loading and validation
# --------------------------------------------------------------------------- #
def test_load_bundled_sample():
    records = load_orders()
    assert len(records) == 6
    assert {r["kind"] for r in records} <= set(ORDER_KINDS)
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids))


def test_bundled_sample_location():
    assert DEMO_ORDERS.is_file()
    assert DEMO_ORDERS.parent == PROJECT_ROOT / "data"


def test_load_missing_file(tmp_path):
    with pytest.raises(PatternError, match="file not found"):
        load_orders(tmp_path / "nope.json")


def test_load_bad_json(tmp_path):
    with pytest.raises(PatternError, match="could not parse"):
        load_orders(_write(tmp_path, "{not json"))


def test_load_empty_list(tmp_path):
    with pytest.raises(PatternError, match="no records"):
        load_orders(_write(tmp_path, []))


def test_load_record_not_object(tmp_path):
    with pytest.raises(PatternError, match="must be a JSON object"):
        load_orders(_write(tmp_path, ["ORD-1"]))


def test_load_missing_field(tmp_path):
    record = _record()
    del record["items"]
    with pytest.raises(PatternError, match="missing field"):
        load_orders(_write(tmp_path, [record]))


def test_load_unknown_kind(tmp_path):
    with pytest.raises(PatternError, match="unknown order kind"):
        load_orders(_write(tmp_path, [_record(kind="drone")]))


def test_load_weight_not_number(tmp_path):
    with pytest.raises(PatternError, match="weight_kg must be a number"):
        load_orders(_write(tmp_path, [_record(weight_kg="heavy")]))


def test_load_negative_distance(tmp_path):
    with pytest.raises(PatternError, match="distance_km must be >= 0"):
        load_orders(_write(tmp_path, [_record(distance_km=-1.0)]))


def test_load_items_below_one(tmp_path):
    with pytest.raises(PatternError, match="items must be >= 1"):
        load_orders(_write(tmp_path, [_record(items=0)]))


# --------------------------------------------------------------------------- #
# Pattern 1: Singleton
# --------------------------------------------------------------------------- #
def test_singleton_returns_same_instance():
    reset_singletons()
    assert AppConfig() is AppConfig()


def test_singleton_shares_state():
    reset_singletons()
    AppConfig().set("mode", "test")
    assert AppConfig().get("mode") == "test"


def test_singletons_are_per_class():
    reset_singletons()

    class Other(metaclass=SingletonMeta):
        pass

    first = Other()
    assert Other() is first
    assert first is not AppConfig()
    reset_singletons()


def test_reset_singletons_gives_fresh_instance():
    reset_singletons()
    before = AppConfig()
    reset_singletons()
    assert AppConfig() is not before


# --------------------------------------------------------------------------- #
# Pattern 2: Factory
# --------------------------------------------------------------------------- #
def test_default_factory_registers_all_kinds():
    assert default_factory().kinds == tuple(sorted(ORDER_KINDS))


def test_factory_builds_every_bundled_order():
    orders = default_factory().create_many(load_orders())
    assert len(orders) == 6
    assert all(isinstance(o, Order) for o in orders)
    assert orders[0].id == "ORD-1001"


def test_factory_rejects_unknown_kind():
    with pytest.raises(PatternError, match="unknown order kind"):
        default_factory().create(_record(kind="drone"))


def test_factory_rejects_non_dict():
    with pytest.raises(PatternError, match="must be a dict"):
        default_factory().create(["ORD-1"])  # type: ignore[arg-type]


def test_factory_rejects_missing_field():
    record = _record(kind="express")
    del record["weight_kg"]
    with pytest.raises(PatternError, match="missing field"):
        default_factory().create(record)


def test_factory_rejects_bad_id():
    with pytest.raises(PatternError, match="order id must be a non-empty"):
        default_factory().create(_record(id=""))


def test_order_is_frozen_and_digital():
    order = default_factory().create(
        _record(id="ORD-9", kind="digital", weight_kg=0.0,
                distance_km=0.0, items=1))
    assert order.is_digital
    with pytest.raises(Exception):
        order.id = "changed"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Pattern 3: Observer
# --------------------------------------------------------------------------- #
def test_publish_counts_deliveries():
    bus = EventBus()
    seen: list[str] = []

    def record_a(payload: str) -> None:
        seen.append(f"a:{payload}")

    def record_b(payload: str) -> None:
        seen.append(f"b:{payload}")

    bus.subscribe("t", record_a)
    bus.subscribe("t", record_b)
    assert bus.publish("t", "x") == 2
    assert seen == ["a:x", "b:x"]


def test_delivery_preserves_subscription_order():
    bus = EventBus()
    order: list[int] = []
    bus.subscribe("t", lambda _p: order.append(1))
    bus.subscribe("t", lambda _p: order.append(2))
    bus.subscribe("t", lambda _p: order.append(3))
    bus.publish("t", None)
    assert order == [1, 2, 3]


def test_duplicate_subscribe_is_ignored():
    bus = EventBus()
    handler = lambda _p: None  # noqa: E731
    bus.subscribe("t", handler)
    bus.subscribe("t", handler)
    assert bus.subscriber_count("t") == 1


def test_unsubscribe_reports_presence():
    bus = EventBus()
    handler = lambda _p: None  # noqa: E731
    bus.subscribe("t", handler)
    assert bus.unsubscribe("t", handler) is True
    assert bus.unsubscribe("t", handler) is False
    assert bus.subscriber_count("t") == 0


def test_failing_handler_is_sandboxed():
    bus = EventBus()
    seen: list[str] = []

    def boom(_p):
        raise ValueError("kaboom")

    bus.subscribe("t", boom)
    bus.subscribe("t", seen.append)
    assert bus.publish("t", "evt") == 1
    assert seen == ["evt"]
    assert len(bus.errors) == 1
    assert isinstance(bus.errors[0][1], ValueError)
    assert bus.errors[0][0] == "t"


def test_subscribe_rejects_bad_inputs():
    bus = EventBus()
    with pytest.raises(PatternError, match="topic must be a non-empty"):
        bus.subscribe("", lambda _p: None)
    with pytest.raises(PatternError, match="handler must be callable"):
        bus.subscribe("t", "not-callable")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Pattern 4: Strategy
# --------------------------------------------------------------------------- #
def _standard_order() -> Order:
    return default_factory().create(_record(id="ORD-S"))


def test_standard_quote_formula():
    quote = StandardShipping().quote(_standard_order())
    assert quote == round(5.0 + 0.10 * 1.0 + 0.05 * 10.0, 2)


def test_express_costs_more_than_standard():
    order = _standard_order()
    assert ExpressShipping().quote(order) > StandardShipping().quote(order)


def test_bulk_discount_for_large_orders():
    small = default_factory().create(_record(items=3, weight_kg=30.0))
    large = default_factory().create(_record(items=12, weight_kg=30.0))
    assert BulkShipping().quote(large) < BulkShipping().quote(small)


def test_digital_orders_are_free():
    digital = default_factory().create(
        _record(kind="digital", weight_kg=0.0, distance_km=0.0))
    for strategy in (StandardShipping(), ExpressShipping(), BulkShipping()):
        assert strategy.quote(digital) == 0.0


def test_pricing_service_swaps_strategies():
    service = PricingService("standard")
    first = service.price(_standard_order())
    service.strategy = "express"
    assert service.price(_standard_order()) > first
    service.strategy = BulkShipping()
    assert service.strategy.name == "bulk"


def test_pricing_service_rejects_unknown_strategy():
    with pytest.raises(PatternError, match="unknown strategy"):
        PricingService("teleport")
    service = PricingService("standard")
    with pytest.raises(PatternError, match="unknown strategy"):
        service.strategy = "teleport"


def test_pricing_service_rejects_non_strategy():
    with pytest.raises(PatternError, match="must be a PricingStrategy"):
        PricingService(42)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Pattern 5: Decorator
# --------------------------------------------------------------------------- #
def test_plain_text_renders_itself():
    assert PlainText("hello").render() == "hello"


def test_upper_case_decorator():
    assert UpperCase(PlainText("abc")).render() == "ABC"


def test_composition_order_matters():
    base = PlainText("ship it")
    forward = Prefix(Truncate(UpperCase(base), 4), ">> ")
    backward = Truncate(Prefix(UpperCase(base), ">> "), 4)
    assert forward.render() == ">> SHIP"
    assert backward.render() == ">> S"
    assert forward.render() != backward.render()


def test_truncate_rejects_bad_length():
    with pytest.raises(PatternError, match="length must be >= 1"):
        Truncate(PlainText("x"), 0)


def test_decorator_requires_text_source():
    with pytest.raises(PatternError, match="must wrap a TextSource"):
        TextDecorator("not a component")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Sections and demo
# --------------------------------------------------------------------------- #
def test_run_pattern_each_name():
    for name in PATTERN_NAMES:
        line = run_pattern(name)
        assert isinstance(line, str)
        assert name.capitalize() in line or name in line.lower()


def test_run_pattern_rejects_unknown_first():
    with pytest.raises(PatternError, match="unknown pattern"):
        run_pattern("flywheel")


def test_run_pattern_is_case_insensitive():
    assert "Strategy" in run_pattern("  STRATEGY ")


def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK" in out
    for name in PATTERN_NAMES:
        assert name.capitalize() in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_cli_list_patterns(capsys):
    assert main(["--list"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == list(PATTERN_NAMES)


def test_cli_pattern_path(capsys):
    assert main(["--pattern", "decorator"]) == 0
    out = capsys.readouterr().out
    assert "Decorator" in out and "Done." in out


def test_cli_pattern_unknown_exits_two(capsys):
    assert main(["--pattern", "flywheel"]) == 2
    assert "unknown pattern" in capsys.readouterr().err


def test_cli_file_valid(capsys):
    assert main(["--file", str(DEMO_ORDERS)]) == 0
    assert "OK: 6 valid order records" in capsys.readouterr().out


def test_cli_file_missing(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.json")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_file_invalid_content(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("[{}]", encoding="utf-8")
    assert main(["--file", str(bad)]) == 2
    assert "missing field" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_cli_mutually_exclusive_actions(capsys):
    with pytest.raises(SystemExit):
        main(["--demo", "--list"])


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    assert capsys.readouterr().out == ""
