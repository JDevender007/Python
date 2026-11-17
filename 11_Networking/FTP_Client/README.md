# FTP Client

An FTP control connection is a **grammar**, not a list of lines: a reply continues while its
fourth character is `-` and ends only at a line whose fourth character is a space with the
same three-digit code. The legacy client keeps the line that ends a reply and throws away
everything the reply *said*:

```python
if line[3:4] == " ": replies.append(line)
```

So the three-line banner arrives as `220 Ready`, and `211-Features:` with its four capability
lines arrives as `211 End` -- one line, zero capabilities. The server later refuses a command
the client never knew existed, and nothing in the logs explains why.

Two more defects sit in the same session. The passive port is **two bytes**, `p1 * 256 + p2`,
but the legacy decode takes the last field of the tuple, so `(10,0,0,5,19,137)` means port
`137` instead of `5001`. And `226 Transfer complete` is a **claim**, not a byte count: it
arrives after a short read too, so a truncated file is written and reported as a success.

The rebuild parses the reply grammar, decodes the port as two bytes, and compares the bytes
that arrived with the number the `150` reply declared before it calls a transfer done.

## What this project teaches

- A reply is a sequence of lines; the continuation character governs where it ends
- Why filtering for the terminating line keeps the frame and loses the payload
- A preliminary reply (`150`) and a final reply (`226`) belonging to one command
- A passive port as two bytes: `p1 * 256 + p2`, not the last field
- Why reading the low byte can connect to a *different* service
- `226` as a claim, and the declared byte count as the evidence that settles it
- A shortfall as `declared - received`, and the received share in permille, not a float
- Refusing an over-long read instead of truncating it silently
- Parsing a bundled transcript as the server side, so the demo needs no network
- Auditing every decoded value against an independent re-parse, with a negative control

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/session.log --json out.json
python src/main.py --file data/session.log --audit
python -m pytest tests -q
```

`--file` names the control transcript; `payload.txt` is read from the same folder. Exit code
`2` means the input was refused -- a malformed record, an unknown direction, a reply whose
continuation never ends, or a payload longer than the byte count the server declared.

## Project structure

```
FTP_Client/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   ├── session.log         # 8 commands, 10 replies, 25 transcript records
│   └── payload.txt         # exactly 1200 ASCII bytes, ending mid-record
├── src/
│   ├── ftp.py              # grammar, decoding, accounting, checks, demo
│   └── main.py             # argparse only
└── tests/
    └── test_ftp.py         # 124 tests
```

## What the demo shows

| command | replies | lines | code | final |
| --- | --: | --: | --: | --- |
| (greeting) | 1 | 3 | 220 | Ready |
| USER | 1 | 1 | 331 | Password required for student |
| PASS | 1 | 1 | 230 | Logged in |
| FEAT | 1 | 6 | 211 | End |
| PASV | 1 | 1 | 227 | Entering Passive Mode (10,0,0,5,19,137) |
| TYPE | 1 | 1 | 200 | Type set to I |
| SIZE | 1 | 1 | 213 | 1234 |
| RETR | **2** | 2 | 226 | Transfer complete |
| QUIT | 1 | 1 | 221 | Bye |

- The banner is **3 lines**; the legacy filter keeps **1** and loses the two that say what
  server this is
- `FEAT` is **6 lines** carrying **4** capabilities (`UTF8`, `MDTM`, `SIZE`, `REST STREAM`);
  the legacy filter keeps **1** line and reports **0**
- `(10,0,0,5,19,137)` decodes to **`10.0.0.5:5001`** because `19 * 256 + 137 = 5001`; the
  legacy decode reads port **137**
- `RETR` is the one command with **two** replies: `150` opens the data connection and
  declares **1234** bytes, `226` closes it
- The payload holds **1200** bytes, so the transfer is short by **34** and the client's own
  verdict is `complete = False` while `legacy_complete = True` on the same `226`
- The received share is **972 permille**, printed as `97.2%`, and half-up is explicit
  (`divide_half_up(1200 * 1000, 1234)`), never a float
- 18/18 audit checks pass, with negative controls that flatten replies back to the legacy
  one-line-at-a-time view and watch the banner check fail on purpose

## Requirements

Python 3.10+, standard library only (`re`, `pathlib`, `argparse`, `dataclasses`). Tests need
pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
