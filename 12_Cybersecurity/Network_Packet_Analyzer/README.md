# Network Packet Analyzer

An IPv4 header is a bit field, and every field has a unit. The legacy analyser is the one every
"parse a pcap in 30 lines" post contains:

```python
offset = 20                        # the IP header is 20 bytes
src_port = int.from_bytes(raw[offset:offset + 2], "big")
field = int.from_bytes(raw[6:8], "big")
flags = field & 0x7
fragment_offset = field
valid = (sum(raw[:offset]) & 0xFFFF) == 0
payload = len(raw) - offset - 8
```

Each line is a unit error, and each one produces a plausible number.

**1. The header length is counted in 32-bit words.** The low nibble of the first byte is the IHL,
so a header with four bytes of TCP options is 24 bytes, not 20. Packet 2 in the bundled capture is
exactly that: reading ports at byte 20 lands inside the option bytes and reports **257 -> 256**
instead of **8443 -> 51001**.

**2. Flags and the fragment offset share one 16-bit field.** The three flags are the *top* bits and
the offset is the low thirteen, counted in 8-byte units. `field & 0x7` reads the bottom of the
offset and calls it flags, and taking the whole field as the offset turns a plain DF packet into a
fragment at byte 131072. Packet 4 (first fragment) then reads as "no flags, offset 8192 units" and
packet 5 (last fragment) as "more fragments follow".

**3. A checksum is verified over the header with its own field zeroed.** The one's-complement sum
of a *correct* header is `0xFFFF`, not zero; a sum that includes the checksum field can only be
zero when the header is wrong. The legacy test therefore rejects **all six** packets while the
rebuild accepts **five** and rejects exactly the one whose TTL was changed after the checksum was
computed.

**4. The total length is the authority, and a short capture is disclosed.** Packet 3 declares 40
bytes and the capture holds 36. Subtracting the captured size reports 8 payload bytes and never
mentions the other 4; the rebuild reports `declared 12, captured 8, truncated by 4`.

## What this project teaches

- Reading a length field in its own unit: IHL counts 32-bit words, not bytes
- Validating a declared header length against the bytes actually held
- Splitting one 16-bit field into a 3-bit flag set and a 13-bit offset
- Why the fragment offset is scaled by 8, and what that does to a "byte" report
- Fragment awareness: the first fragment carries a transport header, a continuation does not
- The one's-complement checksum: field zeroed, folded carries, complement
- Why a correct header sums to `0xFFFF` and what a legacy `== 0` test really claims
- Total length as the authority, with truncation disclosed instead of silently subtracted
- Ports read after a variable-length header, not at a constant offset
- Auditing decoded fields against an independently injected reader

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/capture.txt --json out.json
python src/main.py --file data/capture.txt --audit
python -m pytest tests -q
```

`--file` names a text capture: one `index | hex bytes` record per line, comments and blank lines
ignored, indices running `1..n` in order. Exit code `2` means the capture was refused -- a missing
file, non-ASCII bytes, a stray token, an out-of-order index, a short packet, or a header whose
declared lengths disagree with the bytes present.

## Project structure

```
Network_Packet_Analyzer/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   └── capture.txt         # 6 IPv4 packets: options, truncation, 2 fragments, bad TTL
├── src/
│   ├── packet_analyzer.py  # decode, checksums, legacy view, checks, demo
│   └── main.py             # argparse only
└── tests/
    └── test_packet_analyzer.py   # 114 tests
```

## What the demo shows

```
  #  proto  ihl  len  cap  flags     offset  ports          payload  checksum
  1  tcp    20   60   60   df        0       443->51000     20       ok
  2  tcp    24   52   52   df        0       8443->51001    8        ok
  3  udp    20   40   36   -         0       53->40000      12/8     ok
  4  udp    20   36   36   mf        0       123->40001     8        ok
  5  udp    20   44   44   -         185     fragment       24       ok
  6  tcp    20   44   44   df        0       22->51002      4        BAD
```

- **6 packets, 272 bytes held, 276 declared** -- the 4-byte gap is packet 3's truncation
- Packet 2's **24-byte** header moves its ports from the legacy's **257 -> 256** to the true
  **8443 -> 51001**
- The legacy offset calls a plain DF packet a fragment at **16384 units (131072 bytes)**; the true
  offset is `0`
- The rebuild accepts **5** of 6 checksums, the legacy test **0**: a correct header sums to
  `0xFFFF`, never `0`
- Packet 3 declares **12** payload bytes and holds **8**, truncated by **4**
- Payload accounting: **76 declared**, **72 captured**, **104** by subtraction
- 27/27 audit checks pass, with negative controls that hand the audit a reader which reports the
  legacy ports and watch it disagree with the pinned numbers

## Requirements

Python 3.10+, standard library only (`argparse`, `json`, `dataclasses`). Tests need
pytest==9.1.1. No sockets, no scapy, no binary capture files.

---
**Devender J** -- https://github.com/JDevender007
