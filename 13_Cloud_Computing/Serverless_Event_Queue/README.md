# Serverless Event Queue

An at-least-once queue delivers the same event twice, and queue depth is not backlog age. The legacy
consumer is four lines that each look like the documentation:

```python
message = queue.receive()
ok = handle(message)
if ok:
    queue.delete(message)
if visible_depth > 2:
    page_oncall()
```

**1. At-least-once means duplicates are normal, not exceptional.** A message becomes visible again
when its visibility timeout expires, whether or not the first handler is still working. The slow
handler in the bundled scenario needs 45 seconds under a 20-second visibility timeout, so the queue
hands the same event to a second worker at 26 seconds and both handlers succeed. `processed += 1`
therefore reports more work than the queue contains: **10 successful handler runs for 9 distinct
events**.

**2. Quantity is not age.** `ApproximateNumberOfMessagesVisible` counts what a consumer could pick
up *now*: it excludes everything in flight and says nothing about how long the oldest event has been
waiting. The rebuild reports visible depth, in-flight count, backlog and oldest age side by side.
At **63 seconds** the visible depth is **0** while the oldest unfinished event is already 63 seconds
old; at the worst moment one message has waited **83 seconds**, and the depth-over-two alarm is
silent because nothing is visible.

**3. A max-receive count is an attempt budget, and its destination is a queue.** The legacy handler
deletes the message as soon as the handler fails, so a transient error loses the event. The rebuild
retries within the budget and redrives the exhausted message to the dead-letter queue with its
attempt count and the reason attached: `evt-04` recovers on attempt 2, `evt-05` exhausts three
attempts and lands in the DLQ at 98 seconds.

**4. A receipt handle is not an idempotency key.** Every delivery of the same message carries a
fresh receipt handle, so `if handle in seen` stops **0 of 4** duplicates -- it was never able to
match one. The event's own identifier is the key, and the rebuild records which identifiers were
already applied.

The simulation is a deterministic discrete-event loop in whole seconds: no sleep, no network, no
wall clock. `data/scenario.json` names the queue policy and ten events with their processing time
and failing attempts.

## What this project teaches

- Why at-least-once delivery makes duplicate handling the consumer's job
- Why a visibility timeout shorter than the handler's runtime duplicates work
- Why a duplicate delivery can produce a second real side effect (and why "delete" cannot undo it)
- Why a receipt handle identifies a delivery while an event id identifies the event
- Why queue depth describes visibility, not backlog
- Why backlog age is the metric that catches a starved or slow consumer
- Why in-flight messages are invisible to a depth alarm
- Why `maxReceiveCount` is an attempt budget, not a retry count
- Why a dead-letter queue with a reason beats deleting a failed message
- Why retention can expire a message that never got a worker
- How to drive a queue deterministically without a clock or a broker
- How to audit a run by replaying the scenario and comparing every delivery

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/scenario.json --json out.json
python src/main.py --file data/scenario.json --audit
python -m pytest tests -q
```

`--file` names a scenario: a queue policy (`name`, `visibility`, `max_receive`, `retention`,
`workers`) and a list of `{id, kind, produced_at, process, failures}` events. `--audit` exits `1`
if any check fails. Exit code `2` means the input was refused -- a missing file, non-ASCII bytes,
invalid JSON, a root that is not a mapping, a bad queue name, a visibility or retention outside
1..86400, more than ten attempts or eight workers, an empty event list, a duplicate or malformed
event id, a non-dotted kind, a process time of zero, or a failing attempt outside the
`max_receive` budget.

## Project structure

```
Serverless_Event_Queue/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   └── scenario.json       # 10 events, visibility 20s, max_receive 3, 2 workers
├── src/
│   ├── event_queue.py      # discrete-event queue, metrics, audit, demo
│   └── main.py             # argparse only
└── tests/
    └── test_event_queue.py # 146 tests
```

## What the demo shows

| figure | value |
| --- | --- |
| events / deliveries | 10 / **14** |
| distinct events delivered | 10 |
| duplicate deliveries | **4** |
| successful handler runs | **10** for **9** distinct events |
| repeated side effects | **1** (`evt-03`, the 45-second handler) |
| transient failure recovered | `evt-04`: failure on attempt 1, success on attempt 2 |
| dead-lettered | `evt-05` after **3** attempts at **98s** |
| peak visible depth / peak backlog | **5** / **7** |
| worst backlog age | **83s** at visible depth **0** |
| depth-over-2 alarm | fires at **2 of 19** moments, silent at the worst one |
| legacy delete-on-failure | loses **2** events (`evt-04`, `evt-05`) |
| receipt-handle dedup | stops **0 of 4** duplicates |

Selected timeline rows (visible / in-flight / backlog / oldest age):

```
    At  Visible  In-flight  Backlog  Oldest
    0        5          2        7       0
   22        0          2        4      22
   50        1          1        2      50
   63        0          0        1      63
   83        0          0        1      83
   98        0          0        0       0
```

- `evt-03` is delivered at 5s by worker 0 and again at 26s by worker 1, and both runs succeed: one
  event, two side effects
- At 63s nothing is visible, yet one event has been waiting 63 seconds -- the moment a depth alarm
  is blind and an age alarm is not
- `evt-05` is retried three times, then redriven with `reason=max_receive`
- **15/15 audit checks pass**, including one that replays the scenario and compares every delivery

## Requirements

Python 3.10+, standard library only (`json`, `re`, `dataclasses`, `argparse`). Tests need
pytest==9.1.1. No broker, no credentials, no network, no clock; the scenario is bundled.

---
**Devender J** -- https://github.com/JDevender007
