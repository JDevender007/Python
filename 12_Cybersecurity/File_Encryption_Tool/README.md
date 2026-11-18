# File Encryption Tool

Encryption hides a message. It does not tell you the message survived. The legacy cipher is the
one every "roll your own XOR" tutorial contains:

```python
key = hashlib.sha256(password.encode()).digest()
stream = hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
return bytes(a ^ b for a, b in zip(data, stream))
```

It is a **stream cipher with no authentication and no nonce**. Three consequences follow, and all
of them are silent.

**1. A flipped ciphertext byte is a flipped plaintext byte.** Decrypting the tampered container
does not raise; it returns `'@ttack at dawn. Move the convoy to grid 7.\n'` -- a shorter attack
that still reads as English. Nobody notices, because nothing checks.

**2. Reusing the keystream publishes both messages.** XOR the two ciphertexts and the keys
cancel: `c1 ^ c2 == m1 ^ m2`, so `13110013060a5441165944570703` is printed for the pair
`attack at dawn` and `retreat by 6pm`. That is not a subtle weakness; it is the plaintexts.

**3. A password is not a key.** `sha256(password)` makes a fast, unsalted KDF: a guessable
passphrase is a guessable key, and there is no salt to stop a table of precomputed digests.

The rebuild puts a 6-byte magic and a version in front of a 12-byte nonce, derives a 32-byte key,
encrypts with a keystream that includes the nonce, and appends a **32-byte tag** over the header
and the body. Opening a container verifies the tag before it returns a single plaintext byte, so
a wrong key, a wrong version, a truncated file or a flipped bit are all one refusal:
`a container tag does not match`. Every number is a real byte count: the 43-byte note becomes a
**93-byte** container (18 bytes of header, 32 of tag), an overhead of **116.3%** computed in
tenths and rounded half up.

The demonstration needs no key store and no network: the note and password are bundled, the nonce
is fixed, and the container's sha256 is pinned, so two runs are byte identical.

## What this project teaches

- Confidentiality versus integrity: hiding a message and proving it is the same message
- An unauthenticated stream cipher, and why a flipped byte decrypts into other text
- A nonce's job: make the keystream unique per message, not just per key
- Key reuse as a two-time pad, demonstrated by `c1 ^ c2 == m1 ^ m2`
- A tag over header **and** body, verified before anything is returned
- Refusing a wrong key, an unknown version, a truncated container and a damaged header
- Fixed header and tag sizes as a format contract, not an implementation detail
- Overhead as a ratio in tenths, rounded half up, never a float
- Pinned ciphertext hashes as a determinism check on an otherwise opaque transform
- An empty plaintext that still carries a tag, because the header must be authenticated too

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/secret_note.txt --json out.json
python src/main.py --file data/secret_note.txt --audit
python -m pytest tests -q
```

`--file` names the plaintext note, `--password` sets the passphrase, and `--flip N` damages one
ciphertext byte so the refusal can be watched. Exit code `2` means the input was refused -- a
missing file, a non-ASCII note, an empty note, or a non-integer `--flip` offset outside the
container.

## Project structure

```
File_Encryption_Tool/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   └── secret_note.txt     # 43 ASCII bytes
├── src/
│   ├── crypto_tool.py      # format, keystream, tag, checks, demo
│   └── main.py             # argparse only
└── tests/
    └── test_crypto_tool.py # 110 tests
```

## What the demo shows

| item | legacy cipher | sealed container |
| --- | --- | --- |
| size for the 43-byte note | 43 bytes | **93 bytes** (18 header + 32 tag + 43 body) |
| overhead | 0% -- and no integrity | **116.3%**, tenths rounded half up |
| flip a byte at index 0 | decrypts to `@ttack at dawn...` | refuses: `tag does not match` |
| wrong key | returns the same garbage | refuses |
| truncated file | returns a short plaintext | refuses |
| reuse a nonce | `c1 ^ c2 == m1 ^ m2` | **two nonces, two ciphertexts** |

- The legacy cipher round-trips all 43 bytes correctly, which is exactly why it ships: the happy
  path is perfect and every other path is silently wrong
- Flipping index 0 turns `Attack` into `@ttack` and **no error is raised**; the sealed container
  refuses the identical byte, and also refuses a wrong key, an unknown version and a truncation
- One nonce reused for `attack at dawn` and `retreat by 6pm` prints
  `13110013060a5441165944570703`, which is both `c1 ^ c2` and `m1 ^ m2`
- Under the same key, a fresh nonce produces different ciphertexts that both open, and the
  container's sha256 is pinned to `80d6eb8c...e1b5fa`
- 14/14 audit checks pass, including an empty plaintext that still carries its tag

## Requirements

Python 3.10+, standard library only (`hashlib`, `pathlib`, `argparse`, `dataclasses`). Tests need
pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
