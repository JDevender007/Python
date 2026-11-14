"""Tests for Inventory_Management_System: SKUs, lines, the collection, the file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from inventory import (                                   # noqa: E402
    DATA_FILE,
    LEGACY_PRICE,
    LEGACY_SEARCH,
    LEGACY_STOCK_IN,
    LOW_STOCK,
    DuplicateItem,
    Inventory,
    InventoryError,
    Item,
    Line,
    NotEnoughStock,
    UnknownItem,
    check_cents,
    check_quantity,
    format_cents,
    load_inventory,
    normalise_sku,
    round_half_up,
    run_demo,
    save_inventory,
)


def a_widget(sku="W-100", price=1299, name="Widget steel", category="Hardware"):
    return Item(sku, name, category, price, "Acme")


def a_store(*lines) -> Inventory:
    store = Inventory("Test Store")
    for item, quantity in lines or ((a_widget(), 10),):
        store.add(item, quantity)
    return store


# --------------------------------------------------------------------------- #
# normalise_sku
# --------------------------------------------------------------------------- #
def test_a_sku_is_upper_cased():
    assert normalise_sku("w-100") == "W-100"


def test_a_sku_is_trimmed():
    assert normalise_sku("  W-100  ") == "W-100"


def test_a_sku_that_is_not_text_is_refused():
    with pytest.raises(InventoryError, match="must be text"):
        normalise_sku(100)


def test_an_empty_sku_is_refused():
    with pytest.raises(InventoryError, match="must not be empty"):
        normalise_sku("   ")


def test_a_sku_with_an_inner_space_is_refused():
    with pytest.raises(InventoryError, match="contains whitespace"):
        normalise_sku("W 100")


def test_a_sku_with_a_tab_is_refused():
    with pytest.raises(InventoryError, match="contains whitespace"):
        normalise_sku("W-100\tA")


# --------------------------------------------------------------------------- #
# check_cents / check_quantity
# --------------------------------------------------------------------------- #
def test_check_cents_returns_the_number():
    assert check_cents(1299) == 1299


def test_check_cents_allows_zero():
    assert check_cents(0) == 0


def test_check_cents_refuses_a_float():
    with pytest.raises(InventoryError, match="integer number of cents"):
        check_cents(12.99)


def test_check_cents_names_the_float_drift():
    with pytest.raises(InventoryError, match="a float would drift"):
        check_cents(12.99)


def test_check_cents_refuses_a_bool():
    with pytest.raises(InventoryError, match="got bool"):
        check_cents(True)


def test_check_cents_refuses_a_negative_number():
    with pytest.raises(InventoryError, match="must not be negative"):
        check_cents(-1)


def test_check_cents_uses_its_label():
    with pytest.raises(InventoryError, match="the list price"):
        check_cents(1.5, "the list price")


def test_check_quantity_returns_the_number():
    assert check_quantity(7) == 7


def test_check_quantity_refuses_a_float():
    with pytest.raises(InventoryError, match="whole number of units"):
        check_quantity(1.0)


def test_check_quantity_refuses_a_bool():
    with pytest.raises(InventoryError, match="got bool"):
        check_quantity(False)


def test_check_quantity_refuses_a_negative_number():
    with pytest.raises(InventoryError, match="must not be negative"):
        check_quantity(-7)


def test_check_quantity_uses_its_label():
    with pytest.raises(InventoryError, match="the threshold"):
        check_quantity(-1, "the threshold")


# --------------------------------------------------------------------------- #
# format_cents
# --------------------------------------------------------------------------- #
def test_format_cents_pins_the_total():
    assert format_cents(617112) == "Rs 6,171.12"


def test_format_cents_renders_zero():
    assert format_cents(0) == "Rs 0.00"


def test_format_cents_pads_the_fraction():
    assert format_cents(5) == "Rs 0.05"


def test_format_cents_groups_thousands():
    assert format_cents(123456789) == "Rs 1,234,567.89"


def test_format_cents_renders_a_negative_amount():
    assert format_cents(-125) == "-Rs 1.25"


def test_format_cents_refuses_a_float():
    with pytest.raises(InventoryError, match="integer number of cents"):
        format_cents(1.5)


def test_format_cents_refuses_a_bool():
    with pytest.raises(InventoryError, match="integer number of cents"):
        format_cents(True)


# --------------------------------------------------------------------------- #
# round_half_up
# --------------------------------------------------------------------------- #
def test_round_half_up_rounds_a_half_up():
    assert round_half_up(3, 2) == 2


def test_round_half_up_rounds_just_below_down():
    assert round_half_up(4, 3) == 1


def test_round_half_up_leaves_an_exact_division():
    assert round_half_up(4, 2) == 2


def test_round_half_up_handles_a_negative_numerator():
    assert round_half_up(-3, 2) == -2


def test_round_half_up_refuses_a_zero_denominator():
    with pytest.raises(InventoryError, match="denominator must be positive"):
        round_half_up(1, 0)


# --------------------------------------------------------------------------- #
# Item
# --------------------------------------------------------------------------- #
def test_an_item_normalises_its_sku():
    assert a_widget("w-100").sku == "W-100"


def test_an_item_trims_its_name():
    assert Item("W-100", "  Widget  ", "Hardware", 1).name == "Widget"


def test_an_item_titles_its_category():
    assert Item("W-100", "Widget", "motion parts", 1).category == \
        "Motion Parts"


def test_an_item_keeps_its_price_in_cents():
    assert a_widget(price=1299).price == 1299


def test_an_item_defaults_to_no_supplier():
    assert Item("W-100", "Widget", "Hardware", 1).supplier == ""


def test_an_item_trims_its_supplier():
    assert Item("W-100", "Widget", "Hardware", 1, "  Acme ").supplier == "Acme"


def test_an_item_needs_a_name():
    with pytest.raises(InventoryError, match="needs a name"):
        Item("W-100", "   ", "Hardware", 1)


def test_an_item_needs_a_text_name():
    with pytest.raises(InventoryError, match="needs a name"):
        Item("W-100", 7, "Hardware", 1)


def test_an_item_needs_a_category():
    with pytest.raises(InventoryError, match="needs a category"):
        Item("W-100", "Widget", "  ", 1)


def test_an_item_needs_a_text_supplier():
    with pytest.raises(InventoryError, match="supplier must be text"):
        Item("W-100", "Widget", "Hardware", 1, 7)


def test_an_item_refuses_a_float_price():
    with pytest.raises(InventoryError, match="integer number of cents"):
        Item("W-100", "Widget", "Hardware", 12.99)


def test_items_with_the_same_sku_are_equal():
    assert Item("w-100", "Widget steel", "Hardware", 1299) == \
        Item("W-100", "Widget brass", "Hardware", 1899)


def test_items_with_different_skus_differ():
    assert a_widget("W-100") != a_widget("W-101")


def test_an_item_is_not_equal_to_its_sku():
    assert a_widget() != "W-100"


def test_an_item_is_not_equal_to_a_number():
    assert a_widget() != 42


def test_equal_items_hash_alike():
    assert hash(a_widget("w-100")) == hash(a_widget("W-100"))


def test_a_set_collapses_equal_items():
    assert len({a_widget("w-100"), a_widget("W-100")}) == 1


def test_an_item_is_a_usable_dictionary_key():
    lookup = {a_widget(): 10}
    assert lookup[a_widget("w-100")] == 10


def test_items_order_by_category_then_name():
    widget = Item("W-100", "widget", "Hardware", 1)
    bearing = Item("B-300", "Bearing", "Motion", 1)
    assert widget < bearing
    assert not bearing < widget


def test_an_item_cannot_be_ordered_against_other_types():
    with pytest.raises(TypeError):
        a_widget() < "W-100"


def test_an_item_repr_names_it():
    text = repr(a_widget())
    assert "W-100" in text and "Widget steel" in text and "Rs 12.99" in text


def test_an_item_str_is_one_row():
    text = str(a_widget())
    assert text.startswith("W-100 ")
    assert "Rs 12.99" in text


def test_an_item_formats_its_price():
    assert f"{a_widget():price}" == "Rs 12.99"


def test_an_item_formats_its_name():
    assert f"{a_widget():name}" == "Widget steel"


def test_an_item_formats_its_sku():
    assert f"{a_widget():sku}" == "W-100"


def test_an_item_with_no_spec_formats_as_its_row():
    assert f"{a_widget()}" == str(a_widget())


def test_an_item_refuses_an_unknown_format():
    with pytest.raises(InventoryError, match="unknown item format"):
        format(a_widget(), "colour")


def test_an_item_round_trips():
    item = a_widget()
    assert Item.from_dict(item.to_dict()) == item


def test_an_item_dict_names_its_price_in_cents():
    assert a_widget().to_dict()["price_cents"] == 1299


def test_item_from_dict_refuses_a_non_object():
    with pytest.raises(InventoryError, match="must be an object"):
        Item.from_dict([])


def test_item_from_dict_refuses_an_unknown_key():
    row = a_widget().to_dict()
    row["colour"] = "red"
    with pytest.raises(InventoryError, match="unknown item keys"):
        Item.from_dict(row)


def test_item_from_dict_requires_a_sku():
    row = a_widget().to_dict()
    del row["sku"]
    with pytest.raises(InventoryError, match="missing 'sku'"):
        Item.from_dict(row)


def test_item_from_dict_requires_a_price():
    row = a_widget().to_dict()
    del row["price_cents"]
    with pytest.raises(InventoryError, match="missing 'price_cents'"):
        Item.from_dict(row)


def test_item_from_dict_defaults_the_supplier():
    assert Item.from_dict({"sku": "W-1", "name": "W", "category": "H",
                           "price_cents": 1}).supplier == ""


# --------------------------------------------------------------------------- #
# Line
# --------------------------------------------------------------------------- #
def test_a_line_needs_an_item():
    with pytest.raises(InventoryError, match="needs an Item"):
        Line("W-100", 10)


def test_a_line_refuses_a_negative_quantity():
    with pytest.raises(InventoryError, match="must not be negative"):
        Line(a_widget(), -1)


def test_a_line_refuses_a_float_quantity():
    with pytest.raises(InventoryError, match="whole number of units"):
        Line(a_widget(), 1.0)


def test_a_line_accepts_zero():
    assert Line(a_widget(), 0).quantity == 0


def test_a_line_is_frozen():
    with pytest.raises(Exception):
        Line(a_widget(), 10).quantity = 11              # type: ignore[misc]


def test_adding_units_returns_a_new_line():
    line = Line(a_widget(), 10)
    bigger = line + 5
    assert bigger.quantity == 15 and line.quantity == 10
    assert bigger is not line


def test_adding_keeps_the_item_object():
    line = Line(a_widget(), 10)
    assert (line + 5).item is line.item


def test_subtracting_units_returns_a_new_line():
    line = Line(a_widget(), 10)
    assert (line - 4).quantity == 6


def test_subtracting_to_zero_is_allowed():
    assert (Line(a_widget(), 10) - 10).quantity == 0


def test_subtracting_below_zero_is_refused():
    with pytest.raises(InventoryError, match="must not be negative"):
        Line(a_widget(), 10) - 11


def test_adding_a_float_is_not_supported():
    with pytest.raises(TypeError):
        Line(a_widget(), 10) + 1.5


def test_adding_a_bool_is_not_supported():
    with pytest.raises(TypeError):
        Line(a_widget(), 10) + True


def test_subtracting_a_string_is_not_supported():
    with pytest.raises(TypeError):
        Line(a_widget(), 10) - "1"


def test_a_line_values_itself():
    assert Line(a_widget(price=1299), 10).value == 12990


def test_an_empty_line_is_worth_nothing():
    assert Line(a_widget(), 0).value == 0


def test_a_line_at_the_threshold_is_low():
    assert Line(a_widget(), LOW_STOCK).is_low()


def test_a_line_one_above_the_threshold_is_not_low():
    assert not Line(a_widget(), LOW_STOCK + 1).is_low()


def test_a_line_accepts_its_own_threshold():
    assert Line(a_widget(), 7).is_low(7)


def test_a_line_refuses_a_bad_threshold():
    with pytest.raises(InventoryError, match="a threshold must not be negative"):
        Line(a_widget(), 7).is_low(-1)


def test_a_line_with_stock_is_true():
    assert bool(Line(a_widget(), 1))


def test_an_empty_line_is_false():
    assert not bool(Line(a_widget(), 0))


def test_len_of_a_line_is_its_quantity():
    assert len(Line(a_widget(), 10)) == 10


def test_a_low_line_is_flagged_in_text():
    assert str(Line(a_widget(), LOW_STOCK)).endswith("LOW")


def test_a_stocked_line_is_not_flagged():
    assert "LOW" not in str(Line(a_widget(), 40))


def test_a_line_str_shows_the_value():
    assert "Rs 129.90" in str(Line(a_widget(), 10))


def test_a_line_repr_names_the_sku_and_quantity():
    assert repr(Line(a_widget(), 10)) == "<Line W-100 x10>"


def test_lines_are_equal_by_value():
    assert Line(a_widget(), 10) == Line(a_widget("w-100"), 10)


def test_lines_with_different_quantities_differ():
    assert Line(a_widget(), 10) != Line(a_widget(), 11)


def test_a_line_round_trips():
    line = Line(a_widget(), 10)
    assert Line.from_dict(line.to_dict()) == line


def test_line_from_dict_refuses_a_non_object():
    with pytest.raises(InventoryError, match="must be an object"):
        Line.from_dict("W-100")


def test_line_from_dict_refuses_an_unknown_key():
    row = Line(a_widget(), 10).to_dict()
    row["note"] = "x"
    with pytest.raises(InventoryError, match="unknown line keys"):
        Line.from_dict(row)


def test_line_from_dict_requires_the_quantity():
    row = Line(a_widget(), 10).to_dict()
    del row["quantity"]
    with pytest.raises(InventoryError, match="missing 'quantity'"):
        Line.from_dict(row)


# --------------------------------------------------------------------------- #
# Inventory: the collection protocols
# --------------------------------------------------------------------------- #
def test_an_inventory_needs_a_name():
    with pytest.raises(InventoryError, match="needs a name"):
        Inventory("  ")


def test_an_inventory_needs_a_text_name():
    with pytest.raises(InventoryError, match="needs a name"):
        Inventory(7)


def test_a_new_inventory_is_empty():
    assert len(Inventory()) == 0


def test_an_inventory_trims_its_name():
    assert Inventory("  Main  ").name == "Main"


def test_an_inventory_defaults_its_name():
    assert Inventory().name == "Main Store"


def test_len_counts_the_lines():
    assert len(a_store((a_widget(), 10),
                       (a_widget("W-101", 1899, "Widget brass"), 4))) == 2


def test_iteration_is_in_sku_order():
    store = a_store((a_widget(), 10),
                    (Item("B-300", "Bearing", "Motion", 2599), 18),
                    (Item("A-1", "Anchor", "Motion", 100), 1))
    assert [line.item.sku for line in store] == ["A-1", "B-300", "W-100"]


def test_iteration_is_repeatable():
    store = a_store((a_widget(), 10))
    assert list(store) == list(store)


def test_contains_accepts_a_sku():
    store = a_store((a_widget(), 10))
    assert "W-100" in store


def test_contains_normalises_the_sku():
    store = a_store((a_widget(), 10))
    assert "w-100" in store


def test_contains_accepts_an_item():
    store = a_store((a_widget(), 10))
    assert a_widget("w-100") in store


def test_contains_is_false_for_another_sku():
    assert "NOPE" not in a_store((a_widget(), 10))


def test_contains_is_false_for_a_blank_string():
    assert "   " not in a_store((a_widget(), 10))


def test_contains_is_false_for_a_non_sku():
    assert 7 not in a_store((a_widget(), 10))


def test_getitem_returns_the_line():
    assert a_store((a_widget(), 10))["W-100"].quantity == 10


def test_getitem_raises_for_an_unknown_sku():
    with pytest.raises(UnknownItem, match="no line for SKU"):
        a_store((a_widget(), 10))["NOPE"]


def test_inventories_are_equal_by_name_and_lines():
    assert a_store((a_widget(), 10)) == a_store((a_widget("w-100"), 10))


def test_inventories_with_different_quantities_differ():
    assert a_store((a_widget(), 10)) != a_store((a_widget(), 11))


def test_an_inventory_is_not_equal_to_a_string():
    assert a_store((a_widget(), 10)) != "Test Store"


def test_an_inventory_repr_reports_its_total():
    text = repr(a_store((a_widget(), 10)))
    assert "Test Store" in text and "1 lines" in text and "Rs 129.90" in text


def test_lines_are_returned_as_a_tuple():
    assert isinstance(a_store((a_widget(), 10)).lines, tuple)


def test_lines_are_in_sku_order():
    store = a_store((a_widget(), 10),
                    (Item("A-1", "Anchor", "Motion", 100), 1))
    assert [line.item.sku for line in store.lines] == ["A-1", "W-100"]


def test_get_normalises_the_sku():
    assert a_store((a_widget(), 10)).get("w-100").quantity == 10


def test_quantity_returns_the_number():
    assert a_store((a_widget(), 10)).quantity("W-100") == 10


def test_quantity_of_an_unknown_sku_raises():
    with pytest.raises(UnknownItem):
        a_store((a_widget(), 10)).quantity("NOPE")


# --------------------------------------------------------------------------- #
# Inventory: search and low stock
# --------------------------------------------------------------------------- #
def test_search_matches_the_sku():
    store = a_store((a_widget(), 10), (a_widget("W-101", 1899), 4))
    assert [line.item.sku for line in store.search("w-10")] == \
        ["W-100", "W-101"]


def test_search_matches_the_name():
    store = a_store((a_widget(), 10), (a_widget("W-101", 1899), 4))
    assert len(store.search("widget")) == 2


def test_search_matches_the_category():
    store = a_store((a_widget(), 10),
                    (Item("B-300", "Bearing 608", "Motion", 2599), 18))
    assert [line.item.sku for line in store.search("motion")] == ["B-300"]


def test_search_matches_the_supplier():
    store = a_store((a_widget(), 10),
                    (Item("B-300", "Bearing", "Motion", 2599, "Rotex"), 18))
    assert [line.item.sku for line in store.search("rotex")] == ["B-300"]


def test_search_returns_every_match_not_just_the_first():
    store = a_store((a_widget(), 10),
                    (Item("B-300", "Bearing 608", "Motion", 2599), 18),
                    (Item("B-301", "Bearing 6200", "Motion", 3299), 6))
    assert len(store.search("bearing")) == 2


def test_search_returns_nothing_for_no_match():
    assert a_store((a_widget(), 10)).search("nothing") == []


def test_search_is_case_insensitive():
    store = a_store((a_widget(), 10))
    assert len(store.search("WIDGET")) == 1


def test_search_needs_text():
    with pytest.raises(InventoryError, match="needs text"):
        a_store((a_widget(), 10)).search(7)


def test_search_needs_something_to_look_for():
    with pytest.raises(InventoryError, match="something to look for"):
        a_store((a_widget(), 10)).search("   ")


def test_low_stock_uses_the_default_threshold():
    store = a_store((a_widget(), LOW_STOCK),
                    (a_widget("W-101", 1899), LOW_STOCK + 1))
    assert [line.item.sku for line in store.low_stock()] == ["W-100"]


def test_low_stock_leaves_out_zero():
    store = a_store((a_widget(), LOW_STOCK),
                    (a_widget("W-101", 1899), LOW_STOCK + 1))
    assert [line.item.sku for line in store.low_stock(0)] == []


def test_low_stock_orders_the_emptiest_first():
    store = a_store((a_widget(), 4),
                    (Item("A-1", "Anchor", "Motion", 100), 0),
                    (Item("B-1", "Bolt", "Motion", 100), 2))
    assert [line.item.sku for line in store.low_stock()] == \
        ["A-1", "B-1", "W-100"]


def test_low_stock_accepts_a_threshold():
    store = a_store((a_widget(), 6))
    assert store.low_stock(5) == []
    assert len(store.low_stock(6)) == 1


def test_low_stock_refuses_a_negative_threshold():
    with pytest.raises(InventoryError, match="a threshold must not be negative"):
        a_store((a_widget(), 1)).low_stock(-1)


# --------------------------------------------------------------------------- #
# Inventory: adding, removing, moving stock
# --------------------------------------------------------------------------- #
def test_add_returns_the_new_line():
    store = Inventory("Store")
    line = store.add(a_widget(), 10)
    assert line.quantity == 10 and len(store) == 1


def test_add_defaults_to_zero():
    assert Inventory("Store").add(a_widget()).quantity == 0


def test_add_refuses_a_non_item():
    with pytest.raises(InventoryError, match="only an Item"):
        Inventory("Store").add("W-100", 1)


def test_add_refuses_a_negative_quantity():
    with pytest.raises(InventoryError, match="must not be negative"):
        Inventory("Store").add(a_widget(), -1)


def test_add_refuses_a_duplicate_sku():
    with pytest.raises(DuplicateItem, match="already on the inventory"):
        a_store((a_widget(), 10)).add(a_widget("w-100", 999))


def test_add_refuses_a_duplicate_by_normalised_sku():
    with pytest.raises(DuplicateItem, match="stock it in instead"):
        a_store((a_widget(), 10)).add(Item("w-100", "Second", "Hardware", 1))


def test_a_refused_duplicate_leaves_the_collection_alone():
    store = a_store((a_widget(), 10))
    with pytest.raises(DuplicateItem):
        store.add(a_widget())
    assert len(store) == 1 and store["W-100"].quantity == 10


def test_remove_drops_the_line():
    store = a_store((a_widget(), 10))
    line = store.remove("w-100")
    assert line.item.sku == "W-100" and len(store) == 0


def test_remove_refuses_an_unknown_sku():
    with pytest.raises(UnknownItem, match="no line for SKU"):
        a_store((a_widget(), 10)).remove("NOPE")


def test_stock_in_adds_units():
    store = a_store((a_widget(), 10))
    assert store.stock_in("W-100", 5).quantity == 15


def test_stock_in_returns_the_stored_line():
    store = a_store((a_widget(), 10))
    store.stock_in("W-100", 5)
    assert store["W-100"].quantity == 15


def test_stock_in_refuses_zero():
    with pytest.raises(InventoryError, match="positive whole number"):
        a_store((a_widget(), 10)).stock_in("W-100", 0)


def test_stock_in_refuses_a_negative_number():
    with pytest.raises(InventoryError, match="positive whole number"):
        a_store((a_widget(), 10)).stock_in("W-100", -5)


def test_stock_in_refuses_a_bool():
    with pytest.raises(InventoryError, match="positive whole number"):
        a_store((a_widget(), 10)).stock_in("W-100", True)


def test_stock_in_refuses_a_float():
    with pytest.raises(InventoryError, match="positive whole number"):
        a_store((a_widget(), 10)).stock_in("W-100", 1.0)


def test_a_refused_stock_in_leaves_the_quantity_alone():
    store = a_store((a_widget(), 10))
    with pytest.raises(InventoryError):
        store.stock_in("W-100", -5)
    assert store["W-100"].quantity == 10


def test_stock_out_removes_units():
    store = a_store((a_widget(), 10))
    assert store.stock_out("W-100", 4).quantity == 6


def test_stock_out_can_empty_a_line():
    store = a_store((a_widget(), 10))
    assert store.stock_out("W-100", 10).quantity == 0


def test_stock_out_refuses_an_overdraw():
    with pytest.raises(NotEnoughStock, match="cannot remove"):
        a_store((a_widget(), 10)).stock_out("W-100", 11)


def test_an_overdraw_leaves_the_quantity_alone():
    store = a_store((a_widget(), 10))
    with pytest.raises(NotEnoughStock):
        store.stock_out("W-100", 11)
    assert store["W-100"].quantity == 10


def test_stock_out_of_an_empty_line_refuses_one_unit():
    store = a_store((a_widget(), 0))
    with pytest.raises(NotEnoughStock):
        store.stock_out("W-100", 1)


def test_stock_out_refuses_zero():
    with pytest.raises(InventoryError, match="positive whole number"):
        a_store((a_widget(), 10)).stock_out("W-100", 0)


def test_stock_out_refuses_a_negative_number():
    with pytest.raises(InventoryError, match="positive whole number"):
        a_store((a_widget(), 10)).stock_out("W-100", -5)


def test_stock_movements_refuse_an_unknown_sku():
    with pytest.raises(UnknownItem):
        a_store((a_widget(), 10)).stock_in("NOPE", 1)


# --------------------------------------------------------------------------- #
# Inventory: totals and audit
# --------------------------------------------------------------------------- #
def test_value_of_an_empty_inventory_is_zero():
    assert Inventory("Store").value() == 0


def test_value_sums_the_lines():
    store = a_store((a_widget(price=1299), 10),
                    (a_widget("W-101", 1899), 4))
    assert store.value() == 12990 + 7596


def test_value_ignores_an_empty_line():
    assert a_store((a_widget(price=1299), 0)).value() == 0


def test_by_category_sums_each_category():
    store = a_store((a_widget(price=1299), 10),
                    (Item("B-300", "Bearing", "Motion", 2599), 2))
    assert store.by_category() == {"Hardware": 12990, "Motion": 5198}


def test_by_category_is_sorted():
    store = a_store((a_widget(price=1299), 1),
                    (Item("B-300", "Bearing", "Motion", 2599), 1))
    assert list(store.by_category()) == ["Hardware", "Motion"]


def test_audit_reports_five_checks():
    assert len(a_store((a_widget(), 10)).audit()) == 5


def test_a_fresh_store_passes_every_check():
    store = a_store((a_widget(), 10))
    assert all(passed for _, passed in store.audit())
    assert store.problems() == []


def test_audit_names_its_checks():
    names = [name for name, _ in a_store((a_widget(), 10)).audit()]
    assert "every SKU appears once" in names
    assert "no line holds a negative quantity" in names
    assert "the total equals the sum of the lines" in names


def test_audit_catches_a_hand_edited_negative_quantity():
    store = a_store((a_widget(), 10))
    corrupt = Line(a_widget(), 0)
    object.__setattr__(corrupt, "quantity", -1)
    store._lines["W-100"] = corrupt
    assert store.problems() == ["no line holds a negative quantity"]


def test_audit_is_repeatable():
    store = a_store((a_widget(), 10))
    assert store.audit() == store.audit()


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def test_an_inventory_round_trips():
    store = a_store((a_widget(), 10),
                    (Item("B-300", "Bearing", "Motion", 2599, "Rotex"), 18))
    assert Inventory.from_dict(store.to_dict()) == store


def test_an_inventory_dict_keeps_its_name():
    assert a_store((a_widget(), 10)).to_dict()["name"] == "Test Store"


def test_an_inventory_dict_lists_the_lines():
    payload = a_store((a_widget(), 10)).to_dict()
    assert payload["lines"][0]["quantity"] == 10


def test_inventory_from_dict_refuses_a_non_object():
    with pytest.raises(InventoryError, match="must be an object"):
        Inventory.from_dict([])


def test_inventory_from_dict_refuses_an_unknown_key():
    with pytest.raises(InventoryError, match="unknown inventory keys"):
        Inventory.from_dict({"name": "x", "lines": [], "extra": 1})


def test_inventory_from_dict_requires_its_lines():
    with pytest.raises(InventoryError, match="missing 'lines'"):
        Inventory.from_dict({"name": "x"})


def test_inventory_from_dict_requires_a_list_of_lines():
    with pytest.raises(InventoryError, match="'lines' must be a list"):
        Inventory.from_dict({"name": "x", "lines": {}})


def test_inventory_from_dict_refuses_a_non_object_line():
    with pytest.raises(InventoryError, match="a line must be an object"):
        Inventory.from_dict({"name": "x", "lines": [[]]})


def test_inventory_from_dict_refuses_a_duplicate_sku():
    payload = a_store((a_widget(), 10)).to_dict()
    payload["lines"].append(payload["lines"][0])
    with pytest.raises(DuplicateItem):
        Inventory.from_dict(payload)


def test_the_data_file_is_named_for_its_purpose():
    assert DATA_FILE.name == "inventory.json"
    assert DATA_FILE.parent.name == "data"


def test_the_seeded_inventory_loads():
    seeded = load_inventory()
    assert seeded.name == "Main Store" and len(seeded) == 8


def test_the_seeded_skus_are_in_order():
    assert [line.item.sku for line in load_inventory()] == [
        "B-300", "B-301", "G-200", "G-201", "M-400", "S-500", "W-100",
        "W-101"]


def test_the_seeded_total_is_pinned():
    assert load_inventory().value() == 617112


def test_the_seeded_low_stock_lines_are_pinned():
    assert [line.item.sku for line in load_inventory().low_stock()] == \
        ["G-201", "M-400", "W-101"]


def test_the_seeded_motion_category_is_pinned():
    assert load_inventory().by_category()["Motion"] == 204276


def test_the_seeded_categories_are_pinned():
    assert load_inventory().by_category() == {
        "Electronics": 311400, "Hardware": 59556, "Motion": 204276,
        "Seals": 41880}


def test_the_seeded_inventory_passes_its_own_audit():
    assert load_inventory().problems() == []


def test_the_seeded_inventory_has_two_bearings():
    assert len(load_inventory().search("bearing")) == 2


def test_load_inventory_refuses_a_missing_file(tmp_path):
    with pytest.raises(InventoryError, match="not found"):
        load_inventory(tmp_path / "nope.json")


def test_load_inventory_refuses_invalid_json(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(InventoryError, match="not valid JSON"):
        load_inventory(path)


def test_save_inventory_writes_a_readable_file(tmp_path):
    seeded = load_inventory()
    target = tmp_path / "out.json"
    save_inventory(target, seeded)
    assert load_inventory(target) == seeded


def test_save_inventory_returns_the_path(tmp_path):
    target = tmp_path / "out.json"
    assert save_inventory(target, Inventory("Store")) == target


def test_save_inventory_creates_directories(tmp_path):
    target = tmp_path / "a" / "b" / "inventory.json"
    save_inventory(target, Inventory("Store"))
    assert target.is_file()


def test_save_inventory_ends_with_a_newline(tmp_path):
    target = tmp_path / "out.json"
    save_inventory(target, Inventory("Store"))
    assert target.read_text(encoding="utf-8").endswith("}\n")


def test_save_inventory_is_byte_identical_on_a_second_save(tmp_path):
    target = tmp_path / "out.json"
    seeded = load_inventory()
    save_inventory(target, seeded)
    first = target.read_bytes()
    save_inventory(target, load_inventory(target))
    assert target.read_bytes() == first


def test_the_legacy_constants_are_the_ones_the_demo_proves():
    assert LEGACY_PRICE == "price = Column(Float, nullable=False, default=0.0)"
    assert LEGACY_STOCK_IN == "item.quantity += quantity"
    assert LEGACY_SEARCH == "query.first()"


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_shows_the_float_drift(capsys):
    run_demo()
    assert "59.969999999999999" in capsys.readouterr().out


def test_demo_shows_the_legacy_movement(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "10 -> -5" in out


def test_demo_shows_the_search_difference(capsys):
    run_demo()
    assert "search() returns 2" in capsys.readouterr().out


def test_demo_shows_the_seeded_total(capsys):
    run_demo()
    assert "Rs 6,171.12" in capsys.readouterr().out


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert all(ord(character) < 128 for character in out)


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


def test_cli_lists_the_seeded_lines(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "8 line(s), Rs 6,171.12" in out
    assert "G-201" in out and "LOW" in out


def test_cli_items_flag_does_the_same(capsys):
    assert cli.main(["--items"]) == 0
    assert "8 line(s)" in capsys.readouterr().out


def test_cli_search_finds_both_bearings(capsys):
    assert cli.main(["--search", "bearing"]) == 0
    out = capsys.readouterr().out
    assert "2 line(s) match 'bearing'" in out
    assert "B-300" in out and "B-301" in out


def test_cli_search_with_no_match(capsys):
    assert cli.main(["--search", "nothing"]) == 0
    assert "0 line(s) match" in capsys.readouterr().out


def test_cli_low_stock_uses_the_default(capsys):
    assert cli.main(["--low-stock"]) == 0
    out = capsys.readouterr().out
    assert "3 line(s) at or below 5 units" in out


def test_cli_low_stock_accepts_a_threshold(capsys):
    assert cli.main(["--low-stock", "6"]) == 0
    assert "4 line(s) at or below 6 units" in capsys.readouterr().out


def test_cli_value_breaks_down_the_categories(capsys):
    assert cli.main(["--value"]) == 0
    out = capsys.readouterr().out
    assert "Electronics" in out and "Rs 3,114.00" in out
    assert "Rs 6,171.12" in out


def test_cli_audit_passes(capsys):
    assert cli.main(["--audit"]) == 0
    assert "5/5 checks passed" in capsys.readouterr().out


def test_cli_adds_an_item(capsys):
    assert cli.main(["--add", "P-600:Plunger:Hardware:4.25:25:Acme"]) == 0
    out = capsys.readouterr().out
    assert "added P-600" in out and "x25" in out and "Rs 4.25" in out


def test_cli_counts_a_new_item_in_the_total(tmp_path, capsys):
    saved = tmp_path / "added.json"
    assert cli.main(["--add", "A-900:Anchor:Motion:10:1",
                     "--write", str(saved)]) == 0
    capsys.readouterr()
    assert cli.main(["--value", "--file", str(saved)]) == 0
    assert "Rs 6,181.12" in capsys.readouterr().out     # 617112 + 1000


def test_cli_add_refuses_a_duplicate(capsys):
    assert cli.main(["--add", "w-100:Second:Hardware:1:1"]) == 2
    assert "already on the inventory" in capsys.readouterr().err


def test_cli_add_refuses_a_bad_price(capsys):
    assert cli.main(["--add", "A-900:Anchor:Motion:abc:1"]) == 2
    assert "is not a number" in capsys.readouterr().err


def test_cli_add_refuses_three_decimal_places(capsys):
    assert cli.main(["--add", "A-900:Anchor:Motion:4.256:1"]) == 2
    assert "more than two decimal places" in capsys.readouterr().err


def test_cli_add_refuses_a_malformed_spec(capsys):
    assert cli.main(["--add", "A-900:Anchor"]) == 2
    assert "expected SKU:NAME" in capsys.readouterr().err


def test_cli_add_refuses_a_non_numeric_quantity(capsys):
    assert cli.main(["--add", "A-900:Anchor:Motion:4:many"]) == 2
    assert "not a whole number" in capsys.readouterr().err


def test_cli_stock_in(capsys):
    assert cli.main(["--stock-in", "W-100:5"]) == 0
    assert "W-100 now holds 45" in capsys.readouterr().out


def test_cli_stock_in_refuses_zero(capsys):
    assert cli.main(["--stock-in", "W-100:0"]) == 2
    assert "positive whole number" in capsys.readouterr().err


def test_cli_stock_out(capsys):
    assert cli.main(["--stock-out", "G-200:12"]) == 0
    assert "G-200 now holds 108" in capsys.readouterr().out


def test_cli_stock_out_refuses_an_overdraw(capsys):
    assert cli.main(["--stock-out", "G-201:1"]) == 2
    assert "cannot remove" in capsys.readouterr().err


def test_cli_remove(capsys):
    assert cli.main(["--remove", "S-500"]) == 0
    assert "removed S-500 (12 units)" in capsys.readouterr().out


def test_cli_remove_refuses_an_unknown_sku(capsys):
    assert cli.main(["--remove", "NOPE"]) == 2
    assert "no line for SKU" in capsys.readouterr().err


def test_cli_legacy_mode(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "price = Column(Float" in out
    assert "item.quantity += quantity" in out
    assert "query.first()" in out


def test_cli_json_items(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "items" and len(payload["lines"]) == 8
    assert payload["lines"][0]["sku"] == "B-300"


def test_cli_json_value(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--value", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["total_cents"] == 617112
    assert payload["total"] == "Rs 6,171.12"


def test_cli_json_audit(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--audit", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["clean"] is True and len(payload["checks"]) == 5


def test_cli_json_legacy(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--legacy", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["search"] == "query.first()"


def test_cli_write_saves_the_change(tmp_path, capsys):
    target = tmp_path / "saved.json"
    assert cli.main(["--stock-in", "W-100:5", "--write", str(target)]) == 0
    capsys.readouterr()
    assert load_inventory(target).quantity("W-100") == 45


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.json"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--value", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def cli_price(text):
    return cli._price(text)


def test_cli_price_reads_a_decimal():
    assert cli_price("4.25") == 425


def test_cli_price_reads_a_whole_number():
    assert cli_price("7") == 700


def test_cli_price_pads_one_decimal_place():
    assert cli_price("1.5") == 150


def test_cli_price_strips_thousands_separators():
    assert cli_price("1,299.99") == 129999


def test_cli_price_reads_a_bare_decimal():
    assert cli_price(".5") == 50


def test_cli_price_refuses_an_empty_price():
    with pytest.raises(InventoryError, match="price is empty"):
        cli_price("   ")


def test_cli_price_refuses_a_negative_price():
    with pytest.raises(InventoryError, match="must not be negative"):
        cli_price("-3")


def test_cli_units_reads_a_whole_number():
    assert cli._units("12") == 12


def test_cli_units_refuses_text():
    with pytest.raises(InventoryError, match="not a whole number"):
        cli._units("twelve")
