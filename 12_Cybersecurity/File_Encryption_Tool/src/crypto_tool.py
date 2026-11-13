"""Authenticated file encryption: AES-256-GCM with a scrypt-derived key.

File format (version 1):

    magic   8 bytes   b"\\x89PYENC\\r\\n"
    version 1 byte    0x01
    salt    16 bytes  random, per file
    nonce   12 bytes  random, per file
    body    N bytes   AESGCM(key, nonce).encrypt(plaintext)  (tag appended)

The password never touches disk; only the salt and nonce do. Decryption
verifies the GCM tag, so tampering or a wrong password fails loudly instead
of producing corrupt output.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

LOG = logging.getLogger("file.crypt")

MAGIC = b"\x89PYENC\r\n"
VERSION = 1
SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
HEADER_SIZE = len(MAGIC) + 1 + SALT_SIZE + NONCE_SIZE  # 37

# scrypt parameters: interactive log_n=14 keeps a demo fast (<0.1s/file)
SCRYPT_LOG_N = 14
SCRYPT_R = 8
SCRYPT_P = 1


class CryptoToolError(RuntimeError):
    """Raised for format problems, wrong passwords, and tampered data."""


# --------------------------------------------------------------------------- #
# Key derivation and primitives
# --------------------------------------------------------------------------- #
def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from a password and salt using scrypt."""
    if not password:
        raise CryptoToolError("password must not be empty")
    if len(salt) != SALT_SIZE:
        raise CryptoToolError(f"salt must be {SALT_SIZE} bytes")
    kdf = Scrypt(salt=salt, length=32, n=2 ** SCRYPT_LOG_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def encrypt_bytes(
    plaintext: bytes,
    password: str,
    *,
    salt: bytes | None = None,
    nonce: bytes | None = None,
) -> bytes:
    """Encrypt bytes into the versioned container format."""
    salt = salt if salt is not None else os.urandom(SALT_SIZE)
    nonce = nonce if nonce is not None else os.urandom(NONCE_SIZE)
    if len(salt) != SALT_SIZE:
        raise CryptoToolError(f"salt must be {SALT_SIZE} bytes")
    if len(nonce) != NONCE_SIZE:
        raise CryptoToolError(f"nonce must be {NONCE_SIZE} bytes")

    key = derive_key(password, salt)
    body = AESGCM(key).encrypt(nonce, plaintext, associated_data=MAGIC + bytes([VERSION]))
    return MAGIC + bytes([VERSION]) + salt + nonce + body


def decrypt_bytes(container: bytes, password: str) -> bytes:
    """Decrypt a container, raising CryptoToolError on any problem."""
    parsed = parse_header(container)
    salt = parsed["salt"]
    nonce = parsed["nonce"]
    body = container[HEADER_SIZE:]
    if len(body) < TAG_SIZE:
        raise CryptoToolError("ciphertext is truncated (missing authentication tag)")

    key = derive_key(password, salt)
    try:
        return AESGCM(key).decrypt(nonce, body, associated_data=MAGIC + bytes([VERSION]))
    except InvalidTag as exc:
        raise CryptoToolError(
            "decryption failed: wrong password or tampered file"
        ) from exc


@dataclass
class HeaderInfo:
    """What can be learned from a container without the password."""

    version: int
    salt_hex: str
    nonce_hex: str
    total_size: int
    payload_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "salt": self.salt_hex,
            "nonce": self.nonce_hex,
            "total_size": self.total_size,
            "payload_size": self.payload_size,
        }


def parse_header(container: bytes) -> dict[str, Any]:
    """Validate the container header and return its fields."""
    if len(container) < HEADER_SIZE:
        raise CryptoToolError("file too short to be an encrypted container")
    if not container.startswith(MAGIC):
        raise CryptoToolError("not a PYENC file (bad magic bytes)")
    version = container[len(MAGIC)]
    if version != VERSION:
        raise CryptoToolError(f"unsupported version {version} (expected {VERSION})")
    offset = len(MAGIC) + 1
    salt = container[offset:offset + SALT_SIZE]
    nonce = container[offset + SALT_SIZE:offset + SALT_SIZE + NONCE_SIZE]
    if len(salt) != SALT_SIZE or len(nonce) != NONCE_SIZE:
        raise CryptoToolError("header is truncated")
    return {"version": version, "salt": salt, "nonce": nonce}


def inspect_container(container: bytes) -> HeaderInfo:
    """Return non-secret metadata about an encrypted container."""
    parsed = parse_header(container)
    return HeaderInfo(
        version=parsed["version"],
        salt_hex=parsed["salt"].hex(),
        nonce_hex=parsed["nonce"].hex(),
        total_size=len(container),
        payload_size=len(container) - HEADER_SIZE,
    )


