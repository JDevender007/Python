"""Tests for the chat lab: a message is a frame, not a line."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import chat as module                                    # noqa: E402
import main as cli                                       # noqa: E402
from chat import (                                       # noqa: E402
    FRAME_SEP,
    LEGACY_READER,
    MAX_HEADER,
    MAX_MESSAGE,
    READ_LIMIT,
    Channel,
    ChatClient,
    ChatError,
    ChatServer,
    FrameDecoder,
    Message,
    audit,
    converse,
    divide_half_up,
    encode_frame,
    legacy_decode,
    legacy_deliver,
    measure,
    parse_log,
    problems,
    read_log,
    run_demo,
    split_reads,
    unescape,
    wire_of,
)

MESSAGES = read_log()
MEASURED = measure(MESSAGES)
DELIVERED = ["hello there", "line one\nline two", "caf\u00e9", "5 > 3 and 2 < 4"]


# --------------------------------------------------------------------------- #
# divide_half_up
# --------------------------------------------------------------------------- #
def test_divide_half_up_rounds_a_tie_up():
    assert divide_half_up(5, 2) == 3


def test_divide_half_up_floors_below_the_tie():
    assert divide_half_up(7, 3) == 2



def test_divide_half_up_rounds_a_negative_tie_away_from_zero():
    assert divide_half_up(-5, 2) == -3


def test_divide_half_up_refuses_a_zero_denominator():
    with pytest.raises(ChatError, match="a denominator is positive"):
        divide_half_up(1, 0)


def test_divide_half_up_refuses_a_float():
    with pytest.raises(ChatError, match="a numerator is a whole number"):
        divide_half_up(1.5, 2)


# --------------------------------------------------------------------------- #
# unescape
# --------------------------------------------------------------------------- #
def test_unescape_keeps_plain_text():
    assert unescape("hello there") == "hello there"


def test_unescape_turns_a_backslash_n_into_a_newline():
    assert unescape("line one\\nline two") == "line one\nline two"


def test_unescape_turns_a_backslash_t_into_a_tab():
    assert unescape("a\\tb") == "a\tb"


def test_unescape_reads_four_hex_digits():
    assert unescape("caf\\u00e9") == "caf\u00e9"



def test_unescape_keeps_a_doubled_backslash():
    assert unescape("a\\\\b") == "a\\b"



def test_unescape_refuses_a_short_hex_escape():
    with pytest.raises(ChatError, match="four hex digits"):
        unescape("\\u00e")


def test_unescape_refuses_a_non_hex_digit():
    with pytest.raises(ChatError, match="four hex digits"):
        unescape("\\u00zz")


def test_unescape_refuses_a_surrogate():
    with pytest.raises(ChatError, match="surrogate"):
        unescape("\\ud800")


def test_unescape_refuses_an_unknown_escape():
    with pytest.raises(ChatError, match="unknown escape"):
        unescape("a\\qb")


def test_unescape_refuses_a_lone_trailing_backslash():
    with pytest.raises(ChatError, match="lone backslash"):
        unescape("abc\\")



# --------------------------------------------------------------------------- #
# encode_frame
# --------------------------------------------------------------------------- #
def test_a_frame_is_a_byte_count_a_colon_and_the_payload():
    assert encode_frame("hi") == b"2:hi"


def test_the_header_counts_bytes_not_characters():
    assert encode_frame("caf\u00e9") == b"5:caf\xc3\xa9"


def test_a_newline_is_inside_the_frame_not_after_it():
    assert encode_frame("a\nb") == b"3:a\nb"




def test_encode_frame_refuses_a_larger_message():
    with pytest.raises(ChatError, match="at most 4096 bytes"):
        encode_frame("a" * (MAX_MESSAGE + 1))


def test_encode_frame_refuses_a_blank_message():
    with pytest.raises(ChatError, match="not blank"):
        encode_frame("   ")


def test_encode_frame_refuses_a_non_text_message():
    with pytest.raises(ChatError, match="a message is text"):
        encode_frame(5)


# --------------------------------------------------------------------------- #
# FrameDecoder
# --------------------------------------------------------------------------- #
def test_one_whole_frame_is_one_message():
    assert FrameDecoder().feed(b"2:hi") == ("hi",)


def test_two_frames_in_one_read_are_two_messages():
    assert FrameDecoder().feed(b"2:hi3:bye") == ("hi", "bye")


def test_a_frame_split_across_two_reads_is_delivered_once():
    decoder = FrameDecoder()
    assert decoder.feed(b"5:hel") == ()
    assert decoder.feed(b"lo") == ("hello",)


def test_a_partial_frame_is_held_not_delivered():
    decoder = FrameDecoder()
    decoder.feed(b"5:hel")
    assert decoder.pending == 5 and decoder.need == 2


def test_pending_is_zero_once_the_frame_is_whole():
    decoder = FrameDecoder()
    decoder.feed(b"2:hi")
    assert decoder.pending == 0 and decoder.need == 0


def test_a_newline_inside_a_payload_is_kept():
    assert FrameDecoder().feed(encode_frame("a\nb")) == ("a\nb",)




def test_the_decoder_refuses_a_header_that_is_not_a_count():
    with pytest.raises(ChatError, match="a frame header is a byte count"):
        FrameDecoder().feed(b"x:abc")


def test_the_decoder_refuses_a_leading_zero():
    with pytest.raises(ChatError, match="no leading zero"):
        FrameDecoder().feed(b"02:hi")


def test_the_decoder_refuses_a_header_wider_than_four_digits():
    with pytest.raises(ChatError, match=f"at most {MAX_HEADER} digits"):
        FrameDecoder().feed(b"12345")


def test_the_decoder_refuses_an_oversized_frame():
    with pytest.raises(ChatError, match="at most 4096 bytes"):
        FrameDecoder().feed(b"99999:x")


def test_the_decoder_refuses_a_payload_that_is_not_utf8():
    with pytest.raises(ChatError, match="payload is UTF-8; byte 0"):
        FrameDecoder().feed(b"2:\xff\xfe")



def test_flush_of_a_clean_stream_is_empty():
    assert FrameDecoder().flush() == ()


def test_flush_refuses_an_unfinished_frame():
    decoder = FrameDecoder()
    decoder.feed(b"5:hel")
    with pytest.raises(ChatError, match="not a message until it is whole"):
        decoder.flush()


# --------------------------------------------------------------------------- #
# The legacy reader and the read splitter
# --------------------------------------------------------------------------- #
def test_the_legacy_reader_is_the_split_on_newline():
    assert "recv(4096)" in LEGACY_READER and 'split("\\n")' in LEGACY_READER


def test_a_split_character_becomes_a_replacement_character():
    assert legacy_decode(b"5:caf\xc3") == "5:caf\ufffd"


def test_the_legacy_reader_splits_a_payload_on_its_newline():
    assert legacy_deliver([b"a\nb"]) == ("a", "b")


def test_the_legacy_reader_delivers_each_read_separately():
    assert legacy_deliver([b"5:hel", b"lo"]) == ("5:hel", "lo")




def test_split_reads_returns_short_reads_in_order():
    assert split_reads(b"abcdefgh", 3) == (b"abc", b"def", b"gh")



def test_split_reads_refuses_a_zero_limit():
    with pytest.raises(ChatError, match="a read limit is positive"):
        split_reads(b"abc", 0)


def test_split_reads_refuses_a_non_bytes_stream():
    with pytest.raises(ChatError, match="a stream is bytes"):
        split_reads("abc", 3)


# --------------------------------------------------------------------------- #
# Channel
# --------------------------------------------------------------------------- #
def test_a_write_reports_its_length():
    channel = Channel()
    assert channel.write(b"hello") == 5


def test_a_read_takes_at_most_its_limit():
    channel = Channel()
    channel.write(b"hello")
    assert channel.read(2) == b"he" and channel.pending == 3



def test_a_read_refuses_a_zero_limit():
    channel = Channel()
    channel.write(b"x")
    with pytest.raises(ChatError, match="a read limit is positive"):
        channel.read(0)


def test_a_channel_refuses_a_non_bytes_write():
    with pytest.raises(ChatError, match="a write is bytes"):
        Channel().write("text")


# --------------------------------------------------------------------------- #
# ChatServer and ChatClient
# --------------------------------------------------------------------------- #
def test_a_server_pumps_a_channel_into_messages():
    inbox = Channel()
    inbox.write(wire_of(MESSAGES))
    server = ChatServer(inbox)
    assert server.pump_all() == tuple(DELIVERED)


def test_a_server_counts_reads_and_partial_reads():
    inbox = Channel()
    inbox.write(wire_of(MESSAGES))
    server = ChatServer(inbox)
    server.pump_all()
    assert server.reads == 9 and server.partial_reads == 7


def test_a_server_refuses_a_plain_object_as_its_channel():
    with pytest.raises(ChatError, match="a server reads a channel"):
        ChatServer(b"raw bytes")



def test_a_pump_of_an_empty_channel_is_refused():
    with pytest.raises(ChatError, match="the channel is empty"):
        ChatServer(Channel()).pump()


def test_a_client_writes_one_frame_per_message():
    inbox = Channel()
    client = ChatClient(ChatServer(inbox), "alice")
    assert client.say("hi") == 4 and inbox.pending == 4


def test_a_client_writes_a_whole_conversation():
    inbox = Channel()
    client = ChatClient(ChatServer(inbox), "alice")
    assert client.say_all(["a", "b"]) == 6


def test_a_client_refuses_a_blank_nickname():
    with pytest.raises(ChatError, match="a nickname is text, and not blank"):
        ChatClient(ChatServer(Channel()), "  ")


def test_a_client_refuses_a_pipe_in_the_nickname():
    with pytest.raises(ChatError, match="no '\\|'"):
        ChatClient(ChatServer(Channel()), "a|b")



def test_a_client_refuses_a_non_server():
    with pytest.raises(ChatError, match="a client writes to a server"):
        ChatClient(Channel(), "alice")


# --------------------------------------------------------------------------- #
# Message and the log parser
# --------------------------------------------------------------------------- #
def test_a_message_reports_its_byte_size_and_its_characters():
    message = Message("carol", "caf\u00e9")
    assert message.size == 5 and message.characters == 4


def test_a_message_is_shown_as_ascii():
    assert Message("carol", "caf\u00e9").shown() == "'caf\\xe9'"


def test_a_message_refuses_a_blank_text():
    with pytest.raises(ChatError, match="a message is text, and not blank"):
        Message("alice", " ")


def test_a_message_refuses_a_sender_with_a_pipe():
    with pytest.raises(ChatError, match="a sender holds no"):
        Message("a|b", "hi")



def test_the_bundled_log_holds_four_messages():
    assert [message.sender for message in MESSAGES] == \
        ["alice", "bob", "carol", "dave"]


def test_the_bundled_log_keeps_the_newline_inside_one_message():
    assert MESSAGES[1].text == "line one\nline two"


def test_the_parser_reads_one_line():
    parsed = parse_log("alice | hi\n")
    assert parsed == (Message("alice", "hi"),)


def test_the_parser_ignores_comments_and_blank_lines():
    assert len(parse_log("; a note\n\nbob | hi\n")) == 1


def test_the_parser_refuses_a_line_of_one_field():
    with pytest.raises(ChatError, match="line 1: two fields"):
        parse_log("alice hi")



def test_the_parser_names_the_line_of_a_bad_escape():
    with pytest.raises(ChatError, match="line 2: unknown escape"):
        parse_log("alice | ok\nbob | a\\qb\n")


def test_the_parser_refuses_a_log_with_no_message():
    with pytest.raises(ChatError, match="at least one message"):
        parse_log("; only a comment\n")


def test_the_parser_refuses_a_non_text_log():
    with pytest.raises(ChatError, match="a log is text"):
        parse_log(b"alice | hi")


def test_reading_a_missing_log_says_so(tmp_path):
    with pytest.raises(ChatError, match="file not found"):
        read_log(tmp_path / "nope.txt")


def test_wire_of_concatenates_the_frames():
    assert wire_of(MESSAGES)[:14] == b"11:hello there"


# --------------------------------------------------------------------------- #
# measure
# --------------------------------------------------------------------------- #
def test_measure_pins_the_conversation_size():
    assert MEASURED["count"] == 4 and MEASURED["wire_bytes"] == 59


def test_measure_pins_the_reads():
    assert MEASURED["chunks"] == [7, 7, 7, 7, 7, 7, 7, 7, 3]
    assert MEASURED["reads"] == 9


def test_measure_pins_the_partial_reads_and_their_percentage():
    assert MEASURED["partial_reads"] == 7
    assert MEASURED["boundary_reads"] == 2
    assert MEASURED["split_percent"] == 78


def test_measure_pins_the_delivered_messages():
    assert MEASURED["delivered"] == DELIVERED
    assert MEASURED["pending"] == 0


def test_measure_pins_the_legacy_fragments():
    assert MEASURED["legacy_count"] == 10
    assert MEASURED["legacy_lines"][0] == "11:hell"
    assert MEASURED["legacy_lines"][-1] == "< 4"


def test_measure_pins_the_character_and_byte_counts():
    assert MEASURED["cafe_characters"] == 4
    assert MEASURED["cafe_bytes"] == 5
    assert MEASURED["cafe_header"] == "5"
    assert MEASURED["cafe_frame_bytes"] == 7


def test_measure_pins_the_half_frame():
    assert MEASURED["half_delivered"] == []
    assert MEASURED["half_pending"] == 6
    assert MEASURED["half_need"] == 1
    assert MEASURED["replacement"] == 1


def test_measure_pins_the_two_in_one_and_one_in_two_cases():
    assert MEASURED["two_in_one"] == ["one", "two"]
    assert MEASURED["one_in_two"] == ["whole"]
    assert MEASURED["round_trip"] == ["round trip"]


def test_measure_pins_the_refusals():
    assert MEASURED["flush_refused"] is True
    assert MEASURED["bad_header_refused"] is True
    assert MEASURED["blank_refused"] is True


def test_measure_pins_the_newline_split():
    assert MEASURED["newline_count"] == 1
    assert MEASURED["newline_legacy_pieces"] == 2


def test_measure_follows_the_read_limit_it_is_given():
    small = measure(MESSAGES, 3)
    assert small["reads"] == 20 and small["wire_bytes"] == 59


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "a frame carries its own length in bytes",
    "a message with a newline stays one message",
    "the decoder waits for a whole frame",
    "the decoder reassembles the bundle",
    "every frame is delivered exactly once",
    "the legacy reader splits a message on its newline",
    "the legacy reader delivers a half frame",
    "the header counts bytes not characters",
    "an unfinished frame is refused at the end",
    "a header that is not a count is refused",
    "the split reads are counted and percentaged",
    "an empty message is refused",
]


def real_checks():
    return audit(MEASURED, MESSAGES)


def test_the_audit_holds_twelve_named_checks():
    assert [name for name, _ in real_checks()] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_log():
    assert problems(real_checks()) == []


def test_the_audit_is_repeatable():
    assert real_checks() == real_checks()


def corrupted(**changes) -> dict:
    payload = dict(MEASURED)
    payload.update(changes)
    return payload


def test_the_audit_catches_a_character_count_in_the_header():
    checks = audit(corrupted(cafe_header="4"), MESSAGES)
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_a_lost_newline_message():
    checks = audit(corrupted(delivered=[text for text in DELIVERED
                                        if "\n" not in text]), MESSAGES)
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_a_half_frame_delivered_as_a_message():
    checks = audit(corrupted(half_delivered=["caf"]), MESSAGES)
    assert CHECK_NAMES[2] in problems(checks)


def test_the_audit_catches_a_decoder_that_lost_a_message():
    class Broken:
        pending = 0

        def feed(self, chunk):
            return ("lost",)

    checks = audit(MEASURED, MESSAGES, make_decoder=Broken)
    assert CHECK_NAMES[3] in problems(checks)


def test_the_audit_reassembles_the_bundle_at_any_read_size():
    checks = audit(MEASURED, MESSAGES, read_limit=5)
    assert problems(checks) == []


def test_the_audit_catches_a_missing_read():
    checks = audit(corrupted(reads=8), MESSAGES)
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_a_legacy_reader_that_did_not_split():
    checks = audit(corrupted(legacy_count=4, newline_legacy_pieces=1), MESSAGES)
    assert CHECK_NAMES[5] in problems(checks)


def test_the_audit_catches_a_half_frame_with_no_replacement():
    checks = audit(corrupted(replacement=0), MESSAGES)
    assert CHECK_NAMES[6] in problems(checks)


def test_the_audit_catches_a_header_that_counted_characters():
    checks = audit(corrupted(cafe_bytes=4), MESSAGES)
    assert CHECK_NAMES[7] in problems(checks)


def test_the_audit_catches_a_flush_that_ignored_the_remainder():
    checks = audit(corrupted(flush_refused=False), MESSAGES)
    assert CHECK_NAMES[8] in problems(checks)


def test_the_audit_catches_a_bad_header_that_was_accepted():
    checks = audit(corrupted(bad_header_refused=False), MESSAGES)
    assert CHECK_NAMES[9] in problems(checks)


def test_the_audit_catches_a_percentage_that_does_not_match_the_reads():
    checks = audit(corrupted(split_percent=100), MESSAGES)
    assert CHECK_NAMES[10] in problems(checks)


def test_the_audit_catches_a_blank_message_that_was_sent():
    checks = audit(corrupted(blank_refused=False), MESSAGES)
    assert CHECK_NAMES[11] in problems(checks)


def test_a_missing_measurement_is_a_failure_not_a_traceback():
    payload = corrupted()
    del payload["half_need"]
    checks = audit(payload, MESSAGES)
    assert CHECK_NAMES[2] in problems(checks)
    assert len(checks) == len(CHECK_NAMES)


def test_every_check_has_a_negative_control():
    caught = set()
    caught |= set(problems(audit(corrupted(cafe_header="4"), MESSAGES)))
    caught |= set(problems(audit(corrupted(delivered=[]), MESSAGES)))
    caught |= set(problems(audit(corrupted(half_delivered=["x"]), MESSAGES)))

    class Broken:
        pending = 0

        def feed(self, chunk):
            return ("lost",)

    caught |= set(problems(audit(MEASURED, MESSAGES, make_decoder=Broken)))
    caught |= set(problems(audit(corrupted(reads=1), MESSAGES)))
    caught |= set(problems(audit(corrupted(legacy_count=1), MESSAGES)))
    caught |= set(problems(audit(corrupted(replacement=9), MESSAGES)))
    caught |= set(problems(audit(corrupted(cafe_bytes=9), MESSAGES)))
    caught |= set(problems(audit(corrupted(flush_refused=False), MESSAGES)))
    caught |= set(problems(audit(corrupted(bad_header_refused=False), MESSAGES)))
    caught |= set(problems(audit(corrupted(split_percent=0), MESSAGES)))
    caught |= set(problems(audit(corrupted(blank_refused=False), MESSAGES)))
    assert caught == set(CHECK_NAMES)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith("Demo completed successfully.")
    assert "Cross-checks OK:" in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_legacy_reader(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "CHAT LAB" in out and "recv(4096)" in out


def test_demo_shows_the_fragment_count(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "the legacy reader delivers 10 lines" in out
    assert "9 chunks of 7 bytes" in out


def test_demo_shows_all_twelve_checks(capsys):
    run_demo()
    assert "12/12 checks pass" in capsys.readouterr().out


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


def test_cli_lists_the_messages(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "4 messages, 59 bytes, 9 reads" in out
    assert "7 read(s) ended mid-frame" in out


def test_cli_prints_a_message_with_a_newline_escaped(capsys):
    assert cli.main([]) == 0
    assert "'line one\\nline two'" in capsys.readouterr().out


def test_cli_shows_the_legacy_lines_when_asked(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "the legacy reader delivers 10 line(s)" in out and "'11:hell'" in out


def test_cli_chunk_changes_the_read_count(capsys):
    assert cli.main(["--chunk", "3"]) == 0
    assert "20 reads of 3 bytes" in capsys.readouterr().out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 12 and "FAIL" not in out



def test_cli_writes_the_conversation_as_json(tmp_path, capsys):
    target = tmp_path / "chat.json"
    assert cli.main(["--legacy", "--audit", "--json", str(target),
                     "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["messages"]) == 4
    assert payload["messages"][1]["legacy_lines"] == 2
    assert payload["messages"][2]["characters"] == 4
    assert payload["messages"][2]["bytes"] == 5
    assert payload["measurements"]["cafe_header"] == "5"
    assert len(payload["checks"]) == 12
    assert all(check["ok"] for check in payload["checks"])


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_refuses_a_zero_chunk(capsys):
    assert cli.main(["--chunk", "0"]) == 2
    assert "a read limit is 1..65536" in capsys.readouterr().err


def test_cli_refuses_a_missing_log(tmp_path, capsys):
    assert cli.main(["--file", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_refuses_a_log_with_a_bad_line(tmp_path, capsys):
    broken = tmp_path / "broken.txt"
    broken.write_text("alice hi\n", encoding="utf-8")
    assert cli.main(["--file", str(broken)]) == 2
    assert "two fields" in capsys.readouterr().err


def test_cli_refuses_a_chunk_that_is_not_a_number(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["--chunk", "seven"])
    assert raised.value.code == 2


def test_the_module_exports_the_names_it_is_tested_through():
    assert module.READ_LIMIT == 7
    assert module.MAX_MESSAGE == 4096
    assert module.converse(MESSAGES)[0].delivered == DELIVERED
