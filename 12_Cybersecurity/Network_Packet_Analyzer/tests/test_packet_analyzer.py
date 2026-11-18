"""Tests for the packet analyser: units, bit fields and checksum arithmetic."""

from __future__ import annotations

import dataclasses
import io
import json
import struct
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import packet_analyzer as module  # noqa: E402
import main as cli  # noqa: E402
from packet_analyzer import (  # noqa: E402
    FLAG_NAMES,
    HEADER_MIN,
    MAX_TOTAL,
    PROTOCOLS,
    TCP_MIN,
    UDP_FIXED,
    Decoded,
    LegacyView,
    Packet,
    PacketError,
    audit,
    checksum_is_valid,
    decode,
    divide_half_up,
    dotted,
    flag_names_of,
    format_bp,
    header_checksum,
    legacy_view,
    load_capture,
    measure,
    ones_sum,
    parse_capture,
    parse_hex,
    render_packets,
    report,
    run_demo,
)


def build(
    total: int = 60,
    protocol: int = 6,
    field: int = 0x4000,
    ttl: int = 64,
    payload: bytes = b"A" * 20,
    options: bytes = b"",
    fix_checksum: bool = True,
) -> bytes:
    """Build one IPv4 packet with a correct checksum unless told otherwise."""
    ihl = 5 + len(options) // 4
    header = (
        bytes([0x40 | ihl, 0])
        + struct.pack("!H", total)
        + b"\x1b\x2e"
        + struct.pack("!H", field)
        + bytes([ttl, protocol])
        + b"\x00\x00"
        + bytes([10, 0, 0, 5, 10, 0, 0, 9])
        + options
    )
    if fix_checksum:
        header = header[:10] + struct.pack("!H", header_checksum(header)) + header[12:]
    return header + payload


# --------------------------------------------------------------------------- #
# arithmetic and formatting
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "top,bottom,expected",
    [(10, 4, 3), (5, 2, 3), (1, 3, 0), (2, 3, 1), (-5, 2, -3), (0, 7, 0)],
)
def test_divide_half_up(top, bottom, expected):
    assert divide_half_up(top, bottom) == expected


@pytest.mark.parametrize("bottom", [0, -1])
def test_divide_half_up_refuses_bad_denominators(bottom):
    with pytest.raises(PacketError, match="denominator must be positive"):
        divide_half_up(1, bottom)


@pytest.mark.parametrize("bad", [True, 1.5, "2"])
def test_divide_half_up_refuses_non_integers(bad):
    with pytest.raises(PacketError, match="must be an integer"):
        divide_half_up(bad, 2)


@pytest.mark.parametrize(
    "bp,text", [(10_000, "100.00"), (5000, "50.00"), (0, "0.00"), (5, "0.05"), (-5, "-0.05")]
)
def test_format_bp(bp, text):
    assert format_bp(bp) == text


@pytest.mark.parametrize("bad", [True, 1.5, "5"])
def test_format_bp_refuses_non_integers(bad):
    with pytest.raises(PacketError, match="must be an integer"):
        format_bp(bad)


# --------------------------------------------------------------------------- #
# hex parsing
# --------------------------------------------------------------------------- #
def test_parse_hex_reads_two_digit_tokens():
    assert parse_hex("45 00 1b") == b"\x45\x00\x1b"


def test_parse_hex_accepts_uppercase():
    assert parse_hex("4A FF") == b"\x4a\xff"


def test_parse_hex_refuses_an_empty_record():
    with pytest.raises(PacketError, match="must not be empty"):
        parse_hex("   ")


@pytest.mark.parametrize("token", ["4", "4500", "zz", "4g"])
def test_parse_hex_refuses_a_bad_token(token):
    with pytest.raises(PacketError, match="two hex digits"):
        parse_hex(f"45 {token}")


def test_parse_hex_refuses_non_text():
    with pytest.raises(PacketError, match="must be text"):
        parse_hex(45)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# checksums
# --------------------------------------------------------------------------- #
def test_ones_sum_folds_carries():
    assert ones_sum(b"\xff\xff\xff\xff") == 0xFFFF
    assert ones_sum(b"\x00\x01\x00\x01") == 2


def test_ones_sum_pads_an_odd_length():
    assert ones_sum(b"\x01\x02\x03") == ones_sum(b"\x01\x02\x03\x00")


