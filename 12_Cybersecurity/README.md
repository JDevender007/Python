<div align="center">

# 🔐 Cybersecurity Projects

### Five security programs that each looked like "grade the secret and print the score" — and each one was really a question about what the number can prove. A character set is a union, not a product. A miss from a partial search is not strength. A ciphertext that decrypts is not a ciphertext that survived. A header is a bit field with units. A fix version is the first safe version, not the last affected one.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Every project here is an **offline analyser of a captured artifact**, not a tool pointed at a live
target. A password list, a hash table, a sealed container, an IPv4 capture and an advisory
inventory all ship as bundled ASCII in `data/`; the code parses them with the same strictness it
would apply to real input, and nothing opens a socket, downloads a wordlist or touches the clock.

That choice is deliberate. A demo that dials out is not reproducible, and a demo that cannot be
reproduced cannot show you the number that was wrong last time. Here the whole artifact is on
disk, so two runs print the same bytes and each defect is a printable difference rather than an
occasional mystery.

**The lesson of each project is different, on purpose.** Five variations on "add a regex" would
teach nothing; five different places a security program confuses a model with a measurement, a
sample with a proof, or a format with a guess is the subject.

- **Password_Strength_Analyzer** — *an alphabet is the sum of its classes, and entropy is a
  property of randomness.* `size *= CHARSET_SIZES[name]` multiplies 26 × 26 × 10 into **6760**
  characters for a password that can only draw on **62**; `log2(6760)` then charges **153 bits**
  for 12 characters against a real **71**. `Password2024` is a dictionary word plus a year, so the
  legacy model calls it **100/100 "very strong"** while the rebuild, after deducting **12 bits**
  of recognised structure, says **59/100 fair**. Crack time is `1 << (bits - 1)` guesses over an
  integer rate, never `2 ** entropy / 2`.
- **Hash_Cracker** — *a search has three outcomes, and only two are statements about the
  password.* A wordlist miss returns `None`, which the legacy tool names `strong`: 117 candidates
  say nothing about an unbounded keyspace. The rebuild returns `found`, `exhausted` (the search
  was complete, so the absence is a proof) and `inconclusive` (candidates remained). It also reads
  the **salt** — `sha256("s3cr3t" + "monkey")` misses the bare-word loop and declares a password
  that is *in* the wordlist to be strong — and counts **117 distinct candidates**, not the **126
  lines** that include 6 comments and 3 repeats.
- **File_Encryption_Tool** — *encryption hides a message; it does not tell you the message
  survived.* The legacy cipher is a nonce-less, unauthenticated XOR keystream: a flipped
  ciphertext byte decrypts to `'@ttack at dawn...'` and raises nothing, and reusing the keystream
  gives `c1 ^ c2 == m1 ^ m2`, which is the two plaintexts. The rebuild puts a 6-byte magic, a
  version and a 12-byte nonce in front, derives a 32-byte key, and appends a **32-byte tag** over
  header **and** body — so a wrong key, a wrong version, a truncated file and a flipped bit are
  one refusal: `a container tag does not match`. The 43-byte note becomes a **93-byte** container:
  **116.3%** overhead in tenths, rounded half up.
- **Network_Packet_Analyzer** — *a header is a bit field, and every field has a unit.* `offset =
  20` ignores the IHL, so packet 2's 24-byte header (four option bytes) reads as ports
  **257 → 256** instead of **8443 → 51001**. `field & 0x7` calls the bottom of the fragment
  offset "flags", and the whole field as the offset turns a plain DF packet into a fragment at
  **16384 units (131072 bytes)**. A correct one's-complement checksum sums to **`0xFFFF`**, not
  zero, so the legacy `== 0` test accepts **0 of 6** while the rebuild accepts **5** and rejects
  the packet whose TTL was changed. Packet 3 declares **40** bytes and holds **36**: payload is
  **76 declared, 72 captured, 104** by subtraction.
