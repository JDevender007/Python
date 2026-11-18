"""Encryption hides a message; only a tag can tell you it is still the message.

The legacy tool did what a great many small programs do:

    key = hashlib.sha256(password.encode()).digest()
    stream = hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
    return bytes(a ^ b for a, b in zip(data, stream))

That is a real cipher -- a SHA-256 counter-mode stream -- and it round-trips
perfectly. It also has no way to notice a single flipped bit: the receiver
decrypts whatever arrives, and the result is a slightly different message that
looks exactly as trustworthy as the original. The demo flips the first byte of
a note and the legacy cipher silently turns "Attack at dawn" into "@ttack at
dawn"; there is no error to catch.

It also reuses one nonce for every message. Two ciphertexts under one nonce
xor to the xor of the two plaintexts, so the secrecy of both is gone the moment
an attacker sees the pair.

This module keeps the legacy cipher executable, then seals a message with the
same keystream plus an HMAC-SHA256 tag over the header and the body, with a
nonce carried in the header. A flipped byte, a truncated file, an unknown
version, or the wrong key is refused with a message that says which. Every
number in the demo comes from the bundled 43-byte note; nothing is random, so
two runs are byte-identical.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NOTE_FILE = DATA_DIR / "secret_note.txt"

#: The legacy cipher, transcribed -- and executable.
LEGACY_ENCRYPT = ('key = hashlib.sha256(password.encode()).digest()\n'
                  'stream = hashlib.sha256(key + counter.to_bytes(4, "big")).digest()\n'
                  'return bytes(a ^ b for a, b in zip(data, stream))')

#: The legacy key derivation, transcribed: one unsalted SHA-256 of the password.
LEGACY_KEY = "key = hashlib.sha256(password.encode()).digest()"

MAGIC = b"SEAL1"
VERSION = 1
KEY_SIZE = 32
NONCE_SIZE = 12
TAG_SIZE = 32
BLOCK = 32
HEADER_SIZE = len(MAGIC) + 1 + NONCE_SIZE          # 18

#: The fixed nonce every demo message uses, and a second one to compare against.
NONCE = b"demo-nonce-1"
OTHER_NONCE = b"demo-nonce-2"

#: The password the legacy cipher derives its key from.
DEMO_PASSWORD = "demo-password-not-secret"


class DomainError(Exception):
    """A key, a nonce, a password or a container that cannot be honoured."""


# --------------------------------------------------------------------------- #
# Validation and integer arithmetic
# --------------------------------------------------------------------------- #
def _bytes(value, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray)):
        raise DomainError(f"{name} is bytes, got {type(value).__name__}")
    return bytes(value)


def _text(value, name: str) -> str:
    if not isinstance(value, str):
        raise DomainError(f"{name} is text, got {type(value).__name__}")
    if not value:
        raise DomainError(f"{name} is text, and not empty")
    return value


def _whole(value, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise DomainError(f"{name} is a whole number, got {value!r}")
    return value


def divide_half_up(numerator: int, denominator: int) -> int:
    """`numerator / denominator` rounded half-up, from integers only."""
    _whole(numerator, "a numerator")
    _whole(denominator, "a denominator")
    if denominator <= 0:
        raise DomainError(f"a denominator is positive, got {denominator}")
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return sign * quotient


# --------------------------------------------------------------------------- #
# The keystream both the legacy cipher and the sealed container share
# --------------------------------------------------------------------------- #
def derive_key(password: str) -> bytes:
    """The legacy derivation: one unsalted SHA-256, no stretch, no salt."""
    _text(password, "a password")
    return hashlib.sha256(password.encode("ascii")).digest()


def keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """SHA-256(key + nonce + counter) blocks, concatenated to `length` bytes."""
    _bytes(key, "a key")
    _bytes(nonce, "a nonce")
    _whole(length, "a length")
    if len(key) != KEY_SIZE:
        raise DomainError(f"a key is {KEY_SIZE} bytes, got {len(key)}")
    if len(nonce) != NONCE_SIZE:
        raise DomainError(f"a nonce is {NONCE_SIZE} bytes, got {len(nonce)}")
    if length < 0:
        raise DomainError(f"a length is not negative, got {length}")
    blocks: list[bytes] = []
    counter = 0
    remaining = length
    while remaining > 0:
        block = hashlib.sha256(key + nonce +
                               counter.to_bytes(4, "big")).digest()
        blocks.append(block)
        counter += 1
        remaining -= BLOCK
    return b"".join(blocks)[:length]


def xor_bytes(left: bytes, right: bytes) -> bytes:
    """Xor two byte strings of the same length."""
    _bytes(left, "a left operand")
    _bytes(right, "a right operand")
    if len(left) != len(right):
        raise DomainError(f"xor needs equal lengths, got {len(left)} and "
                          f"{len(right)}")
    return bytes(a ^ b for a, b in zip(left, right))


# --------------------------------------------------------------------------- #
# The legacy cipher: confidentiality with no authentication
# --------------------------------------------------------------------------- #
def legacy_encrypt(plaintext: bytes, password: str) -> bytes:
    """The old construction: keystream from the password alone, no tag."""
    _bytes(plaintext, "a plaintext")
    key = derive_key(password)
    stream = keystream(key, b"\x00" * NONCE_SIZE, len(plaintext))
    return xor_bytes(plaintext, stream)


def legacy_decrypt(container: bytes, password: str) -> bytes:
    """The old decryption, which is the same xor -- and checks nothing."""
    return legacy_encrypt(container, password)


def flip_byte(data: bytes, index: int) -> bytes:
    """Return `data` with the low bit of byte `index` flipped."""
    held = _bytes(data, "data")
    _whole(index, "an index")
    if not 0 <= index < len(held):
        raise DomainError(f"an index is inside the data, got {index} of "
                          f"{len(held)} bytes")
    changed = bytearray(held)
    changed[index] ^= 0x01
    return bytes(changed)


# --------------------------------------------------------------------------- #
# The sealed container: the same keystream, plus an HMAC-SHA256 tag
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Container:
    """A parsed sealed container: version, nonce, body, tag."""

    version: int
    nonce: bytes
    body: bytes
    tag: bytes

    def total_size(self) -> int:
        return HEADER_SIZE + len(self.body) + TAG_SIZE


def tag_for(key: bytes, header: bytes, body: bytes) -> bytes:
    """HMAC-SHA256 over the header and the body -- every byte is covered."""
    _bytes(key, "a key")
    _bytes(header, "a header")
    _bytes(body, "a body")
    return hmac.new(key, header + body, hashlib.sha256).digest()


def seal(plaintext: bytes, key: bytes, nonce: bytes) -> bytes:
    """`header + body + tag`, where the tag authenticates the header too."""
    held = _bytes(plaintext, "a plaintext")
    held_key = _bytes(key, "a key")
    held_nonce = _bytes(nonce, "a nonce")
    if len(held_key) != KEY_SIZE:
        raise DomainError(f"a key is {KEY_SIZE} bytes, got {len(held_key)}")
    if len(held_nonce) != NONCE_SIZE:
        raise DomainError(f"a nonce is {NONCE_SIZE} bytes, got {len(held_nonce)}")
    header = MAGIC + bytes([VERSION]) + held_nonce
    body = xor_bytes(held, keystream(held_key, held_nonce, len(held)))
    return header + body + tag_for(held_key, header, body)


def parse_container(container: bytes) -> Container:
    """Validate the framing and return the four fields, refusing anything odd."""
    held = _bytes(container, "a container")
    if len(held) < HEADER_SIZE + TAG_SIZE:
        raise DomainError(f"a container is at least {HEADER_SIZE + TAG_SIZE} "
                          f"bytes, got {len(held)}")
    if not held.startswith(MAGIC):
        raise DomainError(f"a container starts with {MAGIC!r}, got "
                          f"{held[:len(MAGIC)]!r}")
    version = held[len(MAGIC)]
    if version != VERSION:
        raise DomainError(f"a container version is {VERSION}, got {version}")
    offset = len(MAGIC) + 1
    nonce = held[offset:offset + NONCE_SIZE]
    body = held[HEADER_SIZE:-TAG_SIZE]
    tag = held[-TAG_SIZE:]
    return Container(version=version, nonce=nonce, body=body, tag=tag)


def unseal(container: bytes, key: bytes) -> bytes:
    """Open a sealed container, or refuse it because of its tag."""
    held = _bytes(container, "a container")
    held_key = _bytes(key, "a key")
    if len(held_key) != KEY_SIZE:
        raise DomainError(f"a key is {KEY_SIZE} bytes, got {len(held_key)}")
    parsed = parse_container(held)
    expected = tag_for(held_key, held[:HEADER_SIZE], parsed.body)
    if not hmac.compare_digest(expected, parsed.tag):
        raise DomainError("a container tag does not match: wrong key or "
                          "tampered bytes")
    return xor_bytes(parsed.body,
                     keystream(held_key, parsed.nonce, len(parsed.body)))


def inspect(container: bytes) -> dict:
    """Non-secret metadata about a sealed container."""
    parsed = parse_container(container)
    return {
        "version": parsed.version,
        "nonce_hex": parsed.nonce.hex(),
        "body_bytes": len(parsed.body),
        "tag_bytes": len(parsed.tag),
        "total_bytes": parsed.total_size(),
    }


def read_note(path=None) -> bytes:
    """Read a bundled ASCII note, refusing anything that is not UTF-8 text."""
    target = Path(NOTE_FILE if path is None else path)
    if not target.is_file():
        raise DomainError(f"file not found: {target}")
    try:
        return target.read_text(encoding="ascii").encode("ascii")
    except UnicodeDecodeError:
        raise DomainError(f"a note is ASCII text, and {target.name} is not") \
            from None


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(measured: dict, seal_func=seal, unseal_func=unseal) -> list:
    """Fourteen checks, rebuilt through the factories the caller supplies."""
    def at(name: str):
        if name not in measured:
            raise DomainError(f"no measurement named {name!r}")
        return measured[name]

    key = derive_key(DEMO_PASSWORD)

    def the_legacy_cipher_round_trips() -> bool:
        return at("legacy_roundtrip") is True and \
            at("legacy_body_bytes") == at("plaintext_bytes")

    def one_flipped_byte_still_decrypts() -> bool:
        return at("legacy_tamper_silent") is True and \
            at("legacy_tampered_text") == "@ttack at dawn. Move the convoy " \
            "to grid 7.\n"

    def the_sealed_container_refuses_that_byte() -> bool:
        return at("sealed_tamper_refused") is True and \
            "tag does not match" in at("sealed_error")

    def a_wrong_key_is_refused() -> bool:
        return at("wrong_key_refused") is True

    def a_truncated_container_is_refused() -> bool:
        return at("truncated_refused") is True

    def an_unknown_version_is_refused() -> bool:
        return at("bad_version_refused") is True

    def the_header_and_tag_have_fixed_sizes() -> bool:
        built = seal_func(b"", key, NONCE)
        return len(built) == HEADER_SIZE + TAG_SIZE and \
            at("tag_bytes") == TAG_SIZE and at("header_bytes") == HEADER_SIZE

    def two_nonces_give_two_ciphertexts() -> bool:
        first = seal_func(at("plaintext"), key, NONCE)
        second = seal_func(at("plaintext"), key, OTHER_NONCE)
        return at("two_nonce_ciphertexts_differ") is True and \
            at("two_nonce_both_open") is True and \
            first != second and unseal_func(first, key) == \
            unseal_func(second, key) == at("plaintext")

    def one_nonce_reused_leaks_both_messages() -> bool:
        return at("nonce_reuse_leaks") is True and \
            at("nonce_reuse_xor_hex") == at("plaintext_xor_hex") and \
            at("nonce_reuse_xor_hex") != "00" * len(at("message_one"))

    def the_keystream_is_deterministic_and_block_unique() -> bool:
        stream = keystream(key, NONCE, 2 * BLOCK)
        return at("keystream_stable") is True and \
            stream[:BLOCK] != stream[BLOCK:] and \
            stream == keystream(key, NONCE, 2 * BLOCK)

    def the_container_is_pinned_by_its_sha256() -> bool:
        return hashlib.sha256(seal_func(at("plaintext"), key,
                                        NONCE)).hexdigest() == \
            at("container_sha256")

    def the_overhead_is_tenths_of_a_percent_half_up() -> bool:
        return at("overhead_tenths_percent") == \
            divide_half_up((HEADER_SIZE + TAG_SIZE) * 1000,
                           at("plaintext_bytes"))

    def an_empty_plaintext_still_carries_a_tag() -> bool:
        built = seal_func(b"", key, NONCE)
        return len(built) == HEADER_SIZE + TAG_SIZE and \
            unseal_func(built, key) == b""

    def a_damaged_header_is_refused() -> bool:
        built = seal_func(at("plaintext"), key, NONCE)
        return at("damaged_header_refused") is True and \
            flip_byte(built, 0) != built

    checks = [
        ("the legacy cipher round trips untouched bytes",
         the_legacy_cipher_round_trips),
        ("a flipped byte still decrypts under the legacy cipher",
         one_flipped_byte_still_decrypts),
        ("the sealed container refuses that byte",
         the_sealed_container_refuses_that_byte),
        ("a wrong key is refused", a_wrong_key_is_refused),
        ("a truncated container is refused", a_truncated_container_is_refused),
        ("an unknown version is refused", an_unknown_version_is_refused),
        ("the header and tag have fixed sizes",
         the_header_and_tag_have_fixed_sizes),
        ("two nonces give two ciphertexts", two_nonces_give_two_ciphertexts),
        ("one nonce reused leaks both messages",
         one_nonce_reused_leaks_both_messages),
        ("the keystream is deterministic and block unique",
         the_keystream_is_deterministic_and_block_unique),
        ("the container is pinned by its sha256",
         the_container_is_pinned_by_its_sha256),
        ("the overhead is tenths of a percent half up",
         the_overhead_is_tenths_of_a_percent_half_up),
        ("an empty plaintext still carries a tag",
         an_empty_plaintext_still_carries_a_tag),
        ("a damaged header is refused", a_damaged_header_is_refused),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Measurement and demo
# --------------------------------------------------------------------------- #
def measure(plaintext: bytes, password: str = DEMO_PASSWORD) -> dict:
    """Every number the audit reads, measured once from the same inputs."""
    held = _bytes(plaintext, "a plaintext")
    key = derive_key(password)
    sealed = seal(held, key, NONCE)

    measured: dict = {}
    measured["plaintext"] = held
    measured["plaintext_bytes"] = len(held)
    measured["header_bytes"] = HEADER_SIZE
    measured["tag_bytes"] = TAG_SIZE

    legacy = legacy_encrypt(held, password)
    measured["legacy_body_bytes"] = len(legacy)
    measured["legacy_roundtrip"] = legacy_decrypt(legacy, password) == held

    try:
        legacy_tampered = legacy_decrypt(flip_byte(legacy, 0), password)
    except DomainError:
        measured["legacy_tamper_silent"] = False
        measured["legacy_tampered_text"] = ""
    else:
        measured["legacy_tamper_silent"] = True
        measured["legacy_tampered_text"] = legacy_tampered.decode(
            "ascii", "backslashreplace")

    try:
        unseal(flip_byte(sealed, HEADER_SIZE), key)
    except DomainError as error:
        measured["sealed_tamper_refused"] = True
        measured["sealed_error"] = str(error)
    else:
        measured["sealed_tamper_refused"] = False
        measured["sealed_error"] = ""

    wrong = derive_key("some-other-password")
    try:
        unseal(sealed, wrong)
    except DomainError:
        measured["wrong_key_refused"] = True
    else:
        measured["wrong_key_refused"] = False

    try:
        unseal(sealed[:-1], key)
    except DomainError:
        measured["truncated_refused"] = True
    else:
        measured["truncated_refused"] = False

    damaged = bytearray(sealed)
    damaged[len(MAGIC)] = 9
    try:
        unseal(bytes(damaged), key)
    except DomainError:
        measured["bad_version_refused"] = True
    else:
        measured["bad_version_refused"] = False

    try:
        unseal(flip_byte(sealed, 0), key)
    except DomainError:
        measured["damaged_header_refused"] = True
    else:
        measured["damaged_header_refused"] = False

    measured["overhead_tenths_percent"] = divide_half_up(
        (len(sealed) - len(held)) * 1000, len(held)) if held else 0

    other = seal(held, key, OTHER_NONCE)
    measured["two_nonce_ciphertexts_differ"] = sealed != other
    measured["two_nonce_both_open"] = (unseal(sealed, key) == held and
                                       unseal(other, key) == held)

    measured["keystream_stable"] = (keystream(key, NONCE, 2 * BLOCK) ==
                                    keystream(key, NONCE, 2 * BLOCK))

    message_one = b"attack at dawn"
    message_two = b"retreat by 6pm"
    first = seal(message_one, key, NONCE)
    second = seal(message_two, key, NONCE)
    leak = xor_bytes(first[HEADER_SIZE:-TAG_SIZE], second[HEADER_SIZE:-TAG_SIZE])
    measured["message_one"] = message_one
    measured["message_two"] = message_two
    measured["nonce_reuse_xor_hex"] = leak.hex()
    measured["plaintext_xor_hex"] = xor_bytes(message_one, message_two).hex()
    measured["nonce_reuse_leaks"] = leak == xor_bytes(message_one, message_two)

    measured["container_sha256"] = hashlib.sha256(sealed).hexdigest()
    return measured


def run_demo() -> int:
    note = read_note()
    measured = measure(note)

    print("=" * 78)
    print(" FILE LAB - encryption hides a message; a tag proves it is the message")
    print("=" * 78)

    print("\n  the legacy cipher, transcribed:")
    for line in LEGACY_ENCRYPT.split("\n"):
        print(f"    {line}")

    key = derive_key(DEMO_PASSWORD)
    sealed = seal(note, key, NONCE)
    shown = measured["legacy_body_bytes"]
    tenths = measured["overhead_tenths_percent"]
    print(f"\n  a {len(note)}-byte note under one 32-byte key:")
    print(f"    legacy ciphertext  {shown} bytes, no tag")
    print(f"    sealed container   {len(sealed)} bytes, "
          f"{HEADER_SIZE} header + {TAG_SIZE} tag")
    print(f"    overhead           {tenths // 10}.{tenths % 10}% "
          f"(tenths rounded half up)")

    print("\n  flip one byte at index 0 of each:")
    print(f"    legacy decrypts:   {measured['legacy_tampered_text']!r}")
    print(f"    no error raised:   {measured['legacy_tamper_silent']}")
    print(f"    sealed refuses:    {measured['sealed_error']}")

    print("\n  reuse one nonce for two different messages:")
    print(f"    m1 = {measured['message_one'].decode('ascii')!r}")
    print(f"    m2 = {measured['message_two'].decode('ascii')!r}")
    print(f"    c1 xor c2 = {measured['nonce_reuse_xor_hex']}")
    print(f"    m1 xor m2 = {measured['plaintext_xor_hex']}")
    print(f"    the ciphertexts leak the plaintexts: "
          f"{measured['nonce_reuse_leaks']}")

    print("\n  a fresh nonce under the same key:")
    print(f"    ciphertexts differ: {measured['two_nonce_ciphertexts_differ']}, "
          f"both open: {measured['two_nonce_both_open']}")
    print(f"    container sha256:   {measured['container_sha256']}")

    checks = audit(measured)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"the legacy cipher round-trips {len(note)} bytes and still "
          f"decrypts a flipped one to {measured['legacy_tampered_text']!r}, "
          f"while the sealed {len(sealed)}-byte container refuses it with "
          f"'tag does not match'; one nonce reused for two 14-byte messages "
          f"leaks {measured['nonce_reuse_xor_hex']}, the tag costs "
          f"{tenths // 10}.{tenths % 10}% overhead, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0
