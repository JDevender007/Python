"""Tests for Restaurant_Menu: money, width, the menu, the cart and the CLI."""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from menu import (                                        # noqa: E402
    DATA_FILE,
    LEGACY_WIDTH,
    MENU_WIDTH,
    TAX_BASIS_POINTS,
    Cart,
    MenuError,
    MenuItem,
    display_width,
    dot_leader,
    find_item,
    format_price,
    legacy_line,
    load_menu,
    parse_price,
    render_menu,
    run_demo,
    stats,
    tax_for,
    write_menu,
)

COMBINING = "Cafe\u0301"
WIDE = "\u5bff\u53f8"


@pytest.fixture()
def menu() -> list[MenuItem]:
    return load_menu()


@pytest.fixture()
def cart(menu) -> Cart:
    return Cart(menu)


# --------------------------------------------------------------------------- #
# Prices
# --------------------------------------------------------------------------- #
def test_parse_price_of_a_decimal_string():
    assert parse_price("4.50") == 450


def test_parse_price_of_trailing_zero_cent():
    assert parse_price("19.9") == 1990


def test_parse_price_of_whole_dollars():
    assert parse_price("12") == 1200


def test_parse_price_of_an_integer_means_dollars():
    assert parse_price(4) == 400


def test_parse_price_of_zero():
    assert parse_price("0.00") == 0


def test_parse_price_strips_a_dollar_sign():
    assert parse_price("$12.50") == 1250


def test_parse_price_strips_thousands_separators():
    assert parse_price("$1,234.56") == 123456


def test_parse_price_ignores_surrounding_space():
    assert parse_price("  6.25  ") == 625


def test_parse_price_of_a_float():
    assert parse_price(4.5) == 450


@pytest.mark.parametrize("bad", ["4.505", "0.001", "abc", "-1", "-0.01",
                                 "", "$", "nan", "inf"])
def test_parse_price_refuses_bad_shapes(bad):
    with pytest.raises(MenuError):
        parse_price(bad)


def test_parse_price_refuses_a_boolean():
    with pytest.raises(MenuError, match="boolean"):
        parse_price(True)


def test_parse_price_refuses_a_negative_integer():
    with pytest.raises(MenuError, match="negative"):
        parse_price(-5)


def test_format_price_pads_the_cents():
    assert format_price(450) == "$4.50"
    assert format_price(5) == "$0.05"


def test_format_price_of_zero():
    assert format_price(0) == "$0.00"


def test_format_price_groups_thousands():
    assert format_price(123456) == "$1,234.56"


def test_format_price_of_a_negative():
    assert format_price(-125) == "-$1.25"


def test_format_price_refuses_a_non_integer():
    with pytest.raises(MenuError):
        format_price("4.50")


def test_price_round_trip():
    for text in ("0.01", "4.50", "1999.99"):
        assert format_price(parse_price(text)) == f"${float(text):,.2f}"


# --------------------------------------------------------------------------- #
# Display width
# --------------------------------------------------------------------------- #
def test_display_width_of_ascii():
    assert display_width("Pad Thai") == 8


def test_display_width_of_empty():
    assert display_width("") == 0


def test_display_width_ignores_combining_marks():
    assert len(COMBINING) == 5
    assert display_width(COMBINING) == 4


def test_display_width_counts_wide_characters_twice():
    assert len(WIDE) == 2
    assert display_width(WIDE) == 4


def test_display_width_of_a_fullwidth_character():
    assert display_width("\uff21") == 2                   # FULLWIDTH A


def test_display_width_documentation_matches_unicodedata():
    assert unicodedata.combining("\u0301") != 0
    assert unicodedata.east_asian_width("\u5bff") in ("W", "F")


def test_display_width_refuses_non_text():
    with pytest.raises(MenuError, match="must be a string"):
        display_width(7)


# --------------------------------------------------------------------------- #
# The legacy formatter
# --------------------------------------------------------------------------- #
def test_legacy_line_of_a_short_name():
    assert legacy_line("Pad Thai", 12) == "Pad Thai----------$12"


