"""Tests for the hash-cracking lab: verdicts, salts and counted work."""

from __future__ import annotations

import hashlib
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import cracker  # noqa: E402
import main as cli  # noqa: E402
from cracker import (  # noqa: E402
    ALGORITHMS,
    LEGACY_ATTEMPTS,
    LEGACY_SALT,
    LEGACY_VERDICT,
    MODES,
    PIN_KEYSPACE,
    Search,
    Target,
    CrackerError,
    algorithm_of,
    audit,
    build_targets,
    candidates_for,
    check_digest,
    digest_of,
    digest_with_salt,
    distinct_words,
    divide_half_up,
    format_bp,
    legacy_attempts,
    legacy_search,
    legacy_verdict,
    load_targets,
    load_words,
    measure,
    mode_of,
    pin_candidates,
    read_lines,
    render_searches,
    report,
    run_demo,
    search,
)

SUNSHINE = "a941a4c4fd0c01cddef61b8be963bf4c1e2b0811c037ce3f1835fddf6ef6c223"
MICHAEL_MD5 = "0acf4539a14b3aa27deeb4cbdf6e989f"


def target(
    label: str = "alice",
    algorithm: str = "sha256",
    salt: str = "",
    digest: str = SUNSHINE,
    mode: str = "wordlist",
) -> Target:
    return Target(label=label, algorithm=algorithm, salt=salt, digest=digest, mode=mode)


def row(label: str = "alice", algorithm: str = "sha256", salt: str = "",
        digest: str = SUNSHINE, mode: str = "wordlist") -> dict[str, str]:
    return {
        "label": label,
        "algorithm": algorithm,
        "salt": salt,
        "digest": digest,
        "mode": mode,
    }


# --------------------------------------------------------------------------- #
# arithmetic and formatting
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "top,bottom,expected",
    [(10_000 * 10_000, 10_000, 10_000), (5, 2, 3), (1, 3, 0), (2, 3, 1),
     (-5, 2, -3), (0, 7, 0)],
)
def test_divide_half_up(top, bottom, expected):
    assert divide_half_up(top, bottom) == expected


@pytest.mark.parametrize("bottom", [0, -1])
def test_divide_half_up_refuses_bad_denominators(bottom):
    with pytest.raises(CrackerError, match="denominator must be positive"):
        divide_half_up(1, bottom)


@pytest.mark.parametrize("bad", [True, 1.5, "10"])
def test_divide_half_up_refuses_non_integers(bad):
    with pytest.raises(CrackerError, match="must be an integer"):
        divide_half_up(bad, 2)


@pytest.mark.parametrize(
    "bp,text", [(10_000, "100.00"), (5000, "50.00"), (0, "0.00"), (5, "0.05"), (-5, "-0.05")]
)
def test_format_bp(bp, text):
    assert format_bp(bp) == text


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [("sha256", "sha256"), ("MD5", "md5"), (" Sha1 ", "sha1")])
def test_algorithm_of_normalises(text, expected):
    assert algorithm_of(text) == expected


@pytest.mark.parametrize("text", ["", "md4", "sha-256", "none"])
def test_algorithm_of_refuses_anything_else(text):
    with pytest.raises(CrackerError):
        algorithm_of(text)


@pytest.mark.parametrize("text,expected", [("wordlist", "wordlist"), (" PIN4 ", "pin4")])
def test_mode_of_normalises(text, expected):
    assert mode_of(text) == expected


@pytest.mark.parametrize("text", ["", "rainbow", "brute", "pin5"])
def test_mode_of_refuses_anything_else(text):
    with pytest.raises(CrackerError):
        mode_of(text)


def test_check_digest_accepts_a_sha256_digest():
    assert check_digest("sha256", SUNSHINE) == SUNSHINE


def test_check_digest_lowercases_hex():
    assert check_digest("sha256", SUNSHINE.upper()) == SUNSHINE


def test_check_digest_accepts_a_md5_digest():
    assert check_digest("md5", MICHAEL_MD5) == MICHAEL_MD5


