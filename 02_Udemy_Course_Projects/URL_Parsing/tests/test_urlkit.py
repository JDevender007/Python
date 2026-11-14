"""Tests for URL_Parsing: the components, the grammar, the legacy slices, the CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                        # noqa: E402
from urlkit import (                                      # noqa: E402
    DATA_FILE,
    DEFAULT_PORTS,
    URL,
    URLParseError,
    host_kind,
    legacy_parts,
    load_urls,
    normalise,
    parse,
    percent_decode,
    query_params,
    run_demo,
)

KAGGLE = "https://www.kaggle.com/datasets"


@pytest.fixture()
def urls() -> list[str]:
    return load_urls()


# --------------------------------------------------------------------------- #
# percent_decode
# --------------------------------------------------------------------------- #
def test_percent_decode_of_plain_text():
    assert percent_decode("plain") == "plain"


def test_percent_decode_of_an_uppercase_escape():
    assert percent_decode("%41%42") == "AB"


def test_percent_decode_of_a_lowercase_escape():
    assert percent_decode("%61") == "a"


def test_percent_decode_of_a_space():
    assert percent_decode("%20") == " "


def test_percent_decode_of_a_plus():
    assert percent_decode("a+b") == "a b"


def test_percent_decode_of_a_literal_plus_escape():
    assert percent_decode("%2B") == "+"


def test_percent_decode_of_utf8_bytes():
    assert percent_decode("na%C3%AFve") == "na\u00efve"


def test_percent_decode_of_utf8_has_one_character():
    assert len(percent_decode("%C3%A9")) == 1


def test_percent_decode_of_multibyte_and_ascii_mixed():
    assert percent_decode("%E5%AF%BF%E5%8F%B8") == "\u5bff\u53f8"


def test_percent_decode_of_empty_text():
    assert percent_decode("") == ""


def test_percent_decode_of_a_percent_escape_of_a_percent():
    assert percent_decode("%25") == "%"


@pytest.mark.parametrize("bad", ["%zz", "%4", "%", "%G0", "%1", "%%41",
                                 "%41%"])
def test_percent_decode_refuses_broken_escapes(bad):
    with pytest.raises(URLParseError, match="percent escape"):
        percent_decode(bad)


def test_percent_decode_refuses_a_non_utf8_byte():
    with pytest.raises(URLParseError, match="not valid UTF-8"):
        percent_decode("%E9")


def test_percent_decode_refuses_non_text():
    with pytest.raises(URLParseError, match="must be a string"):
        percent_decode(3)


# --------------------------------------------------------------------------- #
# URL component validation
# --------------------------------------------------------------------------- #
def test_a_bare_url_renders_nothing():
    assert URL().to_url() == ""


def test_url_lowercases_its_scheme():
    assert URL(scheme="HTTPS").scheme == "https"


@pytest.mark.parametrize("bad", ["1http", "ht tp", "ht_tp", "", "-http"])
def test_url_refuses_an_invalid_scheme(bad):
    with pytest.raises(URLParseError, match="not a valid scheme"):
        URL(scheme=bad)


def test_url_refuses_a_non_string_scheme():
    with pytest.raises(URLParseError, match="scheme must be a string"):
        URL(scheme=7)


def test_url_accepts_scheme_characters_of_the_grammar():
    assert URL(scheme="svn+ssh-2").scheme == "svn+ssh-2"


def test_url_refuses_a_non_string_userinfo():
    with pytest.raises(URLParseError, match="userinfo"):
        URL(userinfo=7)


def test_url_refuses_a_non_string_host():
    with pytest.raises(URLParseError, match="host must be a string"):
        URL(host=None)


def test_url_refuses_a_non_string_path():
    with pytest.raises(URLParseError, match="path must be a string"):
        URL(path=None)


def test_url_refuses_a_non_string_query():
    with pytest.raises(URLParseError, match="query must be a string"):
        URL(query=None)


def test_url_refuses_a_non_string_fragment():
    with pytest.raises(URLParseError, match="fragment must be a string"):
        URL(fragment=None)


def test_url_accepts_the_lowest_port():
    assert URL(port=1).port == 1


def test_url_accepts_the_highest_port():
    assert URL(port=65535).port == 65535


@pytest.mark.parametrize("bad", [0, -1, 65536])
def test_url_refuses_an_out_of_range_port(bad):
    with pytest.raises(URLParseError, match="outside 1..65535"):
        URL(port=bad)


def test_url_refuses_a_boolean_port():
    with pytest.raises(URLParseError, match="port must be an integer"):
        URL(port=True)


def test_url_refuses_a_string_port():
    with pytest.raises(URLParseError, match="port must be an integer"):
        URL(port="80")


def test_url_is_frozen():
    with pytest.raises(Exception):
        URL(host="a").host = "b"                          # type: ignore[misc]


def test_url_to_dict_has_every_component():
    payload = parse(KAGGLE).to_dict()
    assert set(payload) == {"scheme", "userinfo", "host", "port", "path",
                            "query", "fragment", "has_authority"}
    assert payload["host"] == "www.kaggle.com"


def test_url_equality_is_by_value():
    assert parse(KAGGLE) == parse(KAGGLE)


# --------------------------------------------------------------------------- #
# authority and rendering
# --------------------------------------------------------------------------- #
def test_authority_of_a_plain_host():
    assert URL(host="example.com").authority == "example.com"


def test_authority_with_userinfo():
    assert URL(host="example.com", userinfo="u:p").authority == "u:p@example.com"


def test_authority_with_a_port():
    assert URL(host="example.com", port=8080).authority == "example.com:8080"


def test_authority_brackets_an_ipv6_host():
    assert URL(host="::1", port=80).authority == "[::1]:80"


def test_authority_of_an_empty_host():
    assert URL().authority == ""


def test_to_url_of_a_full_url():
    url = URL(scheme="https", host="example.com", port=8443, path="/a",
              query="b=1", fragment="c", has_authority=True)
    assert url.to_url() == "https://example.com:8443/a?b=1#c"


def test_to_url_without_an_authority():
    url = URL(scheme="mailto", path="user@example.com")
    assert url.to_url() == "mailto:user@example.com"


def test_to_url_drops_an_empty_query():
    url = URL(scheme="https", host="example.com", path="/",
              has_authority=True)
    assert url.to_url() == "https://example.com/"


def test_to_url_keeps_a_non_empty_query():
    url = URL(scheme="https", host="e.com", path="/", query="a=1",
              has_authority=True)
    assert url.to_url() == "https://e.com/?a=1"


def test_to_url_of_an_empty_authority_keeps_the_double_slash():
    url = URL(scheme="file", path="/C:/x.txt", has_authority=True)
    assert url.to_url() == "file:///C:/x.txt"


# --------------------------------------------------------------------------- #
# parse
# --------------------------------------------------------------------------- #
def test_parse_splits_a_simple_url():
    url = parse("https://www.kaggle.com/datasets")
    assert url.scheme == "https"
    assert url.host == "www.kaggle.com"
    assert url.path == "/datasets"
    assert url.port is None and url.userinfo is None
    assert url.has_authority is True


def test_parse_lowercases_only_the_scheme():
    url = parse("HTTPS://Example.COM/Path")
    assert url.scheme == "https"
    assert url.host == "Example.COM"
    assert url.path == "/Path"


def test_parse_of_a_bare_host_has_an_empty_path():
    assert parse("https://example.com").path == ""


def test_parse_of_a_trailing_slash_keeps_it():
    assert parse("https://example.com/").path == "/"


def test_parse_of_a_port():
    assert parse("http://localhost:8000/").port == 8000


def test_parse_of_an_empty_port_means_none():
    assert parse("http://example.com:/").port is None


def test_parse_of_userinfo():
    url = parse("https://user:pass@example.com:8443/path")
    assert url.userinfo == "user:pass"
    assert url.host == "example.com"
    assert url.port == 8443


def test_parse_of_empty_userinfo():
    assert parse("https://@example.com/").userinfo == ""


def test_parse_splits_userinfo_on_the_last_at():
    url = parse("https://user:p@ss@example.com/")
    assert url.userinfo == "user:p@ss"
    assert url.host == "example.com"


def test_parse_of_a_query():
    assert parse("https://e.com/s?a=1&b=2").query == "a=1&b=2"


def test_parse_of_a_fragment():
    assert parse("https://e.com/s#top").fragment == "top"


def test_parse_query_before_fragment():
    url = parse("https://e.com/s?a=1#top")
    assert url.query == "a=1" and url.fragment == "top"


def test_parse_keeps_a_hash_inside_the_fragment():
    assert parse("https://e.com/#a#b").fragment == "a#b"


def test_parse_keeps_an_ampersand_inside_the_query():
    assert parse("https://e.com/?a=b").query == "a=b"


def test_parse_keeps_a_question_mark_inside_the_query():
    assert parse("https://e.com/?a=b?c").query == "a=b?c"


def test_parse_of_an_ipv6_host():
    url = parse("https://[2001:db8::1]:8080/v1/items")
    assert url.host == "2001:db8::1"
    assert url.port == 8080
    assert url.path == "/v1/items"


def test_parse_of_an_ipv6_host_without_a_port():
    assert parse("http://[::1]/").port is None


def test_parse_of_an_ipv4_host():
    assert parse("http://192.168.0.1:8080/x").host == "192.168.0.1"


def test_parse_of_a_scheme_without_an_authority():
    url = parse("mailto:user@example.com")
    assert url.scheme == "mailto"
    assert url.host == ""
    assert url.path == "user@example.com"
    assert url.has_authority is False


def test_parse_of_a_scheme_and_a_relative_path():
    url = parse("http:example.com")
    assert url.scheme == "http" and url.path == "example.com"
    assert url.has_authority is False


def test_parse_of_a_protocol_relative_url():
    url = parse("//example.com/x")
    assert url.scheme is None
    assert url.host == "example.com"
    assert url.has_authority is True


def test_parse_of_a_file_url():
    url = parse("file:///C:/temp/report.txt")
    assert url.scheme == "file"
    assert url.host == ""
    assert url.path == "/C:/temp/report.txt"


def test_parse_keeps_a_double_slash_in_the_path():
    assert parse("https://e.com//double//slash").path == "//double//slash"


def test_parse_of_a_colon_after_a_slash_is_not_a_scheme():
    url = parse("/a:b")
    assert url.scheme is None and url.path == "/a:b"


def test_parse_of_an_empty_query_is_an_empty_string():
    assert parse("https://e.com/?").query == ""


@pytest.mark.parametrize("bad", ["", "   ", "https://e.com/a b",
                                 "https://e.com/a\tb", "https://e.com/a\nb"])
def test_parse_refuses_empty_and_whitespace(bad):
    with pytest.raises(URLParseError):
        parse(bad)


@pytest.mark.parametrize("bad", [None, 42, b"https://e.com/", ["x"]])
def test_parse_refuses_non_text(bad):
    with pytest.raises(URLParseError, match="must be a string"):
        parse(bad)


@pytest.mark.parametrize("bad", ["1http://example.com/",
                                 "ht~tp://example.com/",
                                 "://example.com/"])
def test_parse_refuses_a_bad_scheme(bad):
    with pytest.raises(URLParseError, match="scheme"):
        parse(bad)


@pytest.mark.parametrize("bad", ["http://example.com:0/",
                                 "http://example.com:65536/",
                                 "http://example.com:http/"])
def test_parse_refuses_a_bad_port(bad):
    with pytest.raises(URLParseError, match="port"):
        parse(bad)


def test_parse_refuses_an_unclosed_ipv6_bracket():
    with pytest.raises(URLParseError, match="closing"):
        parse("https://[::1/")


def test_parse_refuses_an_unbracketed_ipv6_host():
    with pytest.raises(URLParseError, match="brackets"):
        parse("http://::1/")


def test_parse_refuses_text_after_an_ipv6_bracket():
    with pytest.raises(URLParseError, match="after an IPv6 host"):
        parse("http://[::1]abc/")


# --------------------------------------------------------------------------- #
# query_params
# --------------------------------------------------------------------------- #
def test_query_params_of_no_query():
    assert query_params("https://e.com/") == []


def test_query_params_of_one_pair():
    assert query_params("https://e.com/?a=1") == [("a", "1")]


def test_query_params_of_two_pairs():
    assert query_params("https://e.com/?a=1&b=2") == [("a", "1"), ("b", "2")]


def test_query_params_decodes_both_sides():
    assert query_params("https://e.com/?a%20b=c%26d") == [("a b", "c&d")]


def test_query_params_turns_plus_into_space():
    assert query_params("https://e.com/?q=python+urls") == [("q", "python urls")]


def test_query_params_keeps_repeated_keys():
    assert query_params("https://e.com/?q=a&q=b") == [("q", "a"), ("q", "b")]


def test_query_params_keeps_a_valueless_key():
    assert query_params("https://e.com/?flag") == [("flag", "")]


def test_query_params_keeps_an_empty_value():
    assert query_params("https://e.com/?a=") == [("a", "")]


def test_query_params_skips_empty_pieces():
    assert query_params("https://e.com/?a=1&&b=2&") == [("a", "1"), ("b", "2")]


def test_query_params_accepts_a_parsed_url():
    assert query_params(parse("https://e.com/?a=1")) == [("a", "1")]


def test_query_params_decodes_utf8():
    assert query_params("https://e.com/?n=na%C3%AFve") == [("n", "na\u00efve")]


def test_query_params_refuses_a_broken_escape():
    with pytest.raises(URLParseError, match="percent escape"):
        query_params("https://e.com/?a=%zz")


def test_query_params_refuses_a_meaningless_argument():
    with pytest.raises(URLParseError, match="needs a URL"):
        query_params(3)


# --------------------------------------------------------------------------- #
# host_kind
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("host,expected", [
    ("example.com", "domain"),
    ("sub.domain.example.co.uk", "domain"),
    ("example.com.", "domain"),
    ("192.168.0.1", "ipv4"),
    ("2001:db8::1", "ipv6"),
    ("::1", "ipv6"),
    ("localhost", "localhost"),
    ("LOCALHOST", "localhost"),
    ("intranet", "single-label"),
    ("999.1.1.1", "single-label"),
    ("", "none"),
])
def test_host_kind(host, expected):
    assert host_kind(host) == expected


def test_host_kind_refuses_non_text():
    with pytest.raises(URLParseError, match="host must be a string"):
        host_kind(None)


# --------------------------------------------------------------------------- #
# normalise
# --------------------------------------------------------------------------- #
def test_normalise_lowercases_scheme_and_host():
    assert normalise("HTTPS://Example.COM/x") == "https://example.com/x"


def test_normalise_drops_the_https_default_port():
    assert normalise("https://example.com:443/secure") == \
        "https://example.com/secure"


def test_normalise_drops_the_http_default_port():
    assert normalise("http://example.com:80/plain") == "http://example.com/plain"


def test_normalise_drops_the_ftp_default_port():
    assert normalise("ftp://example.com:21/pub") == "ftp://example.com/pub"


def test_normalise_keeps_a_non_default_port():
    assert normalise("http://example.com:8080/x") == "http://example.com:8080/x"


def test_normalise_fills_an_empty_path_with_a_slash():
    assert normalise("HTTPS://Example.COM:443") == "https://example.com/"


def test_normalise_keeps_the_path_the_query_and_the_fragment():
    assert normalise("https://example.com/a?b=1#c") == \
        "https://example.com/a?b=1#c"


def test_normalise_does_not_lowercase_userinfo():
    assert normalise("HTTP://User:Pass@Example.COM:80/x") == \
        "http://User:Pass@example.com/x"


def test_normalise_keeps_an_ipv6_bracket():
    assert normalise("HTTP://[::1]:80/") == "http://[::1]/"


def test_normalise_accepts_a_parsed_url():
    assert normalise(parse("HTTPS://Example.COM")) == "https://example.com/"


def test_normalise_is_idempotent(urls):
    for raw in urls:
        once = normalise(raw)
        assert normalise(once) == once, raw


def test_normalise_refuses_a_meaningless_argument():
    with pytest.raises(URLParseError, match="needs a URL"):
        normalise(3)


def test_normalise_does_not_drop_80_for_an_unknown_scheme():
    assert normalise("gopher://example.com:80/x") == \
        "gopher://example.com:80/x"


def test_default_ports_are_the_three_well_known_ones():
    assert DEFAULT_PORTS == {"http": 80, "https": 443, "ftp": 21}


# --------------------------------------------------------------------------- #
# the legacy slices
# --------------------------------------------------------------------------- #
def test_legacy_parts_of_the_kaggle_url():
    assert legacy_parts(KAGGLE) == {"protocol": "https", "domain": "kaggle",
                                    "page": "/datasets"}


def test_legacy_parts_lose_www_and_the_tld():
    assert legacy_parts(KAGGLE)["domain"] == "kaggle"
    assert ".com" not in legacy_parts(KAGGLE)["domain"]


def test_legacy_parts_of_a_bare_host_drop_the_last_character():
    parts = legacy_parts("https://example.com")
    assert parts["domain"] == "co"
    assert parts["page"] == "m"


def test_legacy_parts_of_a_dotless_host_are_the_whole_string():
    parts = legacy_parts("http://localhost:8000/")
    assert parts["domain"] == "http://localhost:8000"
    assert parts["page"] == "/"


def test_legacy_parts_of_four_labels_keep_only_the_second():
    assert legacy_parts("https://sub.domain.example.co.uk/a")["domain"] == \
        "domain"


def test_legacy_parts_of_three_labels():
    url = "https://mail.google.com/mail"
    assert legacy_parts(url)["domain"] == "google"
    assert legacy_parts(url)["page"] == "/mail"


def test_legacy_parts_refuses_non_text():
    with pytest.raises(URLParseError, match="must be a string"):
        legacy_parts(3)


def test_the_fixed_parser_agrees_with_the_legacy_protocol():
    assert parse(KAGGLE).scheme == legacy_parts(KAGGLE)["protocol"]


def test_the_fixed_host_is_not_the_legacy_domain():
    assert parse(KAGGLE).host != legacy_parts(KAGGLE)["domain"]


# --------------------------------------------------------------------------- #
# the bundled list
# --------------------------------------------------------------------------- #
def test_the_bundled_list_has_twenty_urls(urls):
    assert len(urls) == 20


def test_the_bundled_list_has_no_duplicates(urls):
    assert len(set(urls)) == len(urls)


def test_the_bundled_list_starts_with_the_kaggle_url(urls):
    assert urls[0] == KAGGLE


def test_the_bundled_list_contains_an_ipv6_url(urls):
    assert any("[" in raw for raw in urls)


def test_the_bundled_list_contains_a_file_url(urls):
    assert any(raw.startswith("file://") for raw in urls)


def test_the_bundled_list_contains_a_repeated_query_key(urls):
    assert any("q=a%20b&q=" in raw for raw in urls)


def test_every_bundled_url_parses(urls):
    for raw in urls:
        assert parse(raw).to_url() == raw, raw


def test_every_bundled_url_agrees_with_urlsplit(urls):
    for raw in urls:
        ours = parse(raw)
        reference = urlsplit(raw)
        assert (ours.scheme or "") == reference.scheme.lower(), raw
        assert ours.host.casefold() == (reference.hostname or ""), raw
        assert ours.port == reference.port, raw
        assert ours.path == reference.path, raw
        assert ours.query == reference.query, raw
        assert ours.fragment == reference.fragment, raw


def test_every_bundled_url_agrees_with_parse_qsl(urls):
    from urllib.parse import parse_qsl
    for raw in urls:
        expected = parse_qsl(urlsplit(raw).query, keep_blank_values=True)
        assert query_params(parse(raw)) == expected, raw


def test_the_data_file_is_named_for_its_purpose():
    assert DATA_FILE.name == "urls.txt"
    assert DATA_FILE.parent.name == "data"


def test_load_urls_skips_comments_and_blank_lines(tmp_path):
    path = tmp_path / "u.txt"
    path.write_text("# a comment\n\nhttps://e.com/\n", encoding="utf-8")
    assert load_urls(path) == ["https://e.com/"]


def test_load_urls_strips_surrounding_space(tmp_path):
    path = tmp_path / "u.txt"
    path.write_text("  https://e.com/  \n", encoding="utf-8")
    assert load_urls(path) == ["https://e.com/"]


def test_load_urls_refuses_a_missing_file(tmp_path):
    with pytest.raises(URLParseError, match="not found"):
        load_urls(tmp_path / "nope.txt")


def test_load_urls_refuses_a_list_without_urls(tmp_path):
    path = tmp_path / "u.txt"
    path.write_text("# only a comment\n\n", encoding="utf-8")
    with pytest.raises(URLParseError, match="has no URLs"):
        load_urls(path)


# --------------------------------------------------------------------------- #
# demo
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


def test_demo_shows_the_legacy_kaggle_domain(capsys):
    run_demo()
    assert "'kaggle'" in capsys.readouterr().out


def test_demo_shows_the_bare_host_slices(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "'co'" in out and "'m'" in out


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


def test_cli_lists_the_bundled_urls(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "20 URL(s)" in out
    assert "www.kaggle.com" in out


def test_cli_parse_shows_the_components(capsys):
    assert cli.main(["--parse", "https://user@example.com:8080/a?b=1#c"]) == 0
    out = capsys.readouterr().out
    assert "user" in out and "example.com" in out and "8080" in out
    assert "(domain)" in out


def test_cli_parse_reports_the_host_kind(capsys):
    assert cli.main(["--parse", "http://192.168.0.1/"]) == 0
    assert "(ipv4)" in capsys.readouterr().out


def test_cli_parse_of_bad_input_exits_two(capsys):
    assert cli.main(["--parse", "not a url"]) == 2
    assert "whitespace" in capsys.readouterr().err


def test_cli_normalise(capsys):
    assert cli.main(["--normalise", "HTTPS://Example.COM:443"]) == 0
    out = capsys.readouterr().out
    assert "https://example.com/" in out


def test_cli_normalise_says_when_nothing_changed(capsys):
    assert cli.main(["--normalise", "https://example.com/"]) == 0
    assert "already normalised" in capsys.readouterr().out


def test_cli_params_lists_decoded_pairs(capsys):
    assert cli.main(["--params", "https://e.com/?a%20b=c%26d"]) == 0
    out = capsys.readouterr().out
    assert "a b = c&d" in out
    assert "1 parameter(s)" in out


def test_cli_params_of_no_query(capsys):
    assert cli.main(["--params", "https://e.com/"]) == 0
    out = capsys.readouterr().out
    assert "(no query parameters)" in out


def test_cli_legacy_mode(capsys):
    assert cli.main(["--legacy", KAGGLE]) == 0
    out = capsys.readouterr().out
    assert "'kaggle'" in out
    assert "the legacy domain is not the host" in out


def test_cli_json_parse(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--parse", "https://e.com/a?b=1#c",
                     "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "parse"
    assert payload["components"]["host"] == "e.com"
    assert payload["host_kind"] == "domain"
    assert payload["rebuilt"] == "https://e.com/a?b=1#c"


def test_cli_json_list(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["mode"] == "list"
    assert payload["count"] == 20


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "nope.txt"]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--parse", "https://e.com/", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
