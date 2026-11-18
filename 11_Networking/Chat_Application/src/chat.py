"""A chat message is a frame, not a line, and a byte count is not a character count.

The legacy reader is the one every socket tutorial shows:

    chunk = sock.recv(4096).decode("utf-8", errors="replace")
    for line in chunk.split("\\n"):
        deliver(line)

It is wrong in four ways, and all four are visible in one conversation.

**1. A newline is not a message boundary.** TCP hands you bytes, not messages. A
message whose own text contains a newline -- "line one\\nline two" -- arrives as
one write and leaves the legacy reader as *two* messages. The receiver can never
tell that the sender meant one.

**2. A read is not a message.** `recv(4096)` returns whatever has arrived, so a
read can hold half a frame. The legacy reader delivers that half as though it
were a whole message, and the rest arrives later as another one. A 41-byte
conversation read in 7-byte pieces becomes ten "messages", none of them right.

**3. A length prefix counts bytes, not characters.** "caf\\u00e9" is four
characters and five bytes in UTF-8. A header written from `len(text)` promises
four bytes and then eats the first byte of the next frame.

**4. Decoding each read separately splits characters.** `errors="replace"` turns
the first half of a two-byte sequence into U+FFFD, so a perfectly valid message
arrives corrupted -- silently, because "replace" never raises.

So this module frames every message as `<byte count>:<utf-8 payload>`, keeps one
decoder per connection that holds a partial frame until it is complete, and
refuses anything that is not exactly one frame. The legacy path is kept beside
it, executable, so every claim above is reproduced with a number.

The demonstration is offline: a bundled chat log, framed and read in 7-byte
pieces through an in-memory channel -- no socket is opened.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_FILE = DATA_DIR / "chat_log.txt"

#: The legacy reader, transcribed -- and executable, line for line.
LEGACY_READER = ('chunk = sock.recv(4096).decode("utf-8", errors="replace")\n'
                 'for line in chunk.split("\\n"):\n'
                 '    deliver(line)')

#: A frame is a byte count, then a colon, then exactly that many bytes.
FRAME_SEP = b":"

#: No message is larger than this many bytes.
MAX_MESSAGE = 4096

#: A header is at most this many digits -- 4096 needs four.
MAX_HEADER = len(str(MAX_MESSAGE))

#: How many bytes one in-memory read hands back by default.
READ_LIMIT = 7

#: The escapes a bundled log line may carry.
ESCAPES = {"\\": "\\", "n": "\n", "r": "\r", "t": "\t"}


class ChatError(Exception):
    """A frame, a log line, a message or a read that cannot be honoured, and why."""


# --------------------------------------------------------------------------- #
# Integer arithmetic and validation
# --------------------------------------------------------------------------- #
def divide_half_up(numerator: int, denominator: int) -> int:
    """`numerator / denominator` rounded half-up, from integers only."""
    for value, name in ((numerator, "a numerator"), (denominator, "a denominator")):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ChatError(f"{name} is a whole number, got {value!r}")
    if denominator <= 0:
        raise ChatError(f"a denominator is positive, got {denominator}")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return sign * quotient


def _whole(value, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ChatError(f"{name} is a whole number, got {value!r}")
    return value


def _text(value, name: str) -> str:
    if not isinstance(value, str):
        raise ChatError(f"{name} is text, got {type(value).__name__}")
    if not value.strip():
        raise ChatError(f"{name} is text, and not blank")
    return value


def _bytes(value, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray)):
        raise ChatError(f"{name} is bytes, got {type(value).__name__}")
    return bytes(value)


# --------------------------------------------------------------------------- #
# Escapes in a bundled log line
# --------------------------------------------------------------------------- #
def unescape(field: str) -> str:
    """`"line one\\nline two"` -> the real newline; `\\u00e9` -> one character.

    Only four escapes and `\\uXXXX` are accepted, because a log line is data and
    an unknown escape is a mistake worth naming rather than passing through.
    """
    if not isinstance(field, str):
        raise ChatError(f"a field is text, got {type(field).__name__}")
    out: list[str] = []
    index = 0
    while index < len(field):
        character = field[index]
        if character != "\\":
            out.append(character)
            index += 1
            continue
        if index + 1 >= len(field):
            raise ChatError(f"a field ends with a lone backslash: {field!r}")
        marker = field[index + 1]
        if marker == "u":
            digits = field[index + 2:index + 6]
            if len(digits) != 4 or any(digit not in "0123456789abcdefABCDEF"
                                       for digit in digits):
                raise ChatError(f"'\\u' needs four hex digits, got "
                                f"{field[index:index + 6]!r}")
            value = int(digits, 16)
            if 0xD800 <= value <= 0xDFFF:
                raise ChatError(f"'\\u{digits}' is a surrogate, not a character")
            out.append(chr(value))
            index += 6
            continue
        if marker not in ESCAPES:
            raise ChatError(f"unknown escape '\\{marker}' in {field!r}")
        out.append(ESCAPES[marker])
        index += 2
    return "".join(out)


# --------------------------------------------------------------------------- #
# Framing
# --------------------------------------------------------------------------- #
def encode_frame(text: str) -> bytes:
    """`"caf\\u00e9"` -> `b"5:caf\\xc3\\xa9"` -- the header counts bytes."""
    _text(text, "a message")
    payload = text.encode("utf-8")
    if len(payload) > MAX_MESSAGE:
        raise ChatError(f"a message is at most {MAX_MESSAGE} bytes, got "
                        f"{len(payload)}")
    return str(len(payload)).encode("ascii") + FRAME_SEP + payload


class FrameDecoder:
    """One per connection: holds a partial frame until the rest of it arrives."""

    def __init__(self) -> None:
        self._buffer = b""
        self.frames = 0

    @property
    def pending(self) -> int:
        """How many bytes of an unfinished frame are being held."""
        return len(self._buffer)

    @property
    def need(self) -> int:
        """How many more bytes the frame in hand still needs -- 0 when none is held."""
        index = self._buffer.find(FRAME_SEP)
        if index <= 0 or not self._buffer[:index].isdigit():
            return 0
        length = int(self._buffer[:index])
        return max(0, length - (len(self._buffer) - index - 1))

    @property
    def empty(self) -> bool:
        return not self._buffer

    def feed(self, chunk: bytes) -> tuple[str, ...]:
        """Add bytes; return every message that is now complete."""
        _bytes(chunk, "a read")
        self._buffer += chunk
        messages: list[str] = []
        while True:
            index = self._buffer.find(FRAME_SEP)
            if index < 0:
                if len(self._buffer) > MAX_HEADER:
                    raise ChatError(f"a frame header is at most {MAX_HEADER} "
                                    f"digits, got {len(self._buffer)} bytes with "
                                    f"no colon")
                break
            header = self._buffer[:index]
            if not header or not header.isdigit():
                raise ChatError(f"a frame header is a byte count, got {header!r}")
            if len(header) > 1 and header.startswith(b"0"):
                raise ChatError(f"a frame header carries no leading zero, got "
                                f"{header!r}")
            length = int(header)
            if length > MAX_MESSAGE:
                raise ChatError(f"a frame is at most {MAX_MESSAGE} bytes, got a "
                                f"header of {length}")
            start = index + 1
            if len(self._buffer) - start < length:
                break
            payload = self._buffer[start:start + length]
            self._buffer = self._buffer[start + length:]
            try:
                messages.append(payload.decode("utf-8"))
            except UnicodeDecodeError as error:
                raise ChatError(f"a frame's payload is UTF-8; byte {error.start} "
                                f"of {len(payload)} is not") from None
            self.frames += 1
        return tuple(messages)

    def flush(self) -> tuple[str, ...]:
        """End of stream: an unfinished frame is not a message, so it is refused."""
        if self._buffer:
            raise ChatError(f"{len(self._buffer)} byte(s) of an unfinished frame "
                            f"remain: a frame is not a message until it is whole")
        return ()


def legacy_decode(chunk: bytes) -> str:
    """`chunk.decode("utf-8", errors="replace")` -- a split character becomes U+FFFD."""
    _bytes(chunk, "a read")
    return chunk.decode("utf-8", errors="replace")


def legacy_deliver(chunks) -> tuple[str, ...]:
    """The old reader: decode each read, then split it on newlines."""
    delivered: list[str] = []
    for chunk in chunks:
        for line in legacy_decode(chunk).split("\n"):
            if line:
                delivered.append(line)
    return tuple(delivered)


def split_reads(raw: bytes, limit: int = READ_LIMIT) -> tuple[bytes, ...]:
    """The deterministic stand-in for `recv(limit)`: short reads, in order."""
    _bytes(raw, "a stream")
    _whole(limit, "a read limit")
    if limit <= 0:
        raise ChatError(f"a read limit is positive, got {limit}")
    return tuple(raw[start:start + limit] for start in range(0, len(raw), limit))


# --------------------------------------------------------------------------- #
# An in-memory channel, server and client
# --------------------------------------------------------------------------- #
class Channel:
    """A one-way byte pipe: exactly the bytes a socket would have carried."""

    def __init__(self) -> None:
        self._data = bytearray()

    @property
    def pending(self) -> int:
        return len(self._data)

    @property
    def empty(self) -> bool:
        return not self._data

    def write(self, raw: bytes) -> int:
        """Put bytes on the wire; return how many."""
        _bytes(raw, "a write")
        self._data.extend(raw)
        return len(raw)

    def read(self, limit: int = READ_LIMIT) -> bytes:
        """Take at most `limit` bytes -- a short read is normal, not an error."""
        _whole(limit, "a read limit")
        if limit <= 0:
            raise ChatError(f"a read limit is positive, got {limit}")
        chunk = bytes(self._data[:limit])
        del self._data[:limit]
        return chunk


class ChatServer:
    """Reads frames off a channel; counts the reads that ended mid-frame."""

    def __init__(self, inbox, *, read_limit: int = READ_LIMIT) -> None:
        if not isinstance(inbox, Channel):
            raise ChatError(f"a server reads a channel, got "
                            f"{type(inbox).__name__}")
        _whole(read_limit, "a read limit")
        if read_limit <= 0 or read_limit > 65536:
            raise ChatError(f"a read limit is 1..65536, got {read_limit}")
        self.inbox = inbox
        self.read_limit = read_limit
        self.decoder = FrameDecoder()
        self.delivered: list[str] = []
        self.reads = 0
        self.partial_reads = 0

    def pump(self) -> tuple[str, ...]:
        """One read; return the messages it completed."""
        chunk = self.inbox.read(self.read_limit)
        if not chunk:
            raise ChatError("the channel is empty: a read returned no bytes")
        self.reads += 1
        fresh = self.decoder.feed(chunk)
        if self.decoder.pending:
            self.partial_reads += 1
        self.delivered.extend(fresh)
        return fresh

    def pump_all(self) -> tuple[str, ...]:
        """Read until the channel is empty, then insist the stream ended cleanly."""
        while not self.inbox.empty:
            self.pump()
        self.decoder.flush()
        return tuple(self.delivered)


class ChatClient:
    """Writes frames into a server's channel -- one `say` is one frame."""

    def __init__(self, server: ChatServer, nickname: str) -> None:
        if not isinstance(server, ChatServer):
            raise ChatError(f"a client writes to a server, got "
                            f"{type(server).__name__}")
        self.server = server
        self.nickname = nickname
        _text(nickname, "a nickname")
        if "|" in nickname or "\n" in nickname:
            raise ChatError(f"a nickname holds no '|' and no newline, got "
                            f"{nickname!r}")
        if len(nickname) > 24:
            raise ChatError(f"a nickname is at most 24 characters, got "
                            f"{len(nickname)}")

    def say(self, text: str) -> int:
        """Send one message; return the number of bytes written."""
        return self.server.inbox.write(encode_frame(text))

    def say_all(self, texts) -> int:
        return sum(self.say(text) for text in texts)


