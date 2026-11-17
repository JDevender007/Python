# Port Scanner

A port scan has **three** answers, not two. A `SYN` is answered by a completed handshake
(*open*), by a reset (*closed* -- the packet arrived and nothing was listening), or by nothing
at all (*filtered* -- a firewall dropped it, the host is down, or the reply is late). The
legacy scanner asks one membership question:

```python
open_ports = {row.port for row in rows if row.outcome == "open"}
closed = sorted(set(ports) - open_ports)
```

Everything that did not accept a connection is called **closed**, which is a claim the network
never made. In the bundled scan of 13 ports the truth is **4 open, 6 closed, 3 filtered**; the
legacy report prints **4 open, 9 closed, 0 filtered**. A firewall that silently drops traffic
becomes indistinguishable from a host with nothing on that port -- the two conclusions a scan
exists to separate.

Two more defects live in the same impatience:

**A timeout is not a latency.** The legacy average adds each timed-out probe's full 800 ms wait
to the responses it did get, so probes that answered in **11 ms** on average are reported as
**307 ms**. A timeout is the absence of a reply, not a slow one.

**A retry resolves doubt; it does not create certainty.** The policy allows two attempts per
port. A timeout is retried and a refusal is not, and the strongest evidence wins: port 8443
timed out once and then answered, so it is open, not "still unknown". The legacy code retried
the same way and then discarded what the retry learned by collapsing every non-open port to
`closed`.

The rebuild keeps the three states distinct all the way to the report, averages latency only
over probes that answered, and validates the transcript against the policy -- a "timeout" that
returned in 4 ms, an answer at the timeout boundary, a gap in the attempt numbers, or a third
attempt under a two-attempt policy are all refused by name. The scan is a bundled transcript:
no socket is opened.

## What this project teaches

- A scan result is tri-state: open, closed, filtered -- and `not open` is not `closed`
- A refusal as *evidence* (the host answered) versus a timeout as *absence of evidence*
- Evidence precedence: `open` > `refused` > `timeout`, with the later attempt breaking ties
- Retries as a way to resolve uncertainty, and a policy that bounds them
- Why a timeout must not enter a latency average, and what the difference looks like
- Validating a transcript: a fast "timeout", an answer at the boundary, a gap in attempts
- Classifying by port with a deterministic order, and counting states that must sum to the ports
- Reporting the ports behind each count instead of only the totals
- Auditing classification against an independent tally, with a collapsing negative control
- Keeping the whole scan offline and byte-for-byte reproducible

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/scan.csv --json out.json
python src/main.py --file data/scan.csv --audit
python -m pytest tests -q
```

`--file` names the probe CSV; `policy.csv` is read from the same folder. Exit code `2` means
the input was refused -- a missing column, a port outside 1..65535, an unknown outcome, a
timeout whose latency is not the policy's wait, an answer at or past the timeout, or an attempt
number that is out of sequence or over the retry budget.

## Project structure

```
Port_Scanner/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   ├── policy.csv          # timeout_ms,retries -> 800,2
│   └── scan.csv            # 16 probes across 13 ports
├── src/
│   ├── scanner.py          # validation, classification, latency, checks, demo
│   └── main.py             # argparse only
└── tests/
    └── test_scanner.py     # 107 tests
```

## What the demo shows

| port | service | attempts | evidence | state |
| --: | --- | --: | --- | --- |
| 21 | ftp | 1 | refused | closed |
| 22 | ssh | 1 | open | **open** |
| 23 | telnet | 2 | timeout | **filtered** |
| 25 | smtp | 1 | refused | closed |
| 53 | dns | 1 | timeout | **filtered** |
| 80 | http | 1 | open | **open** |
| 110 | pop3 | 1 | refused | closed |
| 143 | imap | 1 | refused | closed |
| 443 | https | 1 | open | **open** |
| 3306 | mysql | 1 | refused | closed |
| 5432 | postgres | 2 | timeout | **filtered** |
| 8080 | http-alt | 1 | refused | closed |
| 8443 | https-alt | 2 | open | **open** |

- Here: **4 open, 6 closed, 3 filtered**. Legacy: **4 open, 9 closed, 0 filtered** -- the
  difference is exactly the three ports that never answered (`23, 53, 5432`)
- `8443` timed out on attempt 1 and answered on attempt 2, so the verdict is `open` with
  `attempts = 2`; three ports were retried in total
- The six timeouts account for **4800 ms** of waiting. Answered probes average **11 ms**;
  the legacy average is **307 ms** -- a difference of 296 ms that only exists because a
  non-answer was booked as a slow answer
- 18/18 audit checks pass, with a negative control whose classifier collapses `filtered` into
  `closed` and watches the independent tally disagree

## Requirements

Python 3.10+, standard library only (`csv`, `pathlib`, `argparse`, `dataclasses`). Tests need
pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