def test_legacy_line_is_twenty_columns_plus_the_dollar():
    assert len(legacy_line("Pad Thai", 12)) == 21


def test_legacy_line_collapses_a_negative_gap():
    name = "Slow-roasted lamb shoulder"
    line = legacy_line(name, 24)
    assert line == name + "$24"
    assert line.endswith("shoulder$24")


def test_legacy_negative_gap_is_empty_not_an_error():
    assert "-" * (LEGACY_WIDTH - 100) == ""


def test_legacy_line_of_a_len_based_combining_mark_is_short():
    line = legacy_line(COMBINING, 3)
    assert len(line) == 21
    assert display_width(line) == 20


def test_legacy_line_of_wide_characters_is_long():
    line = legacy_line(WIDE, 5)
    assert len(line) == 21
    assert display_width(line) == 23


# --------------------------------------------------------------------------- #
# Dot leaders
# --------------------------------------------------------------------------- #
def test_dot_leader_reaches_the_full_width():
    assert display_width(dot_leader("Pad Thai", 1340)) == MENU_WIDTH


def test_dot_leader_ends_with_the_price():
    assert dot_leader("Pad Thai", 1340).endswith("$13.40")


def test_dot_leader_fills_with_dots():
    line = dot_leader("Pad Thai", 1340)
    assert "." in line and "-" not in line


def test_dot_leader_with_a_long_name_keeps_one_space():
    name = "Slow-roasted lamb shoulder with rosemary"
    line = dot_leader(name, 2400)
    assert line == name + " " + "$24.00"


def test_dot_leader_with_a_long_name_still_shows_the_price():
    line = dot_leader("x" * 60, 100)
    assert line.endswith("$1.00")


def test_dot_leader_handles_a_combining_mark():
    line = dot_leader(COMBINING, 300)
    assert display_width(line) == MENU_WIDTH


def test_dot_leader_handles_wide_characters():
    line = dot_leader(WIDE, 500)
    assert display_width(line) == MENU_WIDTH


def test_dot_leader_with_an_odd_width():
    assert display_width(dot_leader("A", 100, 15)) == 15


# --------------------------------------------------------------------------- #
# MenuItem
# --------------------------------------------------------------------------- #
def test_menu_item_trims_its_name():
    assert MenuItem("  Soup  ", 625).name == "Soup"


def test_menu_item_refuses_a_blank_name():
    with pytest.raises(MenuError, match="must not be empty"):
        MenuItem("   ", 625)


def test_menu_item_refuses_a_non_string_name():
    with pytest.raises(MenuError, match="must not be empty"):
        MenuItem(7, 625)


def test_menu_item_refuses_a_non_integer_price():
    with pytest.raises(MenuError, match="must be an integer"):
        MenuItem("Soup", 6.25)


def test_menu_item_refuses_a_boolean_price():
    with pytest.raises(MenuError, match="must be an integer"):
        MenuItem("Soup", True)


def test_menu_item_refuses_a_negative_price():
    with pytest.raises(MenuError, match="must not be negative"):
        MenuItem("Soup", -1)


def test_menu_item_row_round_trip():
    item = MenuItem("Soup", 625)
    assert MenuItem.from_row(item.to_row()) == item


def test_menu_item_to_row_writes_two_decimals():
    assert MenuItem("Soup", 605).to_row()["price"] == "6.05"


def test_menu_item_from_row_refuses_a_missing_field():
    with pytest.raises(MenuError, match="missing price"):
        MenuItem.from_row({"name": "Soup"})


def test_menu_item_from_row_refuses_an_unknown_field():
    with pytest.raises(MenuError, match="unknown column"):
        MenuItem.from_row({"name": "Soup", "price": "1.00", "course": "main"})


def test_menu_item_from_row_refuses_a_non_mapping():
    with pytest.raises(MenuError, match="mapping"):
        MenuItem.from_row(["Soup", "1.00"])


