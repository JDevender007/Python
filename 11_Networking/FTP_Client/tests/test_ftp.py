"""Tests for the FTP transcript lab: reply grammar, passive ports, byte counts."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import ftp  # noqa: E402
import main as cli  # noqa: E402
from ftp import (  # noqa: E402
    LEGACY_PORT_DECODE,
    LEGACY_REPLY_FILTER,
    Exchange,
    FtpError,
    Reply,
    Transfer,
    audit,
    capabilities,
    check_transfer,
    code_of,
    declared_size,
    divide_half_up,
    exchange_for,
    format_permille,
    greeting,
    greeting_legacy,
    is_continuation,
    legacy_pasv_port,
    legacy_replies,
    legacy_transfer_complete,
    measure,
    parse_replies,
    parse_reply,
    parse_session,
    pasv_address,
    payload_bytes,
    read_text,
    render_replies,
    reply_for,
    report,
    run_demo,
    share_permille,
)

# --------------------------------------------------------------------------- #
# arithmetic
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "top,bottom,expected",
    [(1_200_000, 1234, 972), (5, 2, 3), (1, 3, 0), (2, 3, 1), (-5, 2, -3), (0, 7, 0)],
)
def test_divide_half_up(top, bottom, expected):
    assert divide_half_up(top, bottom) == expected


@pytest.mark.parametrize("bottom", [0, -1])
def test_divide_half_up_refuses_bad_denominators(bottom):
    with pytest.raises(FtpError, match="denominator must be positive"):
        divide_half_up(1, bottom)


@pytest.mark.parametrize("bad", [True, 1.5, "10"])
def test_divide_half_up_refuses_non_integers(bad):
    with pytest.raises(FtpError, match="must be an integer"):
        divide_half_up(bad, 2)


@pytest.mark.parametrize("part,whole,expected", [(1200, 1234, 972), (0, 10, 0), (10, 10, 1000)])
def test_share_permille(part, whole, expected):
    assert share_permille(part, whole) == expected


def test_share_permille_refuses_a_negative_part():
    with pytest.raises(FtpError, match="part must not be negative"):
        share_permille(-1, 10)


def test_share_permille_refuses_a_zero_whole():
    with pytest.raises(FtpError, match="whole must be positive"):
        share_permille(1, 0)


@pytest.mark.parametrize(
    "permille,text", [(972, "97.2"), (1000, "100.0"), (0, "0.0"), (5, "0.5"), (-5, "-0.5")]
)
def test_format_permille(permille, text):
    assert format_permille(permille) == text


# --------------------------------------------------------------------------- #
# reply grammar
# --------------------------------------------------------------------------- #
def test_code_of_reads_the_first_three_digits():
    assert code_of("220 Ready") == 220
    assert code_of("211-Features:") == 211
    assert code_of("150 Opening (1234 bytes)\r\n") == 150


@pytest.mark.parametrize("line", ["", "  ", "hello", "22 Ready", "22x Ready"])
def test_code_of_refuses_a_line_without_a_code(line):
    with pytest.raises(FtpError):
        code_of(line)


@pytest.mark.parametrize("line", ["099 Low", "600 High"])
def test_code_of_refuses_an_out_of_range_code(line):
    with pytest.raises(FtpError, match="code out of range"):
        code_of(line)


@pytest.mark.parametrize(
    "line,expected",
    [("211-Features:", True), ("211 End", False), ("150 Opening (1 byte)", False)],
)
def test_is_continuation_reads_the_fourth_character(line, expected):
    assert is_continuation(line) is expected


def test_parse_reply_keeps_every_line_of_a_multiline_reply():
    reply = parse_reply(["211-Features:", "211- UTF8", "211- SIZE", "211 End"])
    assert reply.code == 211
    assert len(reply.lines) == 4
    assert reply.is_multiline is True
    assert reply.final == "211 End"
    assert reply.text == "Features:\n UTF8\n SIZE\nEnd"


def test_parse_reply_accepts_a_single_line():
    reply = parse_reply(["220 Ready"])
    assert reply.code == 220
    assert reply.is_multiline is False
    assert reply.positive is True


def test_parse_reply_strips_carriage_returns():
    reply = parse_reply(["220 Ready\r\n"])
    assert reply.lines == ("220 Ready",)


def test_parse_reply_refuses_an_empty_run():
    with pytest.raises(FtpError, match="at least one line"):
        parse_reply([])


def test_parse_reply_refuses_a_continuation_that_never_ends():
    with pytest.raises(FtpError, match="is truncated"):
        parse_reply(["211-Features:", "211- UTF8"])


def test_parse_reply_refuses_a_line_that_ends_the_reply_early():
    with pytest.raises(FtpError, match="ends the reply early"):
        parse_reply(["211-Features:", "211 End", "211 Extra"])


def test_parse_reply_refuses_a_changed_code_mid_reply():
    with pytest.raises(FtpError, match="changes the reply code"):
        parse_reply(["220-Hello", "230- Other", "220 Done"])


def test_parse_reply_refuses_a_different_final_code():
    with pytest.raises(FtpError, match="reply ends with code 230"):
        parse_reply(["220-Hello", "220- Still", "230 Done"])


def test_parse_replies_splits_a_preliminary_and_a_final_reply():
    replies = parse_replies(["150 Opening (12 bytes)", "226 Transfer complete"])
    assert [reply.code for reply in replies] == [150, 226]


def test_parse_replies_keeps_a_multiline_pair_together():
    replies = parse_replies(["211-Features:", "211- UTF8", "211 End", "226 Done"])
    assert [len(reply.lines) for reply in replies] == [3, 1]


def test_parse_replies_refuses_an_unterminated_group():
    with pytest.raises(FtpError, match="is truncated"):
        parse_replies(["150 Opening", "150- still going"])


# --------------------------------------------------------------------------- #
# transcript
# --------------------------------------------------------------------------- #
GREETING = ["S> 220-Offline lab FTP server", "S> 220 Ready"]
FEATURES = ["C> FEAT", "S> 211-Features:", "S> 211- UTF8", "S> 211 End"]
PASSIVE = ["C> PASV", "S> 227 Entering Passive Mode (10,0,0,5,19,137)"]


def transcript(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def test_parse_session_reads_a_greeting_and_a_command():
    rows = parse_session(transcript(*GREETING, "C> USER student", "S> 331 Password required"))
    assert len(rows) == 2
    assert rows[0].command is None
    assert rows[0].reply.code == 220
    assert rows[1].command == "USER student"
    assert rows[1].reply.code == 331


def test_parse_session_keeps_a_command_with_two_replies():
    rows = parse_session(
        transcript(
            *GREETING,
            "C> RETR report.csv",
            "S> 150 Opening (1234 bytes)",
            "S> 226 Transfer complete",
        )
    )
    assert len(rows[1].replies) == 2
    assert rows[1].preliminary.code == 150
    assert rows[1].reply.code == 226
    assert rows[1].line_count == 2


def test_exchange_reports_no_preliminary_reply_when_there_is_none():
    rows = parse_session(transcript(*GREETING, "C> QUIT", "S> 221 Bye"))
    assert rows[1].preliminary is None


def test_parse_session_refuses_a_malformed_record():
    with pytest.raises(FtpError, match="not a transcript record"):
        parse_session("this is not a record\n")


def test_parse_session_refuses_an_unknown_direction():
    with pytest.raises(FtpError, match="unknown direction"):
        parse_session("A> hello\n")


def test_parse_session_refuses_an_empty_transcript():
    with pytest.raises(FtpError, match="must not be empty"):
        parse_session("   \n")


def test_parse_session_refuses_a_command_with_an_empty_payload():
    with pytest.raises(FtpError, match="must not be empty"):
        parse_session(transcript(*GREETING, "C>    ", "S> 221 Bye"))


def test_parse_session_skips_blank_lines():
    rows = parse_session("\n".join([*GREETING, "", "C> QUIT", "S> 221 Bye"]) + "\n")
    assert [row.command for row in rows] == [None, "QUIT"]


def test_legacy_replies_keep_only_the_final_line_of_each_reply():
    text = transcript(
        *GREETING,
        "C> FEAT",
        "S> 211-Features:",
        "S> 211- UTF8",
        "S> 211- SIZE",
        "S> 211 End",
    )
    kept = legacy_replies(text)
    assert kept[0] == (None, ["220 Ready"])
    assert kept[1] == ("FEAT", ["211 End"])


def test_greeting_is_the_first_exchange():
    rows = parse_session(transcript(*GREETING, "C> QUIT", "S> 221 Bye"))
    assert greeting(rows).code == 220
    assert len(greeting(rows).lines) == 2


def test_greeting_refuses_a_transcript_that_starts_with_a_command():
    rows = parse_session(transcript("C> QUIT", "S> 221 Bye"))
    with pytest.raises(FtpError, match="starts with a command"):
        greeting(rows)


def test_greeting_refuses_an_empty_transcript():
    with pytest.raises(FtpError, match="no exchanges"):
        greeting([])


def test_reply_for_finds_a_command_by_its_verb():
    rows = parse_session(transcript(*GREETING, "C> RETR report.csv", "S> 226 Done"))
    assert reply_for(rows, "retr").code == 226


def test_reply_for_refuses_a_missing_command():
    rows = parse_session(transcript(*GREETING, "C> QUIT", "S> 221 Bye"))
    with pytest.raises(FtpError, match="no reply for command 'FEAT'"):
        reply_for(rows, "FEAT")


def test_exchange_for_keeps_the_preliminary_reply():
    rows = parse_session(transcript(*GREETING, "C> RETR a.txt", "S> 150 Open", "S> 226 Done"))
    assert exchange_for(rows, "RETR").preliminary.code == 150


def test_exchange_for_finds_a_later_command_with_the_same_verb_name():
    rows = parse_session(
        transcript(*GREETING, "C> SIZE a.txt", "S> 213 5", "C> SIZE b.txt", "S> 213 9")
    )
    assert reply_for(rows, "SIZE").code == 213
    assert len(rows) == 3


def test_capabilities_reads_the_body_and_drops_the_frame():
    reply = parse_reply(["211-Features:", "211- UTF8", "211- REST STREAM", "211 End"])
    assert capabilities(reply) == ["UTF8", "REST STREAM"]


def test_capabilities_refuses_a_reply_that_is_not_211():
    with pytest.raises(FtpError, match="expected a 211 reply"):
        capabilities(parse_reply(["220 Ready"]))


def test_capabilities_is_empty_for_an_empty_feature_list():
    assert capabilities(parse_reply(["211-Features:", "211 End"])) == []


# --------------------------------------------------------------------------- #
# passive mode
# --------------------------------------------------------------------------- #
def test_pasv_address_decodes_two_port_bytes():
    host, port = pasv_address("227 Entering Passive Mode (10,0,0,5,19,137)")
    assert host == "10.0.0.5"
    assert port == 5001
    assert port == 19 * 256 + 137


@pytest.mark.parametrize(
    "line,expected",
    [
        ("227 Entering Passive Mode (127,0,0,1,4,1)", 1025),
        ("227 Entering Passive Mode (192,168,1,9,255,255)", 65535),
        ("227 Entering Passive Mode (10,0,0,5,0,21)", 21),
    ],
)
def test_pasv_address_pins_byte_arithmetic(line, expected):
    assert pasv_address(line)[1] == expected


def test_pasv_address_refuses_a_reply_that_is_not_227():
    with pytest.raises(FtpError, match="expected a 227 reply"):
        pasv_address("220 Ready")


def test_pasv_address_refuses_a_reply_without_a_tuple():
    with pytest.raises(FtpError, match="no address tuple"):
        pasv_address("227 Entering Passive Mode")


def test_pasv_address_refuses_an_out_of_range_byte():
    with pytest.raises(FtpError, match="address byte out of range"):
        pasv_address("227 Entering Passive Mode (10,0,0,5,19,256)")


def test_pasv_address_refuses_a_zero_port():
    with pytest.raises(FtpError, match="passive port must not be zero"):
        pasv_address("227 Entering Passive Mode (10,0,0,5,0,0)")


def test_legacy_pasv_port_reads_only_the_low_byte():
    assert legacy_pasv_port("227 Entering Passive Mode (10,0,0,5,19,137)") == 137


def test_legacy_pasv_port_and_the_decode_agree_on_a_low_server_byte():
    line = "227 Entering Passive Mode (127,0,0,1,0,21)"
    assert legacy_pasv_port(line) == pasv_address(line)[1] == 21


def test_the_two_legacy_snippets_are_kept_as_text():
    assert "line[3:4]" in LEGACY_REPLY_FILTER
    assert "rfind" in LEGACY_PORT_DECODE


# --------------------------------------------------------------------------- #
# transfer accounting
# --------------------------------------------------------------------------- #
def test_declared_size_reads_the_150_reply():
    assert declared_size(parse_reply(["150 Opening BINARY mode (1234 bytes)"])) == 1234


def test_declared_size_accepts_a_125_reply():
    assert declared_size(parse_reply(["125 Data connection already open (12 bytes)"])) == 12


def test_declared_size_accepts_the_singular_byte():
    assert declared_size(parse_reply(["150 Opening (1 byte)"])) == 1


def test_declared_size_refuses_a_final_reply():
    with pytest.raises(FtpError, match="expected a 1xx data reply"):
        declared_size(parse_reply(["226 Transfer complete"]))


def test_declared_size_refuses_a_reply_without_a_count():
    with pytest.raises(FtpError, match="declares no byte count"):
        declared_size(parse_reply(["150 Opening BINARY mode"]))


def test_check_transfer_accepts_an_exact_transfer():
    transfer = check_transfer(1200, 1200)
    assert transfer.complete is True
    assert transfer.shortfall == 0
    assert transfer.permille == 1000


def test_check_transfer_names_a_shortfall():
    transfer = check_transfer(1234, 1200)
    assert transfer.complete is False
    assert transfer.shortfall == 34
    assert transfer.permille == 972
    assert format_permille(transfer.permille) == "97.2"


def test_check_transfer_accepts_a_zero_byte_read_and_calls_it_short():
    transfer = check_transfer(10, 0)
    assert transfer.shortfall == 10
    assert transfer.complete is False
    assert transfer.permille == 0


def test_check_transfer_refuses_more_bytes_than_were_promised():
    with pytest.raises(FtpError, match="received 11 bytes for a 10-byte file"):
        check_transfer(10, 11)


@pytest.mark.parametrize("declared", [0, -1])
def test_check_transfer_refuses_a_non_positive_declaration(declared):
    with pytest.raises(FtpError, match="declared must be positive"):
        check_transfer(declared, 0)


def test_check_transfer_refuses_a_negative_read():
    with pytest.raises(FtpError, match="received must not be negative"):
        check_transfer(10, -1)


def test_transfer_is_frozen():
    transfer = Transfer(declared=10, received=9)
    with pytest.raises(Exception):
        transfer.received = 10


def test_legacy_transfer_complete_trusts_the_226():
    assert legacy_transfer_complete(parse_reply(["226 Transfer complete"])) is True
    assert legacy_transfer_complete(parse_reply(["150 Opening"])) is False


def test_the_legacy_check_and_the_byte_count_disagree_on_a_short_read():
    verdict = legacy_transfer_complete(parse_reply(["226 Transfer complete"]))
    assert verdict is True
    assert check_transfer(1234, 1200).complete is False


# --------------------------------------------------------------------------- #
# files and measurement
# --------------------------------------------------------------------------- #
def test_read_text_refuses_a_missing_file(tmp_path):
    with pytest.raises(FtpError, match="file not found"):
        read_text(tmp_path / "nope.log", tmp_path / "nope.log")


def test_read_text_refuses_non_ascii_bytes(tmp_path):
    path = tmp_path / "bad.log"
    path.write_bytes(b"220 Ready\n\xff\xfe\n")
    with pytest.raises(FtpError, match="is not ASCII text"):
        read_text(path, path)


def test_payload_bytes_refuses_non_ascii_text():
    with pytest.raises(FtpError, match="payload is not ASCII text"):
        payload_bytes("caf\u00e9")


def test_payload_bytes_refuses_an_empty_payload():
    with pytest.raises(FtpError, match="must not be empty"):
        payload_bytes("   ")


def test_measure_pins_the_bundled_session():
    measured = measure()
    assert len(measured["commands"]) == 8
    assert measured["replies"] == 10
    assert measured["banner_lines"] == 3
    assert measured["feature_lines"] == 6
    assert measured["features"] == ["UTF8", "MDTM", "SIZE", "REST STREAM"]
    assert measured["host"] == "10.0.0.5"
    assert measured["port"] == 5001
    assert measured["legacy_port"] == 137
    assert measured["declared"] == 1234
    assert measured["received"] == 1200


def test_measure_pins_the_legacy_gap():
    measured = measure()
    assert measured["legacy_banner_lines"] == 1
    assert measured["legacy_feature_lines"] == 1
    assert measured["legacy_complete"] is True
    assert measured["transfer"].complete is False
    assert measured["transfer"].shortfall == 34


def test_measure_reads_a_payload_from_the_transcript_folder(tmp_path):
    text = transcript(
        *GREETING,
        "C> FEAT",
        "S> 211-Features:",
        "S> 211- UTF8",
        "S> 211 End",
        "C> PASV",
        "S> 227 Entering Passive Mode (127,0,0,1,4,1)",
        "C> RETR a.txt",
        "S> 150 Opening (5 bytes)",
        "S> 226 Transfer complete",
    )
    (tmp_path / "session.log").write_text(text, encoding="ascii")
    (tmp_path / "payload.txt").write_text("abcde", encoding="ascii")
    measured = measure(tmp_path / "session.log")
    assert measured["port"] == 1025
    assert measured["declared"] == 5
    assert measured["transfer"].complete is True
    assert measured["features"] == ["UTF8"]


def test_measure_accepts_an_explicit_payload_path(tmp_path):
    text = transcript(
        *GREETING,
        *FEATURES,
        *PASSIVE,
        "C> RETR a.txt",
        "S> 150 Opening (2 bytes)",
        "S> 226 Done",
    )
    (tmp_path / "s.log").write_text(text, encoding="ascii")
    other = tmp_path / "body.bin"
    other.write_text("hi", encoding="ascii")
    measured = measure(tmp_path / "s.log", payload_path=other)
    assert measured["received"] == 2
    assert measured["transfer"].complete is True


def test_measure_refuses_a_retr_without_a_150_reply(tmp_path):
    text = transcript(
        *GREETING,
        *FEATURES,
        *PASSIVE,
        "C> RETR a.txt",
        "S> 226 Transfer complete",
    )
    (tmp_path / "session.log").write_text(text, encoding="ascii")
    (tmp_path / "payload.txt").write_text("abcde", encoding="ascii")
    with pytest.raises(FtpError, match="no 150 reply"):
        measure(tmp_path / "session.log")


def test_greeting_legacy_keeps_one_line_of_the_banner():
    text = read_text(ftp.SESSION_FILE, ftp.SESSION_FILE)
    assert greeting_legacy(text) == ["220 Ready"]


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "exchanges" not in text
    assert "Reply" not in text
    assert payload["declared_bytes"] == 1234
    assert payload["received_bytes"] == 1200
    assert payload["shortfall_bytes"] == 34
    assert payload["received_permille"] == 972
    assert payload["received_percent"] == "97.2"
    assert payload["complete"] is False
    assert payload["legacy_complete"] is True
    assert payload["capabilities"] == ["UTF8", "MDTM", "SIZE", "REST STREAM"]


def test_render_replies_labels_the_greeting_and_shows_the_final_code():
    rendered = render_replies(measure())
    assert "(greeting)" in rendered
    assert "RETR" in rendered
    assert "226" in rendered
    assert rendered.isascii()


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


def test_audit_negative_control_that_flattens_replies():
    def flattened(text: str):
        rows = []
        for exchange in parse_session(text):
            replies = tuple(Reply(reply.code, (reply.lines[-1],)) for reply in exchange.replies)
            rows.append(Exchange(exchange.command, replies))
        return rows

    results = dict(audit(measure(), read_replies=flattened))
    assert results["the_banner_is_three_lines"] is False


def test_audit_negative_control_reader_that_raises():
    def broken(text: str):
        raise FtpError("boom")

    results = dict(audit(measure(), read_replies=broken))
    assert results["the_banner_is_three_lines"] is False
    assert results["every_reply_line_carries_a_three_digit_code"] is False
    assert results["the_legacy_parser_keeps_one_banner_line"] is True


def test_audit_negative_control_reader_that_reorders_commands():
    def reordered(text: str):
        rows = parse_session(text)
        return rows[::-1]

    results = dict(audit(measure(), read_replies=reordered))
    assert results["the_banner_is_three_lines"] is False


def test_audit_detects_a_tampered_banner_count():
    measured = measure()
    measured["banner_lines"] = 1
    assert dict(audit(measured))["the_banner_is_three_lines"] is False


def test_audit_detects_a_tampered_port():
    measured = measure()
    measured["port"] = 137
    assert dict(audit(measured))["passive_mode_decodes_two_bytes"] is False


def test_audit_detects_a_tampered_feature_list():
    measured = measure()
    measured["features"] = ["UTF8"]
    results = dict(audit(measured))
    assert results["capabilities_are_read_from_the_body"] is False
    assert results["capability_count_matches_an_independent_scan"] is False


def test_audit_detects_a_tampered_transfer():
    measured = measure()
    measured["transfer"] = check_transfer(1234, 1234)
    results = dict(audit(measured))
    assert results["the_shortfall_is_the_difference"] is False
    assert results["the_received_size_is_the_payload_length"] is False


# --------------------------------------------------------------------------- #
# demo and CLI
# --------------------------------------------------------------------------- #
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
    assert "8 commands, 10 replies, 1200 bytes" in out
    assert "port 19*256+137 = 5001" in out
    assert "the legacy decode reads 137" in out
    assert "short by 34" in out
    assert "18/18 checks pass" in out
    assert "FAIL" not in out


def test_demo_output_is_ascii(capsys):
    run_demo()
    assert capsys.readouterr().out.isascii()


def test_demo_writes_nothing_to_stderr():
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        run_demo()
    assert err.getvalue() == ""


def test_cli_demo_exits_zero():
    assert cli.main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_json_writes_a_report(tmp_path):
    target = tmp_path / "report.json"
    assert cli.main(["--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["declared_bytes"] == 1234
    assert payload["port"] == 5001


def test_cli_json_creates_the_parent_folder(tmp_path):
    target = tmp_path / "nested" / "deep" / "report.json"
    assert cli.main(["--json", str(target)]) == 0
    assert target.is_file()


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such/session.log"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_malformed_transcript_exits_two(tmp_path, capsys):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "session.log").write_text("this is not a transcript\n", encoding="ascii")
    (folder / "payload.txt").write_text("abc", encoding="ascii")
    assert cli.main(["--file", str(folder / "session.log")]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_short_transfer_exits_two(tmp_path, capsys):
    folder = tmp_path / "seeds"
    folder.mkdir()
    text = transcript(*GREETING, "C> RETR a.txt", "S> 150 Opening (5 bytes)", "S> 226 Done")
    (folder / "session.log").write_text(text, encoding="ascii")
    (folder / "payload.txt").write_text("abcdef", encoding="ascii")
    assert cli.main(["--file", str(folder / "session.log")]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_quiet_json_still_writes(tmp_path):
    target = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(target)]) == 0
    assert target.is_file()


def test_cli_prints_the_transfer_line(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "transfer 1200/1234 bytes (97.2%), incomplete" in out