def test_a_correct_header_sums_to_ffff():
    header = build(payload=b"")[:HEADER_MIN]
    assert ones_sum(header) == 0xFFFF
    assert checksum_is_valid(header) is True


def test_a_changed_byte_breaks_the_sum():
    header = bytearray(build(payload=b"")[:HEADER_MIN])
    header[8] = 63
    assert checksum_is_valid(bytes(header)) is False


def test_header_checksum_zeroes_its_own_field():
    header = build(total=20, payload=b"")[:HEADER_MIN]
    assert header_checksum(header) == int.from_bytes(header[10:12], "big")


def test_header_checksum_refuses_a_short_header():
    with pytest.raises(PacketError, match="at least 20 bytes"):
        header_checksum(b"\x45\x00")


def test_checksum_of_an_all_zero_header_is_ffff():
    assert header_checksum(b"\x00" * HEADER_MIN) == 0xFFFF


# --------------------------------------------------------------------------- #
# the bundled capture
# --------------------------------------------------------------------------- #
def test_the_capture_holds_six_packets():
    packets = load_capture()
    assert [packet.index for packet in packets] == [1, 2, 3, 4, 5, 6]
    assert len(packets) == 6


def test_the_capture_sizes_are_pinned():
    assert [packet.captured for packet in load_capture()] == [60, 52, 36, 36, 44, 44]


def test_the_capture_totals_are_pinned():
    packets = load_capture()
    assert sum(packet.captured for packet in packets) == 272


def test_load_capture_refuses_a_missing_file(tmp_path):
    with pytest.raises(PacketError, match="file not found"):
        load_capture(tmp_path / "nope.txt")


def test_load_capture_refuses_non_ascii_bytes(tmp_path):
    path = tmp_path / "capture.txt"
    path.write_bytes(b"1 | 45 00\n\xff\n")
    with pytest.raises(PacketError, match="not ASCII text"):
        load_capture(path)


def test_parse_capture_ignores_comments_and_blanks():
    packets = parse_capture("# note\n\n1 | " + " ".join(["00"] * 20) + "\n")
    assert len(packets) == 1


def test_parse_capture_refuses_an_empty_capture():
    with pytest.raises(PacketError, match="holds no packets"):
        parse_capture("# only a comment\n")


def test_parse_capture_refuses_a_line_without_a_pipe():
    with pytest.raises(PacketError, match="not an 'index | hex' record"):
        parse_capture("1 45 00\n")


def test_parse_capture_refuses_a_non_integer_index():
    with pytest.raises(PacketError, match="no integer index"):
        parse_capture("one | 45 00\n")


def test_parse_capture_refuses_a_gap():
    with pytest.raises(PacketError, match="packet 1 was due"):
        parse_capture("2 | " + " ".join(["00"] * 20) + "\n")


def test_parse_capture_refuses_a_short_packet():
    with pytest.raises(PacketError, match="under the 20-byte header"):
        parse_capture("1 | 45 00 00 14\n")


def test_parse_capture_refuses_a_duplicated_index():
    body = "1 | " + " ".join(["00"] * 20) + "\n1 | " + " ".join(["00"] * 20) + "\n"
    with pytest.raises(PacketError, match="packet 2 was due"):
        parse_capture(body)


# --------------------------------------------------------------------------- #
# decoding
# --------------------------------------------------------------------------- #
def test_decode_reads_the_basic_header_fields():
    row = decode(load_capture()[0])
    assert row.version == 4
    assert row.ihl_words == 5
    assert row.ihl_bytes == 20
    assert row.total_length == 60
    assert row.protocol == 6
    assert row.protocol_name == "tcp"
    assert row.ttl == 64
    assert (row.src, row.dst) == ("10.0.0.5", "10.0.0.9")


def test_decode_reads_ports_after_the_header():
    row = decode(load_capture()[0])
    assert (row.src_port, row.dst_port) == (443, 51000)
    assert row.transport_header_bytes == TCP_MIN


def test_decode_honours_the_options_in_the_second_packet():
    row = decode(load_capture()[1])
    assert row.ihl_words == 6
    assert row.ihl_bytes == 24
    assert row.has_options is True
    assert (row.src_port, row.dst_port) == (8443, 51001)


def test_decode_separates_flags_from_the_fragment_offset():
    row = decode(load_capture()[1])
    assert row.flags == 0b010
    assert row.flag_names == ("df",)
    assert row.fragment_offset_units == 0
    assert row.fragment_offset_bytes == 0