# --------------------------------------------------------------------------- #
# The bundled log
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Message:
    """One message a sender meant to send -- newline and all."""

    sender: str
    text: str

    def __post_init__(self) -> None:
        _text(self.sender, "a sender")
        if "|" in self.sender or "\n" in self.sender:
            raise ChatError(f"a sender holds no '|' and no newline, got "
                            f"{self.sender!r}")
        _text(self.text, "a message")
        size = len(self.text.encode("utf-8"))
        if size > MAX_MESSAGE:
            raise ChatError(f"a message is at most {MAX_MESSAGE} bytes, got {size}")

    @property
    def size(self) -> int:
        return len(self.text.encode("utf-8"))

    @property
    def characters(self) -> int:
        return len(self.text)

    def shown(self) -> str:
        """An ASCII-safe rendering, so the demo prints the same bytes everywhere."""
        return ascii(self.text)


def parse_log(text: str) -> tuple[Message, ...]:
    """Read `sender | text` per line; `;` introduces a comment; `\\n` is a newline."""
    if not isinstance(text, str):
        raise ChatError(f"a log is text, got {type(text).__name__}")
    messages: list[Message] = []
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        body = line.split(";", 1)[0].strip()
        if not body:
            continue
        fields = [field.strip() for field in body.split("|")]
        if len(fields) != 2:
            raise ChatError(f"line {number}: two fields are needed -- a sender "
                            f"and a text -- got {len(fields)}")
        sender, raw = fields
        try:
            messages.append(Message(sender, unescape(raw)))
        except ChatError as error:
            raise ChatError(f"line {number}: {error}") from None
    if not messages:
        raise ChatError("a log needs at least one message")
    return tuple(messages)


