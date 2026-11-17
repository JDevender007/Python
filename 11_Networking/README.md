<div align="center">

# 🌐 Networking Projects

### Five network programs that each looked like "read the socket and check the answer" — and each one was really a question about *where the truth lives*. In the frame, not the newline. In the reply body, not its last line. In the elapsed seconds, not the row count. In the absence of a reply, not in "not open". In the exit status, not in the output text. The rebuild keeps each mistake executable, then removes the reason it was possible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Every project here is a **simulator of a network conversation**, not a client of one. A TCP
stream, an FTP control connection, a link-state log, a scan transcript and an SSH session log
all ship as bundled text in `data/`; the code parses them with the same strictness it would
apply to a live socket, and nothing opens a connection.

That choice is deliberate. A demo that dials out is not reproducible, and a demo that cannot be
reproduced cannot show you the number that was wrong last time. Here the entire conversation is
on disk, so two runs print the same bytes and the defect is a printable difference rather than
an occasional mystery.

**The lesson of each project is different, on purpose.** Four variations on "set a timeout"
would teach nothing; four different places a network program confuses a message with a
transcript, a claim with a measurement, or an absence with a negative is the subject.

- **Chat_Application** — *a stream is not a sequence of messages.* `recv(4096)` returns whatever
  arrived, and `split("\n")` treats each read as a message. A 41-byte conversation read in
  7-byte pieces becomes **9 reads**, **7 of them ending mid-frame**, and the legacy line reader
  delivers **10 fragments**, none of which is a message. A message containing a newline becomes
  **2** legacy messages; `caf\u00e9` is **4 characters and 5 bytes**, so a header written from
  `len(text)` promises 4 and eats the next frame's first byte. The rebuild frames each message
  as `<byte count>:<utf-8 payload>` and keeps a per-connection decoder that holds a partial frame
  until it is whole.
- **FTP_Client** — *a reply is a sequence of lines, and a transfer is a claim.* Filtering a
  control stream for lines whose fourth character is a space keeps the terminating line and
  throws away the body, so the three-line banner arrives as `220 Ready` and `211-Features:` with
  its four capability lines arrives as `211 End` — **6 lines and 4 capabilities reduced to 1 and
  0**. A passive port is **two bytes**, `p1 * 256 + p2`, so `(10,0,0,5,19,137)` is port `5001`,
  not `137`. And `226 Transfer complete` cannot settle whether the file arrived: the declared
  `1234` bytes against the `1200` received is a **shortfall of 34**, reported as **972 permille**
  while the same `226` says it succeeded.
- **Network_Monitor** — *a transition is not a duration.* Six state changes over a 10000-second
  window hold the service up for **600 s** and down for **9400 s** — **6.00%** availability — but
  three of six rows say `up`, so the legacy report prints **50.00%**, overstating it by **44
  points**. And the natural pairwise loop over transitions never records the state still in force
  at the window's end: it covers **9700 s** and reports **6.19%**, silently deleting the trailing
  300-second outage. The rebuild tiles the window with half-open intervals and computes MTTR
  (**3133 s**) and MTBF (**200 s**) from them.
- **Port_Scanner** — *a scan has three answers.* `set(ports) - open_ports` calls everything that
  did not accept a connection "closed", so probes that never answered are indistinguishable from
  refusals: **4 open, 6 closed, 3 filtered** becomes **4 open, 9 closed, 0 filtered**. A timeout
  is the absence of a reply, not a slow one, so the legacy average books **4800 ms** of waiting
  and reports **307 ms** where answered probes take **11 ms**. A retry resolves doubt rather than
  creating certainty: port `8443` timed out and then answered, so it is open.
- **SSH_Automation_Tool** — *the exit status is the result, and an argument is not a string.*
  `"active" in output` reads `inactive` as running, so a stopped unit that exited **3** is
  reported healthy. `exit_code != 0` fails a `grep -q` whose exit `1` is its negative answer,
  refusing `[1, 2, 4]` where the declared codes refuse only `[1, 4]`. And
  `f"test -d {path}"` with `path = "/srv/app data"` becomes **4 words instead of 3**, so the test
  asks about `/srv/app` and then about `data`.

**Every number is exact and every claim is checkable.** Durations are integer seconds,
percentages are basis points or permille with an explicit `divide_half_up` (never `round()` and
never a float on the money-or-metric path), byte counts are compared as bytes, and each
project's `audit()` re-derives its own result from the loaded records instead of restating the
summary it just printed. The readers are injectable — `read_replies=`, `read_intervals=`,
`read_verdicts=`, `read_outcomes=`, `make_decoder=` — so a negative control can make exactly one
check fail and prove the check is live.

The libraries used are `pathlib`, `csv`, `re`, `argparse` and `dataclasses` — the standard
library, nothing else. No sockets, no `ftplib`, no `paramiko`, no clock, no `random`.

