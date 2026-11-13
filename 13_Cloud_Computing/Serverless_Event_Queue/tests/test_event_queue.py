"""Tests for the Serverless Event Queue project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from event_queue import (  # noqa: E402
    DEDUP_WINDOW,
    EventProcessor,
    EventQueue,
    FakeClock,
    Message,
    QueueError,
    QueueManager,
    run_demo,
)
from main import main  # noqa: E402


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock(start=1_000.0)


@pytest.fixture()
def queue(clock) -> EventQueue:
    return EventQueue("orders", visibility_timeout=5.0, max_receive_count=3,
                      clock=clock, dead_letter=EventQueue("orders-dlq", clock=clock))


# --------------------------------------------------------------------------- #
# FakeClock
# --------------------------------------------------------------------------- #
def test_clock_advance():
    clock = FakeClock(start=10.0)
    assert clock() == 10.0
    assert clock.advance(5.0) == 15.0
    assert clock() == 15.0


def test_clock_rejects_backward():
    clock = FakeClock()
    with pytest.raises(QueueError, match="backwards"):
        clock.advance(-1)


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #
def test_queue_name_validation():
    with pytest.raises(QueueError, match="invalid queue name"):
        EventQueue("")
    with pytest.raises(QueueError, match="invalid queue name"):
        EventQueue("bad name!")
    assert EventQueue("orders-dlq_1").name == "orders-dlq_1"


def test_queue_parameter_validation(clock):
    with pytest.raises(QueueError, match="visibility_timeout"):
        EventQueue("q", visibility_timeout=0, clock=clock)
    with pytest.raises(QueueError, match="retention"):
        EventQueue("q", retention=-1, clock=clock)
    with pytest.raises(QueueError, match="max_receive_count"):
        EventQueue("q", max_receive_count=0, clock=clock)
    with pytest.raises(QueueError, match="delay"):
        EventQueue("q", delay=-0.5, clock=clock)


# --------------------------------------------------------------------------- #
# Sending and FIFO order
# --------------------------------------------------------------------------- #
def test_send_assigns_ids_and_fifo_order(queue):
    first = queue.send("a")
    second = queue.send("b")
    assert first.id != second.id
    assert [m.body for m in queue.receive(max_messages=10)] == ["a", "b"]


def test_send_requires_string_body(queue):
    with pytest.raises(QueueError, match="body must be a string"):
        queue.send(b"bytes")  # type: ignore[arg-type]


def test_send_batch(queue):
    messages = queue.send_batch(["x", "y", "z"], {"type": "test"})
    assert len(messages) == 3
    assert all(m.attributes["type"] == "test" for m in messages)
    assert queue.sent_total == 3


def test_send_negative_delay_rejected(queue):
    with pytest.raises(QueueError, match="delay"):
        queue.send("late", delay=-1)


# --------------------------------------------------------------------------- #
# Visibility timeout
# --------------------------------------------------------------------------- #
def test_visibility_hides_message_until_timeout(queue, clock):
    message = queue.send("work")
    received = queue.receive()
    assert [m.id for m in received] == [message.id]
    assert queue.depth == 0 and queue.in_flight == 1

    # still hidden right before the timeout
    clock.advance(4.9)
    assert queue.receive() == []

    # visible again after the timeout
    clock.advance(0.2)
    again = queue.receive()
    assert [m.id for m in again] == [message.id]
    assert again[0].receive_count == 2


def test_change_visibility_makes_message_visible_now(queue, clock):
    message = queue.send("work")
    queue.receive()
    assert queue.depth == 0
    queue.change_visibility(message.id, timeout=0)
    assert queue.depth == 1
    assert queue.receive()[0].id == message.id


def test_change_visibility_unknown_id(queue):
    with pytest.raises(QueueError, match="not found"):
        queue.change_visibility("nope", timeout=1)
    with pytest.raises(QueueError, match="timeout"):
        queue.change_visibility(queue.send("x").id, -1)


def test_delete_message(queue):
    message = queue.send("bye")
    queue.delete(message.id)
    assert queue.depth == 0
    assert queue.deleted_total == 1
    with pytest.raises(QueueError, match="not found"):
        queue.delete(message.id)


# --------------------------------------------------------------------------- #
# Delay and retention
# --------------------------------------------------------------------------- #
def test_per_message_delay(queue, clock):
    queue.send("later", delay=10)
    assert queue.receive() == []
    clock.advance(10)
    assert len(queue.receive()) == 1


def test_queue_default_delay(clock):
    delayed = EventQueue("delayed", delay=30, clock=clock)
    delayed.send("x")
    assert delayed.depth == 0
    clock.advance(30)
    assert delayed.depth == 1


def test_retention_expires_messages(queue, clock):
    queue.send("old")
    clock.advance(4000)  # default retention is 3600
    assert queue.receive() == []
    assert queue.depth == 0


def test_receive_count_triggers_dead_letter(queue, clock):
    message = queue.send("poison")
    dlq = queue.dead_letter
    assert dlq is not None

    for attempt in range(3):  # receives 1, 2, 3 all succeed in fetching
        picked = queue.receive()
        assert [m.id for m in picked] == [message.id]
        if attempt < 2:
            clock.advance(5.0)  # visibility expires -> redelivery

    # 4th time around: receive_count+1 > max_receive_count -> redrive
    clock.advance(5.0)
    assert queue.receive() == []
    assert queue.depth == 0
    assert queue.dead_lettered_total == 1
    assert [m.id for m in dlq.messages] == [message.id]
    # DLQ messages are immediately visible there
    assert [m.id for m in dlq.receive()] == [message.id]


def test_dead_letter_without_dlq_drops_message(clock):
    lonely = EventQueue("lonely", visibility_timeout=1.0, max_receive_count=1,
                        clock=clock)
    lonely.send("doomed")
    lonely.receive()
    clock.advance(1.1)
    assert lonely.receive() == []
    assert lonely.dead_lettered_total == 1
    assert lonely.messages == []


# --------------------------------------------------------------------------- #
# Deduplication
# --------------------------------------------------------------------------- #
def test_dedup_window_returns_existing(queue):
    first = queue.send("order", dedup_id="order-1")
    duplicate = queue.send("order again", dedup_id="order-1")
    assert duplicate.id == first.id
    assert queue.sent_total == 1


def test_dedup_window_expires(queue, clock):
    queue.send("order", dedup_id="order-1")
    clock.advance(DEDUP_WINDOW + 1)
    fresh = queue.send("order again", dedup_id="order-1")
    assert queue.sent_total == 2
    assert fresh.body == "order again"


def test_dedup_distinct_ids_both_land(queue):
    queue.send("a", dedup_id="one")
    queue.send("b", dedup_id="two")
    assert queue.depth == 2


# --------------------------------------------------------------------------- #
# Purge and attributes
# --------------------------------------------------------------------------- #
def test_purge(queue):
    queue.send_batch(["a", "b", "c"])
    queue.receive()
    removed = queue.purge()
    assert removed == 3
    assert queue.depth == 0 and queue.in_flight == 0


def test_attributes(queue, clock):
    queue.send_batch(["a", "b"])
    queue.receive()
    attrs = queue.attributes()
    assert attrs["name"] == "orders"
    assert attrs["depth"] == 1 and attrs["in_flight"] == 1
    assert attrs["sent"] == 2 and attrs["received"] == 1
    assert attrs["visibility_timeout"] == 5.0
    assert attrs["max_receive_count"] == 3


def test_depth_counts_only_visible(queue, clock):
    queue.send_batch(["a", "b", "c"])
    queue.receive(max_messages=2)
    assert queue.depth == 1 and queue.in_flight == 2


# --------------------------------------------------------------------------- #
# Message serialization
# --------------------------------------------------------------------------- #
def test_message_roundtrip():
    message = Message(id="abc", body="hello", attributes={"k": "v"},
                      created_at=1.0, visible_at=2.0, receive_count=1,
                      dedup_id="d1")
    restored = Message.from_dict(message.to_dict())
    assert restored == message


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #
def test_manager_create_get_list_delete(clock):
    manager = QueueManager(clock=clock)
    manager.create_queue("a")
    manager.create_queue("b", visibility_timeout=10)
    assert manager.list_queues() == ["a", "b"]
    assert manager.get_queue("b").visibility_timeout == 10

    manager.create_queue("a")  # idempotent
    assert len(manager.queues) == 2

    manager.delete_queue("a")
    assert manager.list_queues() == ["b"]
    with pytest.raises(QueueError, match="unknown queue"):
        manager.get_queue("a")
    with pytest.raises(QueueError, match="unknown queue"):
        manager.delete_queue("ghost")


def test_manager_get_unknown_lists_available(clock):
    manager = QueueManager(clock=clock)
    manager.create_queue("orders")
    with pytest.raises(QueueError, match="available: orders"):
        manager.get_queue("nope")


def test_state_roundtrip(tmp_path, clock):
    manager = QueueManager(clock=clock)
    dlq = manager.create_queue("orders-dlq")
    orders = manager.create_queue("orders", max_receive_count=2, dead_letter=dlq)
    orders.send("hello", {"type": "t"})
    orders.send("world")

    path = manager.save(tmp_path / "state.json")
    loaded = QueueManager.load(path, clock=clock)

    assert loaded.list_queues() == ["orders", "orders-dlq"]
    restored = loaded.get_queue("orders")
    assert [m.body for m in restored.receive(max_messages=10)] == ["hello", "world"]
    assert restored.max_receive_count == 2
    assert restored.dead_letter is loaded.get_queue("orders-dlq")


def test_load_missing_state(tmp_path, clock):
    with pytest.raises(QueueError, match="not found"):
        QueueManager.load(tmp_path / "nope.json", clock=clock)


def test_load_corrupt_state(tmp_path, clock):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(QueueError, match="corrupt"):
        QueueManager.load(bad, clock=clock)


# --------------------------------------------------------------------------- #
# EventProcessor
# --------------------------------------------------------------------------- #
def test_processor_acks_successes(queue, clock):
    queue.send_batch(["ok-1", "ok-2", "ok-3"])
    seen: list[str] = []
    processor = EventProcessor(queue, lambda m: seen.append(m.body))

    stats = processor.run_once(max_messages=10)
    assert stats == {"processed": 3, "failed": 0}
    assert seen == ["ok-1", "ok-2", "ok-3"]
    assert queue.depth == 0
    assert processor.to_dict() == {"queue": "orders", "processed": 3, "failed": 0}


def test_processor_keeps_failures_for_retry(queue, clock):
    queue.send("good")
    queue.send("poison")

    def handler(message: Message) -> None:
        if "poison" in message.body:
            raise ValueError("boom")

    processor = EventProcessor(queue, handler)
    stats = processor.run_once(max_messages=10)
    assert stats == {"processed": 1, "failed": 1}
    assert processor.processed == 1 and processor.failed == 1
    # poison stays in-flight, not deleted
    assert queue.depth == 0 and queue.in_flight == 1

    clock.advance(5.0)  # visibility expires -> redelivery
    stats = processor.run_once(max_messages=10)
    assert stats["failed"] == 1
    assert queue.dead_lettered_total == 0  # only 2 receives so far


def test_processor_empty_queue(queue):
    processor = EventProcessor(queue, lambda m: None)
    assert processor.run_once() == {"processed": 0, "failed": 0}


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Deduplication window" in out
    assert "Processing rounds" in out
    assert "dead_lettered': 2" in out or "dead_lettered\": 2" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out


def _state(tmp_path: Path) -> Path:
    return tmp_path / "queue_state.json"


def test_cli_lifecycle(tmp_path, capsys):
    state = str(_state(tmp_path))

    assert main(["--create", "orders", "--state", state]) == 0
    assert "ready" in capsys.readouterr().out

    assert main(["--send", "orders", "--body", "hello",
                 "--attr", "type=test", "--state", state]) == 0
    assert "Sent" in capsys.readouterr().out

    assert main(["--receive", "orders", "--max", "5", "--state", state]) == 0
    out = capsys.readouterr().out
    assert "hello" in out and "type" in out

    assert main(["--attributes", "orders", "--state", state]) == 0
    out = capsys.readouterr().out
    assert "sent" in out and "1" in out

    assert main(["--list", "--state", state]) == 0
    assert "orders" in capsys.readouterr().out


def test_cli_send_and_delete_by_id(tmp_path, capsys):
    state = str(_state(tmp_path))
    main(["--create", "jobs", "--state", state])
    capsys.readouterr()

    assert main(["--send", "jobs", "--body", "task-1", "--state", state]) == 0
    capsys.readouterr()

    assert main(["--receive", "jobs", "--state", state, "--json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("["):out.rindex("]") + 1])
    message_id = payload[0]["id"]

    assert main(["--delete", "jobs", "--id", message_id, "--state", state]) == 0
    assert "Deleted" in capsys.readouterr().out

    assert main(["--receive", "jobs", "--state", state]) == 0
    assert "no messages" in capsys.readouterr().out


def test_cli_purge(tmp_path, capsys):
    state = str(_state(tmp_path))
    main(["--create", "q", "--state", state])
    main(["--send", "q", "--body", "a", "--state", state])
    main(["--send", "q", "--body", "b", "--state", state])
    capsys.readouterr()

    assert main(["--purge", "q", "--state", state]) == 0
    assert "Purged 2" in capsys.readouterr().out


def test_cli_send_requires_body(tmp_path, capsys):
    state = str(_state(tmp_path))
    main(["--create", "q", "--state", state])
    capsys.readouterr()
    assert main(["--send", "q", "--state", state]) == 2
    assert "--body" in capsys.readouterr().err


def test_cli_delete_requires_id(tmp_path, capsys):
    state = str(_state(tmp_path))
    main(["--create", "q", "--state", state])
    capsys.readouterr()
    assert main(["--delete", "q", "--state", state]) == 2
    assert "--id" in capsys.readouterr().err


def test_cli_unknown_queue(tmp_path, capsys):
    state = str(_state(tmp_path))
    assert main(["--send", "ghost", "--body", "x", "--state", state]) == 2
    assert "unknown queue" in capsys.readouterr().err


def test_cli_bad_attribute(tmp_path, capsys):
    state = str(_state(tmp_path))
    main(["--create", "q", "--state", state])
    capsys.readouterr()
    assert main(["--send", "q", "--body", "x", "--attr", "novalue",
                 "--state", state]) == 2
    assert "K=V" in capsys.readouterr().err


def test_cli_create_with_dlq(tmp_path, capsys):
    state = str(_state(tmp_path))
    assert main(["--create", "main-dlq", "--state", state]) == 0
    assert main(["--create", "main", "--dlq", "main-dlq", "--max-receive", "2",
                 "--visibility", "5", "--state", state]) == 0
    out = capsys.readouterr().out
    assert "max_receive=2" in out and "visibility=5" in out


def test_cli_list_empty(tmp_path, capsys):
    state = str(_state(tmp_path))
    assert main(["--list", "--state", state]) == 0
    assert "no queues" in capsys.readouterr().out


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])
