"""An IPv4 header is a bit field, and every field has a unit.

The legacy analyser is the one every "parse a pcap in 30 lines" post contains:

    offset = 20                       # the IP header is 20 bytes
    src_port = int.from_bytes(raw[offset:offset + 2], "big")
    field = int.from_bytes(raw[6:8], "big")
    flags = field & 0x7
    fragment_offset = field
    valid = (sum(raw[:offset]) & 0xFFFF) == 0
    payload = len(raw) - offset - 8

Each line is a unit error, and each one produces a plausible number.

**1. The header length is counted in 32-bit words.** The low nibble of the
first byte is the IHL, so a header with four bytes of TCP options is 24 bytes,
not 20. Packet 2 in the bundled capture is exactly that: reading ports at byte
20 lands inside the option bytes and reports `257` and `256` instead of `8443`
and `51001`.

**2. Flags and the fragment offset share one 16-bit field.** The three flags are
the *top* bits and the offset is the low thirteen, counted in 8-byte units.
`field & 0x7` reads the bottom of the offset and calls it flags, and taking the
whole field as the offset turns a plain DF packet into a fragment at byte
131072. Packet 4 (first fragment) then reads as "no flags, offset 8192 units"
and packet 5 (last fragment) as "more fragments follow".

**3. A checksum is verified over the header with its own field zeroed.** The
one's-complement sum of a *correct* header is `0xFFFF`, not zero; a sum that
includes the checksum field can only be zero when the header is wrong. The
legacy test therefore rejects all six packets while the rebuild accepts five and
rejects exactly the one whose TTL was changed after the checksum was computed.

**4. The total length is the authority, and a short capture is disclosed.**
Packet 3 declares 40 bytes and the capture holds 36. Subtracting the captured
size reports 8 payload bytes and never mentions the other 4; the rebuild
reports `declared 12, captured 8, truncated by 4`.

The rebuild reads a bundled text capture (one packet per line, `index | hex`),
validates every length before slicing, decodes the bit fields from the field
they actually live in, verifies the checksum the way the standard says to, and
prints the legacy numbers beside the correct ones. No socket, no binary file,
no clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CAPTURE_FILE = DATA_DIR / "capture.txt"

HEADER_MIN = 20
TCP_MIN = 20
UDP_FIXED = 8
MAX_TOTAL = 65_535
MAX_OFFSET_UNITS = 0x1FFF

PROTOCOLS = {1: "icmp", 6: "tcp", 17: "udp"}

FLAG_NAMES = ("reserved", "df", "mf")

#: The legacy parser, transcribed so the demo can print it.
LEGACY_HEADER = "offset = 20                       # the IP header is 20 bytes"
LEGACY_FLAGS = "flags = field & 0x7; fragment_offset = field"
LEGACY_CHECKSUM = "valid = (sum(raw[:offset]) & 0xFFFF) == 0"
LEGACY_PAYLOAD = "payload = len(raw) - offset - 8"

HEX_DIGITS = set("0123456789abcdef")


class PacketError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise PacketError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise PacketError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PacketError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise PacketError(f"{name} must be positive, got {number}")
    return number


def divide_half_up(numerator: int, denominator: int) -> int:
    """Integer division rounding halves away from zero, with no float."""
    top = _whole(numerator, "numerator")
    bottom = _positive(denominator, "denominator")
    sign = -1 if top < 0 else 1
    magnitude = abs(top)
    return sign * ((magnitude * 2 + bottom) // (2 * bottom))


def format_bp(basis_points: int) -> str:
    """Render hundredths of a percent as a two-place percentage."""
    value = _whole(basis_points, "basis_points")
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    return f"{sign}{magnitude // 100}.{magnitude % 100:02d}"


def parse_hex(text: str, name: str = "hex") -> bytes:
    """Strict two-digit byte tokens, so a stray nibble is refused by name."""
    raw = _text(text, name).strip()
    tokens = raw.split()
    if not tokens:
        raise PacketError(f"{name} holds no bytes")
    out = bytearray()
    for token in tokens:
        if len(token) != 2 or not set(token.lower()) <= HEX_DIGITS:
            raise PacketError(f"{name} has a token that is not two hex digits: {token!r}")
        out.append(int(token, 16))
    return bytes(out)


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Packet:
    """One captured frame, exactly as many bytes as the capture holds."""

    index: int
    raw: bytes

    @property
    def captured(self) -> int:
        return len(self.raw)


@dataclass(frozen=True)
class Decoded:
    """What the header says, read from the fields the header actually has."""

    index: int
    version: int
    ihl_words: int
    ihl_bytes: int
    total_length: int
    protocol: int
    protocol_name: str
    flags: int
    flag_names: tuple[str, ...]
    fragment_offset_units: int
    fragment_offset_bytes: int
    ttl: int
    src: str
    dst: str
    checksum_stored: int
    checksum_computed: int
    transport_header_bytes: int
    src_port: int | None
    dst_port: int | None
    declared_payload: int
    captured_payload: int
    truncated_by: int

    @property
    def checksum_ok(self) -> bool:
        return self.checksum_stored == self.checksum_computed

    @property
    def has_options(self) -> bool:
        return self.ihl_bytes > HEADER_MIN

    @property
    def is_fragment(self) -> bool:
        return self.fragment_offset_units > 0 or bool(self.flags & 0b001)


@dataclass(frozen=True)
class LegacyView:
    """The numbers the fixed-offset parser produces for the same bytes."""

    index: int
    src_port: int
    dst_port: int
    flags: int
    fragment_offset_units: int
    checksum_valid: bool
    payload: int


# --------------------------------------------------------------------------- #
# Checksums
# --------------------------------------------------------------------------- #
def ones_sum(data: bytes) -> int:
    """The one's-complement sum of 16-bit big-endian words, folded once."""
    raw = bytes(data)
    if len(raw) % 2:
        raw += b"\x00"
    total = 0
    for index in range(0, len(raw), 2):
        total += (raw[index] << 8) | raw[index + 1]
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return total