---

# 🎓 Learning Objectives

- Frame a message stream yourself, and see why a newline cannot be a frame boundary
- Count a length prefix in bytes while the text is counted in characters
- Hold a partial frame in a decoder instead of decoding every read as a whole message
- Parse a reply grammar by continuation character, and keep the body it carries
- Decode a passive port as two bytes, and see which service the low byte names instead
- Treat a `226` as a claim and the declared byte count as the measurement that settles it
- Convert a transition log into intervals that tile a window exactly
- Treat a window's end as an event, so no tail is silently dropped
- Compute MTTR and MTBF from intervals rather than from row counts
- Keep a scan tri-state, and separate evidence (`refused`) from the absence of it (`timeout`)
- Order evidence, so a retry can only upgrade a verdict with better proof
- Exclude a timeout from a latency average, and measure the difference it made
- Judge a remote task by a declared success set, not by `exit_code == 0`
- Build a command as an argument vector, and quote every argument on the way out
- Split a command line with quote awareness, refusing an unterminated quote
- Reconcile two independent computations and write an `audit()` with a negative control

---

# 🗂️ Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Chat_Application | Length-prefixed framing, a stateful decoder, byte-versus-character counts and a read-boundary report. | 117 | ✅
02 | FTP_Client | Reply grammar with continuations, two-byte passive ports, declared-versus-received byte accounting. | 124 | ✅
03 | Network_Monitor | Half-open intervals over a state-change log, time-weighted availability, MTTR and MTBF. | 105 | ✅
04 | Port_Scanner | Tri-state scan verdicts, evidence precedence across retries, and latency that excludes the waiting. | 107 | ✅
05 | SSH_Automation_Tool | Declared exit-code sets, quote-aware argv splitting and command round-tripping. | 130 | ✅

**Total: 583 tests.**

---

# 🧠 Concepts Covered

- A byte stream versus a message sequence, and where a frame boundary has to live
- Length-prefixed framing, partial reads, and a decoder that survives a split frame
- UTF-8 byte counts versus character counts, and why `errors="replace"` corrupts silently
- FTP reply continuations: `NNN-` continues, `NNN ` terminates, the code must not change
- Multiline replies, capability lists read from the body, and one command with two replies
- Passive-mode address bytes, `p1 * 256 + p2`, and the low byte naming a different port
- A declared transfer size, a received size, a shortfall, and a share in permille
- State-change logs as events, and availability as the integral of a state over time
- Alternation as an invariant, and a first transition that must sit at the window start
- Half-open intervals, exactly-once tiling, and a window end that is itself an event
- MTTR as downtime over outages, MTBF as uptime over recoveries, and the longest outage beside them
- Tri-state port classification: open, closed (reset seen), filtered (nothing came back)
- Evidence strength ordered `open > refused > timeout`, with attempts breaking ties
- Retry policy bounds, attempt numbering, and a timeout that must last the policy's wait
- Latency over answered probes only, versus an average that bills the waiting
- Exit status as the result of a remote command, and declared acceptable codes (`0`, `0;1`)
- A substring test that reads `inactive` as `active`, and how to test a status instead
- POSIX quoting: single quotes, `'\''`, backslash escapes, and refusing an unterminated quote
- Argument vectors versus concatenated command strings, and metacharacters kept inside one word
- Audits that re-derive from source records, with a negative control per injectable reader

---

# 📁 Repository Structure

```text
11_Networking/
│
├── Chat_Application/
│   ├── src/    chat.py, main.py
│   ├── tests/  test_chat.py
│   └── data/   chat_log.txt
│
├── FTP_Client/
│   ├── src/    ftp.py, main.py
│   ├── tests/  test_ftp.py
│   └── data/   session.log, payload.txt
│
├── Network_Monitor/
│   ├── src/    monitor.py, main.py
│   ├── tests/  test_monitor.py
│   └── data/   window.csv, state_changes.csv
│
├── Port_Scanner/
│   ├── src/    scanner.py, main.py
│   ├── tests/  test_scanner.py
│   └── data/   policy.csv, scan.csv
│
└── SSH_Automation_Tool/
    ├── src/    ssh_tool.py, main.py
    ├── tests/  test_ssh_tool.py
    └── data/   tasks.csv, session.log
```

Each project has the same shape: all logic in one library module, a thin `main.py` argparse
CLI, a `tests/` suite, deterministic text seeds in `data/`, a pinned `requirements.txt`, a
`.gitignore`, and a `README.md` that states its own defect and pins its own numbers.

The conversation itself is data. `chat_log.txt` holds 4 messages, `session.log` holds 8 FTP
commands and 10 replies, `state_changes.csv` holds 6 transitions over a 10000-second window,
`scan.csv` holds 16 probes across 13 ports, and `tasks.csv` plus `session.log` hold 5 commands
with their real exit statuses. Each library module still carries the defective expression as an
executable string — `LEGACY_READER`, `LEGACY_REPLY_FILTER`, `LEGACY_UPTIME`, `LEGACY_CLASSIFY`,
`LEGACY_SERVICE_CHECK` — so the tests can run the wrong code beside the right one on the same
bytes.