def read_log(path=None) -> tuple[Message, ...]:
    target = Path(LOG_FILE if path is None else path)
    if not target.is_file():
        raise ChatError(f"file not found: {target}")
    return parse_log(target.read_text(encoding="utf-8"))


def wire_of(messages) -> bytes:
    """The frames for a conversation, concatenated -- what the socket would carry."""
    return b"".join(encode_frame(message.text) for message in messages)


def converse(messages, read_limit: int = READ_LIMIT) -> tuple[ChatServer, bytes]:
    """Frame a conversation, push it through a channel, and read it back."""
    wire = wire_of(messages)
    inbox = Channel()
    inbox.write(wire)
    server = ChatServer(inbox, read_limit=read_limit)
    server.pump_all()
    return server, wire


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(messages, read_limit: int = READ_LIMIT) -> dict:
    """Every number the audit is allowed to read, measured once."""
    held = tuple(messages)
    server, wire = converse(held, read_limit)
    measured: dict = {}

    measured["count"] = len(held)
    measured["wire_bytes"] = len(wire)
    measured["chunks"] = [len(chunk) for chunk in split_reads(wire, read_limit)]
    measured["reads"] = server.reads
    measured["partial_reads"] = server.partial_reads
    measured["split_percent"] = divide_half_up(100 * server.partial_reads,
                                               server.reads)
    measured["delivered"] = list(server.delivered)
    measured["pending"] = server.decoder.pending
    measured["boundary_reads"] = server.reads - server.partial_reads

    legacy = legacy_deliver(split_reads(wire, read_limit))
    measured["legacy_lines"] = list(legacy)
    measured["legacy_count"] = len(legacy)

    cafe = "caf\u00e9"
    measured["cafe_characters"] = len(cafe)
    measured["cafe_bytes"] = len(cafe.encode("utf-8"))
    measured["cafe_header"] = encode_frame(cafe).split(FRAME_SEP, 1)[0].decode()
    measured["cafe_frame_bytes"] = len(encode_frame(cafe))

    half = encode_frame(cafe)[:-1]
    decoder = FrameDecoder()
    measured["half_delivered"] = list(decoder.feed(half))
    measured["half_pending"] = decoder.pending
    measured["half_need"] = decoder.need
    measured["half_legacy"] = legacy_decode(half)
    measured["replacement"] = measured["half_legacy"].count("\ufffd")

    measured["flush_refused"] = not _guard(decoder.flush)

    bad = FrameDecoder()
    measured["bad_header_refused"] = not _guard(lambda: bad.feed(b"x:abc"))

    blank_refused = not _guard(lambda: encode_frame("   "))
    measured["blank_refused"] = blank_refused

    pair = FrameDecoder()
    measured["two_in_one"] = list(pair.feed(encode_frame("one") +
                                            encode_frame("two")))
    single = FrameDecoder()
    first, second = encode_frame("whole")[:3], encode_frame("whole")[3:]
    measured["one_in_two"] = list(single.feed(first)) + list(single.feed(second))
    measured["round_trip"] = list(FrameDecoder().feed(encode_frame("round trip")))

    measured["newline_count"] = sum(1 for message in held if "\n" in message.text)
    measured["newline_legacy_pieces"] = sum(
        len(message.text.split("\n")) for message in held if "\n" in message.text)
    return measured


