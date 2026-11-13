"""In-memory SQS-style event queue for serverless workflows.

Core ideas modelled offline:

- FIFO delivery with visibility timeouts (in-flight messages hide, then return)
- Receive counts and a dead-letter queue (redrive after max receives)
- Per-message delay, retention expiry, and deduplication windows
- A small event processor that dispatches messages to handlers
- Injectable clock - the demo and tests run on a fake clock, so retries and
  timeouts happen instantly and deterministically

The library is fully in-memory. The CLI persists queue state to a local JSON
file so its commands compose across runs. No network, no AWS.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

LOG = logging.getLogger("event.queue")

DEFAULT_VISIBILITY = 30.0
DEFAULT_RETENTION = 3600.0
DEFAULT_MAX_RECEIVE = 3
DEDUP_WINDOW = 300.0


class QueueError(RuntimeError):
    """Raised for unknown queues, bad parameters, and bad message ids."""


# --------------------------------------------------------------------------- #
# Clock
# --------------------------------------------------------------------------- #
class FakeClock:
    """Manually advanced clock for deterministic demos and tests."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise QueueError("cannot move the clock backwards")
        self._now += seconds
        return self._now


# --------------------------------------------------------------------------- #
# Messages and queue
# --------------------------------------------------------------------------- #
@dataclass
class Message:
    """One queued event."""

    id: str
    body: str
    attributes: dict[str, str] = field(default_factory=dict)
    created_at: float = 0.0
    visible_at: float = 0.0
    receive_count: int = 0
    dedup_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(**data)


