"""Tests for GitHub_Profile_Analyzer: a page number is an offset into a list
that moves, and only a cursor says when the collection ends."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                           # noqa: E402
import pagination as module                                 # noqa: E402
from pagination import (                                    # noqa: E402
    LEGACY_ERROR_BODY,
    LEGACY_FETCH,
    MAX_PER_PAGE,
    PER_PAGE,
    REPOS_FILE,
    Item,
    Page,
    PageError,
    Repository,
    Walk,
    audit,
    cursor_for,
    cursor_walk,
    id_from_cursor,
    is_repository_row,
    legacy_fetch,
    offset_walk,
    parse_items,
    problems,
    read_repositories,
    row_text,
    run_demo,
)

ITEMS, ARRIVING = read_repositories()
PER = 4


def an_item(ident: int = 101, name: str = "alpha", stars: int = 1200) -> Item:
    return Item(ident, name, stars)


def a_server(error_on: int | None = None) -> Repository:
    server = Repository(ITEMS, ARRIVING)
    server.error_on = error_on
    return server


def a_page(number: int = 1, items=None, total: int = 10,
           following: str | None = None, per_page: int = PER) -> Page:
    return Page(number, per_page,
                tuple(items) if items is not None else (an_item(),),
                total, following)


def a_walk(mode: str = "offset", pages=None, totals=(10,),
           stopped: str = "empty") -> Walk:
    return Walk(mode, tuple(pages) if pages is not None else ((an_item(),),),
                tuple(totals), stopped)


def offset_and_cursor():
    """The two walks over the moving list, exactly as the demo makes them."""
    server = a_server()
    offset = offset_walk(server, PER,
                         lambda page: server.arrive() if page.number == 1
                         else None)
    server = a_server()
    cursor = cursor_walk(server, PER,
                         lambda page: server.arrive() if page.number == 1
                         else None)
    return offset, cursor


def legacy_rows():
    """The legacy loop over the moving list, and over a rate-limited one."""
    server = a_server()
    plain = legacy_fetch(server, PER,
                         lambda number: server.arrive() if number == 1
                         else None)
    limited = legacy_fetch(a_server(error_on=2), PER)
    return plain, limited


# --------------------------------------------------------------------------- #
# A repository
# --------------------------------------------------------------------------- #
def test_an_item_holds_an_id_a_name_and_a_star_count():
    item = an_item()
    assert (item.id, item.name, item.stars) == (101, "alpha", 1200)


def test_an_item_prints_its_id_and_name():
    assert str(an_item()) == "101 alpha"


def test_items_order_by_id_first():
    assert an_item(101) < an_item(102)


def test_two_items_with_one_id_and_name_are_the_same_item():
    assert an_item() == an_item()


def test_a_zero_id_is_refused():
    with pytest.raises(PageError, match="an id is at least 1"):
        an_item(0)


def test_a_float_id_is_refused():
    with pytest.raises(PageError, match="an id is a whole number"):
        an_item(1.5)


def test_a_bool_id_is_refused():
    with pytest.raises(PageError, match="an id is a whole number"):
        an_item(True)


def test_an_empty_name_is_refused():
    with pytest.raises(PageError, match="a name needs a value"):
        an_item(name="  ")


def test_a_name_with_a_space_is_refused():
    with pytest.raises(PageError, match="a name is one word"):
        an_item(name="al pha")


def test_a_name_that_is_not_text_is_refused():
    with pytest.raises(PageError, match="a name is text"):
        an_item(name=101)


def test_negative_stars_are_refused():
    with pytest.raises(PageError, match="a star count is at least 0"):
        an_item(stars=-1)


def test_zero_stars_are_allowed():
    assert an_item(stars=0).stars == 0


# --------------------------------------------------------------------------- #
# Cursors
# --------------------------------------------------------------------------- #
def test_a_cursor_names_the_repository_before_it():
    assert cursor_for(an_item(104)) == "after=104"


def test_a_cursor_reads_back_to_its_id():
    assert id_from_cursor("after=104") == 104


def test_a_cursor_that_is_not_text_is_refused():
    with pytest.raises(PageError, match="a cursor is text"):
        id_from_cursor(104)


def test_a_cursor_without_the_prefix_is_refused():
    with pytest.raises(PageError, match="is not a cursor"):
        id_from_cursor("104")


def test_a_cursor_with_no_digits_is_refused():
    with pytest.raises(PageError, match="holds no id"):
        id_from_cursor("after=four")


# --------------------------------------------------------------------------- #
# A page
# --------------------------------------------------------------------------- #
def test_a_page_holds_its_window_its_total_and_its_next():
    page = a_page()
    assert (page.number, page.per_page, page.total_count, page.next) == \
        (1, 4, 10, None)


def test_a_page_counts_its_items():
    assert len(a_page(items=(an_item(), an_item(102, "bravo")))) == 2


def test_a_page_names_its_ids():
    page = a_page(items=(an_item(), an_item(102, "bravo")))
    assert page.ids() == (101, 102)


def test_a_page_names_its_repositories():
    page = a_page(items=(an_item(), an_item(102, "bravo")))
    assert page.names() == ("alpha", "bravo")


def test_a_page_with_no_next_is_the_last_page():
    assert a_page().is_last() is True


def test_a_page_with_a_next_is_not_the_last_page():
    assert a_page(following="after=104").is_last() is False


def test_an_empty_page_is_still_a_page():
    page = a_page(items=(), total=0)
    assert len(page) == 0 and page.is_last() is True


def test_a_page_line_shows_the_names_the_total_and_the_next():
    page = a_page(items=(an_item(), an_item(102, "bravo")),
                  following="after=102")
    assert page.line() == ("page 1 [alpha, bravo] total=10 "
                           "next=after=102")


def test_a_page_line_says_next_is_none_on_the_last_page():
    assert a_page(items=(an_item(),)).line() == \
        "page 1 [alpha] total=10 next=None"


def test_a_page_of_zero_size_is_refused():
    with pytest.raises(PageError, match="a page size is at least 1"):
        a_page(per_page=0)


def test_a_page_larger_than_the_limit_is_refused():
    with pytest.raises(PageError, match="holds at most 100 items"):
        a_page(per_page=MAX_PER_PAGE + 1)


def test_a_page_number_of_zero_is_refused():
    with pytest.raises(PageError, match="a page number is at least 1"):
        a_page(number=0)


def test_a_page_holding_more_than_its_size_is_refused():
    with pytest.raises(PageError, match="more than its page size"):
        a_page(items=(an_item(), an_item(102, "bravo")), per_page=1)


def test_a_page_reporting_fewer_items_than_it_holds_is_refused():
    with pytest.raises(PageError, match="reports a total of 2"):
        a_page(items=(an_item(), an_item(102, "bravo"), an_item(103, "c")),
               total=2)


def test_a_page_with_a_cursor_it_cannot_read_is_refused():
    with pytest.raises(PageError, match="is not a cursor"):
        a_page(following="page=2")


# --------------------------------------------------------------------------- #
# A server
# --------------------------------------------------------------------------- #
def test_a_server_holds_its_repositories_newest_first():
    server = a_server()
    assert server.names() == ("alpha", "bravo", "charlie", "delta", "echo",
                              "foxtrot", "golf", "hotel", "india", "juliet")


def test_a_server_counts_its_repositories():
    assert len(a_server()) == 10


def test_a_server_needs_a_repository():
    with pytest.raises(PageError, match="needs at least one repository"):
        Repository(())


def test_a_server_refuses_two_repositories_with_one_id():
    with pytest.raises(PageError, match="share an id"):
        Repository((an_item(), an_item()))


def test_a_server_refuses_a_row_that_is_not_a_repository():
    with pytest.raises(PageError, match="holds repositories"):
        Repository((101,))


def test_a_server_names_the_repository_waiting_to_arrive():
    assert a_server().arriving() == ARRIVING


def test_a_server_has_not_arrived_before_it_does():
    assert a_server().has_arrived() is False


def test_arriving_pushes_the_repository_onto_the_head():
    server = a_server()
    assert server.arrive() == ARRIVING


def test_after_arriving_the_list_has_eleven():
    server = a_server()
    server.arrive()
    assert len(server) == 11 and server.names()[0] == "kilo"


def test_arriving_twice_is_refused():
    server = a_server()
    server.arrive()
    with pytest.raises(PageError, match="has already arrived"):
        server.arrive()


def test_a_server_with_nothing_waiting_cannot_arrive():
    server = Repository(ITEMS[:3])
    with pytest.raises(PageError, match="no repository waiting"):
        server.arrive()


def test_a_page_by_number_starts_at_index_zero():
    assert a_server().page_number(1, PER).names() == \
        ("alpha", "bravo", "charlie", "delta")


def test_a_page_by_number_counts_from_one():
    assert a_server().page_number(2, PER).names()[0] == "echo"


def test_a_page_by_number_holds_the_remainder_on_the_last_page():
    assert a_server().page_number(3, PER).names() == ("india", "juliet")


def test_a_page_past_the_end_is_empty():
    assert len(a_server().page_number(4, PER)) == 0


def test_a_page_by_number_reports_the_total():
    assert a_server().page_number(1, PER).total_count == 10


def test_a_page_by_number_offers_a_next_when_more_remain():
    assert a_server().page_number(1, PER).next == "after=104"


def test_the_last_full_page_by_number_offers_no_next():
    server = Repository(ITEMS[:8])
    assert server.page_number(2, PER).next is None


def test_a_page_by_number_refuses_a_zero_page_size():
    with pytest.raises(PageError, match="a page size is at least 1"):
        a_server().page_number(1, 0)


def test_a_page_after_no_cursor_starts_at_the_head():
    assert a_server().page_after(None, PER).names() == \
        ("alpha", "bravo", "charlie", "delta")


def test_a_page_after_a_cursor_starts_after_that_repository():
    assert a_server().page_after("after=104", PER).names() == \
        ("echo", "foxtrot", "golf", "hotel")


def test_a_page_after_a_cursor_that_has_moved_still_works():
    server = a_server()
    server.arrive()
    assert server.page_after("after=104", PER).names()[0] == "echo"


def test_a_page_after_a_cursor_the_list_no_longer_holds_is_refused():
    with pytest.raises(PageError, match="no longer holds"):
        a_server().page_after("after=999", PER)


def test_a_cursor_on_the_last_repository_offers_no_next():
    assert a_server().page_after("after=108", PER).next is None


def test_the_raw_body_is_a_json_list_of_repositories():
    body = a_server().raw_number(1, PER)
    rows = json.loads(body)
    assert len(rows) == 4 and rows[0]["name"] == "alpha"


def test_the_raw_body_carries_every_field():
    rows = json.loads(a_server().raw_number(1, PER))
    assert rows[0] == {"id": 101, "name": "alpha", "stars": 1200}


def test_the_raw_body_past_the_end_is_an_empty_list():
    assert json.loads(a_server().raw_number(4, PER)) == []


def test_a_rate_limited_page_is_an_error_envelope_not_a_list():
    server = a_server(error_on=2)
    assert json.loads(server.raw_number(2, PER)) == LEGACY_ERROR_BODY


def test_a_page_count_rounds_the_remainder_up():
    assert a_server().page_count(PER) == 3


def test_a_page_count_of_exact_pages_is_exact():
    assert Repository(ITEMS[:8]).page_count(PER) == 2


def test_a_server_counts_the_pages_it_has_served():
    server = a_server()
    server.page_number(1, PER)
    server.page_number(2, PER)
    assert server.served == 2


# --------------------------------------------------------------------------- #
# A walk
# --------------------------------------------------------------------------- #
def test_a_walk_flattens_its_pages_into_rows():
    walk = a_walk(pages=((an_item(),), (an_item(102, "bravo"),)),
                  totals=(2, 2))
    assert [item.name for item in walk.rows()] == ["alpha", "bravo"]


def test_a_walk_names_the_ids_it_collected():
    assert a_walk().ids() == (101,)


def test_a_walk_counts_its_rows():
    walk = a_walk(pages=((an_item(), an_item()), ), totals=(1,))
    assert len(walk) == 2


def test_unique_keeps_the_first_of_a_repeated_id():
    walk = a_walk(pages=((an_item(), an_item()),), totals=(1,))
    assert len(walk.unique()) == 1


def test_duplicates_names_the_repeated_row():
    walk = a_walk(pages=((an_item(), an_item(102, "bravo"), an_item()),
                         ), totals=(2,))
    assert [item.name for item in walk.duplicates()] == ["alpha"]


def test_a_walk_with_no_repeats_has_no_duplicates():
    walk = a_walk(pages=((an_item(), an_item(102, "bravo")),), totals=(2,))
    assert walk.duplicates() == ()


def test_missing_names_a_repository_the_walk_never_saw():
    walk = a_walk(pages=((an_item(),),), totals=(2,))
    assert [item.name for item in walk.missing((an_item(),
                                                an_item(102, "bravo")))] == \
        ["bravo"]


def test_shortfall_counts_the_rows_the_total_promises_and_the_walk_lacks():
    assert a_walk(pages=((an_item(),),), totals=(5,)).shortfall() == 4


def test_shortfall_ignores_a_duplicate():
    walk = a_walk(pages=((an_item(), an_item()),), totals=(1,))
    assert walk.shortfall() == 0


def test_a_walk_with_no_pages_has_no_shortfall():
    assert Walk("cursor", (), (), "next").shortfall() == 0


def test_a_clean_walk_is_complete():
    walk = a_walk(pages=((an_item(), an_item(102, "bravo")),), totals=(2,))
    assert walk.complete() is True


def test_a_walk_with_a_duplicate_is_not_complete():
    walk = a_walk(pages=((an_item(), an_item()),), totals=(1,))
    assert walk.complete() is False


def test_a_walk_with_a_shortfall_is_not_complete():
    assert a_walk(pages=((an_item(),),), totals=(3,)).complete() is False


def test_a_walk_line_names_every_count():
    walk = a_walk(pages=((an_item(), an_item()),), totals=(1,))
    assert walk.line() == ("offset 1 page(s)  2 row(s)  1 unique  1 "
                           "duplicate(s) short  0 stopped on empty")


def test_a_walk_refuses_a_mode_that_is_not_a_walk():
    with pytest.raises(PageError, match="offset or cursor"):
        a_walk(mode="random")


def test_a_walk_refuses_a_stop_that_is_not_one_of_three():
    with pytest.raises(PageError, match="stops on next, empty or limit"):
        a_walk(stopped="done")


def test_a_walk_refuses_one_more_page_than_total():
    with pytest.raises(PageError, match="one total per page"):
        a_walk(pages=((an_item(),), (an_item(),)), totals=(2,))


# --------------------------------------------------------------------------- #
# The two walks
# --------------------------------------------------------------------------- #
def test_the_offset_walk_reads_four_pages():
    offset, _ = offset_and_cursor()
    assert len(offset.pages) == 4


def test_the_offset_walk_collects_eleven_rows():
    offset, _ = offset_and_cursor()
    assert len(offset.rows()) == 11


def test_the_offset_walk_collects_only_ten_repositories():
    offset, _ = offset_and_cursor()
    assert len(offset.unique()) == 10


def test_the_offset_walk_repeats_delta():
    offset, _ = offset_and_cursor()
    assert [item.name for item in offset.duplicates()] == ["delta"]


def test_the_offset_walk_repeats_delta_at_index_three():
    offset, _ = offset_and_cursor()
    ids = offset.ids()
    assert ids.count(104) == 2 and ids.index(104) == 3


def test_the_offset_walk_never_sees_the_repository_that_arrived():
    offset, _ = offset_and_cursor()
    assert ARRIVING not in offset.rows()


def test_the_offset_walk_stops_on_an_empty_page():
    offset, _ = offset_and_cursor()
    assert offset.stopped == "empty"


def test_the_offset_walk_needs_a_fourth_request_to_know_it_is_done():
    offset, _ = offset_and_cursor()
    assert len(offset.pages[3]) == 0


def test_the_offset_walk_reports_a_shortfall_of_one():
    offset, _ = offset_and_cursor()
    assert offset.shortfall() == 1


def test_the_offset_walk_is_not_complete():
    offset, _ = offset_and_cursor()
    assert offset.complete() is False


def test_the_cursor_walk_reads_three_pages():
    _, cursor = offset_and_cursor()
    assert len(cursor.pages) == 3


def test_the_cursor_walk_collects_ten_rows():
    _, cursor = offset_and_cursor()
    assert len(cursor.rows()) == 10


def test_the_cursor_walk_has_no_duplicates():
    _, cursor = offset_and_cursor()
    assert cursor.duplicates() == ()


def test_the_cursor_walk_sees_the_ten_original_repositories():
    _, cursor = offset_and_cursor()
    assert cursor.ids() == tuple(item.id for item in ITEMS)


def test_the_cursor_walk_stops_on_the_missing_next():
    _, cursor = offset_and_cursor()
    assert cursor.stopped == "next"


def test_the_cursor_walk_reports_the_total_growing():
    _, cursor = offset_and_cursor()
    assert cursor.totals == (10, 11, 11)


def test_the_cursor_walk_never_sees_the_repository_that_arrived():
    _, cursor = offset_and_cursor()
    assert ARRIVING not in cursor.rows()


def test_the_cursor_walk_still_reports_the_shortfall():
    _, cursor = offset_and_cursor()
    assert cursor.shortfall() == 1


def test_a_walk_that_hits_its_limit_says_so():
    server = a_server()
    walk = offset_walk(server, PER, limit=1)
    assert walk.stopped == "limit" and len(walk.pages) == 1


def test_a_cursor_walk_that_hits_its_limit_says_so():
    server = a_server()
    walk = cursor_walk(server, PER, limit=1)
    assert walk.stopped == "limit" and len(walk.pages) == 1


def test_a_walk_on_a_still_list_is_complete():
    server = Repository(ITEMS)
    walk = cursor_walk(server, PER)
    assert walk.complete() is True and len(walk.rows()) == 10


def test_an_offset_walk_on_a_still_list_is_complete_too():
    server = Repository(ITEMS)
    walk = offset_walk(server, PER)
    assert walk.complete() is True and len(walk.pages) == 4


def test_an_offset_walk_that_ends_on_an_exact_page_needs_one_more_request():
    server = Repository(ITEMS[:8])
    walk = offset_walk(server, PER)
    assert len(walk.pages) == 3 and len(walk.pages[2]) == 0


def test_a_cursor_walk_that_ends_on_an_exact_page_needs_no_extra_request():
    server = Repository(ITEMS[:8])
    walk = cursor_walk(server, PER)
    assert len(walk.pages) == 2 and walk.stopped == "next"


def test_a_walk_refuses_a_zero_page_size():
    with pytest.raises(PageError, match="a page size is at least 1"):
        offset_walk(a_server(), 0)


def test_a_walk_refuses_a_zero_limit():
    with pytest.raises(PageError, match="a page limit is at least 1"):
        cursor_walk(a_server(), PER, limit=0)


# --------------------------------------------------------------------------- #
# The legacy loop
# --------------------------------------------------------------------------- #
def test_the_legacy_loop_collects_eleven_rows_over_a_moving_list():
    plain, _ = legacy_rows()
    assert len(plain) == 11


def test_the_legacy_loop_repeats_delta():
    plain, _ = legacy_rows()
    names = [row["name"] for row in plain]
    assert names.count("delta") == 2


def test_the_legacy_rows_are_dictionaries_not_repositories():
    plain, _ = legacy_rows()
    assert all(isinstance(row, dict) for row in plain)


def test_every_legacy_row_is_a_repository_row():
    plain, _ = legacy_rows()
    assert all(is_repository_row(row) for row in plain)


def test_the_legacy_loop_never_notices_its_duplicate():
    plain, _ = legacy_rows()
    assert len(plain) != len({row["id"] for row in plain})


def test_the_legacy_loop_turns_a_rate_limit_into_two_strings():
    _, limited = legacy_rows()
    junk = [row for row in limited if not is_repository_row(row)]
    assert junk == ["message", "documentation_url"]


def test_the_legacy_loop_loses_the_four_repositories_on_the_error_page():
    _, limited = legacy_rows()
    assert len([row for row in limited if is_repository_row(row)]) == 6


def test_the_legacy_loop_keeps_going_after_the_error_page():
    _, limited = legacy_rows()
    assert limited[-1]["name"] == "juliet"


def test_the_legacy_loop_stops_on_an_empty_body():
    server = Repository(ITEMS[:4])
    assert len(legacy_fetch(server, PER)) == 4


def test_the_legacy_loop_refuses_a_zero_page_size():
    with pytest.raises(PageError, match="a page size is at least 1"):
        legacy_fetch(a_server(), 0)


def test_a_repository_row_needs_an_id_and_a_name():
    assert is_repository_row({"id": 1, "name": "a"}) is True
    assert is_repository_row({"message": "x"}) is False
    assert is_repository_row("message") is False


def test_row_text_names_a_repository():
    assert row_text({"id": 101, "name": "alpha"}) == "alpha"


def test_row_text_shows_the_string_of_a_junk_row():
    assert row_text("message") == "message"


def test_the_legacy_lines_are_pinned():
    assert "?page=%d" in LEGACY_FETCH
    assert "if not data:" in LEGACY_FETCH
    assert "out += data" in LEGACY_FETCH


# --------------------------------------------------------------------------- #
# Reading the bundle
# --------------------------------------------------------------------------- #
def test_parse_items_reads_the_ten_repositories():
    items, _ = parse_items(REPOS_FILE.read_text(encoding="utf-8"))
    assert len(items) == 10 and items[0].name == "alpha"


def test_parse_items_reads_the_arriving_repository():
    _, arriving = parse_items(REPOS_FILE.read_text(encoding="utf-8"))
    assert arriving.name == "kilo" and arriving.stars == 760


def test_parse_items_skips_a_comment():
    items, _ = parse_items("; note\n101 alpha 12\n")
    assert len(items) == 1


def test_parse_items_skips_a_blank_line():
    items, _ = parse_items("\n101 alpha 12\n\n")
    assert len(items) == 1


def test_parse_items_reads_windows_line_endings():
    items, _ = parse_items("101 alpha 12\r\n102 bravo 9\r\n")
    assert len(items) == 2


def test_parse_items_needs_no_arriving_line():
    items, arriving = parse_items("101 alpha 12\n")
    assert arriving is None and len(items) == 1


def test_parse_items_refuses_a_line_of_two_fields():
    with pytest.raises(PageError, match="is an id, a name and a star count"):
        parse_items("101 alpha\n")


def test_parse_items_refuses_an_id_that_is_not_a_number():
    with pytest.raises(PageError, match="are whole numbers"):
        parse_items("one alpha 12\n")


def test_parse_items_refuses_a_star_count_that_is_not_a_number():
    with pytest.raises(PageError, match="are whole numbers"):
        parse_items("101 alpha many\n")


def test_parse_items_refuses_a_bundle_with_no_repositories():
    with pytest.raises(PageError, match="holds no repositories"):
        parse_items("; nothing\n")


def test_parse_items_refuses_two_repositories_with_one_id():
    with pytest.raises(PageError, match="share an id"):
        parse_items("101 alpha 12\n101 bravo 9\n")


def test_parse_items_refuses_a_second_arrives_line():
    with pytest.raises(PageError, match="a second arrives line"):
        parse_items("101 alpha 12\narrives 9 x 1\narrives 8 y 2\n")


def test_parse_items_refuses_a_short_arrives_line():
    with pytest.raises(PageError, match="arrives takes an id"):
        parse_items("101 alpha 12\narrives 9 x\n")


def test_parse_items_refuses_an_arriving_id_already_in_the_list():
    with pytest.raises(PageError, match="reuses the id"):
        parse_items("101 alpha 12\narrives 101 kilo 7\n")


def test_a_missing_bundle_is_refused(tmp_path):
    with pytest.raises(PageError, match="file not found"):
        module.read_repositories(tmp_path / "nope.txt")


def test_read_repositories_accepts_its_own_file(tmp_path):
    path = tmp_path / "repos.txt"
    path.write_bytes(b"101 alpha 12\narrives 102 bravo 9\n")
    items, arriving = read_repositories(path)
    assert len(items) == 1 and arriving.id == 102


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every page holds unique ids of its own",
    "no page holds more items than its page size",
    "the offset walk repeats a row when the head moves",
    "the offset walk never sees the repository that arrived",
    "the offset walk needs deduping to be ten repositories",
    "the cursor walk has no duplicates and sees the original list",
    "the cursor walk reports that the collection grew",
    "each walk stops on its own signal, not on a limit",
    "the legacy loop turns an error body into rows",
    "every page reports a total big enough for its rows",
]


def real_checks():
    offset, cursor = offset_and_cursor()
    plain, limited = legacy_rows()
    return audit(offset, cursor, plain, limited, ITEMS, ARRIVING, PER)


def test_the_audit_holds_ten_named_checks():
    assert [name for name, _ in real_checks()] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_list():
    assert problems(real_checks()) == []


def test_the_audit_is_repeatable():
    assert real_checks() == real_checks()


def test_the_audit_catches_a_page_that_repeats_an_id_inside_itself():
    offset, cursor = offset_and_cursor()
    plain, limited = legacy_rows()
    broken = a_walk(pages=((an_item(), an_item()),), totals=(1,))
    checks = audit(broken, cursor, plain, limited, ITEMS, ARRIVING, PER)
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_a_page_larger_than_its_size():
    offset, cursor = offset_and_cursor()
    plain, limited = legacy_rows()
    big = (an_item(), an_item(102, "b"), an_item(103, "c"), an_item(104, "d"),
           an_item(105, "e"))
    broken = a_walk(pages=(big,), totals=(5,))
    checks = audit(broken, cursor, plain, limited, ITEMS, ARRIVING, PER)
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_an_offset_walk_with_no_duplicate():
    _, cursor = offset_and_cursor()
    plain, limited = legacy_rows()
    clean = a_walk(pages=(ITEMS[:4], ITEMS[4:]), totals=(10, 10))
    checks = audit(clean, cursor, plain, limited, ITEMS, ARRIVING, PER)
    assert CHECK_NAMES[2] in problems(checks)


def test_the_audit_catches_an_offset_walk_that_saw_the_arriving_repository():
    _, cursor = offset_and_cursor()
    plain, limited = legacy_rows()
    with_new = a_walk(pages=((ARRIVING,),), totals=(11,))
    checks = audit(with_new, cursor, plain, limited, ITEMS, ARRIVING, PER)
    assert CHECK_NAMES[3] in problems(checks)


def test_the_audit_catches_an_offset_walk_of_ten_rows():
    _, cursor = offset_and_cursor()
    plain, limited = legacy_rows()
    ten = a_walk(pages=(ITEMS[:5], ITEMS[5:]), totals=(10, 10))
    checks = audit(ten, cursor, plain, limited, ITEMS, ARRIVING, PER)
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_a_cursor_walk_with_a_duplicate():
    offset, _ = offset_and_cursor()
    plain, limited = legacy_rows()
    repeated = a_walk("cursor", pages=((an_item(), an_item()),), totals=(1,))
    checks = audit(offset, repeated, plain, limited, ITEMS, ARRIVING, PER)
    assert CHECK_NAMES[5] in problems(checks)


def test_the_audit_catches_a_cursor_walk_that_saw_ten_all_along():
    offset, _ = offset_and_cursor()
    plain, limited = legacy_rows()
    flat = a_walk("cursor", pages=(ITEMS,), totals=(10,))
    checks = audit(offset, flat, plain, limited, ITEMS, ARRIVING, PER)
    assert CHECK_NAMES[6] in problems(checks)


def test_the_audit_catches_a_cursor_walk_stopped_by_a_limit():
    offset, cursor = offset_and_cursor()
    plain, limited = legacy_rows()
    truncated = Walk("cursor", cursor.pages, cursor.totals, "limit")
    checks = audit(offset, truncated, plain, limited, ITEMS, ARRIVING, PER)
    assert CHECK_NAMES[7] in problems(checks)


def test_the_audit_catches_a_legacy_run_that_never_met_an_error():
    offset, cursor = offset_and_cursor()
    plain, limited = legacy_rows()
    checks = audit(offset, cursor, plain, plain, ITEMS, ARRIVING, PER)
    assert CHECK_NAMES[8] in problems(checks)


def test_the_audit_catches_a_page_that_reports_too_small_a_total():
    offset, cursor = offset_and_cursor()
    plain, limited = legacy_rows()
    small = Walk("cursor", cursor.pages, (5, 5, 5), "next")
    checks = audit(offset, small, plain, limited, ITEMS, ARRIVING, PER)
    assert CHECK_NAMES[9] in problems(checks)


def test_every_check_has_a_negative_control():
    offset, cursor = offset_and_cursor()
    plain, limited = legacy_rows()
    broken = [
        audit(a_walk(pages=((an_item(), an_item()),), totals=(1,)), cursor,
              plain, limited, ITEMS, ARRIVING, PER),
        audit(a_walk(pages=((an_item(), an_item(102, "b"), an_item(103, "c"),
                             an_item(104, "d"), an_item(105, "e")),),
                    totals=(5,)), cursor, plain, limited, ITEMS, ARRIVING, PER),
        audit(a_walk(pages=(ITEMS[:4], ITEMS[4:]), totals=(10, 10)), cursor,
              plain, limited, ITEMS, ARRIVING, PER),
        audit(a_walk(pages=((ARRIVING,),), totals=(11,)), cursor, plain,
              limited, ITEMS, ARRIVING, PER),
        audit(a_walk(pages=(ITEMS[:5], ITEMS[5:]), totals=(10, 10)), cursor,
              plain, limited, ITEMS, ARRIVING, PER),
        audit(offset, a_walk("cursor", pages=((an_item(), an_item()),),
                             totals=(1,)), plain, limited, ITEMS, ARRIVING,
              PER),
        audit(offset, a_walk("cursor", pages=(ITEMS,), totals=(10,)), plain,
              limited, ITEMS, ARRIVING, PER),
        audit(offset, Walk("cursor", cursor.pages, cursor.totals, "limit"),
              plain, limited, ITEMS, ARRIVING, PER),
        audit(offset, cursor, plain, plain, ITEMS, ARRIVING, PER),
        audit(offset, Walk("cursor", cursor.pages, (5, 5, 5), "next"), plain,
              limited, ITEMS, ARRIVING, PER),
    ]
    caught = {name for checks in broken for name in problems(checks)}
    assert len(caught) == 10


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


def test_demo_shows_the_legacy_loop(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "?page=%d" in out and "out += data" in out


def test_demo_shows_the_offset_pages(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "page 1 [alpha, bravo, charlie, delta] total=10 next=after=104" in out
    assert "page 2 [delta, echo, foxtrot, golf] total=11" in out


def test_demo_shows_the_repeated_row(capsys):
    run_demo()
    assert "duplicated: delta   never seen: kilo" in capsys.readouterr().out


def test_demo_shows_the_cursor_pages(capsys):
    run_demo()
    assert "page 2 [echo, foxtrot, golf, hotel] total=11 next=after=108" in \
        capsys.readouterr().out


def test_demo_shows_the_cursor_walk_has_no_duplicates(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "cursor 3 page(s) 10 row(s) 10 unique  0 duplicate(s)" in out


def test_demo_shows_the_cost_table(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "offset       4    11     10     1     1  empty" in out
    assert "cursor       3    10     10     0     1  next" in out


def test_demo_shows_the_error_body_as_rows(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "alpha bravo charlie delta message documentation_url india juliet" \
        in out
    assert "2 of them are the error body's keys: message, documentation_url" \
        in out


def test_demo_shows_all_ten_checks(capsys):
    run_demo()
    assert "10/10 checks pass" in capsys.readouterr().out


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


def test_cli_compares_both_walks(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "10 repositories, page size 4" in out
    assert "offset 4 page(s) 10 row(s)" in out
    assert "cursor 3 page(s) 10 row(s)" in out


def test_cli_shows_the_legacy_counts(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "legacy: 10 row(s), 10 repositories" in out
    assert "keys: message, documentation_url" in out


def test_cli_walks_by_offset(capsys):
    assert cli.main(["--walk", "offset"]) == 0
    out = capsys.readouterr().out
    assert "[alpha, bravo, charlie, delta]" in out
    assert "offset 4 page(s) 10 row(s) 10 unique" in out


def test_cli_walks_by_cursor(capsys):
    assert cli.main(["--walk", "cursor"]) == 0
    out = capsys.readouterr().out
    assert "[alpha, bravo, charlie, delta]" in out
    assert "stopped on next" in out


def test_cli_insert_makes_the_offset_walk_repeat_a_row(capsys):
    assert cli.main(["--walk", "offset", "--insert"]) == 0
    out = capsys.readouterr().out
    assert "duplicated: delta" in out and "never seen: kilo" in out


def test_cli_insert_leaves_the_cursor_walk_clean(capsys):
    assert cli.main(["--walk", "cursor", "--insert"]) == 0
    out = capsys.readouterr().out
    assert "0 duplicate(s)" in out and "duplicated:" not in out


def test_cli_per_page_changes_the_pages(capsys):
    assert cli.main(["--walk", "offset", "--per-page", "5"]) == 0
    assert "[alpha, bravo, charlie, delta, echo]" in capsys.readouterr().out


def test_cli_refuses_a_page_size_of_zero(capsys):
    assert cli.main(["--per-page", "0"]) == 2
    assert "a page size is between 1 and 100" in capsys.readouterr().err


def test_cli_refuses_a_page_size_above_the_limit(capsys):
    assert cli.main(["--per-page", "101"]) == 2
    assert "a page size is between 1 and 100" in capsys.readouterr().err


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 10 and "FAIL" not in out


def test_cli_writes_the_walks_as_json(tmp_path, capsys):
    target = tmp_path / "pages.json"
    assert cli.main(["--json", str(target), "--quiet", "--insert"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["per_page"] == 4
    assert payload["offset"]["rows"] == 11
    assert payload["offset"]["unique"] == 10
    assert payload["offset"]["duplicates"] == ["delta"]
    assert payload["offset"]["shortfall"] == 1
    assert payload["offset"]["stopped"] == "empty"
    assert payload["cursor"]["rows"] == 10
    assert payload["cursor"]["duplicates"] == []
    assert payload["cursor"]["totals"] == [10, 11, 11]
    assert payload["cursor"]["stopped"] == "next"
    assert payload["legacy"]["error_rows"] == ["message",
                                               "documentation_url"]


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_missing_bundle_exits_two(tmp_path, capsys):
    assert cli.main(["--repos", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_bundle_with_no_arriving_line_exits_two(tmp_path, capsys):
    path = tmp_path / "repos.txt"
    path.write_bytes(b"101 alpha 12\n")
    assert cli.main(["--repos", str(path)]) == 2
    assert "names no arriving repository" in capsys.readouterr().err


def test_cli_a_malformed_bundle_exits_two(tmp_path, capsys):
    path = tmp_path / "repos.txt"
    path.write_bytes(b"101 alpha\n")
    assert cli.main(["--repos", str(path)]) == 2
    assert "is an id, a name and a star count" in capsys.readouterr().err