def test_menu_item_is_frozen():
    with pytest.raises(Exception):
        MenuItem("Soup", 625).name = "Stew"                 # type: ignore[misc]


# --------------------------------------------------------------------------- #
# The bundled menu
# --------------------------------------------------------------------------- #
def test_menu_has_ten_dishes(menu):
    assert len(menu) == 10


def test_menu_starts_with_garlic_bread(menu):
    assert menu[0] == MenuItem("Garlic Bread", 450)


def test_menu_ends_with_lemonade(menu):
    assert menu[-1] == MenuItem("Lemonade", 325)


def test_menu_stats_are_pinned(menu):
    summary = stats(menu)
    assert summary["dishes"] == 10
    assert summary["cheapest"] == 325
    assert summary["dearest"] == 1995


def test_menu_average_is_rounded_at_the_boundary(menu):
    total = sum(item.price_cents for item in menu)
    assert stats(menu)["average"] == round(total / len(menu))


def test_menu_cheapest_and_dearest_are_unique(menu):
    prices = [item.price_cents for item in menu]
    assert prices.count(min(prices)) == 1
    assert prices.count(max(prices)) == 1


def test_every_menu_price_is_positive(menu):
    assert all(item.price_cents > 0 for item in menu)


def test_menu_names_are_unique(menu):
    names = [item.name.casefold() for item in menu]
    assert len(names) == len(set(names))


def test_menu_file_is_named_for_its_purpose():
    assert DATA_FILE.name == "menu.csv"
    assert DATA_FILE.parent.name == "data"


def test_load_refuses_a_missing_file(tmp_path):
    with pytest.raises(MenuError, match="not found"):
        load_menu(tmp_path / "nope.csv")


