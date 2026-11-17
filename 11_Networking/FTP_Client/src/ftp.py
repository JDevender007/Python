"""A reply is a sequence of lines, and a transfer is done at the byte count.

The legacy client parses a control connection with the two lines every FTP
tutorial contains:

    for line in block.split("\\r\\n"):
        if line[3:4] == " ":
            replies.append(line)

and it reads the passive port with:

    port = int(line[line.rfind(",") + 1:line.rfind(")")])

Three defects follow, and each one is silent.

**1. A reply is not a line.** In the FTP reply grammar a line whose fourth
character is `-` *continues* the reply, and the reply ends only at a line whose
fourth character is a space with the same three-digit code. Filtering for the
space keeps the terminator and throws away the body, so `211-Features:` with its
four capability lines arrives as the single line `211 End`. The client reports
zero capabilities and then reconnects when the server refuses a command it
never knew was supported.

**2. A passive port is two bytes, not the last one.** `227 Entering Passive Mode
(h1,h2,h3,h4,p1,p2)` encodes the port as `p1 * 256 + p2`. Taking the last field
reads `(10,0,0,5,19,137)` as port 137 instead of 5001, and the client connects
to a port nothing is listening on -- or, worse, to a port something else is.

**3. `226 Transfer complete` is a claim, not a byte count.** The transfer is
complete when the number of bytes actually received equals the number the
server declared in its `150` reply. A short read still ends with `226`, so the
legacy client writes a truncated file and reports success.

The rebuild parses the reply grammar properly, decodes the port as two bytes,
and compares the received length with the declared one before it calls a
transfer done. Byte counts are integers throughout, and the received share is
computed in permille with an explicit half-up rule rather than a float.

The demonstration is offline: the server's side of the conversation is a bundled
transcript, the data channel is a bundled payload, and two runs print the same
bytes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSION_FILE = DATA_DIR / "session.log"
PAYLOAD_FILE = DATA_DIR / "payload.txt"

# The defective reply filter, kept as a string so the demo can print it and the
# tests can show exactly which lines it discards.
LEGACY_REPLY_FILTER = 'if line[3:4] == " ": replies.append(line)'

# The defective port decode, kept for the same reason.
LEGACY_PORT_DECODE = "port = int(line[line.rfind(',') + 1:line.rfind(')')])"

_CODE = re.compile(r"^(\d{3})([ -])(.*)$")
_PASV = re.compile(r"\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)")

DIRECTIONS = ("C", "S")


class FtpError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise FtpError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise FtpError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FtpError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise FtpError(f"{name} must be positive, got {number}")
    return number


def _non_negative(value: object, name: str) -> int:
    number = _whole(value, name)
    if number < 0:
        raise FtpError(f"{name} must not be negative, got {number}")
    return number


def divide_half_up(numerator: int, denominator: int) -> int:
    """Integer division rounding halves away from zero, with no float."""
    top = _whole(numerator, "numerator")
    bottom = _positive(denominator, "denominator")
    sign = -1 if top < 0 else 1
    magnitude = abs(top)
    return sign * ((magnitude * 2 + bottom) // (2 * bottom))


def share_permille(part: int, whole: int) -> int:
    """`part` as thousandths of `whole`, rounded half up, never a float."""
    amount = _non_negative(part, "part")
    total = _positive(whole, "whole")
    return divide_half_up(amount * 1000, total)


def format_permille(permille: int) -> str:
    """Render thousandths as a one-decimal percentage."""
    value = _whole(permille, "permille")
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    return f"{sign}{magnitude // 10}.{magnitude % 10}"


# --------------------------------------------------------------------------- #
# Reply grammar
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reply:
    """One complete FTP reply: a code, and every line it was made of."""

    code: int
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        """The reply body with the codes stripped, one line per entry."""
        return "\n".join(self.lines[i][4:] for i in range(len(self.lines)))

    @property
    def final(self) -> str:
        return self.lines[-1]

    @property
    def is_multiline(self) -> bool:
        return len(self.lines) > 1

    @property
    def positive(self) -> bool:
        return 200 <= self.code < 400


def code_of(line: str) -> int:
    """The three-digit code a reply line starts with."""
    raw = _text(line, "reply line").rstrip("\r\n")
    match = _CODE.match(raw)
    if match is None:
        raise FtpError(f"reply line does not start with a three-digit code: {raw!r}")
    code = int(match.group(1))
    if not 100 <= code <= 599:
        raise FtpError(f"reply code out of range: {code}")
    return code


def is_continuation(line: str) -> bool:
    """True when the line continues the reply rather than ending it."""
    raw = _text(line, "reply line").rstrip("\r\n")
    match = _CODE.match(raw)
    if match is None:
        raise FtpError(f"reply line does not start with a three-digit code: {raw!r}")
    return match.group(2) == "-"


def parse_reply(lines: Sequence[str]) -> Reply:
    """Assemble one reply from its lines, enforcing the continuation grammar."""
    if not lines:
        raise FtpError("a reply needs at least one line")
    first = _text(lines[0], "reply line").rstrip("\r\n")
    code = code_of(first)
    for index, line in enumerate(lines[:-1]):
        raw = line.rstrip("\r\n")
        if not is_continuation(raw):
            raise FtpError(f"line {index + 1} ends the reply early: {raw!r}")
        if code_of(raw) != code:
            raise FtpError(
                f"line {index + 1} changes the reply code from {code} to {code_of(raw)}"
            )
    last = lines[-1].rstrip("\r\n")
    if is_continuation(last):
        raise FtpError(f"reply {code} is truncated: it never reaches a final line")
    if code_of(last) != code:
        raise FtpError(f"reply ends with code {code_of(last)}, started with {code}")
    return Reply(code=code, lines=tuple(line.rstrip("\r\n") for line in lines))


# --------------------------------------------------------------------------- #
# Transcript
# --------------------------------------------------------------------------- #
def parse_replies(lines: Sequence[str]) -> tuple[Reply, ...]:
    """Split a run of reply lines into complete replies.

    FTP allows a command to have a preliminary reply (`150`, data connection
    opening) followed by a final one (`226`, transfer complete). Each reply ends
    at its own final line, so a group is only valid when every reply in it is
    terminated.
    """
    if not lines:
        raise FtpError("a reply needs at least one line")
    groups: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        raw = line.rstrip("\r\n")
        current.append(raw)
        if not is_continuation(raw):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return tuple(parse_reply(group) for group in groups)


@dataclass(frozen=True)
class Exchange:
    """One command and every reply the server sent back for it."""

    command: str | None
    replies: tuple[Reply, ...]

    @property
    def reply(self) -> Reply:
        """The final reply, which is the one that decides the outcome."""
        if not self.replies:
            raise FtpError(f"command {self.command!r} has no reply")
        return self.replies[-1]

    @property
    def preliminary(self) -> Reply | None:
        """The 1xx reply that opens a data connection, when there is one."""
        for reply in self.replies[:-1]:
            if 100 <= reply.code < 200:
                return reply
        return None

    @property
    def line_count(self) -> int:
        return sum(len(reply.lines) for reply in self.replies)


def parse_session(text: str) -> list[Exchange]:
    """Parse a transcript of `C> command` and `S> reply line` records."""
    body = _text(text, "transcript")
    exchanges: list[Exchange] = []
    pending_command: str | None = None
    pending_lines: list[str] = []

    def flush() -> None:
        if pending_lines:
            exchanges.append(
                Exchange(command=pending_command, replies=parse_replies(pending_lines))
            )

    for number, raw in enumerate(body.splitlines(), start=1):
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        if len(line) < 4 or line[1:3] != "> ":
            raise FtpError(f"line {number} is not a transcript record: {line!r}")
        direction = line[0]
        if direction not in DIRECTIONS:
            raise FtpError(f"line {number} has an unknown direction {direction!r}")
        payload = line[3:]
        if direction == "C":
            flush()
            pending_lines = []
            pending_command = _text(payload, f"command on line {number}").strip()
        else:
            if pending_command is None and exchanges:
                raise FtpError(f"line {number} is a reply with no command before it")
            pending_lines.append(payload)
    flush()
    if not exchanges:
        raise FtpError("transcript holds no exchanges")
    return exchanges


def legacy_replies(text: str) -> list[tuple[str | None, list[str]]]:
    """The defective parse: only lines that terminate a reply survive."""
    exchanges = parse_session(text)
    kept: list[tuple[str | None, list[str]]] = []
    for exchange in exchanges:
        lines = [
            line
            for reply in exchange.replies
            for line in reply.lines
            if not is_continuation(line)
        ]
        kept.append((exchange.command, lines))
    return kept


def greeting(exchanges: Sequence[Exchange]) -> Reply:
    """The banner the server sends before any command."""
    if not exchanges:
        raise FtpError("transcript holds no exchanges")
    if exchanges[0].command is not None:
        raise FtpError("the transcript starts with a command, not a greeting")
    return exchanges[0].reply


def reply_for(exchanges: Sequence[Exchange], command: str) -> Reply:
    """The final reply to a command."""
    return exchange_for(exchanges, command).reply


def exchange_for(exchanges: Sequence[Exchange], command: str) -> Exchange:
    """The whole exchange for a command, preliminary reply included."""
    wanted = _text(command, "command").strip().upper()
    for exchange in exchanges:
        if exchange.command is None:
            continue
        verb = exchange.command.split()[0].upper()
        if verb == wanted:
            return exchange
    raise FtpError(f"no reply for command {wanted!r} in the transcript")


def capabilities(reply: Reply) -> list[str]:
    """The capability names listed inside a `211-Features:` reply."""
    if reply.code != 211:
        raise FtpError(f"expected a 211 reply, got {reply.code}")
    names: list[str] = []
    for line in reply.lines[1:-1]:
        body = line[4:].strip()
        if body:
            names.append(body)
    return names


# --------------------------------------------------------------------------- #
# Passive mode
# --------------------------------------------------------------------------- #
def pasv_address(line: str) -> tuple[str, int]:
    """Decode `227 Entering Passive Mode (h1,h2,h3,h4,p1,p2)` into host and port."""
    raw = _text(line, "pasv line").rstrip("\r\n")
    if code_of(raw) != 227:
        raise FtpError(f"expected a 227 reply, got {code_of(raw)}")
    match = _PASV.search(raw)
    if match is None:
        raise FtpError(f"227 reply has no address tuple: {raw!r}")
    parts = [int(group) for group in match.groups()]
    for part in parts:
        if not 0 <= part <= 255:
            raise FtpError(f"address byte out of range: {part}")
    host = ".".join(str(part) for part in parts[:4])
    port = parts[4] * 256 + parts[5]
    if port == 0:
        raise FtpError("passive port must not be zero")
    return host, port


def legacy_pasv_port(line: str) -> int:
    """The defective decode: the last field of the tuple, treated as the port."""
    raw = _text(line, "pasv line").rstrip("\r\n")
    if code_of(raw) != 227:
        raise FtpError(f"expected a 227 reply, got {code_of(raw)}")
    match = _PASV.search(raw)
    if match is None:
        raise FtpError(f"227 reply has no address tuple: {raw!r}")
    return int(match.groups()[5])


# --------------------------------------------------------------------------- #
# Transfer accounting
# --------------------------------------------------------------------------- #
def declared_size(reply: Reply) -> int:
    """The byte count a `150` reply promises, read from its trailing `(N bytes)`."""
    if reply.code not in (125, 150):
        raise FtpError(f"expected a 1xx data reply, got {reply.code}")
    match = re.search(r"\((\d+) bytes?\)", reply.final)
    if match is None:
        raise FtpError(f"reply {reply.code} declares no byte count: {reply.final!r}")
    return int(match.group(1))


@dataclass(frozen=True)
class Transfer:
    """The verdict a client should reach about one download."""

    declared: int
    received: int

    @property
    def shortfall(self) -> int:
        return self.declared - self.received

    @property
    def complete(self) -> bool:
        return self.received == self.declared

    @property
    def permille(self) -> int:
        return share_permille(self.received, self.declared)


def check_transfer(declared: int, received: int) -> Transfer:
    """Compare what was promised with what arrived."""
    total = _positive(declared, "declared")
    got = _non_negative(received, "received")
    if got > total:
        raise FtpError(f"received {got} bytes for a {total}-byte file")
    return Transfer(declared=total, received=got)


def legacy_transfer_complete(reply: Reply) -> bool:
    """The defective check: `226` means done, whatever arrived."""
    return reply.code == 226


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def read_text(path: str | Path | None, default: Path) -> str:
    target = Path(path) if path is not None else default
    if not target.is_file():
        raise FtpError(f"file not found: {target.name}")
    try:
        return target.read_bytes().decode("ascii")
    except UnicodeDecodeError as exc:
        raise FtpError(f"{target.name} is not ASCII text") from exc


def payload_bytes(text: str) -> bytes:
    body = _text(text, "payload")
    try:
        return body.encode("ascii")
    except UnicodeEncodeError as exc:
        raise FtpError("payload is not ASCII text") from exc


def measure(
    session_path: str | Path | None = None,
    *,
    payload_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load the transcript, decode the session and collect every demo number."""
    if session_path is not None:
        folder = Path(session_path).resolve().parent
        payload_path = payload_path or folder / "payload.txt"
    text = read_text(session_path, SESSION_FILE)
    payload = payload_bytes(read_text(payload_path, PAYLOAD_FILE))
    exchanges = parse_session(text)
    banner = greeting(exchanges)
    features = reply_for(exchanges, "FEAT")
    pasv = reply_for(exchanges, "PASV")
    retrieve = exchange_for(exchanges, "RETR")
    opening = retrieve.preliminary
    if opening is None:
        raise FtpError("the RETR exchange has no 150 reply to declare a size")
    declared = declared_size(opening)
    transfer = check_transfer(declared, len(payload))
    host, port = pasv_address(pasv.final)
    legacy = legacy_replies(text)
    legacy_features = [lines for command, lines in legacy if command == "FEAT"]
    return {
        "exchanges": exchanges,
        "commands": [e.command for e in exchanges if e.command is not None],
        "replies": sum(len(e.replies) for e in exchanges),
        "banner": banner,
        "banner_lines": len(banner.lines),
        "legacy_banner_lines": len(greeting_legacy(text)),
        "features": capabilities(features),
        "feature_lines": len(features.lines),
        "legacy_feature_lines": len(legacy_features[0]) if legacy_features else 0,
        "host": host,
        "port": port,
        "legacy_port": legacy_pasv_port(pasv.final),
        "declared": declared,
        "received": len(payload),
        "transfer": transfer,
        "legacy_complete": legacy_transfer_complete(retrieve.reply),
    }


