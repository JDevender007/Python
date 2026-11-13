<div align="center">

# 📨 Serverless Event Queue

### An SQS-style in-memory event queue for serverless workflows — FIFO delivery, visibility timeouts, dead-letter redrive, dedup windows, and an event processor. Fully offline on a fake clock.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Serverless Event Queue models the semantics that make distributed message queues safe, without any cloud account:

- **FIFO delivery** — messages are received in send order.
- **Visibility timeout** — a received message hides for N seconds; if the consumer never deletes it (crash!), it surfaces again for redelivery.
- **Receive counts & dead-letter queue** — after `max_receive_count` receives, a poison message is redriven to a DLQ instead of blocking the queue forever.
- **Per-message delay & retention expiry** — schedule deliveries; stale messages expire.
- **Deduplication window** — sending the same `dedup_id` within 5 minutes returns the original message.
- **Event processor** — receive → handle → ack, with failures left for retry.
- **Injectable clock** — the demo and tests run on a `FakeClock`, so timeouts, retries, and redrive happen *instantly and deterministically*.

The library is fully in-memory (no sockets). The CLI persists queue state to a local JSON file so `--send` / `--receive` / `--delete` compose across runs. **No network, no AWS, no paho-mqtt.**

---

# ✨ Features

- FIFO queue with visibility timeouts, in-flight accounting, and depth stats
- Dead-letter redrive with per-queue `max_receive_count` (fresh count in the DLQ)
- Per-message delay, queue-level default delay, retention expiry
- Deduplication window (5 min) returning the original message
- `change_visibility` for explicit retry-now / extend-hiding
- `QueueManager` with create/get/list/delete and JSON state save/load
- `EventProcessor`: ack on success, leave in-flight on handler failure
- Fake clock — deterministic demos and tests, zero sleeping
- 45 passing pytest tests

---

# 📂 Folder Structure

```text
Serverless_Event_Queue/
│
├── src/
│   ├── main.py         # CLI: demo, --create, --send, --receive, --delete, --purge
│   └── event_queue.py  # Message, EventQueue, QueueManager, EventProcessor, demo
│
├── tests/
│   └── test_event_queue.py
│
├── data/
│   └── queue_state.json   # written by the CLI (state persistence)
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 13_Cloud_Computing/Serverless_Event_Queue

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: 11 good orders + 2 poison messages, retries, DLQ redrive
python src/main.py --demo

# Create queues (state persists to data/queue_state.json)
python src/main.py --create orders
python src/main.py --create orders-dlq
python src/main.py --create orders --dlq orders-dlq --max-receive 3 --visibility 5

# Send / receive / ack
python src/main.py --send orders --body "order-001 created" --attr type=order.created
python src/main.py --receive orders --max 5
python src/main.py --delete orders --id <message-id>

# Inspect and clean up
python src/main.py --attributes orders
python src/main.py --list
python src/main.py --purge orders
```

JSON output is available on `--send`, `--receive`, `--list`, and `--attributes` via `--json`.

---

# 🧠 The Message Lifecycle

```text
send() ──► [visible] ──receive()──► [in-flight] ──delete()──► gone (acked)
                 ▲                        │
                 └── visibility timeout ──┘   (consumer crashed: retry)
                                                │
                                     receive_count > max
                                                ▼
                                          [dead-letter queue]
```

A consumer **must** `delete()` what it successfully handles; anything else is redelivered. That at-least-once contract is why handlers should be idempotent — the demo's dedup window shows one way to get there.

---

# 🛠 Technologies

- Python (standard library: uuid, json, time, dataclasses, logging)
- argparse / pytest

---

# 📚 Concepts Covered

- At-least-once delivery and the visibility-timeout contract
- Dead-letter queues: containing poison messages without stalling a stream
- Receive-count limits and fresh counts on redrive
- Deduplication windows for idempotent producers
- Retention expiry vs. in-flight hiding (two different "not visible" states)
- Injectable clocks for deterministic time-dependent tests
- Long-polling-style `wait` vs. instant `wait=0` fetches
- State serialization for CLI commands that compose across runs
- Event-driven serverless processing loops

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**45 tests passed** covering clock behavior, FIFO order, visibility timeouts, delay/retention, dead-letter redrive (with and without a DLQ), dedup windows, purge/attributes, manager operations, state round-trips, the event processor, demo idempotency, and every CLI path — all offline with fake time.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
