"""Tests for the file lab: encryption is not authentication."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import crypto_tool as module                                # noqa: E402
import main as cli                                          # noqa: E402
from crypto_tool import (                                   # noqa: E402
    BLOCK,
    DEMO_PASSWORD,
    HEADER_SIZE,
    KEY_SIZE,
    LEGACY_ENCRYPT,
    LEGACY_KEY,
    MAGIC,
    NONCE,
    OTHER_NONCE,
    TAG_SIZE,
    VERSION,
    Container,
    DomainError,
    audit,
    derive_key,
    divide_half_up,
    flip_byte,
    inspect,
    keystream,
    legacy_decrypt,
    legacy_encrypt,
    measure,
    parse_container,
    problems,
    read_note,
    run_demo,
    seal,
    tag_for,
    unseal,
    xor_bytes,
)

NOTE = read_note()
MEASURED = measure(NOTE)
KEY = derive_key(DEMO_PASSWORD)


# --------------------------------------------------------------------------- #
# divide_half_up
# --------------------------------------------------------------------------- #
def test_divide_half_up_rounds_a_tie_up():
    assert divide_half_up(5, 2) == 3


def test_divide_half_up_rounds_1162_79_up_to_1163():
    assert divide_half_up(50 * 1000, 43) == 1163


def test_divide_half_up_floors_below_the_tie():
    assert divide_half_up(7, 3) == 2


def test_divide_half_up_rounds_a_negative_tie_away_from_zero():
    assert divide_half_up(-5, 2) == -3


def test_divide_half_up_refuses_a_zero_denominator():
    with pytest.raises(DomainError, match="a denominator is positive"):
        divide_half_up(1, 0)


def test_divide_half_up_refuses_a_float_numerator():
    with pytest.raises(DomainError, match="a numerator is a whole number"):
        divide_half_up(1.5, 2)


def test_divide_half_up_refuses_a_bool_denominator():
    with pytest.raises(DomainError, match="a denominator is a whole number"):
        divide_half_up(1, True)


# --------------------------------------------------------------------------- #
# derive_key
# --------------------------------------------------------------------------- #
def test_derive_key_is_pinned_for_the_legacy_password():
    assert derive_key(DEMO_PASSWORD).hex() == (
        "622cb6c4f8d7616f5e9e9e8be07dd9d4247b8900077881f6386802f2dd94e3f6")


def test_derive_key_matches_an_unsalted_sha256():
    assert derive_key("x") == hashlib.sha256(b"x").digest()


def test_derive_key_refuses_an_empty_password():
    with pytest.raises(DomainError, match="a password is text, and not empty"):
        derive_key("")


def test_derive_key_refuses_a_number():
    with pytest.raises(DomainError, match="a password is text"):
        derive_key(7)


# --------------------------------------------------------------------------- #
# keystream and xor
# --------------------------------------------------------------------------- #
def test_keystream_of_zero_length_is_empty():
    assert keystream(KEY, NONCE, 0) == b""


def test_keystream_is_exactly_the_length_asked_for():
    assert len(keystream(KEY, NONCE, 43)) == 43


def test_keystream_is_pinned_for_the_first_sixteen_bytes():
    assert keystream(KEY, NONCE, 16).hex() == "470bed8a49691bd0e8205b33e2c22f5c"


def test_keystream_blocks_do_not_repeat():
    stream = keystream(KEY, NONCE, 2 * BLOCK)
    assert stream[:BLOCK] != stream[BLOCK:]


def test_keystream_uses_the_nonce():
    assert keystream(KEY, NONCE, 32) != keystream(KEY, OTHER_NONCE, 32)


def test_keystream_refuses_a_short_key():
    with pytest.raises(DomainError, match="a key is 32 bytes"):
        keystream(b"short", NONCE, 1)


def test_keystream_refuses_a_short_nonce():
    with pytest.raises(DomainError, match="a nonce is 12 bytes"):
        keystream(KEY, b"short", 1)


def test_keystream_refuses_a_negative_length():
    with pytest.raises(DomainError, match="not negative"):
        keystream(KEY, NONCE, -1)


def test_keystream_refuses_a_float_length():
    with pytest.raises(DomainError, match="whole number"):
        keystream(KEY, NONCE, 1.5)


def test_xor_of_two_values_is_reversible():
    assert xor_bytes(xor_bytes(b"abc", b"xyz"), b"xyz") == b"abc"


def test_xor_refuses_different_lengths():
    with pytest.raises(DomainError, match="equal lengths"):
        xor_bytes(b"a", b"bc")


def test_xor_refuses_text():
    with pytest.raises(DomainError, match="a left operand is bytes"):
        xor_bytes("a", b"b")


# --------------------------------------------------------------------------- #
# The legacy cipher
# --------------------------------------------------------------------------- #
def test_the_legacy_cipher_round_trips():
    assert legacy_decrypt(legacy_encrypt(NOTE, DEMO_PASSWORD),
                          DEMO_PASSWORD) == NOTE


def test_the_legacy_body_has_the_plaintext_length():
    assert len(legacy_encrypt(NOTE, DEMO_PASSWORD)) == 43


def test_the_legacy_ciphertext_is_pinned():
    digest = hashlib.sha256(legacy_encrypt(b"Attack at dawn.",
                                           DEMO_PASSWORD)).hexdigest()
    assert digest == "4eb5263611a46708dfcfb7419f93f145f028dbabbd00cecf5aba7293b8eaed28"


def test_the_legacy_cipher_accepts_a_flipped_byte():
    tampered = flip_byte(legacy_encrypt(NOTE, DEMO_PASSWORD), 0)
    assert legacy_decrypt(tampered, DEMO_PASSWORD) == \
        b"@ttack at dawn. Move the convoy to grid 7.\n"


def test_the_legacy_cipher_never_raises_on_a_flip():
    tampered = flip_byte(legacy_encrypt(NOTE, DEMO_PASSWORD), 40)
    assert len(legacy_decrypt(tampered, DEMO_PASSWORD)) == 43


def test_a_wrong_legacy_password_returns_garbage_instead_of_refusing():
    other = legacy_decrypt(legacy_encrypt(NOTE, DEMO_PASSWORD), "wrong")
    assert other != NOTE and len(other) == 43


def test_the_transcribed_legacy_code_names_its_parts():
    assert "hashlib.sha256" in LEGACY_ENCRYPT and "counter" in LEGACY_ENCRYPT
    assert LEGACY_KEY == 'key = hashlib.sha256(password.encode()).digest()'


# --------------------------------------------------------------------------- #
# flip_byte
# --------------------------------------------------------------------------- #
def test_flip_byte_flips_the_low_bit():
    assert flip_byte(b"\x00", 0) == b"\x01"


def test_flip_byte_refuses_an_index_at_the_end():
    with pytest.raises(DomainError, match="an index is inside the data"):
        flip_byte(b"abc", 3)


def test_flip_byte_refuses_a_negative_index():
    with pytest.raises(DomainError, match="an index is inside the data"):
        flip_byte(b"abc", -1)


def test_flip_byte_refuses_a_float_index():
    with pytest.raises(DomainError, match="a whole number"):
        flip_byte(b"abc", 1.0)


# --------------------------------------------------------------------------- #
# seal, parse and unseal
# --------------------------------------------------------------------------- #
def test_seal_round_trips():
    assert unseal(seal(NOTE, KEY, NONCE), KEY) == NOTE


def test_seal_adds_a_header_and_a_tag():
    assert len(seal(NOTE, KEY, NONCE)) == len(NOTE) + HEADER_SIZE + TAG_SIZE


def test_a_sealed_container_starts_with_the_magic():
    assert seal(NOTE, KEY, NONCE).startswith(MAGIC)


def test_a_sealed_container_carries_the_nonce_in_its_header():
    built = seal(NOTE, KEY, NONCE)
    assert built[len(MAGIC) + 1:HEADER_SIZE] == NONCE


def test_seal_accepts_an_empty_plaintext():
    built = seal(b"", KEY, NONCE)
    assert len(built) == HEADER_SIZE + TAG_SIZE and unseal(built, KEY) == b""


def test_seal_refuses_a_short_key():
    with pytest.raises(DomainError, match="a key is 32 bytes"):
        seal(b"x", b"short", NONCE)


def test_seal_refuses_a_long_nonce():
    with pytest.raises(DomainError, match="a nonce is 12 bytes"):
        seal(b"x", KEY, NONCE + b"x")


def test_seal_refuses_text():
    with pytest.raises(DomainError, match="a plaintext is bytes"):
        seal("x", KEY, NONCE)


def test_unseal_refuses_a_wrong_key():
    with pytest.raises(DomainError, match="tag does not match"):
        unseal(seal(NOTE, KEY, NONCE), derive_key("another password"))


def test_unseal_refuses_a_flipped_body_byte():
    built = flip_byte(seal(NOTE, KEY, NONCE), HEADER_SIZE)
    with pytest.raises(DomainError, match="tag does not match"):
        unseal(built, KEY)


def test_unseal_refuses_a_flipped_header_byte():
    built = flip_byte(seal(NOTE, KEY, NONCE), 0)
    with pytest.raises(DomainError, match="starts with b'SEAL1'"):
        unseal(built, KEY)


def test_unseal_refuses_a_truncated_container():
    with pytest.raises(DomainError, match="at least 50 bytes"):
        unseal(seal(NOTE, KEY, NONCE)[:20], KEY)


def test_unseal_refuses_an_unknown_version():
    built = bytearray(seal(NOTE, KEY, NONCE))
    built[len(MAGIC)] = 9
    with pytest.raises(DomainError, match="version is 1, got 9"):
        unseal(bytes(built), KEY)


def test_unseal_refuses_a_short_key():
    with pytest.raises(DomainError, match="a key is 32 bytes"):
        unseal(seal(NOTE, KEY, NONCE), b"short")


def test_parse_container_names_its_four_fields():
    parsed = parse_container(seal(NOTE, KEY, NONCE))
    assert isinstance(parsed, Container)
    assert (parsed.version, parsed.nonce, len(parsed.body), len(parsed.tag)) == \
        (1, NONCE, 43, 32)


def test_parse_container_refuses_short_bytes():
    with pytest.raises(DomainError, match="at least 50 bytes"):
        parse_container(b"SEAL1")


def test_parse_container_refuses_bad_magic():
    with pytest.raises(DomainError, match="starts with b'SEAL1'"):
        parse_container(b"XXXXX" + b"\x01" + NONCE + b"\x00" * 32)


def test_a_container_reports_its_total_size():
    assert parse_container(seal(NOTE, KEY, NONCE)).total_size() == 93


def test_tag_for_covers_the_header_and_the_body():
    header = MAGIC + bytes([VERSION]) + NONCE
    assert tag_for(KEY, header, b"a") != tag_for(KEY, header, b"b")


def test_tag_for_is_thirty_two_bytes():
    assert len(tag_for(KEY, b"", b"")) == TAG_SIZE


# --------------------------------------------------------------------------- #
# inspect and read_note
# --------------------------------------------------------------------------- #
def test_inspect_reports_the_framing_without_the_key():
    info = inspect(seal(NOTE, KEY, NONCE))
    assert info == {
        "version": 1,
        "nonce_hex": NONCE.hex(),
        "body_bytes": 43,
        "tag_bytes": 32,
        "total_bytes": 93,
    }


def test_read_note_reads_the_bundled_forty_three_bytes():
    assert len(NOTE) == 43 and NOTE.startswith(b"Attack at dawn.")


def test_read_note_refuses_a_missing_file(tmp_path):
    with pytest.raises(DomainError, match="file not found"):
        read_note(tmp_path / "nope.txt")


def test_read_note_refuses_non_ascii_bytes(tmp_path):
    path = tmp_path / "note.txt"
    path.write_bytes(b"caf\xc3\xa9\n")
    with pytest.raises(DomainError, match="ASCII text"):
        read_note(path)


# --------------------------------------------------------------------------- #
# measure
# --------------------------------------------------------------------------- #
def test_measure_pins_the_plaintext_length():
    assert MEASURED["plaintext_bytes"] == 43


def test_measure_pins_the_legacy_body_length():
    assert MEASURED["legacy_body_bytes"] == 43


def test_measure_pins_the_silent_tamper():
    assert MEASURED["legacy_tamper_silent"] is True
    assert MEASURED["legacy_tampered_text"] == \
        "@ttack at dawn. Move the convoy to grid 7.\n"


def test_measure_pins_the_sealed_refusal():
    assert MEASURED["sealed_tamper_refused"] is True
    assert "tag does not match" in MEASURED["sealed_error"]


def test_measure_pins_every_refusal():
    assert MEASURED["wrong_key_refused"] is True
    assert MEASURED["truncated_refused"] is True
    assert MEASURED["bad_version_refused"] is True
    assert MEASURED["damaged_header_refused"] is True


def test_measure_pins_the_overhead_tenths():
    assert MEASURED["overhead_tenths_percent"] == 1163


def test_measure_pins_the_nonce_reuse_leak():
    assert MEASURED["nonce_reuse_xor_hex"] == "13110013060a5441165944570703"
    assert MEASURED["plaintext_xor_hex"] == MEASURED["nonce_reuse_xor_hex"]
    assert MEASURED["nonce_reuse_leaks"] is True


def test_measure_pins_the_two_nonce_results():
    assert MEASURED["two_nonce_ciphertexts_differ"] is True
    assert MEASURED["two_nonce_both_open"] is True


def test_measure_pins_the_container_sha256():
    assert MEASURED["container_sha256"] == (
        "80d6eb8cba184966b0193bd3188378132888e44a439364aea0de84691ce1b5fa")


def test_measure_of_an_empty_note_has_no_overhead_percentage():
    empty = measure(b"")
    assert empty["overhead_tenths_percent"] == 0


def test_measure_refuses_text():
    with pytest.raises(DomainError, match="a plaintext is bytes"):
        measure("not bytes")


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "the legacy cipher round trips untouched bytes",
    "a flipped byte still decrypts under the legacy cipher",
    "the sealed container refuses that byte",
    "a wrong key is refused",
    "a truncated container is refused",
    "an unknown version is refused",
    "the header and tag have fixed sizes",
    "two nonces give two ciphertexts",
    "one nonce reused leaks both messages",
    "the keystream is deterministic and block unique",
    "the container is pinned by its sha256",
    "the overhead is tenths of a percent half up",
    "an empty plaintext still carries a tag",
    "a damaged header is refused",
]


def real_checks():
    return audit(MEASURED)


def test_the_audit_holds_fourteen_named_checks():
    assert [name for name, _ in real_checks()] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_note():
    assert problems(real_checks()) == []


def test_the_audit_is_repeatable():
    assert real_checks() == real_checks()


def corrupted(**changes) -> dict:
    payload = dict(MEASURED)
    payload.update(changes)
    return payload


def test_the_audit_catches_a_legacy_cipher_that_lost_a_byte():
    checks = audit(corrupted(legacy_body_bytes=42))
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_a_silent_tamper_that_became_loud():
    checks = audit(corrupted(legacy_tamper_silent=False))
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_the_wrong_tampered_text():
    checks = audit(corrupted(legacy_tampered_text="unchanged"))
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_a_sealed_container_that_accepted_the_byte():
    checks = audit(corrupted(sealed_tamper_refused=False))
    assert CHECK_NAMES[2] in problems(checks)


def test_the_audit_catches_a_wrong_key_that_opened():
    checks = audit(corrupted(wrong_key_refused=False))
    assert CHECK_NAMES[3] in problems(checks)


def test_the_audit_catches_a_truncated_file_that_opened():
    checks = audit(corrupted(truncated_refused=False))
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_an_unknown_version_that_opened():
    checks = audit(corrupted(bad_version_refused=False))
    assert CHECK_NAMES[5] in problems(checks)


def test_the_audit_catches_a_nonce_that_did_not_change_the_ciphertext():
    checks = audit(corrupted(two_nonce_ciphertexts_differ=False))
    assert CHECK_NAMES[7] in problems(checks)


def test_the_audit_catches_a_nonce_reuse_that_did_not_leak():
    checks = audit(corrupted(nonce_reuse_xor_hex="00" * 14))
    assert CHECK_NAMES[8] in problems(checks)


def test_the_audit_catches_a_keystream_that_repeats():
    checks = audit(corrupted(keystream_stable=False))
    assert CHECK_NAMES[9] in problems(checks)


def test_the_audit_catches_a_container_with_another_hash():
    checks = audit(corrupted(container_sha256="00" * 32))
    assert CHECK_NAMES[10] in problems(checks)


def test_the_audit_catches_a_floored_overhead():
    checks = audit(corrupted(overhead_tenths_percent=1162))
    assert CHECK_NAMES[11] in problems(checks)


def test_the_audit_catches_a_damaged_header_that_opened():
    checks = audit(corrupted(damaged_header_refused=False))
    assert CHECK_NAMES[13] in problems(checks)


def test_a_missing_measurement_is_a_failure_not_a_traceback():
    payload = corrupted()
    del payload["wrong_key_refused"]
    checks = audit(payload)
    assert CHECK_NAMES[3] in problems(checks)
    assert len(checks) == len(CHECK_NAMES)


def test_a_broken_seal_factory_fails_the_size_check():
    checks = audit(MEASURED, seal_func=lambda plaintext, key, nonce: plaintext)
    assert CHECK_NAMES[6] in problems(checks)


def test_a_broken_seal_factory_fails_the_nonce_check():
    checks = audit(MEASURED, seal_func=lambda plaintext, key, nonce: plaintext)
    assert CHECK_NAMES[7] in problems(checks)


def test_every_check_has_a_negative_control():
    caught = set()
    for change in (
        {"legacy_body_bytes": 42},
        {"legacy_tamper_silent": False},
        {"sealed_tamper_refused": False},
        {"wrong_key_refused": False},
        {"truncated_refused": False},
        {"bad_version_refused": False},
        {"two_nonce_ciphertexts_differ": False},
        {"two_nonce_both_open": False},
        {"nonce_reuse_xor_hex": "00" * 14},
        {"keystream_stable": False},
        {"container_sha256": "00" * 32},
        {"overhead_tenths_percent": 1162},
        {"damaged_header_refused": False},
    ):
        caught |= set(problems(audit(corrupted(**change))))
    caught |= set(problems(audit(MEASURED,
                                 seal_func=lambda plaintext, key, nonce: plaintext)))
    assert caught == set(CHECK_NAMES)


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


def test_demo_shows_the_legacy_cipher(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "FILE LAB" in out and "hashlib.sha256" in out


def test_demo_shows_the_silent_tamper(capsys):
    run_demo()
    assert "'@ttack at dawn." in capsys.readouterr().out


def test_demo_ends_with_the_two_required_lines(capsys):
    run_demo()
    lines = [line for line in capsys.readouterr().out.split("\n") if line]
    assert lines[-2].startswith("Cross-checks OK: ")
    assert lines[-1] == "Demo completed successfully."


def test_demo_shows_all_fourteen_checks(capsys):
    run_demo()
    assert "14/14 checks pass" in capsys.readouterr().out


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


def test_cli_prints_the_round_trip(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "round trip identical: True" in out
    assert "sealed 93 bytes" in out


def test_cli_flips_a_chosen_byte(capsys):
    assert cli.main(["--flip", "0"]) == 0
    out = capsys.readouterr().out
    assert "'@ttack at dawn." in out and "tag does not match" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 14 and "FAIL" not in out


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_reads_a_file(tmp_path, capsys):
    path = tmp_path / "note.txt"
    path.write_text("hello\n", encoding="ascii")
    assert cli.main(["--file", str(path)]) == 0
    assert "sealed 56 bytes" in capsys.readouterr().out


def test_cli_writes_the_report_as_json(tmp_path, capsys):
    target = tmp_path / "report.json"
    assert cli.main(["--audit", "--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="ascii"))
    assert payload["note_bytes"] == 43
    assert payload["container"]["total_bytes"] == 93
    assert payload["measurements"]["nonce_reuse_xor_hex"] == \
        "13110013060a5441165944570703"
    assert len(payload["checks"]) == 14 and all(c["ok"] for c in payload["checks"])


def test_cli_refuses_a_missing_file(tmp_path, capsys):
    assert cli.main(["--file", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_refuses_a_flip_outside_the_note(capsys):
    assert cli.main(["--flip", "43"]) == 2
    assert "a flip index is inside the 43-byte note" in capsys.readouterr().err


def test_cli_refuses_a_negative_flip(capsys):
    assert cli.main(["--flip", "-1"]) == 2
    assert "flip index is inside" in capsys.readouterr().err


def test_cli_refuses_an_empty_password(capsys):
    assert cli.main(["--password", ""]) == 2
    assert "not empty" in capsys.readouterr().err


def test_cli_refuses_a_non_ascii_note(tmp_path, capsys):
    path = tmp_path / "note.txt"
    path.write_bytes(b"caf\xc3\xa9\n")
    assert cli.main(["--file", str(path)]) == 2
    assert "ASCII text" in capsys.readouterr().err


def test_the_module_exports_what_the_tests_import():
    assert module.HEADER_SIZE == 18
    assert module.TAG_SIZE == 32
    assert module.NONCE_SIZE == 12