class EventQueue:
    """An in-memory FIFO queue with SQS-like semantics."""

    def __init__(
        self,
        name: str,
        *,
        visibility_timeout: float = DEFAULT_VISIBILITY,
        retention: float = DEFAULT_RETENTION,
        max_receive_count: int = DEFAULT_MAX_RECEIVE,
        delay: float = 0.0,
        clock: Callable[[], float] = time.time,
        dead_letter: "EventQueue | None" = None,
    ) -> None:
        if not name or not name.replace("_", "").replace("-", "").isalnum():
            raise QueueError(f"invalid queue name: {name!r}")
        if visibility_timeout <= 0:
            raise QueueError("visibility_timeout must be > 0")
        if retention <= 0:
            raise QueueError("retention must be > 0")
        if max_receive_count < 1:
            raise QueueError("max_receive_count must be >= 1")
        if delay < 0:
            raise QueueError("delay must be >= 0")

        self.name = name
        self.visibility_timeout = visibility_timeout
        self.retention = retention
        self.max_receive_count = max_receive_count
        self.delay = delay
        self.clock = clock
        self.dead_letter = dead_letter

        self.messages: list[Message] = []
        self._dedup: dict[str, float] = {}
        self.sent_total = 0
        self.received_total = 0
        self.deleted_total = 0
        self.dead_lettered_total = 0

    # --- sending -------------------------------------------------------- #
    def send(
        self,
        body: str,
        attributes: dict[str, str] | None = None,
        *,
        delay: float | None = None,
        dedup_id: str | None = None,
    ) -> Message:
        """Enqueue one message (FIFO) and return it."""
        if not isinstance(body, str):
            raise QueueError("body must be a string")
        now = self.clock()
        send_delay = self.delay if delay is None else delay
        if send_delay < 0:
            raise QueueError("delay must be >= 0")

        if dedup_id:
            self._prune_dedup(now)
            seen_at = self._dedup.get(dedup_id)
            if seen_at is not None and now - seen_at < DEDUP_WINDOW:
                existing = next(
                    (m for m in self.messages if m.dedup_id == dedup_id), None
                )
                if existing is not None:
                    LOG.info("dedup hit: %s", dedup_id)
                    return existing

        message = Message(
            id=uuid.uuid4().hex[:12],
            body=body,
            attributes=dict(attributes or {}),
            created_at=now,
            visible_at=now + send_delay,
            dedup_id=dedup_id or "",
        )
        self.messages.append(message)
        self.sent_total += 1
        if dedup_id:
            self._dedup[dedup_id] = now
        LOG.info("sent %s to %s", message.id, self.name)
        return message

    def send_batch(
        self, bodies: list[str], attributes: dict[str, str] | None = None
    ) -> list[Message]:
        """Enqueue several messages in order."""
        return [self.send(body, attributes) for body in bodies]

    def _prune_dedup(self, now: float) -> None:
        expired = [k for k, ts in self._dedup.items() if now - ts >= DEDUP_WINDOW]
        for key in expired:
            del self._dedup[key]

    # --- receiving ------------------------------------------------------ #
    def _expire(self, now: float) -> None:
        """Drop messages older than the retention window."""
        before = len(self.messages)
        self.messages = [
            m for m in self.messages
            if now - m.created_at < self.retention
        ]
        if len(self.messages) != before:
            LOG.info("expired %d message(s) from %s", before - len(self.messages),
                     self.name)

    def _fetch(self, max_messages: int) -> list[Message]:
        now = self.clock()
        self._expire(now)
        picked: list[Message] = []
        exhausted: list[Message] = []
        for message in self.messages:
            if len(picked) >= max_messages:
                break
            if message.visible_at > now:
                continue  # in-flight or delayed
            if message.receive_count + 1 > self.max_receive_count:
                exhausted.append(message)
                continue
            message.receive_count += 1
            message.visible_at = now + self.visibility_timeout
            picked.append(message)
        # redrive after iteration: _redrive removes from self.messages
        for message in exhausted:
            self._redrive(message, now)
        self.received_total += len(picked)
        return picked

    def _redrive(self, message: Message, now: float) -> None:
        """Move an exhausted message to the dead-letter queue."""
        self.messages.remove(message)
        # fresh start in the DLQ: its own max_receive_count applies from 1
        message.receive_count = 0
        message.visible_at = now  # immediately available in the DLQ
        if self.dead_letter is not None:
            self.dead_letter.messages.append(message)
            LOG.info("redrove %s -> %s", message.id, self.dead_letter.name)
        else:
            LOG.info("dropped %s (no dead-letter queue)", message.id)
        self.dead_lettered_total += 1

    def receive(self, max_messages: int = 1, wait: float = 0.0) -> list[Message]:
        """Receive up to `max_messages` visible messages (FIFO order).

        `wait` polls with real sleeps for up to `wait` seconds (long-poll
        style); tests and the demo pass 0 for instant, deterministic results.
        """
        if max_messages < 1:
            raise QueueError("max_messages must be >= 1")
        if wait < 0:
            raise QueueError("wait must be >= 0")
        if wait == 0:
            return self._fetch(max_messages)

        deadline = time.time() + wait
        while True:
            picked = self._fetch(max_messages)
            if picked or time.time() >= deadline:
                return picked
            time.sleep(0.01)

    def delete(self, message_id: str) -> None:
        """Acknowledge/remove a message."""
        for i, message in enumerate(self.messages):
            if message.id == message_id:
                self.messages.pop(i)
                self.deleted_total += 1
                LOG.info("deleted %s from %s", message_id, self.name)
                return
        raise QueueError(f"message not found: {message_id}")

    def change_visibility(self, message_id: str, timeout: float) -> None:
        """Hide a message for `timeout` seconds (0 makes it visible now)."""
        if timeout < 0:
            raise QueueError("timeout must be >= 0")
        for message in self.messages:
            if message.id == message_id:
                message.visible_at = self.clock() + timeout
                return
        raise QueueError(f"message not found: {message_id}")

    def purge(self) -> int:
        """Delete every message; returns how many were removed."""
        count = len(self.messages)
        self.messages.clear()
        self._dedup.clear()
        return count

    # --- state ---------------------------------------------------------- #
    @property
    def depth(self) -> int:
        """Messages currently visible (ready to receive)."""
        now = self.clock()
        return sum(1 for m in self.messages if m.visible_at <= now)

    @property
    def in_flight(self) -> int:
        now = self.clock()
        return sum(1 for m in self.messages if m.visible_at > now)

    def attributes(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "depth": self.depth,
            "in_flight": self.in_flight,
            "dead_lettered": self.dead_lettered_total,
            "sent": self.sent_total,
            "received": self.received_total,
            "deleted": self.deleted_total,
            "visibility_timeout": self.visibility_timeout,
            "max_receive_count": self.max_receive_count,
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "visibility_timeout": self.visibility_timeout,
            "retention": self.retention,
            "max_receive_count": self.max_receive_count,
            "delay": self.delay,
            "dead_letter": self.dead_letter.name if self.dead_letter else None,
            "messages": [m.to_dict() for m in self.messages],
            "dedup": dict(self._dedup),
            "counters": {
                "sent": self.sent_total,
                "received": self.received_total,
                "deleted": self.deleted_total,
                "dead_lettered": self.dead_lettered_total,
            },
        }

    @classmethod
    def from_state(
        cls, data: dict[str, Any], clock: Callable[[], float] = time.time
    ) -> "EventQueue":
        queue = cls(
            data["name"],
            visibility_timeout=data["visibility_timeout"],
            retention=data["retention"],
            max_receive_count=data["max_receive_count"],
            delay=data["delay"],
            clock=clock,
        )
        queue.messages = [Message.from_dict(m) for m in data["messages"]]
        queue._dedup = dict(data.get("dedup", {}))
        counters = data.get("counters", {})
        queue.sent_total = counters.get("sent", 0)
        queue.received_total = counters.get("received", 0)
        queue.deleted_total = counters.get("deleted", 0)
        queue.dead_lettered_total = counters.get("dead_lettered", 0)
        return queue


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #
class QueueManager:
    """Creates and looks up queues; optional JSON persistence for the CLI."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self.queues: dict[str, EventQueue] = {}

    def create_queue(self, name: str, **kwargs: Any) -> EventQueue:
        """Create (or return the existing) queue with the given settings."""
        if name in self.queues:
            return self.queues[name]
        queue = EventQueue(name, clock=self.clock, **kwargs)
        self.queues[name] = queue
        return queue

    def get_queue(self, name: str) -> EventQueue:
        queue = self.queues.get(name)
        if queue is None:
            available = ", ".join(sorted(self.queues)) or "(none)"
            raise QueueError(f"unknown queue {name!r} (available: {available})")
        return queue

    def delete_queue(self, name: str) -> None:
        if name not in self.queues:
            raise QueueError(f"unknown queue {name!r}")
        del self.queues[name]

    def list_queues(self) -> list[str]:
        return sorted(self.queues)

    # --- persistence ---------------------------------------------------- #
    def to_state(self) -> dict[str, Any]:
        return {"queues": [q.to_state() for q in self.queues.values()]}

    @classmethod
    def from_state(
        cls, data: dict[str, Any], clock: Callable[[], float] = time.time
    ) -> "QueueManager":
        manager = cls(clock=clock)
        for queue_data in data.get("queues", []):
            queue = EventQueue.from_state(queue_data, clock=clock)
            manager.queues[queue.name] = queue
        # re-link dead-letter queues by name
        for queue_data, queue in zip(data.get("queues", []), manager.queues.values()):
            dlq_name = queue_data.get("dead_letter")
            if dlq_name:
                queue.dead_letter = manager.queues.get(dlq_name)
        return manager

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_state(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(
        cls, path: str | Path, clock: Callable[[], float] = time.time
    ) -> "QueueManager":
        source = Path(path)
        if not source.is_file():
            raise QueueError(f"state file not found: {source}")
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise QueueError(f"corrupt state file: {exc}") from exc
        return cls.from_state(data, clock=clock)


# --------------------------------------------------------------------------- #
# Serverless-style processing
# --------------------------------------------------------------------------- #
class EventProcessor:
    """Receives messages, runs a handler, acks or leaves them for retry."""

    def __init__(self, queue: EventQueue, handler: Callable[[Message], None]) -> None:
        self.queue = queue
        self.handler = handler
        self.processed = 0
        self.failed = 0

    def run_once(self, max_messages: int = 10) -> dict[str, int]:
        """One receive/handle/ack cycle. Failures stay for later redelivery."""
        stats = {"processed": 0, "failed": 0}
        for message in self.queue.receive(max_messages=max_messages):
            try:
                self.handler(message)
            except Exception as exc:  # noqa: BLE001 - handler failures are data
                self.failed += 1
                stats["failed"] += 1
                LOG.warning("handler failed on %s: %s", message.id, exc)
                continue  # message stays in-flight until visibility expires
            self.queue.delete(message.id)
            self.processed += 1
            stats["processed"] += 1
        return stats

    def to_dict(self) -> dict[str, Any]:
        return {"queue": self.queue.name, "processed": self.processed,
                "failed": self.failed}


# --------------------------------------------------------------------------- #
# Offline demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    """Simulate a failing serverless consumer with retries and a DLQ."""
    print("=" * 60)
    print(" SERVERLESS EVENT QUEUE - offline demo")
    print(" Fake clock: visibility timeouts and retries are instant.")
    print("=" * 60)

    clock = FakeClock(start=1_000_000.0)
    dlq = EventQueue("orders-dlq", clock=clock)
    orders = EventQueue(
        "orders",
        visibility_timeout=5.0,
        max_receive_count=3,
        clock=clock,
        dead_letter=dlq,
    )

    print("\n[1] Sending events (10 good orders + 2 poison messages)")
    for i in range(10):
        orders.send(f"order-{i:03d} created", {"type": "order.created"})
    orders.send("poison: bad payload", {"type": "order.broken"})
    orders.send("poison: also bad", {"type": "order.broken"})
    print(f"    depth={orders.depth} in_flight={orders.in_flight}")

    print("\n[2] Deduplication window")
    first = orders.send("order-000 created", {"type": "order.created"},
                        dedup_id="order-000")
    duplicate = orders.send("order-000 created again", dedup_id="order-000")
    print(f"    same dedup_id -> same message id: {first.id == duplicate.id} "
          f"(depth still {orders.depth})")

    def handler(message: Message) -> None:
        if "poison" in message.body:
            raise ValueError("handler crashed on poison message")
        # success path: nothing to do beyond acking

    processor = EventProcessor(orders, handler)

    print("\n[3] Processing rounds (handler rejects poison messages)")
    total_rounds = 5
    for round_no in range(1, total_rounds + 1):
        stats = processor.run_once(max_messages=6)
        attrs = orders.attributes()
        print(f"    round {round_no}: processed={stats['processed']} "
              f"failed={stats['failed']} depth={attrs['depth']} "
              f"in_flight={attrs['in_flight']} dead_lettered={attrs['dead_lettered']}")
        if round_no < total_rounds:
            clock.advance(5.0)  # visibility timeout expires -> retries surface

    print("\n[4] Final state")
    print(f"    orders  : {orders.attributes()}")
    print(f"    dlq     : depth={dlq.depth}, messages="
          f"{[m.body for m in dlq.messages]}")
    print(f"    processor: {processor.to_dict()}")

    # --- invariants the demo asserts -----------------------------------
    assert orders.depth == 0, "all orders should be consumed or dead-lettered"
    assert orders.in_flight == 0, "nothing should remain in-flight"
    assert dlq.depth == 2, "both poison messages should be in the DLQ"
    assert processor.processed == 11, "all 11 good orders should be processed"
    assert orders.dead_lettered_total == 2

    # change_visibility demo: requeue one message immediately
    extra = orders.send("retry me")
    orders.change_visibility(extra.id, timeout=0)
    assert orders.receive()[0].id == extra.id
    orders.delete(extra.id)

    print("\nDemo completed successfully.")
    return 0
