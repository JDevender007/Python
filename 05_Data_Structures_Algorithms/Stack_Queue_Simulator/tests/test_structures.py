"""Tests for Stack_Queue_Simulator: undo is a second stack, and a counter is not
a history."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
import structures                                             # noqa: E402
from structures import (                                      # noqa: E402
    ACTIONS,
    CAPACITY,
    KINDS,
    LEGACY_CALLBACKS,
    LEGACY_COUNTER,
    LEGACY_COUNTER_SITES,
    LEGACY_THEORY,
    MAX_LENGTH,
    MUTATIONS,
    READS,
    SESSION_FILE,
    Deque,
    Divergence,
    HistoryError,
    Overflow,
    PriorityQueue,
    Queue,
    Simulator,
    Stack,
    Step,
    StructureError,
    Underflow,
    ValidationError,
    audit,
    check_capacity,
    check_priority,
    check_value,
    problems,
    read_session,
    run_demo,
    run_session,
)

FINAL = {"stack": ("red", "green"), "queue": ("two",), "deque": (),
         "heap": ("soon", "later")}


def session_file(folder: Path, text: str, name: str = "session.txt") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(text.encode("utf-8"))
    return path


def simulator() -> Simulator:
    return run_session(read_session())


# --------------------------------------------------------------------------- #
# Values
# --------------------------------------------------------------------------- #
def test_a_capacity_must_be_an_integer():
    with pytest.raises(ValidationError, match="a capacity must be an integer"):
        check_capacity(1.5)


def test_a_boolean_capacity_is_refused():
    with pytest.raises(ValidationError, match="a capacity must be an integer"):
        check_capacity(True)


def test_a_capacity_of_zero_is_refused():
    with pytest.raises(ValidationError, match="a capacity must be at least one"):
        check_capacity(0)


def test_a_capacity_of_one_is_allowed():
    assert check_capacity(1) == 1


def test_a_value_is_stripped():
    assert check_value("  red  ") == "red"


def test_an_empty_value_is_refused():
    with pytest.raises(ValidationError, match="a value cannot be empty"):
        check_value("   ")


def test_a_value_that_is_not_text_is_refused():
    with pytest.raises(ValidationError, match="a value must be text"):
        check_value(7)


def test_a_value_longer_than_the_limit_is_refused():
    with pytest.raises(ValidationError, match="at most 12 characters, got 13"):
        check_value("x" * 13)


def test_a_value_of_exactly_the_limit_is_allowed():
    assert len(check_value("x" * MAX_LENGTH)) == 12


def test_a_value_with_a_space_inside_is_refused():
    with pytest.raises(ValidationError, match="cannot hold a space"):
        check_value("a b")


def test_a_priority_must_be_an_integer():
    with pytest.raises(ValidationError, match="a priority must be an integer"):
        check_priority("high")


def test_a_negative_priority_is_allowed():
    assert check_priority(-3) == -3


# --------------------------------------------------------------------------- #
# Stack
# --------------------------------------------------------------------------- #
def test_a_stack_is_empty_when_it_starts():
    stack = Stack(3)
    assert stack.is_empty and stack.size == 0 and len(stack) == 0


def test_a_push_returns_the_value_it_stored():
    assert Stack(3).push("a") == "a"


def test_a_push_puts_the_value_on_top():
    stack = Stack(3)
    stack.push("a")
    stack.push("b")
    assert stack.items == ("a", "b") and stack.peek() == "b"


def test_a_pop_returns_the_top_and_removes_it():
    stack = Stack(3)
    stack.push("a")
    stack.push("b")
    assert stack.pop() == "b" and stack.items == ("a",)


def test_a_stack_is_last_in_first_out():
    stack = Stack(4)
    for value in ("a", "b", "c"):
        stack.push(value)
    assert [stack.pop() for _ in range(3)] == ["c", "b", "a"]


def test_a_full_stack_refuses_a_push():
    stack = Stack(2)
    stack.push("a")
    stack.push("b")
    assert stack.is_full
    with pytest.raises(Overflow, match="stack overflow: capacity is 2"):
        stack.push("c")


def test_an_empty_stack_refuses_a_pop():
    with pytest.raises(Underflow, match="stack underflow: it is empty"):
        Stack(2).pop()


def test_an_empty_stack_refuses_a_peek():
    with pytest.raises(Underflow, match="stack underflow: it is empty"):
        Stack(2).peek()


def test_a_clear_returns_what_it_removed():
    stack = Stack(3)
    stack.push("a")
    stack.push("b")
    assert stack.clear() == ((None, "a"), (None, "b"))
    assert stack.is_empty


def test_a_stack_prints_its_capacity_and_items():
    stack = Stack(2)
    stack.push("a")
    assert repr(stack) == "Stack(capacity=2, items=['a'])"


def test_a_stack_of_zero_capacity_cannot_be_built():
    with pytest.raises(ValidationError, match="at least one"):
        Stack(0)


def test_a_stack_will_not_store_a_bad_value():
    with pytest.raises(ValidationError, match="cannot be empty"):
        Stack(2).push("  ")


# --------------------------------------------------------------------------- #
# Queue
# --------------------------------------------------------------------------- #
def test_a_queue_is_first_in_first_out():
    queue = Queue(4)
    for value in ("a", "b", "c"):
        queue.enqueue(value)
    assert [queue.dequeue() for _ in range(3)] == ["a", "b", "c"]


def test_the_front_and_the_rear_are_different_ends():
    queue = Queue(3)
    queue.enqueue("a")
    queue.enqueue("b")
    assert queue.front() == "a" and queue.rear() == "b"


def test_a_queue_items_run_from_front_to_rear():
    queue = Queue(3)
    queue.enqueue("a")
    queue.enqueue("b")
    assert queue.items == ("a", "b")


def test_add_front_puts_a_value_back_at_the_front():
    queue = Queue(3)
    queue.enqueue("b")
    queue.add_front("a")
    assert queue.items == ("a", "b")


def test_remove_rear_takes_the_last_value():
    queue = Queue(3)
    queue.enqueue("a")
    queue.enqueue("b")
    assert queue.remove_rear() == "b" and queue.items == ("a",)


def test_an_empty_queue_refuses_a_dequeue():
    with pytest.raises(Underflow, match="queue underflow: it is empty"):
        Queue(2).dequeue()


def test_an_empty_queue_refuses_a_front():
    with pytest.raises(Underflow, match="queue underflow: it is empty"):
        Queue(2).front()


def test_an_empty_queue_refuses_a_rear():
    with pytest.raises(Underflow, match="queue underflow: it is empty"):
        Queue(2).rear()


def test_a_full_queue_refuses_an_enqueue():
    queue = Queue(1)
    queue.enqueue("a")
    with pytest.raises(Overflow, match="queue overflow: capacity is 1"):
        queue.enqueue("b")


def test_a_queue_clear_returns_front_to_rear():
    queue = Queue(3)
    queue.enqueue("a")
    queue.enqueue("b")
    assert queue.clear() == ((None, "a"), (None, "b"))


# --------------------------------------------------------------------------- #
# Deque
# --------------------------------------------------------------------------- #
def test_a_deque_adds_and_removes_at_both_ends():
    deque_ = Deque(4)
    deque_.push_front("f")
    deque_.push_back("b")
    assert deque_.items == ("f", "b")
    assert deque_.pop_front() == "f" and deque_.pop_back() == "b"


def test_a_deque_is_a_stack_at_the_front():
    deque_ = Deque(4)
    deque_.push_front("a")
    deque_.push_front("b")
    assert [deque_.pop_front(), deque_.pop_front()] == ["b", "a"]


def test_a_deque_is_a_queue_at_the_back():
    deque_ = Deque(4)
    deque_.push_back("a")
    deque_.push_back("b")
    assert [deque_.pop_back(), deque_.pop_back()] == ["b", "a"]


def test_a_deque_reports_its_ends():
    deque_ = Deque(3)
    deque_.push_back("a")
    deque_.push_front("z")
    assert deque_.front() == "z" and deque_.rear() == "a"


def test_an_empty_deque_refuses_both_pops():
    with pytest.raises(Underflow, match="deque underflow"):
        Deque(2).pop_front()
    with pytest.raises(Underflow, match="deque underflow"):
        Deque(2).pop_back()


def test_a_full_deque_refuses_both_pushes():
    deque_ = Deque(1)
    deque_.push_back("a")
    with pytest.raises(Overflow, match="deque overflow"):
        deque_.push_front("b")


# --------------------------------------------------------------------------- #
# PriorityQueue
# --------------------------------------------------------------------------- #
def test_a_heap_pops_the_smallest_priority_first():
    heap = PriorityQueue(4)
    for value, priority in (("x", 5), ("y", 1), ("z", 3)):
        heap.push(value, priority)
    assert [heap.pop() for _ in range(3)] == ["y", "z", "x"]


def test_a_heap_breaks_ties_by_insertion_order():
    heap = PriorityQueue(4)
    for value in ("first", "second", "third"):
        heap.push(value, 0)
    assert heap.items == ("first", "second", "third")


def test_a_heap_push_returns_the_entry_it_stored():
    entry = PriorityQueue(2).push("x", 4)
    assert entry == (4, 0, "x")


def test_a_heaps_second_push_carries_a_later_sequence_number():
    heap = PriorityQueue(2)
    heap.push("a")
    assert heap.push("b")[1] == 1


def test_the_heap_order_is_the_pop_order():
    heap = PriorityQueue(4)
    for value, priority in (("x", 2), ("y", 1), ("z", 2)):
        heap.push(value, priority)
    assert heap.items == ("y", "x", "z")


def test_top_reports_the_priority_and_the_value():
    heap = PriorityQueue(2)
    heap.push("x", 7)
    assert heap.top() == (7, "x")


def test_pop_entry_returns_the_whole_entry():
    heap = PriorityQueue(2)
    entry = heap.push("x", 7)
    assert heap.pop_entry() == entry


def test_push_entry_puts_an_exact_entry_back():
    heap = PriorityQueue(3)
    entry = heap.push("x", 7)
    heap.pop()
    heap.push_entry(entry)
    assert heap.items == ("x",)


def test_push_entry_keeps_a_tie_in_its_old_place():
    heap = PriorityQueue(4)
    first = heap.push("a", 0)
    heap.push("b", 0)
    heap.pop()
    heap.push_entry(first)
    assert heap.items == ("a", "b")


def test_remove_entry_takes_exactly_one_entry():
    heap = PriorityQueue(3)
    entry = heap.push("a", 0)
    heap.push("b", 0)
    assert heap.remove_entry(entry) and heap.items == ("b",)


def test_remove_entry_reports_a_missing_entry():
    heap = PriorityQueue(3)
    assert not heap.remove_entry((0, 99, "ghost"))


def test_a_heap_clear_keeps_the_tie_order():
    heap = PriorityQueue(4)
    for value in ("a", "b", "c"):
        heap.push(value, 1)
    restored = heap.clear()
    for priority, value in restored:
        heap.push(value, priority)
    assert heap.items == ("a", "b", "c")


def test_a_full_heap_refuses_a_push():
    heap = PriorityQueue(1)
    heap.push("a")
    with pytest.raises(Overflow, match="heap overflow: capacity is 1"):
        heap.push("b")


def test_an_empty_heap_refuses_a_pop():
    with pytest.raises(Underflow, match="heap underflow"):
        PriorityQueue(1).pop()


# --------------------------------------------------------------------------- #
# Step
# --------------------------------------------------------------------------- #
def test_a_step_prints_its_number_structure_action_and_value():
    assert str(Step(3, "stack", "push", "red")) == "#3 stack push red"


def test_a_step_with_a_priority_prints_it():
    assert str(Step(4, "heap", "heap_push", "soon", 3)) == \
        "#4 heap heap_push soon @3"


def test_a_step_for_a_clear_counts_its_items():
    assert str(Step(5, "queue", "clear", None, None, ((None, "a"),))) == \
        "#5 queue clear 1 item(s)"


def test_a_step_is_frozen():
    with pytest.raises(Exception):
        Step(1, "stack", "push", "a").number = 2   # type: ignore[misc]


def test_a_step_defaults_to_no_value_and_no_entry():
    step = Step(1, "stack", "clear")
    assert step.value is None and step.entry is None and step.restored == ()


# --------------------------------------------------------------------------- #
# Simulator: the four structures and the counters
# --------------------------------------------------------------------------- #
def test_a_simulator_starts_with_four_empty_structures():
    lab = Simulator(4)
    assert set(lab.snapshot()) == set(KINDS)
    assert all(not items for items in lab.snapshot().values())


def test_a_simulator_refuses_an_unknown_structure():
    with pytest.raises(ValidationError, match="no such structure: 'list'"):
        Simulator(4).structure("list")


def test_a_mutation_counts_as_applied():
    lab = Simulator(4)
    lab.push("a")
    assert lab.applied == 1 and lab.undo_depth == 1


def test_a_read_counts_as_a_read_and_nothing_else():
    lab = Simulator(4)
    lab.push("a")
    lab.peek()
    assert lab.reads == 1 and lab.applied == 1


def test_a_failed_read_is_not_counted():
    lab = Simulator(4)
    with pytest.raises(Underflow):
        lab.peek()
    assert lab.reads == 0


def test_a_refused_push_counts_as_refused():
    lab = Simulator(1)
    lab.push("a")
    with pytest.raises(Overflow):
        lab.push("b")
    assert lab.applied == 1 and lab.refused == 1


def test_a_refused_pop_counts_as_refused():
    lab = Simulator(2)
    with pytest.raises(Underflow):
        lab.pop()
    assert lab.refused == 1 and lab.undo_depth == 0


def test_the_total_mixes_success_and_failure():
    lab = Simulator(1)
    lab.push("a")
    with pytest.raises(Overflow):
        lab.push("b")
    assert lab.total == 2 and lab.applied == 1


def test_a_refused_operation_is_not_undoable():
    lab = Simulator(1)
    lab.push("a")
    with pytest.raises(Overflow):
        lab.push("b")
    assert lab.undo_depth == 1


def test_clearing_an_empty_structure_records_nothing():
    assert Simulator(2).clear("stack") == ()


def test_clearing_a_structure_returns_its_values():
    lab = Simulator(3)
    lab.push("a")
    lab.push("b")
    assert lab.clear("stack") == ("a", "b")
    assert lab.structure("stack").items == ()


def test_a_simulator_refuses_a_zero_capacity():
    with pytest.raises(ValidationError, match="at least one"):
        Simulator(0)


def test_the_snapshot_is_a_copy():
    lab = Simulator(2)
    lab.push("a")
    first = lab.snapshot()
    lab.push("b")
    assert first["stack"] == ("a",)


# --------------------------------------------------------------------------- #
# Undo and redo
# --------------------------------------------------------------------------- #
def test_an_undo_reverses_a_push():
    lab = Simulator(2)
    lab.push("a")
    step = lab.undo()
    assert step.action == "push" and lab.structure("stack").items == ()


def test_an_undo_reverses_a_pop():
    lab = Simulator(2)
    lab.push("a")
    lab.pop()
    lab.undo()
    assert lab.structure("stack").items == ("a",)


def test_an_undo_reverses_an_enqueue():
    lab = Simulator(2)
    lab.enqueue("a")
    lab.enqueue("b")
    lab.undo()
    assert lab.structure("queue").items == ("a",)


def test_an_undo_reverses_a_dequeue():
    lab = Simulator(2)
    lab.enqueue("a")
    lab.dequeue()
    lab.undo()
    assert lab.structure("queue").items == ("a",)


def test_an_undo_reverses_a_deque_push_at_the_front():
    lab = Simulator(2)
    lab.push_front("a")
    lab.push_back("b")
    lab.undo()
    assert lab.structure("deque").items == ("a",)


def test_an_undo_reverses_a_heap_push_even_after_other_pushes():
    lab = Simulator(4)
    lab.heap_push("a", 1)
    lab.heap_push("b", 9)
    lab.heap_push("c", 3)
    lab.undo()
    assert lab.structure("heap").items == ("a", "b")


def test_an_undo_reverses_a_heap_pop_with_its_priority():
    lab = Simulator(4)
    lab.heap_push("a", 5)
    lab.heap_push("b", 1)
    lab.heap_pop()
    lab.undo()
    assert lab.structure("heap").items == ("b", "a")


def test_an_undo_reverses_a_clear():
    lab = Simulator(3)
    lab.push("a")
    lab.push("b")
    lab.clear("stack")
    lab.undo()
    assert lab.structure("stack").items == ("a", "b")


def test_an_undo_of_a_clear_keeps_a_heaps_tie_order():
    lab = Simulator(4)
    for value in ("a", "b", "c"):
        lab.heap_push(value, 1)
    lab.clear("heap")
    lab.undo()
    assert lab.structure("heap").items == ("a", "b", "c")


def test_a_redo_replays_a_push():
    lab = Simulator(2)
    lab.push("a")
    lab.undo()
    lab.redo()
    assert lab.structure("stack").items == ("a",)


def test_a_redo_replays_a_pop():
    lab = Simulator(2)
    lab.push("a")
    lab.pop()
    lab.undo()
    lab.redo()
    assert lab.structure("stack").items == ()


def test_a_new_operation_clears_the_future():
    lab = Simulator(2)
    lab.push("a")
    lab.undo()
    assert lab.can_redo
    lab.push("b")
    assert not lab.can_redo and lab.redo_depth == 0


def test_the_discarded_steps_are_counted():
    lab = Simulator(2)
    lab.push("a")
    lab.push("b")
    lab.undo()
    lab.undo()
    lab.push("c")
    assert lab.discarded == 2


def test_the_bookkeeping_adds_up():
    lab = Simulator(3)
    for value in ("a", "b", "c"):
        lab.push(value)
    lab.undo()
    lab.undo()
    lab.push("d")
    assert lab.undo_depth + lab.redo_depth + lab.discarded == lab.applied


def test_undo_all_returns_how_many_it_undid():
    lab = simulator()
    assert lab.undo_all() == 15


def test_undo_all_empties_every_structure():
    lab = simulator()
    lab.undo_all()
    assert all(not items for items in lab.snapshot().values())


def test_redo_all_restores_the_final_state():
    lab = simulator()
    final = lab.snapshot()
    lab.undo_all()
    assert lab.redo_all() == 15
    assert lab.snapshot() == final


def test_undoing_with_an_empty_history_is_refused():
    with pytest.raises(HistoryError, match="there is nothing to undo"):
        Simulator(2).undo()


def test_redoing_with_an_empty_future_is_refused():
    lab = Simulator(2)
    lab.push("a")
    with pytest.raises(HistoryError, match="there is nothing to redo"):
        lab.redo()


def test_a_step_keeps_its_number_across_an_undo_and_a_redo():
    lab = Simulator(2)
    lab.push("a")
    number = lab.history[-1].number
    lab.undo()
    assert lab.future[-1].number == number
    lab.redo()
    assert lab.history[-1].number == number


def test_a_failed_undo_leaves_the_step_in_the_history():
    lab = Simulator(2)
    lab.push("a")
    lab.push("b")
    lab.structure("stack").pop()            # tamper, outside the history
    with pytest.raises(Divergence):
        lab.undo()
    assert lab.undo_depth == 2 and not lab.can_redo


def test_a_failed_redo_leaves_the_step_in_the_future():
    lab = Simulator(2)
    lab.push("a")
    lab.pop()
    lab.undo()
    lab.structure("stack").push("x")        # tamper, outside the history
    with pytest.raises(Divergence):
        lab.redo()
    assert lab.redo_depth == 1 and lab.undo_depth == 1


def test_a_missing_heap_entry_is_a_divergence():
    lab = Simulator(3)
    lab.heap_push("a", 1)
    lab.structure("heap").pop()             # tamper, outside the history
    with pytest.raises(Divergence, match="no longer in the heap"):
        lab.undo()


def test_an_unknown_action_has_no_inverse():
    lab = Simulator(2)
    with pytest.raises(HistoryError, match="no inverse for 'fly'"):
        lab._revert(Step(1, "stack", "fly"))


def test_an_unknown_action_has_no_replay():
    lab = Simulator(2)
    with pytest.raises(HistoryError, match="no replay for 'fly'"):
        lab._replay(Step(1, "stack", "fly"))


# --------------------------------------------------------------------------- #
# Session files
# --------------------------------------------------------------------------- #
def test_read_session_refuses_a_missing_file(tmp_path):
    with pytest.raises(ValidationError, match="session file not found"):
        read_session(tmp_path / "nope.txt")


def test_read_session_skips_comments_and_blank_lines(tmp_path):
    path = session_file(tmp_path, "; head\n\npush a\n// note\n")
    assert read_session(path) == (("push", "a"),)


def test_read_session_splits_a_heap_push_into_three_parts(tmp_path):
    path = session_file(tmp_path, "heap_push urgent 1\n")
    assert read_session(path) == (("heap_push", "urgent", "1"),)


def test_read_session_refuses_an_unknown_action(tmp_path):
    path = session_file(tmp_path, "push a\nfly\n")
    with pytest.raises(ValidationError, match="session.txt:2: 'fly' is not an "
                                              "action"):
        read_session(path)


def test_read_session_refuses_a_push_without_a_value(tmp_path):
    with pytest.raises(ValidationError, match="push takes one value"):
        read_session(session_file(tmp_path, "push\n"))


def test_read_session_refuses_a_push_with_two_values(tmp_path):
    with pytest.raises(ValidationError, match="push takes one value"):
        read_session(session_file(tmp_path, "push a b\n"))


def test_read_session_refuses_arguments_after_a_pop(tmp_path):
    with pytest.raises(ValidationError, match="pop takes no arguments"):
        read_session(session_file(tmp_path, "pop a\n"))


def test_read_session_refuses_a_heap_push_with_one_argument(tmp_path):
    with pytest.raises(ValidationError, match="heap_push takes a value and a "
                                              "priority"):
        read_session(session_file(tmp_path, "heap_push urgent\n"))


def test_the_bundled_session_has_seventeen_lines():
    assert len(read_session()) == 17


def test_the_bundled_session_file_holds_eighteen_lines_of_bytes():
    assert SESSION_FILE.read_bytes().count(b"\n") == 18


def test_running_the_bundled_session_leaves_the_pinned_state():
    assert simulator().snapshot() == FINAL


def test_the_bundled_session_applies_fifteen_steps():
    assert simulator().applied == 15


def test_the_bundled_session_counts_two_reads():
    assert simulator().reads == 2


def test_the_bundled_session_refuses_nothing():
    assert simulator().refused == 0


def test_a_session_that_underflows_names_its_line(tmp_path):
    path = session_file(tmp_path, "push a\npop\npop\n")
    with pytest.raises(Underflow, match=r"line 3 \(pop\): stack underflow"):
        run_session(read_session(path))


def test_a_session_that_overflows_names_its_line(tmp_path):
    path = session_file(tmp_path, "push a\npush b\npush c\n")
    with pytest.raises(Overflow, match=r"line 3 \(push c\): stack overflow"):
        run_session(read_session(path), Simulator(2))


def test_a_session_with_a_bad_priority_names_its_line(tmp_path):
    path = session_file(tmp_path, "heap_push a high\n")
    with pytest.raises(ValidationError, match="a priority must be a whole "
                                              "number"):
        run_session(read_session(path))


def test_a_session_with_a_value_that_is_too_long_names_its_line(tmp_path):
    path = session_file(tmp_path, "push " + "x" * 13 + "\n")
    with pytest.raises(ValidationError, match="at most 12 characters"):
        run_session(read_session(path))


def test_the_session_can_be_run_twice_with_the_same_result():
    assert run_session(read_session()).snapshot() == \
        run_session(read_session()).snapshot()


# --------------------------------------------------------------------------- #
# The legacy claims
# --------------------------------------------------------------------------- #
def test_the_legacy_theory_sentence_is_pinned():
    assert LEGACY_THEORY == \
        "Function calls, undo/redo systems, expression evaluation, "


def test_the_legacy_panel_declared_eleven_callbacks():
    assert len(LEGACY_CALLBACKS) == 11


def test_none_of_the_legacy_callbacks_undoes_anything():
    assert [name for name in LEGACY_CALLBACKS if "undo" in name] == []


def test_the_legacy_counter_line_is_pinned():
    assert LEGACY_COUNTER == "self.operations_performed += 1"
    assert LEGACY_COUNTER_SITES == 2


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_the_audit_holds_twelve_named_checks():
    assert [name for name, _ in audit(simulator())] == [
        "every step names a structure that exists",
        "the stack is last-in first-out",
        "the queue is first-in first-out",
        "the deque is a stack at the front and a queue at the back",
        "the heap pops in non-decreasing priority",
        "the heap breaks ties by insertion order",
        "a lookup does not enter the history",
        "a new operation after an undo clears the redo stack",
        "undoing a clear restores every item in its old order",
        "the bookkeeping adds up",
        "the stack agrees with its own history",
        "no read is ever recorded as a step"]


def test_the_audit_passes_on_the_bundled_session():
    assert problems(audit(simulator())) == []


def test_the_audit_catches_a_step_for_a_structure_that_does_not_exist():
    lab = simulator()
    lab._past.append(Step(99, "list", "push", "x"))
    assert "every step names a structure that exists" in problems(audit(lab))


def test_the_audit_catches_a_stack_that_is_not_last_in_first_out(monkeypatch):
    monkeypatch.setattr(structures.Stack, "pop", lambda self: "wrong")
    assert "the stack is last-in first-out" in problems(audit(simulator()))


def test_the_audit_catches_a_queue_that_is_not_first_in_first_out(monkeypatch):
    monkeypatch.setattr(structures.Queue, "dequeue", lambda self: "wrong")
    assert "the queue is first-in first-out" in problems(audit(simulator()))


def test_the_audit_catches_a_deque_with_one_end(monkeypatch):
    monkeypatch.setattr(structures.Deque, "pop_back",
                        lambda self: "wrong")
    assert "the deque is a stack at the front and a queue at the back" in \
        problems(audit(simulator()))


def test_the_audit_catches_a_heap_in_the_wrong_order(monkeypatch):
    monkeypatch.setattr(structures.PriorityQueue, "pop", lambda self: "wrong")
    assert "the heap pops in non-decreasing priority" in problems(audit(
        simulator()))


def test_the_audit_catches_a_heap_that_ignores_its_ties(monkeypatch):
    monkeypatch.setattr(structures.PriorityQueue, "pop",
                        lambda self: self._items.pop()[2])
    assert "the heap breaks ties by insertion order" in problems(audit(
        simulator()))


def test_the_audit_catches_a_recorded_read(monkeypatch):
    """The check builds its own probe, so the defect must be planted in the
    probe's own method -- a step appended to the real history proves only that
    the other check ("no read is ever recorded") works."""
    original = Simulator.peek

    def recording_peek(self):
        value = original(self)
        self._record("stack", "push", value)
        return value

    monkeypatch.setattr(Simulator, "peek", recording_peek)
    assert "a lookup does not enter the history" in problems(audit(simulator()))


def test_the_audit_catches_a_redo_that_survives_a_new_operation(monkeypatch):
    """Put the discarded future back, and the check must notice."""
    original = Simulator._record

    def forgetful(self, *args, **kwargs):
        future = list(self._future)
        step = original(self, *args, **kwargs)
        self._future[:] = future
        return step

    monkeypatch.setattr(Simulator, "_record", forgetful)
    assert "a new operation after an undo clears the redo stack" in \
        problems(audit(simulator()))


def test_the_audit_catches_a_clear_that_cannot_be_undone(monkeypatch):
    monkeypatch.setattr(structures.Stack, "clear", lambda self: ())
    assert "undoing a clear restores every item in its old order" in \
        problems(audit(simulator()))


def test_the_audit_catches_bookkeeping_that_lost_a_step():
    lab = simulator()
    lab.discarded += 1
    assert "the bookkeeping adds up" in problems(audit(lab))


def test_the_audit_catches_a_stack_that_disagrees_with_its_history():
    lab = simulator()
    lab.structure("stack").push("unrecorded")
    assert "the stack agrees with its own history" in problems(audit(lab))


def test_the_audit_catches_a_read_in_the_future():
    lab = simulator()
    lab.undo()
    lab._future.append(Step(99, "queue", "front", "two"))
    assert "no read is ever recorded as a step" in problems(audit(lab))


def test_the_audit_is_repeatable():
    assert audit(simulator()) == audit(simulator())


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out and "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_final_state(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "    stack  red green" in out
    assert "    heap   soon later" in out


def test_demo_shows_the_counters(capsys):
    run_demo()
    assert "15 applied, 0 refused, 2 reads, 15 undoable" in \
        capsys.readouterr().out


def test_demo_shows_the_history_numbered(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "    #1 stack push red" in out
    assert "    #15 heap heap_pop urgent @1" in out


def test_demo_shows_the_undo_and_redo_round_trip(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "after undoing all 15:" in out
    assert "every structure empty again: yes" in out
    assert "after redoing all 15:" in out
    assert "the same state as before the undos: yes" in out


def test_demo_shows_the_redo_rule(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "one new operation: 14 undoable, 0 redoable -- the future is gone" \
        in out
    assert "discarded steps so far: 2" in out


def test_demo_shows_that_a_peek_is_not_an_operation(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "three pushes and a peek: 3 undoable, 1 read counted" in out
    assert "one undo leaves a b" in out


def test_demo_shows_the_legacy_claims(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "control panel: 11 callbacks, 0 of them undo anything" in out
    assert "appears 2 times -- once for success, once for failure" in out


def test_demo_shows_all_twelve_checks(capsys):
    run_demo()
    assert "12/12 checks pass" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_prints_the_state(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "data/session.txt: 17 lines, capacity 8" in out
    assert "15 applied, 0 refused, 2 reads, 15 undoable, 0 redoable" in out
    assert "    queue  two" in out


def test_cli_history_prints_the_steps(capsys):
    assert cli.main(["--history"]) == 0
    out = capsys.readouterr().out
    assert "recorded steps, oldest first:" in out
    assert "#1 stack push red" in out


def test_cli_undo_prints_the_state_after_it(capsys):
    assert cli.main(["--undo", "2"]) == 0
    out = capsys.readouterr().out
    assert "    heap   urgent later" in out
    assert "13 undoable, 2 redoable" in out


def test_cli_undo_all_empties_everything(capsys):
    assert cli.main(["--undo-all"]) == 0
    out = capsys.readouterr().out
    assert "0 undoable, 15 redoable" in out
    assert out.count("    ") == 4


def test_cli_redo_after_undo_restores_the_state(capsys):
    assert cli.main(["--undo-all", "--redo-all"]) == 0
    out = capsys.readouterr().out
    assert "    stack  red green" in out
    assert "15 undoable, 0 redoable" in out


def test_cli_undoing_too_far_exits_two(capsys):
    assert cli.main(["--undo", "99"]) == 2
    assert "there is nothing to undo" in capsys.readouterr().err


def test_cli_redoing_without_an_undo_exits_two(capsys):
    assert cli.main(["--redo", "1"]) == 2
    assert "there is nothing to redo" in capsys.readouterr().err


def test_cli_legacy_prints_the_claims(capsys):
    assert cli.main(["--legacy"]) == 0
    out = capsys.readouterr().out
    assert "its control panel declared 11 callbacks, 0 of which undo anything" \
        in out
    assert "success and failure alike" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 12 and "FAIL" not in out


def test_cli_json_writes_the_state_and_history(tmp_path, capsys):
    target = tmp_path / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["capacity"] == 8
    assert payload["state"] == {kind: list(values)
                                for kind, values in FINAL.items()}
    assert payload["counts"]["applied"] == 15
    assert payload["counts"]["undoable"] == 15
    assert payload["history"][0] == "#1 stack push red"
    assert payload["future"] == []


def test_cli_json_creates_directories(tmp_path, capsys):
    target = tmp_path / "a" / "b" / "out.json"
    assert cli.main(["--json", str(target)]) == 0
    capsys.readouterr()
    assert target.is_file()


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_missing_session_exits_two(tmp_path, capsys):
    assert cli.main(["--session", str(tmp_path / "nope.txt")]) == 2
    assert "session file not found" in capsys.readouterr().err


def test_cli_a_bad_capacity_exits_two(capsys):
    assert cli.main(["--capacity", "0"]) == 2
    assert "at least one" in capsys.readouterr().err


def test_cli_reads_another_session(tmp_path, capsys):
    path = session_file(tmp_path, "push a\npush b\npop\n")
    assert cli.main(["--session", str(path)]) == 0
    out = capsys.readouterr().out
    assert "session.txt: 3 lines, capacity 8" in out
    assert "    stack  a" in out


def test_cli_a_session_that_underflows_exits_two(tmp_path, capsys):
    path = session_file(tmp_path, "pop\n")
    assert cli.main(["--session", str(path)]) == 2
    assert "line 1 (pop): stack underflow" in capsys.readouterr().err
