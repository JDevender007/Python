"""Tests for Job_Listing_Scraper: a link is a structure, resolved by its parts,
confined by host equality, and fetched once whatever its fragment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                           # noqa: E402
import urls as module                                        # noqa: E402
from urls import (                                           # noqa: E402
    BASE_URL,
    DOCUMENT_SCHEMES,
    LEGACY_JOIN,
    LEGACY_VALID,
    LINKS_FILE,
    Link,
    Page,
    Url,
    UrlError,
    audit,
    crawl,
    dedupe,
    legacy_join,
    legacy_valid,
    parse_rows,
    parse_url,
    problems,
    read_page,
    resolve,
    run_demo,
    same_site,
)

BASE = parse_url(BASE_URL)


def a_page() -> Page:
    return read_page()


def a_url(text: str = "https://jobs.example/jobs/42") -> Url:
    return parse_url(text)


def raw_url(scheme: str = "https", host: str = "jobs.example",
            path: str = "/jobs/42", query: str = "",
            fragment: str = "") -> Url:
    """A Url with the validation bypassed, so an audit can disagree with it."""
    url = object.__new__(Url)
    for name, value in (("scheme", scheme), ("host", host), ("path", path),
                        ("query", query), ("fragment", fragment)):
        object.__setattr__(url, name, value)
    return url


class BrokenPrinting(Url):
    """A link that prints itself as a different address."""

    def __str__(self) -> str:
        return "https://jobs.example/jobs/99"


def a_link(href: str = "/jobs/42", label: str = "Data Engineer",
           url: Url | None = None, note: str = "") -> Link:
    return Link(href, label, a_url() if url is None else url, note)


# --------------------------------------------------------------------------- #
# A URL, in parts
# --------------------------------------------------------------------------- #
def test_a_url_holds_its_five_parts():
    url = a_url("https://jobs.example/jobs/42?page=2#apply")
    assert (url.scheme, url.host, url.path, url.query, url.fragment) == \
        ("https", "jobs.example", "/jobs/42", "page=2", "apply")


def test_a_url_prints_itself_back_together():
    assert str(a_url()) == "https://jobs.example/jobs/42"


def test_a_url_with_no_path_prints_the_root():
    assert str(a_url("https://jobs.example")) == "https://jobs.example/"


def test_a_url_with_a_fragment_prints_it():
    assert str(a_url("https://jobs.example/jobs/44#apply")).endswith("#apply")


def test_without_fragment_drops_the_fragment():
    url = a_url("https://jobs.example/jobs/44#apply").without_fragment()
    assert url.fragment == "" and str(url) == "https://jobs.example/jobs/44"


def test_a_document_scheme_is_http_or_https():
    assert DOCUMENT_SCHEMES == ("http", "https")


def test_a_url_refuses_a_scheme_that_is_not_a_document():
    with pytest.raises(UrlError, match="only http and https"):
        Url("ftp", "jobs.example")


def test_a_url_keeps_the_scheme_it_was_given_in_lower_case():
    assert a_url("HTTPS://jobs.example/jobs/42").scheme == "https"


def test_a_url_refuses_an_empty_host():
    with pytest.raises(UrlError, match="a link needs a host"):
        Url("https", "")


def test_a_url_refuses_a_host_that_is_not_text():
    with pytest.raises(UrlError, match="a link needs a host"):
        Url("https", 7)


def test_a_url_refuses_an_upper_case_host():
    with pytest.raises(UrlError, match="written in lower case"):
        Url("https", "Jobs.Example")


def test_a_url_refuses_a_host_naming_a_user():
    with pytest.raises(UrlError, match="cannot name a user"):
        Url("https", "user@jobs.example")


def test_a_url_refuses_a_path_that_does_not_start_at_the_root():
    with pytest.raises(UrlError, match="a path starts at the root"):
        Url("https", "jobs.example", "jobs/42")


def test_a_url_refuses_a_space_in_the_path():
    with pytest.raises(UrlError, match="the path cannot hold ' '"):
        Url("https", "jobs.example", "/a b")


def test_a_url_refuses_a_newline_in_the_query():
    with pytest.raises(UrlError, match="cannot hold"):
        Url("https", "jobs.example", "/x", "a=1\nb=2")


def test_a_url_refuses_a_query_that_is_not_text():
    with pytest.raises(UrlError, match="the query is text"):
        Url("https", "jobs.example", "/x", 5)


def test_a_url_refuses_a_fragment_that_is_not_text():
    with pytest.raises(UrlError, match="the fragment is text"):
        Url("https", "jobs.example", "/x", "", 5)


def test_a_job_link_is_a_numeric_id_under_jobs():
    assert a_url().is_job() is True


def test_a_listing_link_is_not_a_job_link():
    assert a_url(BASE_URL).is_job() is False


def test_a_job_id_is_read_as_a_whole_number():
    assert a_url().job_id() == 42


def test_a_listing_link_has_no_job_id():
    assert a_url(BASE_URL).job_id() is None


def test_a_job_path_with_a_sub_page_is_not_a_job():
    assert a_url("https://jobs.example/jobs/42/apply").job_id() is None


def test_a_job_path_with_a_word_is_not_a_job():
    assert a_url("https://jobs.example/jobs/analyst").job_id() is None


def test_the_key_ignores_the_fragment():
    plain = a_url("https://jobs.example/jobs/42")
    anchored = a_url("https://jobs.example/jobs/42#apply")
    assert plain.key() == anchored.key()


def test_the_key_orders_the_query_fields():
    left = a_url("https://jobs.example/jobs/42?b=2&a=1")
    right = a_url("https://jobs.example/jobs/42?a=1&b=2")
    assert left.key() == right.key()


def test_the_key_separates_two_different_queries():
    left = a_url("https://jobs.example/jobs/42?page=1")
    right = a_url("https://jobs.example/jobs/42?page=2")
    assert left.key() != right.key()


def test_two_urls_with_one_address_are_equal():
    assert a_url() == a_url()


# --------------------------------------------------------------------------- #
# Reading an absolute URL
# --------------------------------------------------------------------------- #
def test_parse_url_reads_an_absolute_link():
    url = a_url()
    assert (url.host, url.path) == ("jobs.example", "/jobs/42")


def test_parse_url_lower_cases_the_host():
    assert parse_url("https://JOBS.EXAMPLE/jobs/42").host == "jobs.example"


def test_parse_url_drops_a_trailing_dot_from_the_host():
    assert parse_url("https://jobs.example./jobs/42").host == "jobs.example"


def test_parse_url_drops_a_numeric_port():
    assert parse_url("https://jobs.example:8080/jobs/42").host == \
        "jobs.example"


def test_parse_url_keeps_a_query():
    assert parse_url("https://jobs.example/jobs?page=2").query == "page=2"


def test_parse_url_keeps_a_fragment():
    assert parse_url("https://jobs.example/jobs#top").fragment == "top"


def test_parse_url_gives_a_bare_host_the_root_path():
    assert parse_url("https://jobs.example").path == "/"


def test_parse_url_trims_surrounding_space():
    assert parse_url("  https://jobs.example/jobs/42  ") == a_url()


def test_parse_url_refuses_an_empty_text():
    with pytest.raises(UrlError, match="the link text is empty"):
        parse_url("   ")


def test_parse_url_refuses_a_relative_reference():
    with pytest.raises(UrlError, match="is relative"):
        parse_url("jobs/42")


def test_parse_url_refuses_a_link_with_no_scheme_at_all():
    with pytest.raises(UrlError, match="is relative"):
        parse_url("//jobs.example/jobs/42")


def test_parse_url_refuses_a_scheme_that_is_not_a_document():
    with pytest.raises(UrlError, match="not a document link"):
        parse_url("javascript:void(0)")


def test_parse_url_refuses_a_mail_address():
    with pytest.raises(UrlError, match="not a document link"):
        parse_url("mailto:jobs@example.test")


def test_parse_url_refuses_a_space():
    with pytest.raises(UrlError, match="a link cannot hold ' '"):
        parse_url("https://jobs.example/a b")


def test_parse_url_refuses_a_link_that_names_a_user():
    with pytest.raises(UrlError, match="cannot name a user"):
        parse_url("https://user:pw@jobs.example/jobs/42")


def test_parse_url_refuses_a_link_that_names_no_host():
    with pytest.raises(UrlError, match="names no host"):
        parse_url("https:///jobs/42")


def test_parse_url_refuses_something_that_is_not_text():
    with pytest.raises(UrlError, match="a link is text"):
        parse_url(None)


# --------------------------------------------------------------------------- #
# Resolving a reference
# --------------------------------------------------------------------------- #
def test_an_absolute_path_keeps_the_host():
    assert str(resolve(BASE, "/jobs/42")) == "https://jobs.example/jobs/42"


def test_a_relative_reference_resolves_against_the_directory():
    assert str(resolve(BASE, "43")) == "https://jobs.example/jobs/43"


def test_a_relative_reference_does_not_glue_onto_the_file_name():
    assert str(resolve(BASE, "43")) != "https://jobs.example/jobs/list.html43"


def test_a_dot_dot_removes_one_segment():
    assert str(resolve(BASE, "../jobs/43")) == "https://jobs.example/jobs/43"


def test_a_dot_keeps_the_directory():
    assert str(resolve(BASE, "./43")) == "https://jobs.example/jobs/43"


def test_a_deep_dot_dot_climbs_to_the_root_and_stops():
    assert str(resolve(BASE, "../../../../x")) == "https://jobs.example/x"


def test_a_protocol_relative_link_inherits_the_scheme():
    assert str(resolve(BASE, "//jobs.example/jobs/45")) == \
        "https://jobs.example/jobs/45"


def test_a_protocol_relative_link_may_name_another_host():
    assert resolve(BASE, "//other.test/x").host == "other.test"


def test_an_absolute_link_with_a_scheme_is_used_as_it_stands():
    assert str(resolve(BASE, "https://jobs.example/jobs/44#apply")) == \
        "https://jobs.example/jobs/44#apply"


def test_an_absolute_link_may_leave_the_site():
    assert same_site(resolve(BASE, "https://other.test/x"), BASE) is False


def test_a_bare_fragment_names_the_same_page():
    url = resolve(BASE, "#top")
    assert (url.path, url.query, url.fragment) == ("/jobs/list.html", "",
                                                   "top")


def test_a_query_with_no_path_keeps_the_path():
    url = resolve(BASE, "?page=2")
    assert (url.path, url.query) == ("/jobs/list.html", "page=2")


def test_a_reference_with_a_path_takes_its_own_query():
    url = resolve(BASE, "43?ref=list")
    assert (url.path, url.query) == ("/jobs/43", "ref=list")


def test_a_reference_with_a_path_and_no_query_ends_the_base_query():
    base = a_url("https://jobs.example/jobs/list.html?page=2")
    url = resolve(base, "/jobs/43")
    assert url.query == ""


def test_an_empty_reference_is_refused_rather_than_the_base():
    with pytest.raises(UrlError, match="the link text is empty"):
        resolve(BASE, "   ")


def test_resolve_refuses_a_space():
    with pytest.raises(UrlError, match="a link cannot hold ' '"):
        resolve(BASE, "a b")


def test_resolve_refuses_a_scheme_that_is_not_a_document():
    with pytest.raises(UrlError, match="not a document link"):
        resolve(BASE, "javascript:void(0)")


def test_resolve_refuses_an_address():
    with pytest.raises(UrlError, match="not a document link"):
        resolve(BASE, "mailto:jobs@example.test")


def test_resolve_refuses_something_that_is_not_text():
    with pytest.raises(UrlError, match="a link is text"):
        resolve(BASE, 42)


def test_resolve_trims_surrounding_space():
    assert str(resolve(BASE, "  43  ")) == "https://jobs.example/jobs/43"


def test_resolve_keeps_the_fragment_as_written():
    assert resolve(BASE, "/jobs/42#Apply").fragment == "Apply"


def test_a_path_with_a_trailing_slash_stays_a_directory():
    assert str(resolve(BASE, "sub/")) == "https://jobs.example/jobs/sub/"


def test_every_curious_href_that_resolves_prints_and_parses_back():
    for href, _ in module.CURIOUS:
        try:
            url = resolve(BASE, href)
        except UrlError:
            continue
        assert parse_url(str(url)) == url


# --------------------------------------------------------------------------- #
# Folding dots
# --------------------------------------------------------------------------- #
def test_remove_dots_folds_one_dot_dot():
    assert module._remove_dots("/jobs/../x") == "/x"


def test_remove_dots_keeps_a_plain_path():
    assert module._remove_dots("/jobs/42") == "/jobs/42"


def test_remove_dots_drops_single_dots():
    assert module._remove_dots("/jobs/./42") == "/jobs/42"


def test_remove_dots_keeps_a_trailing_slash():
    assert module._remove_dots("/jobs/../x/") == "/x/"


def test_remove_dots_at_the_root_stays_the_root():
    assert module._remove_dots("/..") == "/"


def test_remove_dots_never_climbs_above_the_root():
    assert module._remove_dots("/a/../../b") == "/b"


def test_join_path_with_a_rooted_reference_replaces_the_path():
    assert module._join_path("/a/b/c", "/d") == "/d"


def test_join_path_with_a_relative_reference_appends_to_the_directory():
    assert module._join_path("/a/b/c", "d") == "/a/b/d"


def test_join_path_on_a_root_base_keeps_the_root():
    assert module._join_path("/", "d") == "/d"


# --------------------------------------------------------------------------- #
# Confinement and deduplication
# --------------------------------------------------------------------------- #
def test_two_links_on_one_host_are_on_the_same_site():
    assert same_site(a_url(), a_url("https://jobs.example/jobs/99")) is True


def test_a_subdomain_is_a_foreign_site():
    assert same_site(a_url(), a_url("https://api.jobs.example/jobs/99")) \
        is False


def test_a_lookalike_host_is_a_foreign_site():
    lookalike = a_url("https://jobs.example.com.evil.test/jobs/99")
    assert same_site(lookalike, a_url()) is False


def test_a_lookalike_host_starts_with_the_real_host():
    lookalike = a_url("https://jobs.example.com.evil.test/jobs/99")
    assert lookalike.host.startswith(a_url().host) is True


def test_a_host_that_contains_the_real_one_is_foreign():
    assert same_site(a_url(), a_url("https://evil.test/jobs.example")) \
        is False


def test_dedupe_keeps_the_first_of_a_repeat():
    first = a_url("https://jobs.example/jobs/42")
    second = a_url("https://jobs.example/jobs/42#apply")
    kept = dedupe((first, second))
    assert kept == (first,)


def test_dedupe_keeps_the_order_it_found():
    left = a_url("https://jobs.example/jobs/42")
    right = a_url("https://jobs.example/jobs/43")
    assert dedupe((right, left)) == (right, left)


def test_dedupe_keeps_two_queries_apart():
    left = a_url("https://jobs.example/jobs/list.html?page=1")
    right = a_url("https://jobs.example/jobs/list.html?page=2")
    assert dedupe((left, right)) == (left, right)


def test_dedupe_of_nothing_is_nothing():
    assert dedupe(()) == ()


def test_dedupe_drops_every_repeat_after_the_first():
    url = a_url()
    assert dedupe((url, url, url)) == (url,)


def test_dedupe_ignores_the_order_of_the_query_fields():
    left = a_url("https://jobs.example/jobs/42?b=2&a=1")
    right = a_url("https://jobs.example/jobs/42?a=1&b=2")
    assert dedupe((left, right)) == (left,)


# --------------------------------------------------------------------------- #
# The legacy pair
# --------------------------------------------------------------------------- #
def test_the_legacy_validator_accepts_a_normal_link():
    assert legacy_valid("https://jobs.example/jobs/42") is True


def test_the_legacy_validator_accepts_a_lookalike_host():
    assert legacy_valid("https://jobs.example.com.evil.test/jobs/99") is True


def test_the_legacy_validator_accepts_a_space_because_it_never_looks():
    assert legacy_valid("https://jobs.example/a b") is True


def test_the_legacy_validator_refuses_a_relative_reference():
    assert legacy_valid("/jobs/42") is False


def test_the_legacy_validator_refuses_a_script_link():
    assert legacy_valid("javascript:void(0)") is False


def test_the_legacy_validator_refuses_something_that_is_not_text():
    assert legacy_valid(None) is False


def test_the_legacy_join_glues_two_strings():
    assert legacy_join("https://jobs.example/jobs/list.html", "43") == \
        "https://jobs.example/jobs/list.html43"


def test_the_legacy_join_builds_a_path_that_never_existed():
    glued = legacy_join(BASE_URL, "43")
    assert glued != str(resolve(BASE, "43"))


def test_the_legacy_join_doubles_a_slash_on_an_absolute_path():
    assert legacy_join("https://jobs.example/jobs/list.html", "/jobs/42") == \
        "https://jobs.example/jobs/list.html/jobs/42"


def test_the_legacy_lines_are_pinned():
    assert LEGACY_VALID.startswith("parsed = urlparse(url)")
    assert LEGACY_JOIN == "return base + href"


# --------------------------------------------------------------------------- #
# Links and a page
# --------------------------------------------------------------------------- #
def test_a_link_prints_its_address_and_label():
    assert a_link().line() == \
        f"{'https://jobs.example/jobs/42':<46} Data Engineer"


def test_a_refused_link_prints_the_word_refused():
    link = Link("javascript:void(0)", "Apply", None, "no document")
    assert link.line().startswith("refused")


def test_a_note_line_prints_the_href_and_the_reason():
    link = Link("javascript:void(0)", "Apply", None, "not a document link")
    assert link.note_line() == \
        f"{'javascript:void(0)'!r:<40} not a document link"


def test_a_page_cannot_be_empty():
    with pytest.raises(UrlError, match="at least one link"):
        Page(BASE, ())


def test_a_page_reads_its_anchors_from_the_bundled_file():
    assert len(a_page().links) == 9


def test_the_page_base_is_the_address_it_was_printed_at():
    assert str(a_page().base) == BASE_URL


def test_seven_of_the_anchors_resolve_on_site():
    assert len(a_page().urls()) == 7


def test_one_anchor_leaves_the_site():
    assert len(a_page().offsite()) == 1


def test_the_offsite_link_is_the_lookalike_host():
    assert a_page().offsite()[0].href == \
        "https://jobs.example.com.evil.test/jobs/99"


def test_one_anchor_is_refused():
    assert len(a_page().refused()) == 1


def test_the_refused_anchor_is_the_script_link():
    assert a_page().refused()[0].href == "javascript:void(0)"


def test_the_refusal_carries_the_reason():
    assert "not a document link" in a_page().refused()[0].note


def test_the_crawl_deduplicates_the_fragment_repeat():
    assert len(a_page().crawl()) == 6


def test_the_crawl_keeps_the_first_of_the_two_job_42_anchors():
    jobs = [str(url) for url in a_page().crawl() if url.job_id() == 42]
    assert jobs == ["https://jobs.example/jobs/42"]


def test_the_crawl_holds_no_duplicate_key():
    keys = [url.key() for url in a_page().crawl()]
    assert len(set(keys)) == len(keys)


def test_every_crawled_link_is_on_the_site():
    assert all(same_site(url, BASE) for url in a_page().crawl())


def test_the_page_names_four_jobs():
    assert [url.job_id() for url in a_page().jobs()] == [42, 43, 44, 45]


def test_the_job_links_are_unique():
    ids = [url.job_id() for url in a_page().jobs()]
    assert len(set(ids)) == len(ids)


def test_a_query_string_does_not_make_a_second_job():
    page = crawl(BASE, (("/jobs/42", "a"), ("/jobs/42?ref=x", "b"),
                        ("43", "c")))
    assert [url.job_id() for url in page.jobs()] == [42, 43]


def test_the_listing_page_is_in_the_crawl_but_is_not_a_job():
    page = a_page()
    assert any(url.path == "/jobs/list.html" for url in page.crawl())
    assert all(url.is_job() for url in page.jobs())


def test_crawl_keeps_an_off_site_link_out_of_urls():
    page = crawl(BASE, (("https://other.test/x", "away"),))
    assert page.urls() == () and len(page.offsite()) == 1


def test_crawl_keeps_a_refusal_as_a_note_not_an_exception():
    page = crawl(BASE, (("javascript:void(0)", "Apply"),))
    assert page.links[0].url is None
    assert "not a document link" in page.links[0].note


def test_crawl_resolves_every_row_against_the_same_base():
    page = crawl(BASE, (("43", "a"), ("/jobs/44", "b")))
    assert [str(url) for url in page.urls()] == [
        "https://jobs.example/jobs/43", "https://jobs.example/jobs/44"]


# --------------------------------------------------------------------------- #
# Reading the file
# --------------------------------------------------------------------------- #
def test_parse_rows_reads_an_href_and_a_label():
    assert parse_rows("/jobs/42\tData Engineer\n") == \
        (("/jobs/42", "Data Engineer"),)


def test_parse_rows_trims_both_fields():
    assert parse_rows("  43 \t Analyst  \n") == (("43", "Analyst"),)


def test_parse_rows_skips_a_comment():
    assert len(parse_rows("; a note\n43\tAnalyst\n")) == 1


def test_parse_rows_skips_a_blank_line():
    assert len(parse_rows("\n\n43\tAnalyst\n\n")) == 1


def test_parse_rows_reads_windows_line_endings():
    assert len(parse_rows("43\ta\r\n44\tb\r\n")) == 2


def test_parse_rows_keeps_a_tab_inside_the_label():
    assert parse_rows("43\ta\tb\n")[0][1] == "a\tb"


def test_parse_rows_refuses_a_line_without_a_tab():
    with pytest.raises(UrlError, match="line 1: expected an href"):
        parse_rows("43 Analyst\n")


def test_parse_rows_numbers_the_bad_line():
    with pytest.raises(UrlError, match="line 3: expected an href"):
        parse_rows("43\ta\n44\tb\n45 c\n")


def test_parse_rows_refuses_a_page_with_no_rows():
    with pytest.raises(UrlError, match="holds no links"):
        parse_rows("; nothing\n")


def test_the_bundled_file_holds_nine_rows():
    text = LINKS_FILE.read_text(encoding="utf-8")
    rows = [line for line in text.split("\n")
            if line.strip() and not line.lstrip().startswith(";")]
    assert len(rows) == 9


def test_a_missing_page_is_refused(tmp_path):
    with pytest.raises(UrlError, match="file not found"):
        module.read_page(tmp_path / "nope.txt")


def test_read_page_accepts_its_own_base(tmp_path):
    path = tmp_path / "links.txt"
    path.write_bytes(b"43\tAnalyst\n")
    page = read_page(path, "https://other.test/list.html")
    assert str(page.urls()[0]) == "https://other.test/43"


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every link that resolved is an http or https document",
    "every crawled link prints and parses back to the same parts",
    "the legacy validator accepts a lookalike host",
    "the site test is a whole host, not a substring",
    "the legacy splice of base and href builds a path that never existed",
    "a fragment never makes two links different",
    "every crawled link is one the site test accepts",
    "deduplication keeps the first of a repeated link",
    "every link that could not be resolved carries the reason",
]


def test_the_audit_holds_nine_named_checks():
    assert [name for name, _ in audit(a_page())] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_page():
    assert problems(audit(a_page())) == []


def test_the_audit_is_repeatable():
    assert audit(a_page()) == audit(a_page())


def test_the_audit_catches_a_link_that_is_not_a_document():
    page = Page(BASE, (a_link(url=raw_url(scheme="ftp")),))
    assert CHECK_NAMES[0] in problems(audit(page))


def test_the_audit_does_not_raise_on_a_broken_scheme():
    page = Page(BASE, (a_link(url=raw_url(scheme="ftp")),))
    assert len(audit(page)) == 9


def test_the_audit_catches_a_link_that_prints_something_else():
    page = Page(BASE, (a_link(url=BrokenPrinting("https", "jobs.example",
                                                 "/jobs/42")),))
    assert CHECK_NAMES[1] in problems(audit(page))


def test_the_audit_catches_a_base_that_is_the_lookalike_itself():
    base = parse_url("https://jobs.example.com.evil.test/jobs/list.html")
    page = Page(base, (a_link(url=base),))
    assert CHECK_NAMES[2] in problems(audit(page))


def test_the_audit_catches_a_substring_site_test():
    page = a_page()
    assert CHECK_NAMES[3] in problems(
        audit(page, same=lambda left, right: right.host in left.host))


def test_the_audit_catches_a_site_test_that_accepts_nothing():
    assert CHECK_NAMES[6] in problems(audit(a_page(),
                                            same=lambda left, right: False))


def test_the_audit_catches_a_page_with_no_repeat_to_drop():
    page = Page(BASE, (a_link(),))
    assert CHECK_NAMES[7] in problems(audit(page))


def test_the_audit_catches_a_refusal_with_no_reason():
    page = Page(BASE, (Link("javascript:void(0)", "Apply", None, ""),))
    assert CHECK_NAMES[8] in problems(audit(page))


def test_the_audit_catches_a_page_with_no_refusal_at_all():
    page = Page(BASE, (a_link(),))
    assert CHECK_NAMES[8] in problems(audit(page))


def test_seven_of_the_nine_checks_have_a_negative_control():
    """Checks 5 and 6 pin the two legacy lines; they cannot be broken."""
    lookalike_base = parse_url(
        "https://jobs.example.com.evil.test/jobs/list.html")
    broken = [
        audit(Page(BASE, (a_link(url=raw_url(scheme="ftp")),))),
        audit(Page(BASE, (a_link(url=BrokenPrinting(
            "https", "jobs.example", "/jobs/42")),))),
        audit(Page(lookalike_base, (a_link(url=lookalike_base),))),
        audit(a_page(), same=lambda left, right: right.host in left.host),
        audit(a_page(), same=lambda left, right: True),
        audit(Page(BASE, (a_link(),))),
        audit(Page(BASE, (Link("javascript:void(0)", "Apply", None, ""),))),
    ]
    caught = {name for checks in broken for name in problems(checks)}
    assert len(caught) == 7


# --------------------------------------------------------------------------- #
# The curious hrefs
# --------------------------------------------------------------------------- #
def test_the_curious_hrefs_are_all_ascii():
    assert all(ord(character) < 128
               for href, _ in module.CURIOUS for character in href)


def test_the_curious_table_holds_twelve_hrefs():
    assert len(module.CURIOUS) == 12


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


def test_demo_shows_the_legacy_pair(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert 'parsed = urlparse(url)' in out
    assert "return base + href" in out


def test_demo_shows_the_splice_and_the_resolution(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "= https://jobs.example/jobs/list.html43" in out
    assert "= https://jobs.example/jobs/43" in out


def test_demo_shows_the_four_job_ids(capsys):
    run_demo()
    assert "job ids: 42, 43, 44, 45" in capsys.readouterr().out


def test_demo_shows_the_crawl_counts(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "9 anchors, 1 refused, 1 off site, 7 on site, 6 unique" in out


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


def test_cli_reads_the_bundled_page(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "9 anchor(s) on https://jobs.example/jobs/list.html" in out
    assert "7 on site, 6 unique" in out
    assert "job ids: 42, 43, 44, 45" in out


def test_cli_resolves_one_href(capsys):
    assert cli.main(["--resolve", "43"]) == 0
    out = capsys.readouterr().out
    assert "'43' -> https://jobs.example/jobs/43  (on site)" in out
    assert "list.html43" in out


def test_cli_resolves_several_hrefs(capsys):
    assert cli.main(["--resolve", "/jobs/42", "//jobs.example/jobs/45"]) == 0
    out = capsys.readouterr().out
    assert "https://jobs.example/jobs/42" in out
    assert "https://jobs.example/jobs/45" in out


def test_cli_marks_an_offsite_href(capsys):
    assert cli.main(["--resolve", "https://other.test/x"]) == 0
    assert "(OFF SITE)" in capsys.readouterr().out


def test_cli_a_href_it_cannot_resolve_exits_two(capsys):
    assert cli.main(["--resolve", "javascript:void(0)"]) == 2
    assert "not a document link" in capsys.readouterr().err


def test_cli_keeps_going_after_a_bad_href(capsys):
    assert cli.main(["--resolve", "43", "javascript:void(0)"]) == 2
    captured = capsys.readouterr()
    assert "jobs/43" in captured.out and "not a document" in captured.err


def test_cli_a_base_it_cannot_read_exits_two(capsys):
    assert cli.main(["--base", "/nope"]) == 2
    assert "is relative" in capsys.readouterr().err


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_writes_the_crawl_as_json(tmp_path, capsys):
    target = tmp_path / "crawl.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["base"] == BASE_URL
    assert payload["jobs"] == [
        {"id": 42, "url": "https://jobs.example/jobs/42"},
        {"id": 43, "url": "https://jobs.example/jobs/43"},
        {"id": 44, "url": "https://jobs.example/jobs/44#apply"},
        {"id": 45, "url": "https://jobs.example/jobs/45"},
    ]
    assert payload["duplicates"] == 1
    assert payload["links"][4]["legacy_valid"] is True
    assert payload["links"][5]["url"] is None


def test_cli_json_records_the_legacy_verdict_on_the_offsite_link(tmp_path,
                                                                capsys):
    target = tmp_path / "crawl.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    lookalike = payload["links"][4]
    assert lookalike["legacy_valid"] is True
    assert lookalike["url"] not in payload["crawl"]


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_a_missing_page_exits_two(tmp_path, capsys):
    assert cli.main(["--links", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_malformed_page_exits_two(tmp_path, capsys):
    path = tmp_path / "links.txt"
    path.write_bytes(b"43 Analyst\n")
    assert cli.main(["--links", str(path)]) == 2
    assert "expected an href" in capsys.readouterr().err