# --------------------------------------------------------------------------- #
# File operations
# --------------------------------------------------------------------------- #
def encrypt_file(source: str | Path, target: str | Path, password: str) -> Path:
    """Encrypt `source` into `target` and return the target path."""
    src = Path(source)
    if not src.is_file():
        raise CryptoToolError(f"file not found: {src}")
    dst = Path(target)
    if dst.resolve() == src.resolve():
        raise CryptoToolError("output path must differ from the input path")
    dst.parent.mkdir(parents=True, exist_ok=True)
    container = encrypt_bytes(src.read_bytes(), password)
    dst.write_bytes(container)
    LOG.info("encrypted %s -> %s (%s bytes)", src, dst, len(container))
    return dst


def decrypt_file(source: str | Path, target: str | Path, password: str) -> Path:
    """Decrypt `source` into `target` and return the target path."""
    src = Path(source)
    if not src.is_file():
        raise CryptoToolError(f"file not found: {src}")
    dst = Path(target)
    if dst.resolve() == src.resolve():
        raise CryptoToolError("output path must differ from the input path")
    plaintext = decrypt_bytes(src.read_bytes(), password)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(plaintext)
    LOG.info("decrypted %s -> %s (%s bytes)", src, dst, len(plaintext))
    return dst


def file_info(path: str | Path) -> HeaderInfo:
    """Inspect an encrypted file on disk."""
    target = Path(path)
    if not target.is_file():
        raise CryptoToolError(f"file not found: {target}")
    return inspect_container(target.read_bytes())


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
DEMO_PASSWORD = "demo-password-not-secret"


def run_demo(workdir: Path | None = None) -> int:
    """Create, encrypt, verify, and decrypt a sample file — fully offline."""
    print("=" * 60)
    print(" FILE ENCRYPTION TOOL - offline demo")
    print(f" AES-256-GCM + scrypt (log_n={SCRYPT_LOG_N}) - nothing leaves this machine")
    print("=" * 60)

    directory = workdir or Path(__file__).resolve().parent.parent / "data"
    directory.mkdir(parents=True, exist_ok=True)

    plain = directory / "secret_note.txt"
    encrypted = directory / "secret_note.txt.enc"
    restored = directory / "secret_note.restored.txt"

    # idempotent: rewrite the sample every run
    payload = (
        "Top secret memo.\n"
        "The project roadmap lives at D:\\Projects\\Python.\n"
        "Delete this file after the demo - the ciphertext is safe to keep.\n"
    )
    plain.write_text(payload, encoding="utf-8")
    print(f"\n[1] Wrote sample plaintext: {plain.name} ({plain.stat().st_size} bytes)")

    encrypt_file(plain, encrypted, DEMO_PASSWORD)
    info = file_info(encrypted)
    overhead = info.total_size - plain.stat().st_size
    print(f"[2] Encrypted -> {encrypted.name} ({info.total_size} bytes, +{overhead} overhead)")
    print(f"    version={info.version} salt={info.salt_hex[:16]}... "
          f"nonce={info.nonce_hex[:16]}...")

    # deterministic verification: decrypt in memory and compare
    restored_bytes = decrypt_bytes(encrypted.read_bytes(), DEMO_PASSWORD)
    identical = restored_bytes == plain.read_bytes()
    print(f"[3] Decrypt verified in memory: identical={identical}")
    assert identical, "demo round-trip failed"

    decrypt_file(encrypted, restored, DEMO_PASSWORD)
    print(f"[4] Decrypted -> {restored.name} "
          f"({restored.stat().st_size} bytes, identical={restored.read_text(encoding='utf-8') == payload})")

    print("\n[5] Security properties:")
    second = encrypt_bytes(plain.read_bytes(), DEMO_PASSWORD)
    print(f"    - fresh salt/nonce each time: ciphertexts differ "
          f"({encrypted.read_bytes() == second})")
    try:
        decrypt_bytes(encrypted.read_bytes(), "wrong-password")
        print("    - WRONG PASSWORD ACCEPTED (this must never happen!)")
        return 1
    except CryptoToolError as exc:
        print(f"    - wrong password rejected: {exc}")
    tampered = bytearray(encrypted.read_bytes())
    tampered[-1] ^= 0xFF
    try:
        decrypt_bytes(bytes(tampered), DEMO_PASSWORD)
        print("    - TAMPERED FILE ACCEPTED (this must never happen!)")
        return 1
    except CryptoToolError as exc:
        print(f"    - tampering detected: {exc}")

    print("\nDemo completed successfully.")
    return 0
