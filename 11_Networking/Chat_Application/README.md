# Chat Application

TCP hands you **bytes**, not messages, and the reader every socket tutorial shows treats a
`recv` as a message:

```python
chunk = sock.recv(4096).decode("utf-8", errors="replace")
for line in chunk.split("\n"):
    deliver(line)
```

Four defects fall out of those two lines, and all four are visible in one four-message
conversation. A newline inside a message splits it in two. A read that lands mid-frame is
delivered as if it were whole. A header written from `len(text)` promises characters while the
wire carries bytes. And `errors="replace"` turns the first half of a multi-byte character into
`U+FFFD` instead of waiting for the rest.

The rebuild frames every message as `<byte count>:<utf-8 payload>`, keeps one decoder per
connection that holds a partial frame until it is complete, and refuses anything that is not
exactly one frame. The legacy path is kept beside it, executable, so every claim is
reproduced with a number.

## What this project teaches

- A stream is not a sequence of messages; a frame boundary has to be carried in the data
- Why `split("\n")` cannot survive a message that contains a newline
- A length prefix that counts **bytes** while the code counts **characters**
- Keeping partial bytes in the decoder instead of decoding each read separately
- Why `errors="replace"` corrupts silently where `errors="strict"` would raise
- Refusing an unfinished frame at end of stream instead of delivering it
- Refusing a header that is not a decimal byte count, and an empty message
- An in-memory channel as the whole transport, so the demo needs no socket
- Counting how many reads land mid-frame, and dividing the share half up
- Auditing delivered messages against an independent re-read, with negative controls

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/chat_log.txt --json out.json
python src/main.py --file data/chat_log.txt --audit
python -m pytest tests -q
```

`--file` names the bundled chat log: comment lines start with `;`, and each message is
`sender | text` where `\n`, `\r`, `\t`, `\\` and `\uXXXX` are escapes. Exit code `2` means the
log was refused -- a malformed record, an unknown escape, an empty message, or a frame that
never completes.

## Project structure

```
Chat_Application/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   └── chat_log.txt        # 4 messages, 59 framed bytes
├── src/
│   ├── chat.py             # framing, decoder, channel, checks, demo
│   └── main.py             # argparse only
└── tests/
    └── test_chat.py        # 117 tests
```

## What the demo shows

| message | characters | bytes | legacy reader |
| --- | --: | --: | --- |
| `hello there` | 11 | 11 | split across reads |
| `line one\nline two` | 17 | 17 | **2 messages** |
| `caf\u00e9` | **4** | **5** | `caf\ufffd` if cut mid-character |
| `5 > 3 and 2 < 4` | 15 | 15 | split across reads |

- 4 messages are **59** framed bytes, read as **9** chunks of 7 bytes, of which **7** end
  mid-frame (**78%**) and 2 land exactly on a boundary
- The decoder delivers exactly **4** messages; the legacy line reader delivers **10**
  fragments, none of which is a message
- The one message with an embedded newline becomes **1** message here and **2** legacy
  messages
- `caf\u00e9` is **4** characters but **5** bytes, so its frame header says `5`, not `4`, and
  the frame occupies **7** bytes on the wire
- Half a frame leaves **6** bytes held and **1** byte still needed; the legacy reader instead
  produces `5:caf\ufffd` with one replacement character
- 12/12 audit checks pass, with negative controls that hand the audit a decoder which
  delivers a partial frame and watch exactly one check fail

## Requirements

Python 3.10+, standard library only (`pathlib`, `argparse`, `dataclasses`). Tests need
pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