def test_decode_marks_the_first_fragment():
    row = decode(load_capture()[3])
    assert row.flag_names == ("mf",)
    assert row.is_fragment is True
    assert (row.src_port, row.dst_port) == (123, 40001)


def test_decode_marks_the_last_fragment_and_skips_its_transport_header():
    row = decode(load_capture()[4])
    assert row.fragment_offset_units == 185
    assert row.fragment_offset_bytes == 1480
    assert row.is_fragment is True
    assert row.src_port is None
    assert row.dst_port is None
    assert row.transport_header_bytes == 0


def test_decode_discloses_a_truncated_capture():
    row = decode(load_capture()[2])
    assert row.total_length == 40
    assert row.declared_payload == 12
    assert row.captured_payload == 8
    assert row.truncated_by == 4


def test_decode_verifies_the_checksum():
    rows = [decode(packet) for packet in load_capture()]
    assert [row.checksum_ok for row in rows] == [True, True, True, True, True, False]


def test_decode_reads_the_udp_header_length():
    row = decode(load_capture()[2])
    assert row.protocol_name == "udp"
    assert row.transport_header_bytes == UDP_FIXED


def test_decode_refuses_a_non_ipv4_version():
    with pytest.raises(PacketError, match="not IPv4"):
        decode(Packet(1, b"\x65" + b"\x00" * 19))


def test_decode_refuses_an_ihl_below_five():
    with pytest.raises(PacketError, match="under the 5-word minimum"):
        decode(Packet(1, b"\x44" + b"\x00" * 19))


def test_decode_refuses_a_header_longer_than_the_packet():
    with pytest.raises(PacketError, match="declares a 24-byte header but holds 20"):
        decode(Packet(1, b"\x46" + b"\x00" * 19))


def test_decode_refuses_a_total_below_the_header():
    with pytest.raises(PacketError, match="less than its 20-byte header"):
        decode(Packet(1, build(total=8, payload=b"")[:20]))


def test_decode_refuses_a_packet_under_the_minimum():
    with pytest.raises(PacketError, match="under 20"):
        decode(Packet(1, b"\x45\x00"))


def test_decode_refuses_a_tcp_packet_short_of_its_header():
    raw = build(total=24, protocol=6, payload=b"")[:24]
    with pytest.raises(PacketError, match="short of its TCP header"):
        decode(Packet(1, raw))


def test_decode_refuses_a_udp_packet_short_of_its_header():
    raw = build(total=24, protocol=17, payload=b"")[:24]
    with pytest.raises(PacketError, match="short of its UDP header"):
        decode(Packet(1, raw))


def test_decode_refuses_a_total_smaller_than_the_headers():
    raw = build(total=20, protocol=17, payload=b"")[:20]
    with pytest.raises(PacketError, match="short of its UDP header"):
        decode(Packet(1, raw))


def test_decode_refuses_a_capture_shorter_than_its_transport_header():
    raw = build(total=60, protocol=17, payload=b"")[:24]
    with pytest.raises(PacketError, match="short of its UDP header"):
        decode(Packet(1, raw))


def test_decode_names_an_unknown_protocol_by_number():
    raw = build(total=24, protocol=47, payload=b"")[:24]
    assert decode(Packet(1, raw)).protocol_name == "ip-47"


def test_decode_reports_a_reserved_flag():
    raw = build(total=24, protocol=47, field=0x8000, payload=b"")[:24]
    assert decode(Packet(1, raw)).flag_names == ("reserved",)


def test_decoded_is_frozen():
    row = decode(load_capture()[0])
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.ttl = 1  # type: ignore[misc]


def test_flag_names_of_reads_the_top_bits():
    assert flag_names_of(0b010) == ("df",)
    assert flag_names_of(0b001) == ("mf",)
    assert flag_names_of(0b111) == ("reserved", "df", "mf")
    assert flag_names_of(0b000) == ()


def test_dotted_refuses_a_short_address():
    with pytest.raises(PacketError, match="is 4 bytes"):
        dotted(b"\x0a\x00\x00")


def test_dotted_renders_four_octets():
    assert dotted(b"\x0a\x00\x00\x09") == "10.0.0.9"