def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def audit(measured: dict, messages, make_decoder=FrameDecoder,
          read_limit: int = READ_LIMIT) -> list[tuple[str, bool]]:
    """Twelve checks, re-derived from what the demo measured or freshly built."""
    held = tuple(messages)

    def at(name: str):
        if name not in measured:
            raise ChatError(f"no measurement named {name!r}")
        return measured[name]

    def a_frame_carries_its_own_length_in_bytes() -> bool:
        return at("cafe_header") == "5" and at("cafe_characters") == 4 and \
            at("cafe_bytes") == 5 and at("cafe_frame_bytes") == 7

    def a_message_with_a_newline_stays_one_message() -> bool:
        delivered = at("delivered")
        return len(delivered) == len(held) and \
            any("\n" in text for text in delivered) and \
            at("newline_count") >= 1

    def the_decoder_waits_for_a_whole_frame() -> bool:
        return at("half_delivered") == [] and at("half_pending") == 6 and \
            at("half_need") == 1

    def the_decoder_reassembles_the_bundle() -> bool:
        decoder = make_decoder()
        delivered: list[str] = []
        for chunk in split_reads(wire_of(held), read_limit):
            delivered.extend(decoder.feed(chunk))
        return delivered == at("delivered") and decoder.pending == 0

    def every_frame_is_delivered_exactly_once() -> bool:
        return sorted(at("delivered")) == sorted(message.text for message in held) \
            and at("reads") == len(at("chunks")) and at("pending") == 0

    def the_legacy_reader_splits_a_message_on_its_newline() -> bool:
        return at("legacy_count") > at("count") and \
            at("newline_legacy_pieces") >= 2

    def the_legacy_reader_delivers_a_half_frame() -> bool:
        return at("replacement") == 1 and at("half_legacy").endswith("\ufffd") \
            and at("half_pending") == 6

    def the_header_counts_bytes_not_characters() -> bool:
        return at("cafe_bytes") - at("cafe_characters") == 1

    def an_unfinished_frame_is_refused_at_the_end() -> bool:
        return at("flush_refused") is True

    def a_header_that_is_not_a_count_is_refused() -> bool:
        return at("bad_header_refused") is True

    def the_split_reads_are_counted_and_percentaged() -> bool:
        chunks = at("chunks")
        return len(chunks) == at("reads") and sum(chunks) == at("wire_bytes") and \
            at("split_percent") == divide_half_up(100 * at("partial_reads"),
                                                  len(chunks))

    def an_empty_message_is_refused() -> bool:
        return at("blank_refused") is True

    checks = [
        ("a frame carries its own length in bytes",
         a_frame_carries_its_own_length_in_bytes),
        ("a message with a newline stays one message",
         a_message_with_a_newline_stays_one_message),
        ("the decoder waits for a whole frame",
         the_decoder_waits_for_a_whole_frame),
        ("the decoder reassembles the bundle", the_decoder_reassembles_the_bundle),
        ("every frame is delivered exactly once",
         every_frame_is_delivered_exactly_once),
        ("the legacy reader splits a message on its newline",
         the_legacy_reader_splits_a_message_on_its_newline),
        ("the legacy reader delivers a half frame",
         the_legacy_reader_delivers_a_half_frame),
        ("the header counts bytes not characters",
         the_header_counts_bytes_not_characters),
        ("an unfinished frame is refused at the end",
         an_unfinished_frame_is_refused_at_the_end),
        ("a header that is not a count is refused",
         a_header_that_is_not_a_count_is_refused),
        ("the split reads are counted and percentaged",
         the_split_reads_are_counted_and_percentaged),
        ("an empty message is refused", an_empty_message_is_refused),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    messages = read_log()
    measured = measure(messages)

    print("=" * 78)
    print(" CHAT LAB - a message is a frame, not a line")
    print("=" * 78)

    print("\n  the legacy reader, transcribed:")
    for line in LEGACY_READER.split("\n"):
        print(f"    {line}")

    print(f"\n  {measured['count']} messages -> {measured['wire_bytes']} bytes, "
          f"read as {measured['reads']} chunks of {READ_LIMIT} bytes")
    print(f"  {measured['partial_reads']} of those reads ended mid-frame "
          f"({measured['split_percent']}%), {measured['boundary_reads']} landed "
          f"exactly on a frame boundary")

    print("\n  delivered here, one message per frame:")
    for text in measured["delivered"]:
        print(f"    {ascii(text)}")

    print(f"\n  the legacy reader delivers {measured['legacy_count']} lines:")
    for line in measured["legacy_lines"]:
        print(f"    {ascii(line)}")

    print(f"\n  a newline inside a message: {measured['newline_count']} message(s)")
    print("    here:   one message, newline kept")
    print(f"    legacy: {measured['newline_legacy_pieces']} messages, "
          f"the newline gone")

    print("\n  a length prefix counts bytes, not characters:")
    print(f"    'caf\\u00e9' is {measured['cafe_characters']} characters and "
          f"{measured['cafe_bytes']} bytes")
    print(f"    frame -> {measured['cafe_header']} bytes of payload, "
          f"{measured['cafe_frame_bytes']} bytes on the wire")

    print("\n  half a frame is not a message:")
    print(f"    here:   {len(measured['half_delivered'])} messages, "
          f"{measured['half_pending']} bytes held, "
          f"{measured['half_need']} more byte needed")
    print(f"    legacy: {ascii(measured['half_legacy'])}, "
          f"{measured['replacement']} replacement character")

    checks = audit(measured, messages)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{measured['count']} messages are {measured['wire_bytes']} framed "
          f"bytes, read in {measured['reads']} chunks of which "
          f"{measured['partial_reads']} ended mid-frame "
          f"({measured['split_percent']}%), the decoder delivers exactly "
          f"{len(measured['delivered'])} of them while the legacy line reader "
          f"delivers {measured['legacy_count']} fragments, the newline inside "
          f"one message becomes {measured['newline_legacy_pieces']} legacy "
          f"messages, 'caf\\u00e9' is {measured['cafe_characters']} characters "
          f"but {measured['cafe_bytes']} bytes and so its header says "
          f"{measured['cafe_header']}, and half a frame leaves "
          f"{measured['half_pending']} bytes held and "
          f"{measured['half_need']} byte still needed here against "
          f"{measured['replacement']} replacement character in the legacy "
          f"reader, with {sum(1 for _, okay in checks if okay)}/{len(checks)} "
          f"checks holding")

    print("Demo completed successfully.")
    return 0