- **Vulnerability_Scanner** — *a version is an ordered tuple, and a fix is an exclusive upper
  bound.* `"1.10.0" < "1.9.0"` is true as text, so `quartz 1.9.9` reads as newer than the 1.10.0
  fix and scans clean; `version <= fixed` reports `basalt 0.10.0` — the fix itself — as vulnerable
  forever; and a dictionary keyed by package keeps only `lumen`'s second window, losing
  `1.2.0` entirely. The legacy scan finds **2** where the rebuild finds **4**: **1 false
  positive** and **3 missed**, with `aegis` reported unknown rather than safe.

**Every number is exact and every claim is checkable.** Money and ratios are integers —
`divide_half_up`, basis points, permille, tenths of a percent — never `round()` or a float on the
measurement path, and byte counts are compared as bytes. Each project's `audit()` re-derives its
own result from the loaded records instead of restating the summary it just printed, and its
readers are injectable — `read_decoded=`, `interpret=`, `recompute=`, `seal_func=`, `crack=` — so
a negative control can make exactly one check fail and prove the check is live.

The libraries used are `csv`, `hashlib`, `hmac`, `math`, `string`, `functools`, `argparse` and
`dataclasses` — the standard library, nothing else. No sockets, no `scapy`, no `cryptography`
package, no clock, no `random`.

---

# 🎓 Learning Objectives

- Count a character set as the union of its classes, and see the product invent an alphabet
- Treat entropy as an upper bound for random strings, then deduct recognised structure explicitly
- Keep a password out of every printed line while still reporting its length
- Convert a keyspace into integer guesses, and render a duration without float division
- Recognise that a wordlist miss is inconclusive until the keyspace is exhausted
- Read a salt as part of the hashed input, and validate an algorithm against its digest length
- Count work as distinct candidates, not as lines in a file
- Separate confidentiality from integrity, and verify a tag before returning any plaintext
- Design a container format: magic, version, nonce, length, tag, and a pinned ciphertext hash
- Read the IHL in 32-bit words and find the transport header after a variable-length header
- Split one 16-bit field into a 3-bit flag set and a 13-bit offset scaled by 8
- Verify a one's-complement checksum with its own field zeroed, and know why `0xFFFF` is success
- Let a declared total length govern, and disclose a short capture instead of subtracting silently
- Parse and order versions numerically, including zero-padding and pre-releases
- Treat an introduced version as inclusive and a fix as an exclusive upper bound
- Keep every affected window per package, and report a gap version as clean on purpose
- Report the nearest safe version above the installed one, or `no fix known`
- Reconcile two independent computations and write an `audit()` with a negative control

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Password_Strength_Analyzer | Alias-free alphabets, structure penalties, integer crack time and mask-only output. | 177 | ✅
02 | Hash_Cracker | Tri-state search verdicts, salted digests, deduplicated candidates and counted work. | 133 | ✅
03 | File_Encryption_Tool | Authenticated container format: nonce, tag, fail-closed opening and overhead in tenths. | 110 | ✅
04 | Network_Packet_Analyzer | IPv4 header units, flag/offset bit fields, one's-complement checksums and truncation. | 114 | ✅
05 | Vulnerability_Scanner | Numeric version order, half-open advisory windows and open-ended fixes. | 97 | ✅

**Total: 631 tests**, and **110 audit checks** across the five projects (26 + 18 + 14 + 27 + 25).

---

# 🧠 Concepts Covered

- Character classes as a union (26 + 26 + 10 = 62) versus a product (26 × 26 × 10 = 6760)
- Entropy as a ceiling for random strings, and structure as a documented deduction
- Half-open score bands: `very weak`, `weak`, `fair`, `strong`, `very strong`
- Integer keyspaces, integer guess rates, and durations rendered from whole seconds
- Masking as a rendering concern: `******** (8 chars)`, never the secret
- Wordlist, mutation and bounded brute-force searches with declared keyspaces
- Found / exhausted / inconclusive, and what a complete search can prove
- Salted digests, MD5 versus SHA-256 digest lengths, and order-preserving deduplication
- Stream ciphers, keystream reuse, and the two-time-pad identity `c1 ^ c2 == m1 ^ m2`
- Key derivation from a passphrase, a per-message nonce, and a tag over header and body
- Fail-closed opening: wrong key, wrong version, truncation and bit flips are one refusal
- Container overhead as a ratio in tenths, rounded half up
- IPv4 IHL in 32-bit words, options, and ports read after a variable-length header
- Flags as the top three bits of one field, fragment offset as the low thirteen, scaled by 8
- One's-complement checksums, folded carries and the `0xFFFF` success condition
- Declared total length, captured size, and truncation disclosed as a number
- Semantic version ordering: three integer parts, zero padding, pre-release identifiers
- Advisory windows: inclusive introduction, exclusive fix, disjoint ranges, open-ended entries
- Audits that re-derive from source records, with a negative control per injectable reader