def header_checksum(header: bytes) -> int:
    """The checksum the standard defines: the field zeroed, then complemented."""
    raw = bytes(header)
    if len(raw) < HEADER_MIN:
        raise PacketError(f"a header is at least {HEADER_MIN} bytes, got {len(raw)}")
    zeroed = raw[:10] + b"\x00\x00" + raw[12:]
    return (~ones_sum(zeroed)) & 0xFFFF


def checksum_is_valid(header: bytes) -> bool:
    """A correct header sums to 0xFFFF once its own checksum is included."""
    return ones_sum(header) == 0xFFFF


# --------------------------------------------------------------------------- #
# Capture parsing
# --------------------------------------------------------------------------- #
def parse_capture(text: str) -> list[Packet]:
    """Read `index | hex bytes` records, refusing a gap or a stray token."""
    body = _text(text, "capture")
    packets: list[Packet] = []
    for number, line in enumerate(body.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "|" not in stripped:
            raise PacketError(f"line {number} is not an 'index | hex' record")
        left, right = stripped.split("|", 1)
        try:
            index = int(left.strip(), 10)
        except ValueError as exc:
            raise PacketError(f"line {number} has no integer index: {left.strip()!r}") from exc
        if index != len(packets) + 1:
            raise PacketError(
                f"line {number} is packet {index}, but packet {len(packets) + 1} was due"
            )
        raw = parse_hex(right, f"packet {index}")
        if len(raw) < HEADER_MIN:
            raise PacketError(
                f"packet {index} holds {len(raw)} bytes, under the {HEADER_MIN}-byte header"
            )
        packets.append(Packet(index=index, raw=raw))
    if not packets:
        raise PacketError("the capture holds no packets")
    return packets


def load_capture(path: str | Path | None = None) -> list[Packet]:
    target = Path(path) if path is not None else CAPTURE_FILE
    if not target.is_file():
        raise PacketError(f"file not found: {target.name}")
    try:
        body = target.read_bytes().decode("ascii")
    except UnicodeDecodeError as exc:
        raise PacketError(f"{target.name} is not ASCII text") from exc
    return parse_capture(body)


# --------------------------------------------------------------------------- #
# Decoding one packet
# --------------------------------------------------------------------------- #
def dotted(raw: bytes) -> str:
    if len(raw) != 4:
        raise PacketError(f"an IPv4 address is 4 bytes, got {len(raw)}")
    return ".".join(str(byte) for byte in raw)


def flag_names_of(flags: int) -> tuple[str, ...]:
    named = tuple(
        name for bit, name in ((4, "reserved"), (2, "df"), (1, "mf")) if flags & bit
    )
    return named


def decode(packet: Packet) -> Decoded:
    """Decode one packet, refusing anything whose lengths disagree."""
    raw = bytes(packet.raw)
    index = packet.index
    if len(raw) < HEADER_MIN:
        raise PacketError(f"packet {index} holds {len(raw)} bytes, under {HEADER_MIN}")
    version = raw[0] >> 4
    if version != 4:
        raise PacketError(f"packet {index} is version {version}, not IPv4")
    ihl_words = raw[0] & 0x0F
    if ihl_words < 5:
        raise PacketError(f"packet {index} declares IHL {ihl_words}, under the 5-word minimum")
    ihl_bytes = ihl_words * 4
    if ihl_bytes > len(raw):
        raise PacketError(
            f"packet {index} declares a {ihl_bytes}-byte header but holds {len(raw)} bytes"
        )
    total_length = int.from_bytes(raw[2:4], "big")
    if total_length < ihl_bytes:
        raise PacketError(
            f"packet {index} declares {total_length} bytes, less than its {ihl_bytes}-byte header"
        )
    if total_length > MAX_TOTAL:
        raise PacketError(f"packet {index} declares {total_length} bytes, over {MAX_TOTAL}")
    field = int.from_bytes(raw[6:8], "big")
    flags = field >> 13
    offset_units = field & MAX_OFFSET_UNITS
    protocol = raw[9]
    checksum_stored = int.from_bytes(raw[10:12], "big")
    checksum_computed = header_checksum(raw[:ihl_bytes])

    transport_bytes = 0
    src_port: int | None = None
    dst_port: int | None = None
    if offset_units == 0 and protocol in (6, 17):
        if protocol == 6:
            if len(raw) < ihl_bytes + TCP_MIN:
                raise PacketError(
                    f"packet {index} holds {len(raw)} bytes, short of its TCP header"
                )
            data_offset = (raw[ihl_bytes + 12] >> 4) * 4
            if data_offset < TCP_MIN:
                raise PacketError(
                    f"packet {index} declares a {data_offset}-byte TCP header, under {TCP_MIN}"
                )
            transport_bytes = data_offset
        else:
            if len(raw) < ihl_bytes + UDP_FIXED:
                raise PacketError(
                    f"packet {index} holds {len(raw)} bytes, short of its UDP header"
                )
            transport_bytes = UDP_FIXED
        src_port = int.from_bytes(raw[ihl_bytes:ihl_bytes + 2], "big")
        dst_port = int.from_bytes(raw[ihl_bytes + 2:ihl_bytes + 4], "big")

    declared_payload = total_length - ihl_bytes - transport_bytes
    if declared_payload < 0:
        raise PacketError(
            f"packet {index} declares {total_length} bytes for "
            f"{ihl_bytes + transport_bytes} bytes of headers"
        )
    truncated_by = max(0, total_length - len(raw))
    captured_payload = declared_payload - truncated_by
    if captured_payload < 0:
        raise PacketError(
            f"packet {index} is short by {truncated_by} bytes, more than its "
            f"{declared_payload}-byte payload"
        )
    return Decoded(
        index=index,
        version=version,
        ihl_words=ihl_words,
        ihl_bytes=ihl_bytes,
        total_length=total_length,
        protocol=protocol,
        protocol_name=PROTOCOLS.get(protocol, f"ip-{protocol}"),
        flags=flags,
        flag_names=flag_names_of(flags),
        fragment_offset_units=offset_units,
        fragment_offset_bytes=offset_units * 8,
        ttl=raw[8],
        src=dotted(raw[12:16]),
        dst=dotted(raw[16:20]),
        checksum_stored=checksum_stored,
        checksum_computed=checksum_computed,
        transport_header_bytes=transport_bytes,
        src_port=src_port,
        dst_port=dst_port,
        declared_payload=declared_payload,
        captured_payload=captured_payload,
        truncated_by=truncated_by,
    )


# --------------------------------------------------------------------------- #
# The legacy view
# --------------------------------------------------------------------------- #
def legacy_view(packet: Packet) -> LegacyView:
    """What the fixed-offset parser reports for the same bytes."""
    raw = bytes(packet.raw)
    if len(raw) < HEADER_MIN:
        raise PacketError(f"packet {packet.index} is under {HEADER_MIN} bytes")
    field = int.from_bytes(raw[6:8], "big")
    return LegacyView(
        index=packet.index,
        src_port=int.from_bytes(raw[20:22], "big"),
        dst_port=int.from_bytes(raw[22:24], "big"),
        flags=field & 0x7,
        fragment_offset_units=field,
        checksum_valid=(ones_sum(raw[:HEADER_MIN]) & 0xFFFF) == 0,
        payload=len(raw) - HEADER_MIN - UDP_FIXED,
    )


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(path: str | Path | None = None) -> dict[str, Any]:
    packets = load_capture(path)
    decoded = [decode(packet) for packet in packets]
    views = [legacy_view(packet) for packet in packets]
    by_index = {row.index: row for row in decoded}
    views_by_index = {row.index: row for row in views}
    return {
        "packets": packets,
        "decoded": decoded,
        "views": views,
        "by_index": by_index,
        "views_by_index": views_by_index,
        "valid_checksums": [row.index for row in decoded if row.checksum_ok],
        "bad_checksums": [row.index for row in decoded if not row.checksum_ok],
        "legacy_valid": [row.index for row in views if row.checksum_valid],
        "options_packets": [row.index for row in decoded if row.has_options],
        "fragments": [row.index for row in decoded if row.is_fragment],
        "truncated": [row.index for row in decoded if row.truncated_by],
        "declared_payload": sum(row.declared_payload for row in decoded),
        "captured_payload": sum(row.captured_payload for row in decoded),
        "legacy_payload": sum(row.payload for row in views),
        "truncated_bytes": sum(row.truncated_by for row in decoded),
        "header_bytes": sum(row.ihl_bytes for row in decoded),
        "total_bytes": sum(row.total_length for row in decoded),
        "captured_bytes": sum(packet.captured for packet in packets),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    return {
        "packets": len(measured["packets"]),
        "captured_bytes": measured["captured_bytes"],
        "header_bytes": measured["header_bytes"],
        "total_bytes": measured["total_bytes"],
        "valid_checksums": measured["valid_checksums"],
        "bad_checksums": measured["bad_checksums"],
        "legacy_valid": measured["legacy_valid"],
        "options_packets": measured["options_packets"],
        "fragments": measured["fragments"],
        "truncated": measured["truncated"],
        "truncated_bytes": measured["truncated_bytes"],
        "declared_payload": measured["declared_payload"],
        "captured_payload": measured["captured_payload"],
        "legacy_payload": measured["legacy_payload"],
        "decoded": [
            {
                "index": row.index,
                "version": row.version,
                "ihl_words": row.ihl_words,
                "ihl_bytes": row.ihl_bytes,
                "total_length": row.total_length,
                "protocol": row.protocol_name,
                "flags": list(row.flag_names),
                "fragment_offset_units": row.fragment_offset_units,
                "fragment_offset_bytes": row.fragment_offset_bytes,
                "ttl": row.ttl,
                "src": row.src,
                "dst": row.dst,
                "checksum_ok": row.checksum_ok,
                "src_port": row.src_port,
                "dst_port": row.dst_port,
                "declared_payload": row.declared_payload,
                "captured_payload": row.captured_payload,
                "truncated_by": row.truncated_by,
            }
            for row in measured["decoded"]
        ],
        "legacy": [
            {
                "index": row.index,
                "src_port": row.src_port,
                "dst_port": row.dst_port,
                "flags": row.flags,
                "fragment_offset_units": row.fragment_offset_units,
                "checksum_valid": row.checksum_valid,
                "payload": row.payload,
            }
            for row in measured["views"]
        ],
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:
        return False


def _refuses(call) -> bool:
    try:
        call()
    except PacketError:
        return True
    return False


def audit(
    measured: dict[str, Any],
    *,
    read_decoded: Callable[[Sequence[Packet]], list[Decoded]] | None = None,
) -> list[tuple[str, bool]]:
    """Every check compares the measured numbers with an independent read."""
    reader = read_decoded or (lambda packets: [decode(packet) for packet in packets])
    packet_rows = measured["packets"]
    decoded = measured["decoded"]
    by_index = measured["by_index"]
    views = measured["views_by_index"]

    def independent() -> list[Decoded]:
        return reader(packet_rows)

    def independent_payload() -> int:
        total = 0
        for row in independent():
            if row.fragment_offset_units:
                total += row.total_length - row.ihl_bytes
            elif row.protocol in (6, 17):
                total += row.total_length - row.ihl_bytes - row.transport_header_bytes
            else:
                total += row.total_length - row.ihl_bytes
        return total

    checks = [
        (
            "every_packet_decodes",
            lambda: len(independent()) == len(decoded) == 6,
        ),
        (
            "the_header_length_is_counted_in_thirty_two_bit_words",
            lambda: independent()[1].ihl_words == 6
            and independent()[1].ihl_bytes == 24 == independent()[1].ihl_words * 4
            and independent()[0].ihl_words == 5,
        ),
        (
            "only_one_packet_carries_options",
            lambda: measured["options_packets"] == [2],
        ),
        (
            "ports_are_read_after_the_options",
            lambda: (independent()[1].src_port, independent()[1].dst_port) == (8443, 51001),
        ),
        (
            "the_legacy_parser_reads_ports_at_a_fixed_offset",
            lambda: (views[2].src_port, views[2].dst_port) == (257, 256)
            and (views[2].src_port, views[2].dst_port) != (8443, 51001),
        ),
        (
            "flags_are_the_top_three_bits",
            lambda: by_index[1].flags == 0b010
            and by_index[1].flag_names == ("df",)
            and by_index[4].flags == 0b001
            and by_index[4].flag_names == ("mf",),
        ),
        (
            "the_fragment_offset_is_the_low_thirteen_bits",
            lambda: by_index[5].fragment_offset_units == 185
            and by_index[5].fragment_offset_bytes == 1480,
        ),
        (
            "the_legacy_flags_read_the_bottom_of_the_field",
            lambda: views[4].flags == 0 and views[5].flags == 1,
        ),
        (
            "the_legacy_offset_is_the_whole_field",
            lambda: views[1].fragment_offset_units == 16_384
            and views[4].fragment_offset_units == 8_192
            and by_index[1].fragment_offset_units == 0,
        ),
        (
            "only_the_two_fragments_are_marked",
            lambda: measured["fragments"] == [4, 5],
        ),
        (
            "a_continuation_fragment_has_no_transport_header",
            lambda: by_index[5].src_port is None
            and by_index[5].dst_port is None
            and by_index[5].transport_header_bytes == 0,
        ),
        (
            "a_first_fragment_still_has_one",
            lambda: (by_index[4].src_port, by_index[4].dst_port) == (123, 40001),
        ),
        (
            "the_checksum_is_verified_with_its_own_field_zeroed",
            lambda: measured["valid_checksums"] == [1, 2, 3, 4, 5]
            and by_index[1].checksum_stored == by_index[1].checksum_computed,
        ),
        (
            "exactly_one_packet_fails_its_checksum",
            lambda: measured["bad_checksums"] == [6]
            and by_index[6].checksum_stored != by_index[6].checksum_computed,
        ),
        (
            "a_correct_header_sums_to_ffff",
            lambda: checksum_is_valid(measured["packets"][0].raw[:20]) is True
            and checksum_is_valid(measured["packets"][5].raw[:20]) is False,
        ),
        (
            "the_legacy_checksum_includes_the_field_so_nothing_verifies",
            lambda: measured["legacy_valid"] == [] and len(measured["decoded"]) == 6,
        ),
        (
            "the_total_length_is_the_authority",
            lambda: by_index[3].total_length == 40
            and measured["packets"][2].captured == 36,
        ),
        (
            "a_short_capture_is_disclosed",
            lambda: by_index[3].truncated_by == 4
            and by_index[3].declared_payload == 12
            and by_index[3].captured_payload == 8,
        ),
        (
            "the_legacy_payload_uses_the_captured_size_only",
            lambda: views[3].payload == 8
            and measured["legacy_payload"] == 104
            and measured["legacy_payload"] != measured["declared_payload"] == 76,
        ),
        (
            "payload_accounting_matches_an_independent_sum",
            lambda: measured["declared_payload"] == independent_payload() == 76,
        ),
        (
            "a_non_ipv4_version_is_refused",
            lambda: _refuses(lambda: decode(Packet(1, b"\x65" + b"\x00" * 19))),
        ),
        (
            "an_ihl_below_five_is_refused",
            lambda: _refuses(lambda: decode(Packet(1, b"\x44" + b"\x00" * 19))),
        ),
        (
            "a_header_longer_than_the_packet_is_refused",
            lambda: _refuses(lambda: decode(Packet(1, b"\x46" + b"\x00" * 19))),
        ),
        (
            "a_capture_shorter_than_its_headers_is_refused",
            lambda: _refuses(
                lambda: decode(
                    Packet(1, b"\x45\x00\x00\x08\x00\x01\x00\x00\x40\x11" + b"\x00" * 10)
                )
            ),
        ),
        (
            "a_malformed_hex_record_is_refused",
            lambda: _refuses(lambda: parse_capture("1 | 45 0 00\n")),
        ),
        (
            "an_out_of_order_index_is_refused",
            lambda: _refuses(lambda: parse_capture("2 | 45 00\n")),
        ),
        (
            "rebuild_is_deterministic",
            lambda: independent() == decoded,
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_packets(measured: dict[str, Any]) -> str:
    lines = [
        "  #  proto  ihl  len  cap  flags     offset  ports          payload  checksum"
    ]
    for row in measured["decoded"]:
        flags = ",".join(row.flag_names) if row.flag_names else "-"
        ports = (
            f"{row.src_port}->{row.dst_port}"
            if row.src_port is not None
            else "fragment"
        )
        checksum = "ok" if row.checksum_ok else "BAD"
        payload = f"{row.declared_payload}"
        if row.truncated_by:
            payload += f"/{row.captured_payload}"
        lines.append(
            f"  {row.index:<3}{row.protocol_name:<7}{row.ihl_bytes:<5}"
            f"{row.total_length:<5}{measured['packets'][row.index - 1].captured:<5}"
            f"{flags:<10}{row.fragment_offset_units:<8}{ports:<15}"
            f"{payload:<9}{checksum}"
        )
    return "\n".join(lines)


def run_demo() -> int:
    measured = measure()
    by_index = measured["by_index"]
    views = measured["views_by_index"]
    options = by_index[2]
    legacy_options = views[2]
    first_fragment = by_index[4]
    last_fragment = by_index[5]
    short = by_index[3]
    print("Packet analyser -- a header is a bit field, and a field has a unit")
    print("=" * 68)
    print()
    print(
        f"Capture: {len(measured['packets'])} packets, {measured['captured_bytes']} bytes "
        f"held, {measured['total_bytes']} declared."
    )
    print()
    print(render_packets(measured))
    print()
    print("1. The header length is counted in 32-bit words.")
    print("   " + LEGACY_HEADER)
    print(
        f"   packet 2 declares IHL {options.ihl_words}, so its header is "
        f"{options.ihl_bytes} bytes; reading ports at byte 20 gives "
        f"{legacy_options.src_port}->{legacy_options.dst_port},"
    )
    print(
        f"   and reading them after the options gives "
        f"{options.src_port}->{options.dst_port}."
    )
    print()
    print("2. Flags and the fragment offset share one 16-bit field.")
    print("   " + LEGACY_FLAGS)
    print(
        f"   packet 1 is a plain DF packet, but the legacy offset reads "
        f"{views[1].fragment_offset_units} units ({views[1].fragment_offset_units * 8} bytes)."
    )
    print(
        f"   packet 4 (first fragment) reads as flags {views[4].flags} at offset "
        f"{views[4].fragment_offset_units}; the truth is mf at offset "
        f"{first_fragment.fragment_offset_units}."
    )
    print(
        f"   packet 5 (last fragment) reads as flags {views[5].flags}, which is MF; "
        f"its offset {last_fragment.fragment_offset_units} units "
        f"({last_fragment.fragment_offset_bytes} bytes) is right by accident."
    )
    print()
    print("3. A checksum is verified with its own field zeroed.")
    print("   " + LEGACY_CHECKSUM)
    print(
        f"   the rebuild accepts {len(measured['valid_checksums'])} of "
        f"{len(measured['decoded'])} packets and rejects {measured['bad_checksums']}, "
        "the one whose TTL changed."
    )
    print(
        f"   the legacy test accepts {len(measured['legacy_valid'])} of "
        f"{len(measured['decoded'])}: a correct header sums to 0xFFFF, never 0."
    )
    print()
    print("4. The total length is the authority.")
    print("   " + LEGACY_PAYLOAD)
    print(
        f"   packet 3 declares {short.total_length} bytes and holds "
        f"{measured['packets'][2].captured}: payload {short.declared_payload} declared, "
        f"{short.captured_payload} captured, truncated by {short.truncated_by}."
    )
    print(
        f"   the legacy subtraction reports {views[3].payload} bytes and never mentions the "
        f"missing {short.truncated_by}."
    )
    print()
    print("Checks")
    results = audit(measured)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: "
        f"{len(measured['packets'])} packets hold {measured['captured_bytes']} of "
        f"{measured['total_bytes']} declared bytes and decode to "
        f"{len(measured['valid_checksums'])} valid checksums against "
        f"{len(measured['legacy_valid'])} under the legacy test; packet 2's "
        f"{options.ihl_bytes}-byte header moves its ports from the legacy's "
        f"{legacy_options.src_port}->{legacy_options.dst_port} to "
        f"{options.src_port}->{options.dst_port}; the legacy offset calls a DF packet "
        f"a fragment at {views[1].fragment_offset_units} units and reverses which "
        f"fragment is which; payloads declare {measured['declared_payload']} bytes, "
        f"capture {measured['captured_payload']} and the legacy reports "
        f"{measured['legacy_payload']}; {passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