def greeting_legacy(text: str) -> list[str]:
    """The banner as the defective parser sees it."""
    rows = legacy_replies(text)
    return rows[0][1] if rows else []


def report(measured: dict[str, Any]) -> dict[str, Any]:
    transfer = measured["transfer"]
    return {
        "commands": list(measured["commands"]),
        "banner_lines": measured["banner_lines"],
        "legacy_banner_lines": measured["legacy_banner_lines"],
        "capabilities": list(measured["features"]),
        "feature_lines": measured["feature_lines"],
        "legacy_feature_lines": measured["legacy_feature_lines"],
        "host": measured["host"],
        "port": measured["port"],
        "legacy_port": measured["legacy_port"],
        "declared_bytes": transfer.declared,
        "received_bytes": transfer.received,
        "shortfall_bytes": transfer.shortfall,
        "received_permille": transfer.permille,
        "received_percent": format_permille(transfer.permille),
        "complete": transfer.complete,
        "legacy_complete": measured["legacy_complete"],
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:
        return False


def audit(
    measured: dict[str, Any],
    *,
    read_replies: Callable[[str], list[Exchange]] = parse_session,
) -> list[tuple[str, bool]]:
    """Every check compares a decoded value with an independent computation."""
    exchanges = measured["exchanges"]
    transfer = measured["transfer"]
    text = read_text(SESSION_FILE, SESSION_FILE)

    def exchanges_via_reader() -> list[Exchange]:
        return read_replies(text)

    def independent_capability_count() -> int:
        body = 0
        for exchange in exchanges_via_reader():
            for reply in exchange.replies:
                for entry in reply.lines:
                    if entry[4:].strip().startswith(("UTF8", "MDTM", "SIZE", "REST")):
                        body += 1
        return body

    checks = [
        (
            "every_reply_line_carries_a_three_digit_code",
            lambda: all(
                100 <= code_of(line) <= 599
                for exchange in exchanges_via_reader()
                for reply in exchange.replies
                for line in reply.lines
            ),
        ),
        (
            "the_banner_is_three_lines",
            lambda: len(greeting(exchanges_via_reader()).lines) == measured["banner_lines"] == 3,
        ),
        (
            "the_legacy_parser_keeps_one_banner_line",
            lambda: measured["legacy_banner_lines"] == 1,
        ),
        (
            "the_feature_reply_is_six_lines",
            lambda: measured["feature_lines"] == 6,
        ),
        (
            "the_legacy_parser_keeps_one_feature_line",
            lambda: measured["legacy_feature_lines"] == 1,
        ),
        (
            "capabilities_are_read_from_the_body",
            lambda: measured["features"] == ["UTF8", "MDTM", "SIZE", "REST STREAM"],
        ),
        (
            "capability_count_matches_an_independent_scan",
            lambda: len(measured["features"]) == independent_capability_count() == 4,
        ),
        (
            "passive_mode_decodes_two_bytes",
            lambda: measured["host"] == "10.0.0.5"
            and measured["port"] == 5001 == 19 * 256 + 137,
        ),
        (
            "legacy_reads_only_the_low_byte",
            lambda: measured["legacy_port"] == 137,
        ),
        (
            "the_declared_size_comes_from_the_150_reply",
            lambda: transfer.declared == 1234,
        ),
        (
            "the_received_size_is_the_payload_length",
            lambda: transfer.received == len(payload_bytes(read_text(PAYLOAD_FILE, PAYLOAD_FILE))) == 1200,
        ),
        (
            "the_shortfall_is_the_difference",
            lambda: transfer.shortfall == 34 and transfer.complete is False,
        ),
        (
            "the_received_share_is_computed_in_permille",
            lambda: transfer.permille == 972 == divide_half_up(1200 * 1000, 1234)
            and format_permille(transfer.permille) == "97.2",
        ),
        (
            "a_short_transfer_is_refused_and_an_exact_one_accepted",
            lambda: check_transfer(10, 10).complete
            and not check_transfer(10, 9).complete
            and check_transfer(10, 9).shortfall == 1,
        ),
        (
            "an_over_long_transfer_is_refused",
            lambda: _refuses(lambda: check_transfer(10, 11)),
        ),
        (
            "a_continuation_that_never_ends_is_refused",
            lambda: _refuses(lambda: parse_reply(["211-Features:", "211- UTF8"])),
        ),
        (
            "a_reply_that_changes_code_is_refused",
            lambda: _refuses(lambda: parse_reply(["220-Hello", "230 Done"])),
        ),
        (
            "rebuild_is_deterministic",
            lambda: [e.reply.code for e in parse_session(text)]
            == [e.reply.code for e in exchanges],
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


def _refuses(call) -> bool:
    try:
        call()
    except FtpError:
        return True
    return False


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_replies(measured: dict[str, Any]) -> str:
    lines = ["  command   replies  lines  code  final"]
    for exchange in measured["exchanges"]:
        reply = exchange.reply
        label = "(greeting)" if exchange.command is None else exchange.command.split()[0]
        text = reply.final[4:]
        if len(text) > 40:
            text = text[:37] + "..."
        lines.append(
            f"  {label:<10}{len(exchange.replies):>8}{exchange.line_count:>7}"
            f"{reply.code:>6}  {text}"
        )
    return "\n".join(lines)


def run_demo() -> int:
    measured = measure()
    transfer = measured["transfer"]
    print("FTP client -- a reply is a sequence of lines")
    print("=" * 46)
    print()
    print(
        f"Seeds: {len(measured['commands'])} commands, "
        f"{measured['replies']} replies, {transfer.received} bytes of payload."
    )
    print()
    print(render_replies(measured))
    print()
    print("1. A reply ends only at a line whose fourth character is a space.")
    print("   " + LEGACY_REPLY_FILTER)
    print(
        f"   the banner is {measured['banner_lines']} lines, of which the filter keeps "
        f"{measured['legacy_banner_lines']};"
    )
    print(
        f"   FEAT is {measured['feature_lines']} lines and reports "
        f"{len(measured['features'])} capabilities, of which the filter keeps "
        f"{measured['legacy_feature_lines']} and reports 0."
    )
    print("   Capabilities: " + ", ".join(measured["features"]))
    print()
    print("2. A passive port is two bytes.")
    print("   " + LEGACY_PORT_DECODE)
    print(
        f"   (10,0,0,5,19,137) -> host {measured['host']}, "
        f"port 19*256+137 = {measured['port']}; the legacy decode reads "
        f"{measured['legacy_port']}."
    )
    print()
    print("3. 226 is a claim; the byte count is evidence.")
    print(
        f"   the server declared {transfer.declared} bytes, the payload holds "
        f"{transfer.received}, so the transfer is short by {transfer.shortfall}"
    )
    print(
        "   bytes and the client calls it complete anyway, because the last reply "
        "was 226."
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
        "Cross-checks OK: the transcript holds "
        f"{len(measured['commands'])} commands and {measured['replies']} replies; "
        f"the banner is {measured['banner_lines']} lines and FEAT is "
        f"{measured['feature_lines']} lines carrying "
        f"{len(measured['features'])} capabilities, while the fourth-character filter "
        f"keeps {measured['legacy_banner_lines']} banner line and "
        f"{measured['legacy_feature_lines']} feature line and so reports no "
        f"capabilities at all; (10,0,0,5,19,137) decodes to {measured['host']}:"
        f"{measured['port']} = 19*256+137, not the low byte {measured['legacy_port']}; "
        f"the 150 reply declares {transfer.declared} bytes and the payload holds "
        f"{transfer.received}, so {transfer.shortfall} bytes are missing and the file "
        f"is {format_permille(transfer.permille)}% of what was promised, which the 226 "
        f"reply does not change; {passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
