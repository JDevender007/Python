"""Tests for the File Encryption Tool project."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from crypto_tool import (  # noqa: E402
    DEMO_PASSWORD,
    HEADER_SIZE,
    MAGIC,
    NONCE_SIZE,
    SALT_SIZE,
    TAG_SIZE,
    VERSION,
    CryptoToolError,
    decrypt_bytes,
    decrypt_file,
    derive_key,
    encrypt_bytes,
    encrypt_file,
    file_info,
    inspect_container,
    parse_header,
    run_demo,
)
from main import main  # noqa: E402


SAMPLE = b"attack at dawn, then retreat by noon\x00\x01\x02"
PW = "correct horse battery staple"


# --------------------------------------------------------------------------- #
# Bytes round-trips
# --------------------------------------------------------------------------- #
def test_encrypt_decrypt_roundtrip():
    container = encrypt_bytes(SAMPLE, PW)
    assert decrypt_bytes(container, PW) == SAMPLE


def test_container_layout():
    container = encrypt_bytes(SAMPLE, PW)
    assert container.startswith(MAGIC)
    assert container[len(MAGIC)] == VERSION
    assert len(container) == HEADER_SIZE + len(SAMPLE) + TAG_SIZE


def test_empty_plaintext_roundtrip():
    container = encrypt_bytes(b"", PW)
    assert decrypt_bytes(container, PW) == b""


def test_fresh_salt_and_nonce_each_time():
    first = encrypt_bytes(SAMPLE, PW)
    second = encrypt_bytes(SAMPLE, PW)
    assert first != second  # random salt + nonce
    assert first[SALT_SIZE + 1 + len(MAGIC):][:NONCE_SIZE] != \
        second[SALT_SIZE + 1 + len(MAGIC):][:NONCE_SIZE]


def test_deterministic_with_fixed_salt_and_nonce():
    salt, nonce = b"\x01" * SALT_SIZE, b"\x02" * NONCE_SIZE
    a = encrypt_bytes(SAMPLE, PW, salt=salt, nonce=nonce)
    b = encrypt_bytes(SAMPLE, PW, salt=salt, nonce=nonce)
    assert a == b
    assert decrypt_bytes(a, PW) == SAMPLE


# --------------------------------------------------------------------------- #
# Key derivation
# --------------------------------------------------------------------------- #
def test_derive_key_is_32_bytes():
    key = derive_key(PW, b"\x00" * SALT_SIZE)
    assert len(key) == 32 and isinstance(key, bytes)


def test_derive_key_deterministic_per_salt():
    salt = b"\x07" * SALT_SIZE
    assert derive_key(PW, salt) == derive_key(PW, salt)
    assert derive_key(PW, salt) != derive_key("other", salt)
    assert derive_key(PW, salt) != derive_key(PW, b"\x08" * SALT_SIZE)


def test_derive_key_rejects_bad_inputs():
    with pytest.raises(CryptoToolError, match="empty"):
        derive_key("", b"\x00" * SALT_SIZE)
    with pytest.raises(CryptoToolError, match="salt"):
        derive_key(PW, b"short")


# --------------------------------------------------------------------------- #
# Header parsing / inspection
# --------------------------------------------------------------------------- #
def test_parse_header_fields():
    parsed = parse_header(encrypt_bytes(SAMPLE, PW))
    assert parsed["version"] == VERSION
    assert len(parsed["salt"]) == SALT_SIZE
    assert len(parsed["nonce"]) == NONCE_SIZE


def test_inspect_container_metadata():
    container = encrypt_bytes(SAMPLE, PW)
    info = inspect_container(container)
    assert info.version == VERSION
    assert len(info.salt_hex) == SALT_SIZE * 2
    assert info.total_size == len(container)
    assert info.payload_size == len(container) - HEADER_SIZE
    assert set(info.to_dict()) == {"version", "salt", "nonce", "total_size", "payload_size"}


def test_parse_header_rejects_bad_magic():
    with pytest.raises(CryptoToolError, match="magic"):
        parse_header(b"NOTPYENC" + b"\x00" * 60)


def test_parse_header_rejects_short_file():
    with pytest.raises(CryptoToolError, match="too short"):
        parse_header(b"\x89PYENC\r\n\x01")


def test_parse_header_rejects_bad_version():
    blob = MAGIC + bytes([99]) + b"\x00" * (SALT_SIZE + NONCE_SIZE + TAG_SIZE)
    with pytest.raises(CryptoToolError, match="version 99"):
        parse_header(blob)


# --------------------------------------------------------------------------- #
# Error paths
# --------------------------------------------------------------------------- #
def test_wrong_password_rejected():
    container = encrypt_bytes(SAMPLE, PW)
    with pytest.raises(CryptoToolError, match="wrong password or tampered"):
        decrypt_bytes(container, "not-the-password")


def test_tampered_body_rejected():
    blob = bytearray(encrypt_bytes(SAMPLE, PW))
    blob[-1] ^= 0x01
    with pytest.raises(CryptoToolError, match="wrong password or tampered"):
        decrypt_bytes(bytes(blob), PW)


def test_tampered_header_rejected():
    blob = bytearray(encrypt_bytes(SAMPLE, PW))
    blob[HEADER_SIZE - 1] ^= 0x01  # flip a nonce bit
    with pytest.raises(CryptoToolError):
        decrypt_bytes(bytes(blob), PW)


def test_truncated_body_rejected():
    container = encrypt_bytes(SAMPLE, PW)
    with pytest.raises(CryptoToolError, match="truncated"):
        decrypt_bytes(container[:HEADER_SIZE + 4], PW)


def test_empty_container_rejected():
    with pytest.raises(CryptoToolError):
        decrypt_bytes(b"", PW)


# --------------------------------------------------------------------------- #
# File operations
# --------------------------------------------------------------------------- #
def test_encrypt_decrypt_file_roundtrip(tmp_path):
    src = tmp_path / "note.txt"
    src.write_text("file contents here", encoding="utf-8")
    enc = tmp_path / "note.enc"
    out = tmp_path / "note.out.txt"

    encrypt_file(src, enc, PW)
    assert enc.is_file() and enc.read_bytes().startswith(MAGIC)
    decrypt_file(enc, out, PW)
    assert out.read_text(encoding="utf-8") == "file contents here"


def test_encrypt_file_missing_source(tmp_path):
    with pytest.raises(CryptoToolError, match="not found"):
        encrypt_file(tmp_path / "nope.txt", tmp_path / "out.enc", PW)


def test_decrypt_file_missing_source(tmp_path):
    with pytest.raises(CryptoToolError, match="not found"):
        decrypt_file(tmp_path / "nope.enc", tmp_path / "out.txt", PW)


def test_encrypt_file_refuses_in_place(tmp_path):
    src = tmp_path / "note.txt"
    src.write_text("x", encoding="utf-8")
    with pytest.raises(CryptoToolError, match="differ"):
        encrypt_file(src, src, PW)


def test_decrypt_file_wrong_password(tmp_path):
    src = tmp_path / "note.txt"
    src.write_text("x", encoding="utf-8")
    enc = tmp_path / "note.enc"
    encrypt_file(src, enc, PW)
    with pytest.raises(CryptoToolError, match="wrong password"):
        decrypt_file(enc, tmp_path / "out.txt", "bad")


def test_file_info_on_disk(tmp_path):
    src = tmp_path / "note.txt"
    src.write_bytes(b"abc")
    enc = tmp_path / "note.enc"
    encrypt_file(src, enc, PW)
    info = file_info(enc)
    assert info.payload_size == 3 + TAG_SIZE
    with pytest.raises(CryptoToolError, match="not found"):
        file_info(tmp_path / "nope.enc")


def test_file_info_on_plain_file(tmp_path):
    plain = tmp_path / "plain.txt"
    plain.write_text("hello, this file is definitely not encrypted at all!", encoding="utf-8")
    with pytest.raises(CryptoToolError, match="magic"):
        file_info(plain)


def test_binary_content_survives(tmp_path):
    payload = bytes(range(256)) * 4
    src = tmp_path / "blob.bin"
    src.write_bytes(payload)
    enc = tmp_path / "blob.enc"
    out = tmp_path / "blob.out"
    encrypt_file(src, enc, PW)
    decrypt_file(enc, out, PW)
    assert out.read_bytes() == payload


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(tmp_path, capsys):
    assert run_demo(workdir=tmp_path) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "wrong password rejected" in out
    assert "tampering detected" in out
    assert (tmp_path / "secret_note.txt.enc").is_file()


def test_run_demo_is_idempotent(tmp_path, capsys):
    assert run_demo(workdir=tmp_path) == 0
    assert run_demo(workdir=tmp_path) == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "identical=True" in out


def test_cli_encrypt_decrypt_roundtrip(tmp_path, capsys):
    src = tmp_path / "msg.txt"
    src.write_text("round trip me", encoding="utf-8")
    enc = tmp_path / "msg.enc"
    out = tmp_path / "msg.out"

    assert main(["--encrypt", str(src), "--out", str(enc), "--password", PW]) == 0
    assert "Encrypted" in capsys.readouterr().out
    assert enc.is_file()

    assert main(["--decrypt", str(enc), "--out", str(out), "--password", PW]) == 0
    assert out.read_text(encoding="utf-8") == "round trip me"


def test_cli_default_output_names(tmp_path, capsys):
    src = tmp_path / "auto.txt"
    src.write_text("auto", encoding="utf-8")
    assert main(["--encrypt", str(src), "--password", PW]) == 0
    default_enc = tmp_path / "auto.txt.enc"
    assert default_enc.is_file()

    assert main(["--decrypt", str(default_enc), "--password", PW]) == 0
    assert (tmp_path / "auto.txt").read_text(encoding="utf-8") == "auto"


def test_cli_wrong_password_exit_one(tmp_path, capsys):
    src = tmp_path / "msg.txt"
    src.write_text("x", encoding="utf-8")
    enc = tmp_path / "msg.enc"
    main(["--encrypt", str(src), "--out", str(enc), "--password", PW])
    capsys.readouterr()

    assert main(["--decrypt", str(enc), "--out", str(tmp_path / "o.txt"),
                 "--password", "bad"]) == 1
    assert "wrong password" in capsys.readouterr().err


def test_cli_info_text_and_json(tmp_path, capsys):
    src = tmp_path / "msg.txt"
    src.write_text("info", encoding="utf-8")
    enc = tmp_path / "msg.enc"
    main(["--encrypt", str(src), "--out", str(enc), "--password", PW])
    capsys.readouterr()

    assert main(["--info", str(enc)]) == 0
    out = capsys.readouterr().out
    assert "Version" in out and "Salt" in out and "Nonce" in out

    assert main(["--info", str(enc), "--json"]) == 0
    import json

    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == VERSION
    assert len(payload["salt"]) == SALT_SIZE * 2


def test_cli_info_on_plain_file(tmp_path, capsys):
    plain = tmp_path / "plain.txt"
    plain.write_text("not encrypted - just a regular text file!", encoding="utf-8")
    assert main(["--info", str(plain)]) == 2
    assert "magic" in capsys.readouterr().err


def test_cli_missing_input(tmp_path, capsys):
    assert main(["--encrypt", str(tmp_path / "nope.txt"), "--password", PW]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_pass_file(tmp_path, capsys):
    src = tmp_path / "msg.txt"
    src.write_text("pf", encoding="utf-8")
    pw_file = tmp_path / "pw.txt"
    pw_file.write_text(PW + "\n", encoding="utf-8")  # echo-style trailing newline
    enc = tmp_path / "msg.enc"
    out = tmp_path / "msg.out"

    assert main(["--encrypt", str(src), "--out", str(enc), "--pass-file", str(pw_file)]) == 0
    assert main(["--decrypt", str(enc), "--out", str(out), "--pass-file", str(pw_file)]) == 0
    assert out.read_text(encoding="utf-8") == "pf"


def test_cli_pass_file_missing(tmp_path, capsys):
    src = tmp_path / "msg.txt"
    src.write_text("x", encoding="utf-8")
    assert main(["--encrypt", str(src), "--pass-file", str(tmp_path / "nope.txt")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_empty_password(tmp_path, capsys):
    src = tmp_path / "msg.txt"
    src.write_text("x", encoding="utf-8")
    assert main(["--encrypt", str(src), "--password", ""]) == 2
    assert "empty" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])