def test_check_digest_refuses_a_truncated_digest():
    with pytest.raises(CrackerError, match="is 64 hex characters"):
        check_digest("sha256", SUNSHINE[:8])


def test_check_digest_refuses_an_over_long_digest():
    with pytest.raises(CrackerError, match="is 32 hex characters"):
        check_digest("md5", SUNSHINE)


def test_check_digest_refuses_a_non_hex_character():
    with pytest.raises(CrackerError, match="not hexadecimal"):
        check_digest("md5", "z" * 32)


def test_check_digest_refuses_an_unknown_algorithm():
    with pytest.raises(CrackerError, match="algorithm must be one of"):
        check_digest("md4", "00")


def test_algorithm_lengths_are_pinned():
    assert ALGORITHMS == {"md5": 32, "sha1": 40, "sha256": 64}
    assert MODES == ("wordlist", "pin4")


# --------------------------------------------------------------------------- #
# records
# --------------------------------------------------------------------------- #
def test_a_wordlist_target_has_no_bounded_keyspace():
    assert target().keyspace is None


def test_a_pin_target_has_the_pin_keyspace():
    assert target(mode="pin4").keyspace == PIN_KEYSPACE == 10_000


def test_a_target_knows_whether_it_is_salted():
    assert target().salted is False
    assert target(salt="s3cr3t").salted is True


def test_a_found_search_proves_something():
    assert Search("alice", "found", 9, "sunshine", None).proven is True


def test_an_exhausted_search_proves_something():
    assert Search("erin", "exhausted", 10_000, None, PIN_KEYSPACE).proven is True


def test_an_inconclusive_search_proves_nothing():
    assert Search("dave", "inconclusive", 117, None, None).proven is False


def test_missed_is_about_the_recovered_word():
    assert Search("dave", "inconclusive", 117, None, None).missed is True
    assert Search("alice", "found", 9, "sunshine", None).missed is False


# --------------------------------------------------------------------------- #
# hashing
# --------------------------------------------------------------------------- #
def test_digest_of_pins_a_sha256():
    assert digest_of("sunshine") == SUNSHINE


def test_digest_of_pins_a_md5():
    assert digest_of("michael", "md5") == MICHAEL_MD5


def test_digest_of_is_stable():
    assert digest_of("monkey") == digest_of("monkey")


def test_digest_of_changes_with_the_algorithm():
    assert digest_of("monkey") != digest_of("monkey", "sha1")
    assert len(digest_of("monkey", "sha1")) == 40


def test_digest_of_refuses_an_empty_candidate():
    with pytest.raises(CrackerError, match="must not be empty"):
        digest_of("   ")


def test_digest_of_refuses_non_ascii_text():
    with pytest.raises(CrackerError, match="must be ASCII text"):
        digest_of("caf\u00e9")


def test_digest_with_salt_prepends_the_salt():
    carol = target(salt="s3cr3t", digest=digest_of("s3cr3tmonkey"))
    assert digest_with_salt(carol, "monkey") == carol.digest


def test_the_bare_word_does_not_produce_the_salted_digest():
    carol = target(salt="s3cr3t", digest=digest_of("s3cr3tmonkey"))
    assert digest_of("monkey") != carol.digest


# --------------------------------------------------------------------------- #
# candidate lists
# --------------------------------------------------------------------------- #
def test_read_lines_reads_the_bundled_wordlist():
    lines = read_lines()
    assert len(lines) == 126
    assert lines[0] == "# Bundled offline wordlist for the Hash Cracker demo."
    assert lines[-1] == "password"


def test_read_lines_refuses_a_missing_file(tmp_path):
    with pytest.raises(CrackerError, match="file not found"):
        read_lines(tmp_path / "nope.txt")


def test_read_lines_refuses_non_ascii_bytes(tmp_path):
    path = tmp_path / "list.txt"
    path.write_bytes(b"alpha\n\xff\n")
    with pytest.raises(CrackerError, match="not ASCII text"):
        read_lines(path)


def test_read_lines_refuses_a_file_of_blank_lines(tmp_path):
    path = tmp_path / "list.txt"
    path.write_text("\n\n  \n", encoding="ascii")
    with pytest.raises(CrackerError, match="holds no lines"):
        read_lines(path)