---

# 📁 Repository Structure

```text
12_Cybersecurity/
│
├── Password_Strength_Analyzer/
│   ├── src/    analyzer.py, main.py
│   ├── tests/  test_analyzer.py
│   └── data/   passwords.csv
│
├── Hash_Cracker/
│   ├── src/    cracker.py, main.py
│   ├── tests/  test_cracker.py
│   └── data/   targets.csv, wordlist.txt
│
├── File_Encryption_Tool/
│   ├── src/    crypto_tool.py, main.py
│   ├── tests/  test_crypto_tool.py
│   └── data/   secret_note.txt
│
├── Network_Packet_Analyzer/
│   ├── src/    packet_analyzer.py, main.py
│   ├── tests/  test_packet_analyzer.py
│   └── data/   capture.txt
│
├── Vulnerability_Scanner/
│   ├── src/    scanner.py, main.py
│   ├── tests/  test_scanner.py
│   └── data/   inventory.csv, advisories.csv
│
└── README.md
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse CLI,
a `tests/` suite, deterministic ASCII seeds in `data/`, a pinned `requirements.txt`, a
`.gitignore`, and a `README.md` that states its own defect and pins its own numbers.

The artifact itself is data. `passwords.csv` holds 6 invented secrets, `targets.csv` holds 5
digests with their salts and algorithms over a 117-candidate wordlist, `secret_note.txt` holds a
43-byte note, `capture.txt` holds 6 IPv4 packets (one with options, one truncated, one continuation
fragment, one bad checksum), and `inventory.csv` plus `advisories.csv` hold 7 packages against 9
windows. Each library module still carries the defective expression as an executable string —
`LEGACY_CHARSET`, `LEGACY_SCORE`, `LEGACY_CRACK`, `LEGACY_READER`, `LEGACY_VERDICT`,
`LEGACY_CIPHER`, `LEGACY_KDF`, `LEGACY_HEADER`, `LEGACY_FLAGS`, `LEGACY_CHECKSUM`,
`LEGACY_PAYLOAD`, `LEGACY_COMPARE`, `LEGACY_UPPER`, `LEGACY_INDEX` — so the tests can run the
wrong code beside the right one on the same bytes.

No module imports `socket`, `scapy`, `cryptography` or `time`. The cipher is byte arithmetic over
a fixed nonce, the capture is parsed from hex records, and every demo is byte-for-byte
reproducible.

---

# ▶️ Run any project

```bash
cd 12_Cybersecurity/Network_Packet_Analyzer