def test_load_refuses_an_empty_file(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(MenuError, match="is empty"):
        load_menu(path)


def test_load_refuses_the_wrong_header(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("dish,cost\nSoup,4.00\n", encoding="utf-8")
    with pytest.raises(MenuError, match="expected"):
        load_menu(path)


def test_load_refuses_a_file_without_dishes(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("name,price\n", encoding="utf-8")
    with pytest.raises(MenuError, match="no dishes"):
        load_menu(path)


def test_load_names_the_line_of_a_bad_price(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("name,price\nSoup,four\n", encoding="utf-8")
    with pytest.raises(MenuError, match="line 2"):
        load_menu(path)


def test_load_refuses_a_row_with_too_many_fields(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("name,price\nSoup,4.00,extra\n", encoding="utf-8")
    with pytest.raises(MenuError, match="expected 2"):
        load_menu(path)


def test_load_refuses_a_duplicate_name(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("name,price\nSoup,4.00\nsoup,4.50\n", encoding="utf-8")
    with pytest.raises(MenuError, match="twice"):
        load_menu(path)


def test_load_skips_comments_and_blank_lines(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("# a menu\n\nname,price\n\nSoup,4.00\n", encoding="utf-8")
    assert load_menu(path) == [MenuItem("Soup", 400)]


def test_load_accepts_a_dollar_sign_in_the_file(tmp_path):
    path = tmp_path / "m.csv"
    path.write_text("name,price\nSoup,$4.00\n", encoding="utf-8")
    assert load_menu(path)[0].price_cents == 400


def test_find_item_is_case_insensitive(menu):
    assert find_item(menu, "PAD THAI").price_cents == 1340


def test_find_item_strips_space(menu):
    assert find_item(menu, "  Lemonade ").price_cents == 325


def test_find_item_refuses_an_unknown_dish(menu):
    with pytest.raises(MenuError, match="not on the menu"):
        find_item(menu, "Plague Burger")


def test_find_item_refuses_a_blank_name(menu):
    with pytest.raises(MenuError, match="must not be empty"):
        find_item(menu, "   ")


def test_render_menu_has_a_heading_and_every_dish(menu):
    lines = render_menu(menu).splitlines()
    assert len(lines) == 11
    assert "MENU" in lines[0]
    for item in menu:
        assert any(line.startswith(item.name) for line in lines[1:])


def test_render_menu_lines_are_all_the_same_width(menu):
    for line in render_menu(menu).splitlines()[1:]:
        assert display_width(line) == MENU_WIDTH, line


def test_render_menu_with_a_custom_width(menu):
    lines = render_menu(menu, 28).splitlines()
    assert all(display_width(line) == 28 for line in lines[1:])


# --------------------------------------------------------------------------- #
# Tax
# --------------------------------------------------------------------------- #
def test_tax_rate_constant_is_eight_point_seven_five_percent():
    assert TAX_BASIS_POINTS == 875


def test_tax_of_one_thousand_rounds_half_up():
    assert tax_for(1000) == 88                            # 87.5 -> 88


def test_tax_of_zero_is_zero():
    assert tax_for(0) == 0


def test_tax_of_571_cents():
    assert tax_for(571) == 50                             # 49.9625 -> 50


def test_tax_of_4175_cents():
    assert tax_for(4175) == 365


def test_tax_of_4500_cents():
    assert tax_for(4500) == 394


def test_tax_with_a_custom_rate():
    assert tax_for(8000, basis_points=1000) == 800


def test_tax_with_zero_rate():
    assert tax_for(9999, basis_points=0) == 0


def test_tax_with_a_hundred_percent_rate():
    assert tax_for(4500, basis_points=10000) == 4500


def test_tax_refuses_a_non_integer_subtotal():
    with pytest.raises(MenuError, match="integer number of cents"):
        tax_for("4500")


def test_tax_refuses_a_negative_subtotal():
    with pytest.raises(MenuError, match="must not be negative"):
        tax_for(-1)


def test_tax_refuses_a_negative_rate():
    with pytest.raises(MenuError, match="basis points"):
        tax_for(1000, basis_points=-1)


def test_tax_refuses_a_rate_above_hundred_percent():
    with pytest.raises(MenuError, match="basis points"):
        tax_for(1000, basis_points=10001)


# --------------------------------------------------------------------------- #
# Cart
# --------------------------------------------------------------------------- #
def test_a_new_cart_is_empty(cart):
    assert cart.count == 0 and cart.items == 0
    assert cart.subtotal() == 0


def test_add_returns_the_item(cart):
    assert cart.add("Lemonade") == MenuItem("Lemonade", 325)


def test_add_records_one_line(cart):
    cart.add("Lemonade")
    assert cart.count == 1 and cart.items == 1


def test_add_merges_the_same_dish(cart):
    cart.add("Lemonade")
    cart.add("Lemonade", 2)
    assert cart.count == 1 and cart.items == 3


def test_add_creates_a_separate_line_per_dish(cart):
    cart.add("Lemonade")
    cart.add("Tiramisu")
    assert cart.count == 2


def test_add_is_case_insensitive(cart):
    cart.add("lemonade")
    assert cart.quantity_of("Lemonade") == 1


def test_add_refuses_a_quantity_of_zero(cart):
    with pytest.raises(MenuError, match="at least 1"):
        cart.add("Lemonade", 0)


def test_add_refuses_a_negative_quantity(cart):
    with pytest.raises(MenuError, match="at least 1"):
        cart.add("Lemonade", -2)


def test_add_refuses_a_non_integer_quantity(cart):
    with pytest.raises(MenuError, match="must be an integer"):
        cart.add("Lemonade", "2")


def test_add_refuses_a_dish_not_on_the_menu(cart):
    with pytest.raises(MenuError, match="not on the menu"):
        cart.add("Plague Burger")


def test_remove_drops_the_line(cart):
    cart.add("Lemonade")
    assert cart.remove("Lemonade") == MenuItem("Lemonade", 325)
    assert cart.count == 0


def test_remove_refuses_a_dish_that_is_not_in_the_cart(cart):
    with pytest.raises(MenuError, match="not in the cart"):
        cart.remove("Lemonade")


def test_remove_of_an_unknown_dish_says_so(cart):
    with pytest.raises(MenuError, match="not on the menu"):
        cart.remove("Plague Burger")


def test_quantity_of_an_absent_dish_is_zero(cart):
    assert cart.quantity_of("Tiramisu") == 0


def test_quantity_of_counts_only_its_own_line(cart):
    cart.add("Lemonade", 2)
    cart.add("Tiramisu")
    assert cart.quantity_of("Lemonade") == 2
    assert cart.quantity_of("Tiramisu") == 1


def test_subtotal_multiplies_by_quantity(cart):
    cart.add("Garlic Bread", 3)
    assert cart.subtotal() == 1350


def test_subtotal_of_the_pinned_cart(cart):
    cart.add("Margherita Pizza", 2)
    cart.add("Lemonade")
    cart.add("Garlic Bread", 3)
    assert cart.subtotal() == 4175


def test_tax_of_the_pinned_cart(cart):
    cart.add("Margherita Pizza", 2)
    cart.add("Lemonade")
    cart.add("Garlic Bread", 3)
    assert cart.tax() == 365


def test_total_of_the_pinned_cart(cart):
    cart.add("Margherita Pizza", 2)
    cart.add("Lemonade")
    cart.add("Garlic Bread", 3)
    assert cart.total() == 4540


def test_total_is_subtotal_plus_tax(cart):
    cart.add("Beef Burger", 2)
    assert cart.total() == cart.subtotal() + cart.tax()


def test_an_empty_cart_renders_a_message(cart):
    assert cart.render() == "(the cart is empty)"


def test_the_rendered_cart_lists_each_line(cart):
    cart.add("Lemonade")
    cart.add("Tiramisu", 2)
    text = cart.render()
    assert "1 x Lemonade" in text and "2 x Tiramisu" in text


def test_the_rendered_cart_has_the_three_totals(cart):
    cart.add("Lemonade")
    text = cart.render()
    assert "Subtotal" in text and "Tax (8.75%)" in text and "Total" in text


def test_rendered_cart_lines_fit_the_width(cart):
    cart.add("Margherita Pizza", 2)
    cart.add("Garlic Bread", 3)
    for line in cart.render().splitlines():
        assert display_width(line) <= MENU_WIDTH, line


def test_a_cart_does_not_mutate_the_menu(menu):
    before = list(menu)
    cart = Cart(menu)
    cart.add("Lemonade", 5)
    assert menu == before


def test_stats_of_an_empty_menu():
    assert stats([]) == {"dishes": 0, "cheapest": None, "dearest": None,
                         "average": None}


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
def test_write_round_trips(tmp_path, menu):
    path = tmp_path / "m.csv"
    write_menu(path, menu)
    assert load_menu(path) == menu


def test_write_uses_the_canonical_header(tmp_path, menu):
    path = tmp_path / "m.csv"
    write_menu(path, menu)
    assert path.read_text(encoding="utf-8").splitlines()[0] == "name,price"


def test_write_is_byte_identical_on_a_second_write(tmp_path, menu):
    path = tmp_path / "m.csv"
    write_menu(path, menu)
    first = path.read_bytes()
    write_menu(path, load_menu(path))
    assert path.read_bytes() == first


def test_write_creates_directories(tmp_path, menu):
    path = tmp_path / "a" / "b" / "m.csv"
    write_menu(path, menu)
    assert path.is_file()


def test_write_leaves_no_temporary_file(tmp_path, menu):
    write_menu(tmp_path / "m.csv", menu)
    assert [item.name for item in tmp_path.iterdir()] == ["m.csv"]


def test_write_keeps_the_two_decimal_form(tmp_path):
    write_menu(tmp_path / "m.csv", [MenuItem("Soup", 605)])
    assert "Soup,6.05" in (tmp_path / "m.csv").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Demo and CLI
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


def test_demo_shows_the_legacy_collapse(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "Pad Thai----------$12" in out
    assert "shoulder$24" in out


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_prints_the_menu(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "Garlic Bread" in out and "10 dishes" in out


def test_cli_stats(capsys):
    assert cli.main(["--stats"]) == 0
    out = capsys.readouterr().out
    assert "$3.25" in out and "$19.95" in out
    assert "Lemonade" in out and "Grilled Salmon" in out


def test_cli_price_lookup(capsys):
    assert cli.main(["--price", "Pad Thai"]) == 0
    assert "$13.40" in capsys.readouterr().out


def test_cli_price_of_an_unknown_dish_exits_two(capsys):
    assert cli.main(["--price", "Plague Burger"]) == 2
    assert "not on the menu" in capsys.readouterr().err


def test_cli_order_totals(capsys):
    assert cli.main(["--order", "Margherita Pizza:2",
                     "--order", "Lemonade",
                     "--order", "Garlic Bread:3"]) == 0
    out = capsys.readouterr().out
    assert "$41.75" in out and "$3.65" in out and "$45.40" in out


def test_cli_order_custom_tax_rate(capsys):
    assert cli.main(["--order", "Garlic Bread", "--tax-rate", "10"]) == 0
    out = capsys.readouterr().out
    assert "$0.45" in out and "Tax (10%)" in out


def test_cli_order_refuses_a_malformed_spec(capsys):
    assert cli.main(["--order", ":2"]) == 2
    assert "expected DISH:QUANTITY" in capsys.readouterr().err


def test_cli_order_quantity_is_optional(capsys):
    assert cli.main(["--order", "Lemonade"]) == 0
    out = capsys.readouterr().out
    assert "1 x Lemonade" in out


def test_cli_order_refuses_a_non_numeric_quantity(capsys):
    assert cli.main(["--order", "Lemonade:two"]) == 2
    assert "not a whole number" in capsys.readouterr().err


def test_cli_order_refuses_an_unknown_dish(capsys):
    assert cli.main(["--order", "Plague Burger:1"]) == 2
    assert "not on the menu" in capsys.readouterr().err


def test_cli_legacy_mode(capsys):
    assert cli.main(["--legacy", "Pad Thai:12"]) == 0
    out = capsys.readouterr().out
    assert "Pad Thai----------$12" in out
    assert "10 dash(es)" in out


def test_cli_legacy_collapse_is_reported(capsys):
    assert cli.main(["--legacy", "Slow-roasted lamb shoulder:24"]) == 0
    out = capsys.readouterr().out
    assert "no gap" not in out
    assert "'-' * 0 is ''" in out


def test_cli_legacy_refuses_a_decimal_price(capsys):
    assert cli.main(["--legacy", "Pad Thai:12.50"]) == 2
    assert "whole dollars" in capsys.readouterr().err


def test_cli_legacy_refuses_a_malformed_argument(capsys):
    assert cli.main(["--legacy", "Pad Thai"]) == 2
    assert "expected DISH:PRICE" in capsys.readouterr().err


def test_cli_refuses_a_zero_width(capsys):
    assert cli.main(["--width", "0"]) == 2
    assert "at least 1" in capsys.readouterr().err


def test_cli_refuses_an_impossible_tax_rate(capsys):
    assert cli.main(["--order", "Lemonade", "--tax-rate", "150"]) == 2
    assert "between 0 and 100" in capsys.readouterr().err


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.csv"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_write_prints_a_confirmation(tmp_path, capsys):
    target = tmp_path / "m.csv"
    assert cli.main(["--write", str(target)]) == 0
    assert "written to m.csv" in capsys.readouterr().out
    assert load_menu(target) == load_menu()


def test_cli_json_menu(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "menu"
    assert len(payload["items"]) == 10


def test_cli_json_order(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--order", "Lemonade:2", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "order"
    assert payload["subtotal_cents"] == 650
    assert payload["items"] == 2


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--stats", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