def test_load_words_drops_the_comments():
    words = load_words()
    assert len(words) == 120
    assert all(not word.startswith("#") for word in words)


def test_load_words_refuses_a_wordlist_of_comments_only(tmp_path):
    path = tmp_path / "list.txt"
    path.write_text("# nothing here\n", encoding="ascii")
    with pytest.raises(CrackerError, match="holds no candidates"):
        load_words(path)


def test_distinct_words_keeps_the_first_occurrence():
    assert distinct_words(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_distinct_words_keeps_the_attack_order():
    assert distinct_words(["zebra", "apple"]) == ["zebra", "apple"]


def test_distinct_words_refuses_a_non_text_entry():
    with pytest.raises(CrackerError, match="must be text"):
        distinct_words(["a", 3])  # type: ignore[list-item]


def test_the_bundled_wordlist_has_117_distinct_candidates():
    assert len(distinct_words(load_words())) == 117


def test_pin_candidates_count_is_the_keyspace():
    assert len(pin_candidates()) == PIN_KEYSPACE


def test_pin_candidates_are_zero_padded_and_ordered():
    rows = pin_candidates(2)
    assert rows[0] == "00"
    assert rows[-1] == "99"
    assert rows[7] == "07"


def test_pin_candidates_refuses_a_zero_width():
    with pytest.raises(CrackerError, match="must be positive"):
        pin_candidates(0)


def test_pin_candidates_refuses_a_huge_width():
    with pytest.raises(CrackerError, match="at most 6"):
        pin_candidates(7)


def test_candidates_for_a_wordlist_target_are_the_distinct_words():
    assert candidates_for(target(), ["a", "b", "a"]) == ["a", "b"]


def test_candidates_for_a_pin_target_ignores_the_wordlist():
    assert len(candidates_for(target(mode="pin4"), ["a"])) == PIN_KEYSPACE


def test_candidates_for_refuses_an_empty_wordlist():
    with pytest.raises(CrackerError, match="no candidates"):
        candidates_for(target(), [])


# --------------------------------------------------------------------------- #
# the search
# --------------------------------------------------------------------------- #
def test_search_finds_a_word_and_counts_the_examined_candidates():
    result = search(target(), ["alpha", "sunshine", "omega"])
    assert result.verdict == "found"
    assert result.attempts == 2
    assert result.recovered == "sunshine"


def test_search_reports_a_partial_miss_as_inconclusive():
    result = search(target(), ["alpha", "beta"])
    assert result.verdict == "inconclusive"
    assert result.attempts == 2
    assert result.recovered is None


def test_search_reports_a_complete_miss_as_exhausted():
    result = search(target(digest=digest_of("48213"), mode="pin4"), pin_candidates())
    assert result.verdict == "exhausted"
    assert result.attempts == PIN_KEYSPACE


def test_search_finds_a_pin_inside_the_keyspace():
    result = search(target(digest=digest_of("0042"), mode="pin4"), pin_candidates())
    assert result.verdict == "found"
    assert result.attempts == 43
    assert result.recovered == "0042"


def test_search_uses_the_salt():
    carol = target(salt="s3cr3t", digest=digest_of("s3cr3tmonkey"))
    assert search(carol, ["monkey"]).verdict == "found"


def test_search_without_the_salt_misses_the_same_word():
    carol = target(digest=digest_of("s3cr3tmonkey"))
    assert search(carol, ["monkey"]).verdict == "inconclusive"


def test_search_refuses_an_empty_candidate_list():
    with pytest.raises(CrackerError, match="at least one candidate"):
        search(target(), [])


def test_search_refuses_a_non_ascii_candidate():
    with pytest.raises(CrackerError, match="must be ASCII text"):
        search(target(), ["caf\u00e9"])


def test_search_is_deterministic():
    first = search(target(), ["alpha", "sunshine"])
    second = search(target(), ["alpha", "sunshine"])
    assert first == second


# --------------------------------------------------------------------------- #
# the legacy reports
# --------------------------------------------------------------------------- #
def test_legacy_search_finds_an_unsalted_word():
    assert legacy_search(target(), load_words()) == "sunshine"


def test_legacy_search_misses_the_salted_target():
    carol = target(label="carol", salt="s3cr3t", digest=digest_of("s3cr3tmonkey"))
    assert legacy_search(carol, load_words()) is None


def test_legacy_search_misses_the_long_passphrase():
    dave = target(label="dave", digest=digest_of("correct horse battery staple"))
    assert legacy_search(dave, load_words()) is None


def test_legacy_search_ignores_the_salt_field_entirely():
    carol = target(salt="s3cr3t", digest=digest_of("s3cr3tmonkey"))
    assert legacy_search(carol, ["monkey"]) is None


def test_legacy_verdict_calls_a_miss_strong():
    assert legacy_verdict(None) == "strong"
    assert legacy_verdict("sunshine") == "weak"


def test_legacy_attempts_counts_every_non_empty_line():
    assert legacy_attempts(["a", "", "# note", "a"]) == 3


def test_legacy_attempts_reads_the_bundled_wordlist():
    assert legacy_attempts(read_lines()) == 126


def test_the_counted_work_differs_from_the_hashed_work():
    lines = read_lines()
    assert legacy_attempts(lines) - len(distinct_words(load_words())) == 9


# --------------------------------------------------------------------------- #
# loading targets
# --------------------------------------------------------------------------- #
def test_load_targets_reads_the_bundled_file():
    targets = load_targets()
    assert [row.label for row in targets] == ["alice", "bob", "carol", "dave", "erin"]


def test_load_targets_pins_the_algorithms_and_modes():
    targets = {row.label: row for row in load_targets()}
    assert targets["alice"].algorithm == "sha256"
    assert targets["bob"].algorithm == "md5"
    assert targets["carol"].salt == "s3cr3t"
    assert targets["dave"].salt == ""
    assert targets["erin"].mode == "pin4"
    assert targets["alice"].mode == "wordlist"


def test_load_targets_pins_the_digests():
    targets = {row.label: row for row in load_targets()}
    assert targets["alice"].digest == SUNSHINE
    assert targets["bob"].digest == MICHAEL_MD5
    assert targets["carol"].digest == digest_of("s3cr3tmonkey")
    assert targets["erin"].digest == digest_of("48213")


def test_load_targets_refuses_a_missing_file(tmp_path):
    with pytest.raises(CrackerError, match="file not found"):
        load_targets(tmp_path / "nope.csv")


def test_load_targets_refuses_non_ascii_bytes(tmp_path):
    path = tmp_path / "targets.csv"
    path.write_bytes(b"label,algorithm,salt,digest,mode\nalice,sha256,,\xff,wordlist\n")
    with pytest.raises(CrackerError, match="not ASCII text"):
        load_targets(path)


def test_load_targets_refuses_a_missing_column(tmp_path):
    path = tmp_path / "targets.csv"
    path.write_text("label,algorithm\n", encoding="ascii")
    with pytest.raises(CrackerError, match="missing column"):
        load_targets(path)


def test_build_targets_refuses_an_empty_table():
    with pytest.raises(CrackerError, match="holds no targets"):
        build_targets([])


def test_build_targets_refuses_an_unknown_algorithm():
    with pytest.raises(CrackerError, match="algorithm must be one of"):
        build_targets([row(algorithm="md4")])


def test_build_targets_refuses_a_digest_of_the_wrong_length():
    with pytest.raises(CrackerError, match="is 32 hex characters"):
        build_targets([row(algorithm="md5", digest=SUNSHINE)])


def test_build_targets_refuses_a_duplicate_label():
    with pytest.raises(CrackerError, match="must be unique"):
        build_targets([row(), row(algorithm="md5", digest=MICHAEL_MD5)])


def test_build_targets_refuses_an_unknown_mode():
    with pytest.raises(CrackerError, match="mode must be one of"):
        build_targets([row(mode="rainbow")])


def test_build_targets_refuses_an_empty_label():
    with pytest.raises(CrackerError, match="must not be empty"):
        build_targets([row(label="  ")])


# --------------------------------------------------------------------------- #
# measure and report
# --------------------------------------------------------------------------- #
def test_measure_pins_the_seed():
    measured = measure()
    assert len(measured["targets"]) == 5
    assert len(measured["lines"]) == 126
    assert len(measured["distinct"]) == 117
    assert measured["legacy_attempts"] == 126
    assert measured["found"] == ["alice", "bob", "carol"]
    assert measured["exhausted"] == ["erin"]
    assert measured["inconclusive"] == ["dave"]
    assert measured["legacy_strong"] == ["carol", "dave", "erin"]


def test_measure_pins_the_attempt_counts():
    searches = {row.label: row for row in measure()["searches"]}
    assert searches["alice"].attempts == 9
    assert searches["bob"].attempts == 32
    assert searches["carol"].attempts == 16
    assert searches["dave"].attempts == 117
    assert searches["erin"].attempts == 10_000


def test_measure_pins_the_recovered_words():
    searches = {row.label: row for row in measure()["searches"]}
    assert searches["alice"].recovered == "sunshine"
    assert searches["bob"].recovered == "michael"
    assert searches["carol"].recovered == "monkey"


def test_measure_pins_the_legacy_misses():
    assert measure()["legacy"] == {
        "alice": "sunshine",
        "bob": "michael",
        "carol": None,
        "dave": None,
        "erin": None,
    }


def test_measure_reads_the_wordlist_beside_the_targets(tmp_path):
    (tmp_path / "wordlist.txt").write_text("alpha\nbeta\n", encoding="ascii")
    (tmp_path / "targets.csv").write_text(
        "label,algorithm,salt,digest,mode\n"
        f"one,sha256,,{digest_of('beta')},wordlist\n",
        encoding="ascii",
    )
    measured = measure(tmp_path / "targets.csv")
    assert measured["found"] == ["one"]
    assert measured["searches"][0].attempts == 2


def test_measure_accepts_an_explicit_wordlist_path(tmp_path):
    (tmp_path / "targets.csv").write_text(
        "label,algorithm,salt,digest,mode\n"
        f"one,sha256,,{digest_of('beta')},wordlist\n",
        encoding="ascii",
    )
    other = tmp_path / "other.txt"
    other.write_text("beta\n", encoding="ascii")
    measured = measure(tmp_path / "targets.csv", wordlist_path=other)
    assert measured["searches"][0].attempts == 1


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "Target(" not in text
    assert payload["targets"] == 5
    assert payload["distinct_candidates"] == 117
    assert payload["wordlist_duplicates"] == 3
    assert payload["legacy_attempts"] == 126
    assert payload["pin_coverage_bp"] == 10_000
    assert payload["pin_coverage_percent"] == "100.00"
    assert payload["searches"][0] == {
        "label": "alice",
        "verdict": "found",
        "attempts": 9,
        "recovered": "sunshine",
        "keyspace": None,
    }


def test_report_keeps_the_legacy_answers_plain():
    payload = report(measure())
    assert payload["legacy"]["carol"] is None
    assert payload["legacy"]["alice"] == "sunshine"


def test_render_searches_shows_every_target():
    rendered = render_searches(measure())
    assert "alice" in rendered
    assert "exhausted" in rendered
    assert "10000" in rendered
    assert rendered.count("\n") == 5


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_audit_passes_every_check():
    results = audit(measure())
    assert len(results) == 18
    assert all(ok for _, ok in results)


def test_audit_names_are_unique():
    names = [name for name, _ in audit(measure())]
    assert len(names) == len(set(names))


def test_audit_negative_control_cracker_that_never_finds_anything():
    def blind(one, candidates):
        return Search(one.label, "inconclusive", len(list(candidates)), None, one.keyspace)

    results = dict(audit(measure(), crack=blind))
    assert results["verdicts_match_an_independent_scan"] is False
    assert results["the_verdicts_are_pinned"] is True
    assert results["rebuild_is_deterministic"] is False


def test_audit_negative_control_cracker_that_raises():
    def broken(one, candidates):
        raise CrackerError("boom")

    results = dict(audit(measure(), crack=broken))
    assert results["every_target_gets_exactly_one_search"] is False
    assert results["rebuild_is_deterministic"] is False


def test_audit_negative_control_cracker_that_stops_early():
    def lazy(one, candidates):
        return search(one, list(candidates)[:2])

    results = dict(audit(measure(), crack=lazy))
    assert results["verdicts_match_an_independent_scan"] is False


def test_audit_detects_a_tampered_verdict():
    measured = measure()
    measured["searches"][3] = Search("dave", "exhausted", 117, None, None)
    results = dict(audit(measured))
    assert results["the_verdicts_are_pinned"] is False
    assert results["a_partial_miss_is_inconclusive_not_strong"] is False


def test_audit_detects_a_tampered_recovered_word():
    measured = measure()
    measured["searches"][0] = Search("alice", "found", 9, "sunsh1ne", None)
    assert dict(audit(measured))["the_recovered_passwords_are_pinned"] is False


def test_audit_detects_a_tampered_legacy_answer():
    measured = measure()
    measured["legacy"]["carol"] = "monkey"
    results = dict(audit(measured))
    assert results["ignoring_the_salt_misses_carol"] is False
    assert results["the_legacy_verdict_calls_every_miss_strong"] is False


def test_audit_detects_a_tampered_attempt_count():
    measured = measure()
    measured["searches"][0] = Search("alice", "found", 8, "sunshine", None)
    assert dict(audit(measured))["a_hit_counts_only_the_candidates_it_examined"] is False


# --------------------------------------------------------------------------- #
# demo and CLI
# --------------------------------------------------------------------------- #
def test_the_legacy_snippets_are_kept_as_text():
    assert "hexdigest()" in LEGACY_SALT
    assert '"strong"' in LEGACY_VERDICT
    assert "attempts += 1" in LEGACY_ATTEMPTS


def test_run_demo_returns_zero_and_ends_with_the_contract(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    second = capsys.readouterr().out
    assert first == second


def test_demo_prints_the_pinned_numbers(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "126 non-empty wordlist lines, 117 distinct, 3 repeated" in out
    assert "no hit after 117 of an unbounded keyspace" in out
    assert "10000 of 10000 four-digit PINs" in out
    assert "the legacy report calls 3 misses strong: carol, dave, erin" in out
    assert "monkey' is line 16 of the wordlist" in out
    assert "18/18 checks pass" in out
    assert "FAIL " not in out


def test_demo_output_is_ascii_and_silent_on_stderr(capsys):
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        run_demo()
    assert err.getvalue() == ""


def test_demo_output_is_ascii(capsys):
    run_demo()
    assert capsys.readouterr().out.isascii()


def test_cli_demo_exits_zero():
    assert cli.main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_json_writes_a_report(tmp_path):
    destination = tmp_path / "report.json"
    assert cli.main(["--json", str(destination)]) == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["found"] == ["alice", "bob", "carol"]
    assert payload["inconclusive"] == ["dave"]


def test_cli_json_creates_the_parent_folder(tmp_path):
    destination = tmp_path / "nested" / "deep" / "report.json"
    assert cli.main(["--json", str(destination)]) == 0
    assert destination.is_file()


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such/targets.csv"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_truncated_digest_exits_two(tmp_path, capsys):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "wordlist.txt").write_text("alpha\n", encoding="ascii")
    (folder / "targets.csv").write_text(
        "label,algorithm,salt,digest,mode\nalice,sha256,,a941a4c4,wordlist\n",
        encoding="ascii",
    )
    assert cli.main(["--file", str(folder / "targets.csv")]) == 2
    assert "hex characters" in capsys.readouterr().err


def test_cli_prints_the_summary(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "found ['alice', 'bob', 'carol'], exhausted ['erin'], inconclusive ['dave']" in out


def test_cli_quiet_json_still_writes(tmp_path):
    destination = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(destination)]) == 0
    assert destination.is_file()


def test_module_audit_is_exposed():
    assert cracker.audit is audit


def test_hashing_matches_the_standard_library():
    assert hashlib.sha256(b"sunshine").hexdigest() == SUNSHINE