def test_constants_are_pinned():
    assert HEADER_MIN == 20
    assert TCP_MIN == 20
    assert UDP_FIXED == 8
    assert MAX_TOTAL == 65_535
    assert FLAG_NAMES == ("reserved", "df", "mf")
    assert PROTOCOLS == {1: "icmp", 6: "tcp", 17: "udp"}


# --------------------------------------------------------------------------- #
# the legacy view
# --------------------------------------------------------------------------- #
def test_legacy_view_reads_ports_at_a_fixed_offset():
    view = legacy_view(load_capture()[1])
    assert (view.src_port, view.dst_port) == (257, 256)


def test_legacy_view_masks_the_wrong_bits_for_flags():
    view = legacy_view(load_capture()[3])
    assert view.flags == 0


def test_legacy_view_reports_the_whole_field_as_the_offset():
    view = legacy_view(load_capture()[0])
    assert view.fragment_offset_units == 16_384


def test_legacy_view_calls_the_last_fragment_mf():
    view = legacy_view(load_capture()[4])
    assert view.flags == 1


def test_legacy_view_never_validates_a_checksum():
    views = [legacy_view(packet) for packet in load_capture()]
    assert [view.checksum_valid for view in views] == [False] * 6


def test_legacy_view_subtracts_from_the_captured_size():
    view = legacy_view(load_capture()[2])
    assert view.payload == 8


def test_legacy_view_refuses_a_short_packet():
    with pytest.raises(PacketError, match="under 20 bytes"):
        legacy_view(Packet(1, b"\x45\x00"))


def test_legacy_view_is_frozen():
    view = LegacyView(1, 443, 51000, 0, 0, True, 20)
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.payload = 1  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# measurement and report
# --------------------------------------------------------------------------- #
def test_measure_pins_the_capture():
    measured = measure()
    assert len(measured["packets"]) == 6
    assert measured["captured_bytes"] == 272
    assert measured["total_bytes"] == 276
    assert measured["header_bytes"] == 124


def test_measure_pins_the_checksum_verdicts():
    measured = measure()
    assert measured["valid_checksums"] == [1, 2, 3, 4, 5]
    assert measured["bad_checksums"] == [6]
    assert measured["legacy_valid"] == []


def test_measure_pins_the_structural_lists():
    measured = measure()
    assert measured["options_packets"] == [2]
    assert measured["fragments"] == [4, 5]
    assert measured["truncated"] == [3]
    assert measured["truncated_bytes"] == 4


def test_measure_pins_the_payload_accounting():
    measured = measure()
    assert measured["declared_payload"] == 76
    assert measured["captured_payload"] == 72
    assert measured["legacy_payload"] == 104


def test_measure_keeps_the_packets_and_the_views_apart():
    measured = measure()
    assert measured["by_index"][2].src_port == 8443
    assert measured["views_by_index"][2].src_port == 257


def test_measure_accepts_an_explicit_path(tmp_path):
    path = tmp_path / "one.txt"
    udp = build(total=36, protocol=17, payload=b"B" * 8)
    path.write_text("1 | " + " ".join(f"{byte:02x}" for byte in udp) + "\n", encoding="ascii")
    measured = measure(path)
    assert len(measured["packets"]) == 1
    assert measured["declared_payload"] == 8


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "Packet(" not in text
    assert payload["packets"] == 6
    assert payload["truncated_bytes"] == 4
    assert payload["valid_checksums"] == [1, 2, 3, 4, 5]


def test_report_pins_the_second_packet():
    payload = report(measure())
    row = payload["decoded"][1]
    assert row["ihl_bytes"] == 24
    assert row["src_port"] == 8443
    assert row["dst_port"] == 51001
    assert row["flags"] == ["df"]


def test_report_pins_the_legacy_numbers():
    payload = report(measure())
    row = payload["legacy"][1]
    assert row["src_port"] == 257
    assert row["dst_port"] == 256
    assert row["checksum_valid"] is False


def test_render_packets_shows_every_packet():
    rendered = render_packets(measure())
    assert rendered.count("\n") == 6
    assert "8443->51001" in rendered
    assert "fragment" in rendered
    assert "BAD" in rendered
    assert "12/8" in rendered


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_audit_passes_every_check():
    results = audit(measure())
    assert len(results) == 27
    assert all(ok for _, ok in results)


def test_audit_names_are_unique():
    names = [name for name, _ in audit(measure())]
    assert len(names) == len(set(names))


