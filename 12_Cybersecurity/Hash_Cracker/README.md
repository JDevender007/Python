# Hash Cracker

A wordlist attack returns one of three things, and the legacy tool has a name for only two of
them:

```python
for line in open(wordlist):
    if hashlib.sha256(line.encode()).hexdigest() == digest:
        return line
return None                              # "password is strong"

verdict = "strong" if recovered is None else "weak"
```

**1. A miss from a partial search is not strength.** 117 candidates say nothing about an
unbounded keyspace. Reporting `strong` after 117 guesses is a claim about the password that the
work did not earn. The only negative a search can *prove* is the one a **complete** search
proves: run all 10000 four-digit PINs, find nothing, and "not a 4-digit PIN" is a fact. The
rebuild returns three verdicts -- `found`, `exhausted` (the search was complete, so the absence
is a proof) and `inconclusive` (the search stopped while candidates remained) -- and the bundled
targets hit all three: **3 found, 1 inconclusive, 1 exhausted**.

**2. The salt is part of the hash.** `carol`'s digest is `sha256("s3cr3t" + "monkey")`, and
`monkey` is line 16 of the wordlist the attack already read. The legacy loop hashes the bare
word, misses, and declares a password that is *in the wordlist* to be strong. A field that is
present in the record and ignored by the search is a false negative with no log line.

**3. Work is counted, not timed.** The legacy counter increments once per line, so **126** lines
are reported as 126 attempts when **117** distinct candidates were hashed: 6 comment lines and 3
repeated words were counted as work nobody did. The throughput printed beside it comes from a
clock, so two runs of the same demo print two different rates.

The rebuild reads the salt, validates each record's algorithm against its digest length (MD5 is
32 hex characters, SHA-256 is 64), deduplicates the candidate list while keeping the attack
order, and never samples the clock. `--demo` twice prints the same bytes.

## What this project teaches

- A search has three outcomes, and only two of them are statements about the password
- Why "not found" is inconclusive until the keyspace is exhausted
- What a *complete* search can prove: absence inside a bounded space, and nothing more
- A salt as part of the hashed input, and the false negative that ignoring it produces
- Digest length as part of an algorithm's contract, validated before any comparison
- Work as a count of distinct candidates, not a count of lines in a file
- Comments and duplicate entries inflating an attempt counter that nobody audits
- Why a clock in a report makes two runs of the same demo disagree
- Order-preserving deduplication, so an attack is reproducible step for step
- Auditing verdicts against an independent scan, with injectable search functions

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/targets.csv --json out.json
python src/main.py --file data/targets.csv --audit
python -m pytest tests -q
```

`--file` names the target CSV; `wordlist.txt` is read from the same folder. Exit code `2` means
the input was refused -- a missing column, an unknown algorithm or mode, a digest whose length
does not match its algorithm, a non-hexadecimal digest, or a duplicated label.

## Project structure

```
Hash_Cracker/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   ├── targets.csv         # 5 targets: sha256, md5, salted, missing, PIN
│   └── wordlist.txt        # 126 non-empty lines, 117 distinct candidates
├── src/
│   ├── cracker.py          # validation, search, verdicts, checks, demo
│   └── main.py             # argparse only
└── tests/
    └── test_cracker.py     # 133 tests
```

## What the demo shows

| label | algorithm | mode | verdict | attempts | recovered |
| --- | --- | --- | --- | --: | --- |
| alice | sha256 | wordlist | **found** | 9 | `sunshine` |
| bob | md5 | wordlist | **found** | 32 | `michael` |
| carol | sha256 | wordlist | **found** | 16 | `monkey` (with salt `s3cr3t`) |
| dave | sha256 | wordlist | **inconclusive** | 117 | -- |
| erin | sha256 | pin4 | **exhausted** | 10000 | -- |

- `dave` misses after **117** candidates of an **unbounded** keyspace: nothing is proven
- `erin` misses after **10000 of 10000** four-digit PINs: **100.00%** of that keyspace is
  covered, so "not a 4-digit PIN" is established -- and that is all
- `carol` is found only because the salt is prepended; the salt-blind legacy loop misses her and
  calls the password strong
- The legacy report calls **3** misses strong -- `carol`, `dave`, `erin` -- one of which is a
  password that was in the wordlist all along
- **126** lines are counted as attempts against **117** hashed candidates; the difference of
  **9** is 6 comments and 3 repeated words
- 18/18 audit checks pass, with negative controls that hand the audit a search which finds
  nothing and watch the independent scan disagree

## Requirements

Python 3.10+, standard library only (`hashlib`, `csv`, `string`, `argparse`, `dataclasses`).
Tests need pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