python src/main.py --demo          # offline, deterministic, exit 0
python src/main.py --file data/capture.txt --json out.json
python src/main.py --audit         # every check with PASS/FAIL
python -m pytest tests -q          # the suite
```

Every project supports `--demo`, `--quiet` with `--demo` (prints nothing on stdout or stderr),
`--audit`, `--json <path>` and `--file <input>` naming the primary seed file; sibling seeds are
read from the same folder. Exit code `2` means the input was refused, with `error: ...` on
stderr — a malformed record, a duplicate label or package, a non-ASCII byte, a version with too
many parts, an inverted advisory window, a header longer than the packet it announces. Nothing
opens a connection and no demo writes into the repository: JSON output goes only where you point
it.

---

# ✅ Verify the whole category

```powershell
Get-ChildItem -Directory | ForEach-Object {
    Push-Location $_
    python -m compileall -q src tests
    python -m pytest tests -q
    python src\main.py --demo
    python src\main.py --demo --quiet
    Pop-Location
}
```

The gates each project must pass, and does:

1. `compileall` on `src` and `tests` exits 0
2. `pytest` passes with no skips, 97+ tests
3. `--demo` exits 0, prints `Cross-checks OK: ...` then `Demo completed successfully.` as its last two lines
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing at all
5. no non-ASCII byte in `src/`, `tests/` or the text data files

---

# ⚠️ Ethical Use

These projects are defensive and educational. Scan, crack, decrypt and analyse only artifacts you
own or have explicit permission to test; never point a technique at someone else's account,
host or traffic. The seeds are invented, the nonces are fixed, and the wordlist is a lab fixture.

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why a character set is a union, and why multiplying class sizes invents an alphabet
- Why entropy describes a random draw, not a password someone chose
- Why "not in the wordlist" is not a strength verdict until the keyspace is empty
- Why a salt that is present in a record and ignored by the search is a silent false negative
- Why a ciphertext that decrypts proves nothing about the plaintext that came out
- Why a tag must cover the header as well as the body
- Why a header length is counted in words while a payload length is counted in bytes
- Why three bits of one field are flags and thirteen are an offset in 8-byte units
- Why a correct checksum sums to `0xFFFF`, and what `== 0` is really testing
- Why the declared total length, not the captured size, is the authority
- Why `"1.10.0" < "1.9.0"` and why no string compare can fix it
- Why a fix version is the first safe version, so the upper bound must be exclusive
- Why one window per package loses every affected range but the last
- How to write an audit whose every check has a negative control
- How to make a security demonstration reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `parse_capture`, `parse_hex`, `parse_version`, `load_rows`, `load_targets`, `load_items`, `load_advisories`, `read_note`
Records — `Row`, `Password`, `Target`, `Outcome`, `Container`, `Packet`, `Decoded`, `LegacyView`, `Version`, `Item`, `Advisory`, `Finding`
Validation — `AnalyzerError`, `CrackerError`, `CryptoError`, `PacketError`, `ScannerError`
Alphabets — `detect_classes`, `charset_size`, `legacy_charset_size`, `milli_bits_per_char`, `format_millibits`
Scoring — `find_issues`, `penalty_bits`, `guess_bits_of`, `band_of`, `score_of`, `mask`
Search — `crack`, `search`, `build_targets`, `dedupe`, `verdict`, `exhausted`, `bounded_search`
Crypto — `seal`, `unseal`, `derive_key`, `keystream`, `tag_of`, `format_container`, `parse_container`
Packets — `decode`, `header_checksum`, `ones_sum`, `checksum_is_valid`, `flag_names_of`, `dotted`, `legacy_view`
Versions — `parse_version`, `compare`, `_prerelease_key`, `Version.parts`, `Advisory.contains`, `nearest_fix`
Legacy — `LEGACY_CHARSET`, `LEGACY_SCORE`, `LEGACY_CRACK`, `LEGACY_READER`, `LEGACY_VERDICT`, `LEGACY_CIPHER`, `LEGACY_KDF`, `LEGACY_HEADER`, `LEGACY_FLAGS`, `LEGACY_CHECKSUM`, `LEGACY_PAYLOAD`, `LEGACY_COMPARE`, `LEGACY_UPPER`, `LEGACY_INDEX`
Arithmetic — `divide_half_up`, `format_bp`, `format_permille`, `format_duration`
Reporting — `measure`, `report`, `render_rows`, `render_targets`, `render_container`, `render_packets`, `render_inventory`, `--json`
Auditing — `audit`, `_guard`, injectable readers, decoders, interpreters, seal functions and scanners
Testing — exact pinned numbers, validation refusals, one failing check per negative control

---

# 🚀 Future Improvements

- A shared `--batch` runner that executes all five demos and compares their output hashes
- A key-file mode beside the passphrase, so the container format carries a second credential path
- A pcapng reader behind the same `decode()` interface, keeping the capture model unchanged
- A version-range grammar (`^1.2`, `~2.0`, `<3`) that lowers to the same half-open windows
- A property-based fuzz harness for the decoder, asserting it never invents a packet or a frame
- A scoring harness that compares the guess-bit model against a large public password corpus
- A terminal-diff view that highlights the exact bytes the legacy cipher changed

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a clear message.
4. Push the branch.
5. Open a Pull Request.

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