def test_audit_accepts_an_explicit_reader():
    measured = measure()
    results = audit(measured, read_decoded=lambda packets: [decode(p) for p in packets])
    assert all(ok for _, ok in results)


def test_audit_negative_control_reader_with_the_legacy_ports():
    def legacy_reader(packets):
        rows = [decode(packet) for packet in packets]
        rows[1] = dataclasses.replace(rows[1], src_port=257, dst_port=256)
        return rows

    results = dict(audit(measure(), read_decoded=legacy_reader))
    assert results["ports_are_read_after_the_options"] is False
    assert results["rebuild_is_deterministic"] is False
    assert results["the_header_length_is_counted_in_thirty_two_bit_words"] is True


def test_audit_negative_control_reader_that_raises():
    def broken(packets):
        raise PacketError("boom")

    results = dict(audit(measure(), read_decoded=broken))
    assert results["every_packet_decodes"] is False
    assert results["payload_accounting_matches_an_independent_sum"] is False
    assert results["rebuild_is_deterministic"] is False


def test_audit_negative_control_reader_with_a_fixed_header_size():
    def fixed(packets):
        return [dataclasses.replace(decode(packet), ihl_bytes=HEADER_MIN) for packet in packets]

    results = dict(audit(measure(), read_decoded=fixed))
    assert results["the_header_length_is_counted_in_thirty_two_bit_words"] is False
    assert results["payload_accounting_matches_an_independent_sum"] is False


def test_audit_detects_a_tampered_payload_sum():
    measured = measure()
    measured["declared_payload"] = 99
    results = dict(audit(measured))
    assert results["the_legacy_payload_uses_the_captured_size_only"] is False
    assert results["payload_accounting_matches_an_independent_sum"] is False


def test_audit_detects_a_tampered_checksum_list():
    measured = measure()
    measured["valid_checksums"] = [1, 2, 3, 4, 5, 6]
    measured["bad_checksums"] = []
    results = dict(audit(measured))
    assert results["the_checksum_is_verified_with_its_own_field_zeroed"] is False
    assert results["exactly_one_packet_fails_its_checksum"] is False


def test_audit_detects_a_tampered_captured_size():
    measured = measure()
    measured["packets"][2] = Packet(3, measured["packets"][2].raw + b"\x00\x00\x00\x00")
    assert dict(audit(measured))["the_total_length_is_the_authority"] is False


# --------------------------------------------------------------------------- #
# demo and CLI
# --------------------------------------------------------------------------- #
def test_the_legacy_snippets_are_kept_as_text():
    assert "offset = 20" in module.LEGACY_HEADER
    assert "field & 0x7" in module.LEGACY_FLAGS
    assert "0xFFFF) == 0" in module.LEGACY_CHECKSUM
    assert "len(raw)" in module.LEGACY_PAYLOAD


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
    assert "Capture: 6 packets, 272 bytes held, 276 declared." in out
    assert "packet 2 declares IHL 6, so its header is 24 bytes" in out
    assert "reading ports at byte 20 gives 257->256" in out
    assert "reading them after the options gives 8443->51001" in out
    assert "the legacy offset reads 16384 units (131072 bytes)" in out
    assert "the legacy test accepts 0 of 6" in out
    assert "payload 12 declared, 8 captured, truncated by 4" in out
    assert "27/27 checks pass" in out
    assert "FAIL " not in out


def test_demo_writes_nothing_to_stderr():
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
    assert payload["bad_checksums"] == [6]
    assert payload["fragments"] == [4, 5]


def test_cli_json_creates_the_parent_folder(tmp_path):
    destination = tmp_path / "nested" / "deep" / "report.json"
    assert cli.main(["--json", str(destination)]) == 0
    assert destination.is_file()


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such/capture.txt"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_malformed_capture_exits_two(tmp_path, capsys):
    path = tmp_path / "capture.txt"
    path.write_text("1 | 45 0z\n", encoding="ascii")
    assert cli.main(["--file", str(path)]) == 2
    assert "hex digits" in capsys.readouterr().err


def test_cli_prints_the_summary(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "6 packets, valid checksums [1, 2, 3, 4, 5], bad [6]" in out


def test_cli_quiet_json_still_writes(tmp_path):
    destination = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(destination)]) == 0
    assert destination.is_file()


def test_module_audit_is_exposed():
    assert module.audit is audit