No module imports `socket`, `ftplib`, `paramiko` or `psutil`. The transport is an in-memory
channel or a parsed transcript, which is why the demos are byte-for-byte reproducible.

---

# ▶️ Run any project

```bash
cd 11_Networking/04_Port_Scanner

python src/main.py --demo          # offline, deterministic, exit 0
python src/main.py --file data/scan.csv --json out.json
python src/main.py --audit         # every check with PASS/FAIL
python -m pytest tests -q          # the suite
```

Every project supports `--demo`, `--quiet` with `--demo` (prints nothing on stdout or stderr),
`--audit`, `--json <path>` and `--file <input>` naming the primary seed file; its sibling seeds
are read from the same folder. Exit code `2` means the input was refused, with `error: ...` on
stderr — a malformed record, a reply continuation that never ends, a repeated state, an answer
at the timeout boundary, a declared code outside `0..255`. Nothing opens a connection and no
demo writes into the repository: JSON output goes only where you point it.

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
2. `pytest` passes with no skips, 105+ tests
3. `--demo` exits 0, prints `Cross-checks OK: ...` then `Demo completed successfully.` as its last two lines
4. `--demo` twice produces byte-identical output, and `--demo --quiet` prints nothing at all
5. no non-ASCII byte in `src/`, `tests/` or the text data files

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why "the message arrived" is a claim no stream can make without a frame boundary
- Why a length prefix written from `len(str)` corrupts the *next* message, not this one
- Why a reply's last line is not its content, and what the continuation character is for
- Why a port is two bytes, and how the low byte can point at a different service
- Why a success reply can arrive after a truncated transfer
- Why a percentage of transitions is not a percentage of time
- Why the last state has no successor, and what that does to a pairwise loop
- Why "not open" is two different findings, only one of which is evidence
- Why a timeout cannot be averaged in as a slow reply
- Why `inactive` contains `active`, and why no substring test can fix that
- Why exit `1` from `grep` is a result and exit `1` from `curl` is a failure
- Why a command is a vector, and quoting is not escaping
- How to write an audit whose every check has a negative control
- How to make a network demonstration reproducible byte for byte

---

# 🧩 Patterns Included

Parsing — `parse_log`, `parse_session`, `parse_replies`, `parse_reply`, `load_changes`, `load_probes`, `load_tasks`, `load_results`
Records — `Message`, `Reply`, `Exchange`, `Transfer`, `Transition`, `Interval`, `Probe`, `Verdict`, `Task`, `Result`, `Outcome`
Validation — `ChatError`, `FtpError`, `MonitorError`, `ScanError`, `SshError`
Framing — `encode_frame`, `FrameDecoder`, `split_reads`, `wire_of`, `payload_bytes`
Protocols — `code_of`, `is_continuation`, `capabilities`, `pasv_address`, `declared_size`, `check_transfer`
Time — `build_intervals`, `legacy_intervals`, `totals`, `uptime_bp`, `mttr_s`, `mtbf_s`
Scanning — `classify`, `strongest`, `state_counts`, `ports_by_state`, `retried_ports`, `answered_latency_ms`
Shell — `quote_arg`, `build_command`, `split_argv`, `parse_ok_codes`, `verdict`, `pair_up`
Legacy — `LEGACY_READER`, `LEGACY_REPLY_FILTER`, `LEGACY_PORT_DECODE`, `LEGACY_UPTIME`, `LEGACY_INTERVALS`, `LEGACY_CLASSIFY`, `LEGACY_LATENCY`, `LEGACY_SERVICE_CHECK`, `LEGACY_FAILURE_CHECK`
Arithmetic — `divide_half_up`, `format_bp`, `format_permille`
Reporting — `measure`, `report`, `render_replies`, `render_intervals`, `render_verdicts`, `render_outcomes`, `--json`
Auditing — `audit`, `_guard`, injectable readers and decoder factories for negative controls
Testing — exact pinned numbers, validation refusals, one failing check per negative control

---

# 🚀 Future Improvements

- A shared `--batch` runner that executes all five demos and compares their output hashes
- A live adapter behind the same parser interfaces, so the offline transcript and a real socket feed identical records
- A fuzz harness that splices frames at every byte offset and asserts the decoder never invents a message
- A pcap reader for `Port_Scanner` so the same classifier can score a captured scan
- Half-open interval algebra shared by `Network_Monitor` and any future latency/uptime project
- A terminal-diff view for `FTP_Client` that highlights the lines the legacy filter discarded
- Property-based tests that generate random seeds and assert the invariants still hold

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
