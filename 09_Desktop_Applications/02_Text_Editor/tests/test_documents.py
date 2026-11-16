"""Tests for the document lab: saving is not writing a string to a file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import documents as module                                 # noqa: E402
import main as cli                                          # noqa: E402
from documents import (                                    # noqa: E402
    DEMO_EDIT,
    LEGACY_LOAD,
    LEGACY_SAVE,
    NEWLINES,
    NOTES_FILE,
    Document,
    DocumentError,
    Edit,
    atomic_save,
    audit,
    decode,
    detect_newline,
    encode,
    legacy_load,
    legacy_save,
    measure,
    normalise,
    problems,
    run_demo,
)

NOTE_BYTES = NOTES_FILE.read_bytes()
SOURCE = Document.load(NOTES_FILE)


# --------------------------------------------------------------------------- #
# encode
# --------------------------------------------------------------------------- #
def test_encode_writes_lf_text_unchanged():
    assert encode("one\ntwo\n") == b"one\ntwo\n"


def test_encode_turns_each_break_into_crlf():
    assert encode("one\ntwo\n", "\r\n") == b"one\r\ntwo\r\n"


def test_a_crlf_policy_costs_one_byte_per_break():
    text = "one\ntwo\nthree\n"
    assert len(encode(text, "\r\n")) - len(encode(text, "\n")) == 3


def test_encode_refuses_text_that_already_holds_a_carriage_return():
    with pytest.raises(DocumentError, match="holds a carriage return"):
        encode("one\r\ntwo\n")


def test_encode_refuses_a_newline_that_is_not_one():
    with pytest.raises(DocumentError, match="a newline is"):
        encode("one\n", "\r")


def test_encode_refuses_something_that_is_not_text():
    with pytest.raises(DocumentError, match="a document is text"):
        encode(b"one\n")


def test_the_two_newline_policies_are_the_two_constants():
    assert NEWLINES == ("\n", "\r\n")


# --------------------------------------------------------------------------- #
# decode
# --------------------------------------------------------------------------- #
def test_decode_reads_utf8():
    assert decode(b"caf\xc3\xa9\n") == "caf\u00e9\n"


def test_decode_keeps_crlf_as_written():
    assert decode(b"one\r\ntwo\r\n") == "one\r\ntwo\r\n"


def test_decode_names_the_byte_that_broke():
    with pytest.raises(DocumentError, match="byte 3 is not valid UTF-8"):
        decode(b"caf\xe9 au lait\n")


def test_decode_refuses_a_string():
    with pytest.raises(DocumentError, match="a file is bytes"):
        decode("one")


def test_decode_accepts_a_bytearray():
    assert decode(bytearray(b"one")) == "one"


# --------------------------------------------------------------------------- #
# detect_newline
# --------------------------------------------------------------------------- #
def test_detect_newline_finds_lf():
    assert detect_newline("one\ntwo\n") == "\n"


def test_detect_newline_finds_crlf():
    assert detect_newline("one\r\ntwo\r\n") == "\r\n"


def test_detect_newline_assumes_lf_for_a_single_line():
    assert detect_newline("no breaks here") == "\n"


def test_detect_newline_refuses_a_mixed_file_and_names_the_line():
    with pytest.raises(DocumentError, match="line 2 ends with LF"):
        detect_newline("first\r\nsecond\nthird\r\n")


def test_detect_newline_refuses_a_lone_carriage_return():
    with pytest.raises(DocumentError, match="line 1 holds a carriage return"):
        detect_newline("first\rsecond\n")


def test_detect_newline_refuses_something_that_is_not_text():
    with pytest.raises(DocumentError, match="a file is text"):
        detect_newline(b"one\n")


# --------------------------------------------------------------------------- #
# normalise
# --------------------------------------------------------------------------- #
def test_normalise_reduces_crlf_to_lf():
    assert normalise("one\r\ntwo\r\n") == "one\ntwo\n"


def test_normalise_leaves_lf_alone():
    assert normalise("one\ntwo\n") == "one\ntwo\n"


def test_normalise_refuses_a_mixed_file():
    with pytest.raises(DocumentError, match="one convention"):
        normalise("a\r\nb\n")


# --------------------------------------------------------------------------- #
# atomic_save
# --------------------------------------------------------------------------- #
def test_atomic_save_writes_the_bytes_and_returns_the_count(tmp_path):
    target = tmp_path / "note.txt"
    assert atomic_save(target, "one\ntwo\n") == 8
    assert target.read_bytes() == b"one\ntwo\n"


def test_atomic_save_honours_the_crlf_policy(tmp_path):
    target = tmp_path / "note.txt"
    assert atomic_save(target, "one\ntwo\n", "\r\n") == 10
    assert target.read_bytes() == b"one\r\ntwo\r\n"


def test_atomic_save_leaves_no_temporary_file_behind(tmp_path):
    target = tmp_path / "note.txt"
    atomic_save(target, "one\n")
    assert [path.name for path in tmp_path.iterdir()] == ["note.txt"]


def test_atomic_save_replaces_an_existing_document(tmp_path):
    target = tmp_path / "note.txt"
    target.write_bytes(b"the old one\n")
    atomic_save(target, "the new one\n")
    assert target.read_bytes() == b"the new one\n"


def test_atomic_save_keeps_the_original_when_the_temporary_cannot_be_made(tmp_path):
    target = tmp_path / "note.txt"
    target.write_bytes(b"the original\n")
    (tmp_path / "note.txt.tmp").mkdir()
    with pytest.raises(DocumentError, match="could not be written"):
        atomic_save(target, "the replacement\n")
    assert target.read_bytes() == b"the original\n"


def test_atomic_save_refuses_a_directory(tmp_path):
    with pytest.raises(DocumentError, match="is a directory, not a file"):
        atomic_save(tmp_path, "one\n")


def test_atomic_save_refuses_text_with_a_carriage_return(tmp_path):
    with pytest.raises(DocumentError, match="holds a carriage return"):
        atomic_save(tmp_path / "note.txt", "one\r\n")


def test_atomic_save_creates_the_file_when_it_is_new(tmp_path):
    target = tmp_path / "fresh.txt"
    atomic_save(target, "")
    assert target.read_bytes() == b""


# --------------------------------------------------------------------------- #
# The legacy path
# --------------------------------------------------------------------------- #
def test_the_legacy_save_writes_a_whole_document(tmp_path):
    target = tmp_path / "note.txt"
    assert legacy_save(target, "one\ntwo\n") == 8


def test_the_legacy_save_loses_the_original_when_it_fails(tmp_path):
    target = tmp_path / "note.txt"
    target.write_bytes(NOTE_BYTES)
    with pytest.raises(DocumentError, match="disk went away"):
        legacy_save(target, SOURCE.text + "\nmore", fail_after=8)
    assert target.stat().st_size == 8
    assert target.stat().st_size < len(NOTE_BYTES)


def test_the_legacy_save_truncates_before_it_writes(tmp_path):
    target = tmp_path / "note.txt"
    target.write_bytes(b"a much longer original document\n")
    legacy_save(target, "short")
    assert target.read_bytes() == b"short"


def test_the_legacy_loader_returns_nothing_for_a_damaged_file(tmp_path):
    target = tmp_path / "damaged.txt"
    target.write_bytes(b"caf\xe9 au lait\n")
    assert legacy_load(target) == ""


def test_the_legacy_loader_reads_a_sound_file(tmp_path):
    target = tmp_path / "note.txt"
    target.write_bytes(b"one\n")
    assert legacy_load(target) == "one\n"


def test_the_transcribed_legacy_save_is_the_four_lines():
    assert LEGACY_SAVE.startswith("def save(path, text):")
    assert 'open(path, "w")' in LEGACY_SAVE
    assert LEGACY_SAVE.rstrip().endswith("handle.write(text)")


def test_the_transcribed_legacy_load_swallows_the_decode_error():
    assert "except UnicodeDecodeError:" in LEGACY_LOAD
    assert 'return ""' in LEGACY_LOAD


# --------------------------------------------------------------------------- #
# Edit
# --------------------------------------------------------------------------- #
def test_an_edit_holds_where_what_and_the_cursor_either_side():
    edit = Edit(2, "ab", "c", 4, 3)
    assert (edit.start, edit.removed, edit.inserted) == (2, "ab", "c")


def test_an_edit_counts_the_characters_it_touches():
    assert len(Edit(0, "ab", "cd", 2, 2)) == 4


def test_an_edit_line_names_everything():
    assert Edit(2, "ab", "c", 4, 3).line() == \
        "at 2: -2 'ab' +1 'c' cursor 4->3"


def test_an_edit_before_the_start_is_refused():
    with pytest.raises(DocumentError, match="starts at 0 or later"):
        Edit(-1, "", "x", 0, 1)


def test_an_edit_of_something_that_is_not_text_is_refused():
    with pytest.raises(DocumentError, match="removes and inserts text"):
        Edit(0, 1, "x", 0, 1)


def test_an_edit_with_a_negative_cursor_is_refused():
    with pytest.raises(DocumentError, match="cursor positions are 0 or later"):
        Edit(0, "", "x", -1, 1)


# --------------------------------------------------------------------------- #
# Document: construction and reading
# --------------------------------------------------------------------------- #
def test_a_document_keeps_its_text():
    assert Document("one two").text == "one two"


def test_a_document_starts_with_the_cursor_at_the_end():
    assert Document("one two").cursor == 7


def test_a_document_starts_clean_and_unedited():
    doc = Document("one")
    assert doc.dirty() is False and doc.edited() is False


def test_a_document_counts_its_characters():
    assert len(Document("one two")) == 7


def test_a_document_splits_its_lines():
    assert Document("one\ntwo\nthree").lines() == ("one", "two", "three")


def test_a_document_counts_its_lines():
    assert Document("one\ntwo").line_count() == 2


def test_a_document_names_the_line_the_cursor_is_on():
    doc = Document("one\ntwo\nthree")
    doc.move_to(5)
    assert doc.cursor_line() == 2


def test_a_document_reports_its_newline_policy():
    assert Document("one", "\r\n").newline == "\r\n"


def test_a_document_line_says_clean_or_dirty():
    doc = Document("one", name="note.txt")
    assert doc.line() == "note.txt: 3 chars, 1 line(s), clean, revision 0, '\\n'"


def test_a_document_line_says_dirty_after_an_edit():
    doc = Document("one")
    doc.insert("!")
    assert "dirty" in doc.line()


def test_a_document_refuses_an_unknown_newline():
    with pytest.raises(DocumentError, match="a newline is"):
        Document("one", "\r")


def test_a_document_refuses_text_with_a_carriage_return():
    with pytest.raises(DocumentError, match=r"holds '\\n' only"):
        Document("one\r\n")


def test_a_document_refuses_something_that_is_not_text():
    with pytest.raises(DocumentError, match="a document is text"):
        Document(7)


def test_a_document_needs_a_name():
    with pytest.raises(DocumentError, match="needs a name"):
        Document("one", "\n", "  ")


# --------------------------------------------------------------------------- #
# Document: editing
# --------------------------------------------------------------------------- #
def test_insert_puts_text_at_the_cursor():
    doc = Document("one ")
    doc.insert("two")
    assert doc.text == "one two" and doc.cursor == 7


def test_insert_returns_true_when_it_changed_something():
    assert Document("").insert("x") is True


def test_inserting_nothing_is_not_an_edit():
    doc = Document("one")
    assert doc.insert("") is False and doc.revision == 0


def test_insert_refuses_a_carriage_return():
    with pytest.raises(DocumentError, match=r"holds '\\n' only"):
        Document("one").insert("a\r\n")


def test_insert_refuses_something_that_is_not_text():
    with pytest.raises(DocumentError, match="inserts text"):
        Document("one").insert(7)


def test_backspace_removes_the_character_before_the_cursor():
    doc = Document("one")
    doc.backspace()
    assert doc.text == "on" and doc.cursor == 2


def test_backspace_at_the_start_does_nothing():
    doc = Document("one")
    doc.move_to(0)
    assert doc.backspace() is False and doc.text == "one"


def test_delete_removes_the_character_at_the_cursor():
    doc = Document("one")
    doc.move_to(0)
    doc.delete()
    assert doc.text == "ne" and doc.cursor == 0


def test_delete_at_the_end_does_nothing():
    assert Document("one").delete() is False


def test_every_edit_moves_the_revision():
    doc = Document("one")
    doc.insert("!")
    doc.backspace()
    assert doc.revision == 2


def test_an_edit_that_changes_nothing_keeps_the_revision():
    doc = Document("one")
    doc.move_to(0)
    doc.insert("")
    doc.backspace()
    assert doc.revision == 0


def test_move_to_puts_the_cursor_somewhere():
    assert Document("one").move_to(1) == 1


def test_move_to_refuses_a_spot_past_the_text():
    with pytest.raises(DocumentError, match="between 0 and 3"):
        Document("one").move_to(4)


def test_move_to_refuses_a_negative_spot():
    with pytest.raises(DocumentError, match="between 0 and 3"):
        Document("one").move_to(-1)


def test_move_to_refuses_a_float():
    with pytest.raises(DocumentError, match="whole number"):
        Document("one").move_to(1.0)


def test_move_to_refuses_a_true():
    with pytest.raises(DocumentError, match="whole number"):
        Document("one").move_to(True)


# --------------------------------------------------------------------------- #
# Document: undo and redo
# --------------------------------------------------------------------------- #
def test_undo_restores_the_text():
    doc = Document("one")
    doc.insert("!")
    doc.undo()
    assert doc.text == "one"


def test_undo_restores_the_cursor():
    doc = Document("one")
    doc.insert("!")
    doc.undo()
    assert doc.cursor == 3


def test_undo_puts_the_edit_on_the_redo_stack():
    doc = Document("one")
    doc.insert("!")
    doc.undo()
    assert (doc.undo_depth(), doc.redo_depth()) == (0, 1)


def test_undo_with_nothing_to_undo_does_nothing():
    assert Document("one").undo() is False


def test_redo_puts_the_edit_back():
    doc = Document("one")
    doc.insert("!")
    doc.undo()
    doc.redo()
    assert doc.text == "one!" and doc.cursor == 4


def test_redo_with_nothing_to_redo_does_nothing():
    assert Document("one").redo() is False


def test_a_new_edit_clears_the_redo_stack():
    doc = Document("one")
    doc.insert("!")
    doc.undo()
    doc.insert("?")
    assert doc.redo_depth() == 0


def test_undo_and_redo_restore_a_backspace():
    doc = Document("one")
    doc.backspace()
    doc.undo()
    assert doc.text == "one"


def test_undo_and_redo_restore_a_delete():
    doc = Document("one")
    doc.move_to(0)
    doc.delete()
    doc.undo()
    assert doc.text == "one" and doc.cursor == 0


def test_ten_inserts_undo_one_at_a_time():
    doc = Document("")
    for character in "0123456789":
        doc.insert(character)
    for _ in range(10):
        doc.undo()
    assert doc.text == "" and doc.cursor == 0


def test_undo_counts_as_a_revision():
    doc = Document("one")
    doc.insert("!")
    before = doc.revision
    doc.undo()
    assert doc.revision == before + 1


# --------------------------------------------------------------------------- #
# Document: saving and loading
# --------------------------------------------------------------------------- #
def test_save_writes_under_the_document_newline(tmp_path):
    doc = Document("one\ntwo\n", "\r\n", "note.txt")
    written = doc.save(tmp_path / "note.txt")
    assert written == 10
    assert (tmp_path / "note.txt").read_bytes() == b"one\r\ntwo\r\n"


def test_save_clears_the_dirty_flag(tmp_path):
    doc = Document("one")
    doc.insert("!")
    assert doc.dirty() is True
    doc.save(tmp_path / "note.txt")
    assert doc.dirty() is False


def test_the_dirty_flag_returns_on_the_next_edit(tmp_path):
    doc = Document("one")
    doc.save(tmp_path / "note.txt")
    doc.insert("!")
    assert doc.dirty() is True


def test_save_adopts_the_file_name_it_wrote(tmp_path):
    doc = Document("one")
    doc.save(tmp_path / "newname.txt")
    assert doc.name == "newname.txt"


def test_load_reads_the_bundled_note():
    assert SOURCE.text.startswith("The first line.")


def test_load_keeps_the_crlf_policy_of_the_file():
    assert SOURCE.newline == "\r\n"


def test_load_reduces_the_text_to_lf():
    assert "\r" not in SOURCE.text


def test_load_adopts_the_file_name():
    assert SOURCE.name == "notes.txt"


def test_load_refuses_a_missing_file(tmp_path):
    with pytest.raises(DocumentError, match="file not found"):
        Document.load(tmp_path / "nope.txt")


def test_load_refuses_a_damaged_file(tmp_path):
    target = tmp_path / "damaged.txt"
    target.write_bytes(b"caf\xe9 au lait\n")
    with pytest.raises(DocumentError, match="not valid UTF-8"):
        Document.load(target)


def test_load_refuses_a_mixed_file(tmp_path):
    target = tmp_path / "mixed.txt"
    target.write_bytes(b"one\r\ntwo\n")
    with pytest.raises(DocumentError, match="one convention"):
        Document.load(target)


def test_a_round_trip_writes_the_same_bytes(tmp_path):
    written = SOURCE.save(tmp_path / "again.txt")
    assert written == len(NOTE_BYTES)
    assert (tmp_path / "again.txt").read_bytes() == NOTE_BYTES


def test_a_round_trip_keeps_the_line_count(tmp_path):
    again = Document.load(NOTES_FILE)
    again.save(tmp_path / "again.txt")
    assert again.line_count() == SOURCE.line_count()


# --------------------------------------------------------------------------- #
# measure
# --------------------------------------------------------------------------- #
def test_measure_reports_the_original_size():
    measured, _ = measure(SOURCE)
    assert measured["original_bytes"] == len(NOTE_BYTES)


def test_measure_finds_the_legacy_fragment_smaller_than_the_original():
    measured, _ = measure(SOURCE)
    assert measured["legacy_truncated"] == 8 < measured["original_bytes"]


def test_measure_finds_the_atomic_file_intact():
    measured, _ = measure(SOURCE)
    assert measured["atomic_kept"] == measured["original_bytes"]


def test_measure_costs_one_byte_per_break_for_crlf():
    measured, _ = measure(SOURCE)
    assert measured["explicit_crlf"] - measured["explicit_lf"] == \
        measured["line_breaks"]


def test_measure_pins_the_lf_size():
    measured, _ = measure(SOURCE)
    assert measured["explicit_lf"] == measured["original_bytes"] - \
        measured["line_breaks"]


def test_measure_names_the_mixed_file_line():
    measured, _ = measure(SOURCE)
    assert measured["mixed_line"] == 2


def test_measure_names_the_damaged_byte():
    measured, _ = measure(SOURCE)
    assert measured["invalid_offset"] == 3


def test_measure_records_the_legacy_empty_answer():
    measured, _ = measure(SOURCE)
    assert measured["legacy_invalid"] == ""


def test_measure_returns_undo_to_the_original_cursor():
    measured, _ = measure(SOURCE)
    assert measured["undo_text"] == measured["before_text"]
    assert measured["undo_cursor"] == measured["before_cursor"]


def test_measure_shows_the_typed_text_is_longer():
    measured, _ = measure(SOURCE)
    assert measured["typed_cursor"] == measured["before_cursor"] + len(DEMO_EDIT)


def test_measure_leaves_no_redo_step_after_a_new_edit():
    measured, _ = measure(SOURCE)
    assert measured["redo_after_new_edit"] == 0


def test_measure_clears_the_dirty_flag_and_sets_it_again():
    measured, _ = measure(SOURCE)
    assert measured["dirty_after_save"] is False
    assert measured["dirty_after_edit"] is True


def test_measure_keeps_the_revision_steady_through_idle_edits():
    measured, _ = measure(SOURCE)
    assert measured["revision_before_idle"] == measured["revision_after_idle"]


def test_measure_restores_the_bundled_note_byte_for_byte():
    measured, _ = measure(SOURCE)
    assert measured["restored_bytes"] == measured["original_bytes"]


def test_measure_writes_nothing_into_the_repository():
    before = sorted(path.name for path in (PROJECT / "data").iterdir())
    measure(SOURCE)
    after = sorted(path.name for path in (PROJECT / "data").iterdir())
    assert before == after


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "a failed write loses the original",
    "the atomic write kept the original intact",
    "the CRLF policy costs one byte per newline",
    "an explicit policy writes the text byte for byte",
    "a mixed file is refused and named",
    "a damaged file is refused, not emptied",
    "undo restores the text and the cursor",
    "redo puts the edit back",
    "a new edit clears the redo stack",
    "the dirty flag clears on save and returns on the next edit",
    "an edit that changes nothing does not move the revision",
]

MEASURED, SCRATCH = measure(SOURCE)


def real_checks():
    return audit(MEASURED, SCRATCH)


def test_the_audit_holds_eleven_named_checks():
    assert [name for name, _ in real_checks()] == CHECK_NAMES


def test_the_audit_passes_on_the_bundled_note():
    assert problems(real_checks()) == []


def test_the_audit_is_repeatable():
    assert real_checks() == real_checks()


def corrupted(**changes) -> dict:
    payload = dict(MEASURED)
    payload.update(changes)
    return payload


def test_the_audit_catches_a_legacy_save_that_kept_the_whole_file():
    checks = audit(corrupted(legacy_truncated=len(NOTE_BYTES)), SCRATCH)
    assert CHECK_NAMES[0] in problems(checks)


def test_the_audit_catches_an_atomic_save_that_emptied_the_file():
    checks = audit(corrupted(atomic_kept=0), SCRATCH)
    assert CHECK_NAMES[1] in problems(checks)


def test_the_audit_catches_a_crlf_policy_that_costs_nothing():
    checks = audit(corrupted(explicit_crlf=MEASURED["explicit_lf"]), SCRATCH)
    assert CHECK_NAMES[2] in problems(checks)


def test_the_audit_catches_text_mode_writing_platform_newlines():
    checks = audit(corrupted(explicit_lf=MEASURED["explicit_crlf"]), SCRATCH)
    assert CHECK_NAMES[3] in problems(checks)


def test_the_audit_catches_a_mixed_file_read_as_one_convention():
    checks = audit(corrupted(mixed_line=0, mixed_message="no refusal"), SCRATCH)
    assert CHECK_NAMES[4] in problems(checks)


def test_the_audit_catches_a_damaged_file_emptied_instead_of_refused():
    checks = audit(corrupted(legacy_invalid="cafe au lait\n"), SCRATCH)
    assert CHECK_NAMES[5] in problems(checks)


def test_the_audit_catches_undo_that_left_the_cursor_behind():
    checks = audit(corrupted(undo_cursor=MEASURED["typed_cursor"]), SCRATCH)
    assert CHECK_NAMES[6] in problems(checks)


def test_the_audit_catches_redo_that_did_not_put_the_edit_back():
    checks = audit(corrupted(redo_text=MEASURED["before_text"]), SCRATCH)
    assert CHECK_NAMES[7] in problems(checks)


def test_the_audit_catches_a_redo_stack_that_survived_a_new_edit():
    checks = audit(corrupted(redo_after_new_edit=1), SCRATCH)
    assert CHECK_NAMES[8] in problems(checks)


def test_the_audit_catches_a_dirty_flag_that_never_cleared():
    checks = audit(corrupted(dirty_after_save=True), SCRATCH)
    assert CHECK_NAMES[9] in problems(checks)


def test_the_audit_catches_a_revision_that_moved_for_nothing():
    checks = audit(corrupted(revision_after_idle=99), SCRATCH)
    assert CHECK_NAMES[10] in problems(checks)


def test_a_missing_measurement_is_a_failure_not_a_traceback():
    payload = corrupted()
    del payload["dirty_after_save"]
    checks = audit(payload, SCRATCH)
    assert CHECK_NAMES[9] in problems(checks)
    assert len(checks) == len(CHECK_NAMES)


def test_every_check_has_a_negative_control():
    caught = set()
    caught |= set(problems(audit(corrupted(legacy_truncated=52), SCRATCH)))
    caught |= set(problems(audit(corrupted(atomic_kept=0), SCRATCH)))
    caught |= set(problems(audit(corrupted(explicit_crlf=49), SCRATCH)))
    caught |= set(problems(audit(corrupted(explicit_lf=52), SCRATCH)))
    caught |= set(problems(audit(corrupted(mixed_line=0,
                                            mixed_message="no refusal"),
                                 SCRATCH)))
    caught |= set(problems(audit(corrupted(legacy_invalid="x"), SCRATCH)))
    caught |= set(problems(audit(corrupted(undo_cursor=21), SCRATCH)))
    caught |= set(problems(audit(corrupted(redo_text="one two"), SCRATCH)))
    caught |= set(problems(audit(corrupted(redo_after_new_edit=1), SCRATCH)))
    caught |= set(problems(audit(corrupted(dirty_after_save=True), SCRATCH)))
    caught |= set(problems(audit(corrupted(revision_after_idle=1), SCRATCH)))
    assert caught == set(CHECK_NAMES)


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


def test_demo_shows_the_legacy_save(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "DOCUMENT LAB" in out and 'open(path, "w")' in out


def test_demo_shows_the_fragment_left_by_a_failed_save(capsys):
    run_demo()
    assert "8 byte(s) -- the original is gone" in capsys.readouterr().out


def test_demo_shows_all_eleven_checks(capsys):
    run_demo()
    assert "11/11 checks pass" in capsys.readouterr().out


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


def test_cli_prints_the_bundled_note(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "notes.txt" in out and "The first line." in out


def test_cli_edits_and_saves(tmp_path, capsys):
    target = tmp_path / "edited.txt"
    assert cli.main(["--edit", "!", "--save", str(target), "--quiet"]) == 0
    capsys.readouterr()
    assert target.read_bytes().endswith(b"!")


def test_cli_saves_with_crlf(tmp_path, capsys):
    target = tmp_path / "crlf.txt"
    assert cli.main(["--newline", "crlf", "--save", str(target), "--quiet"]) == 0
    capsys.readouterr()
    assert b"\r\n" in target.read_bytes()


def test_cli_saves_with_lf(tmp_path, capsys):
    target = tmp_path / "lf.txt"
    assert cli.main(["--newline", "lf", "--save", str(target), "--quiet"]) == 0
    capsys.readouterr()
    assert b"\r\n" not in target.read_bytes()


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 11 and "FAIL" not in out


def test_cli_writes_the_document_as_json(tmp_path, capsys):
    target = tmp_path / "document.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["document"]["name"] == "notes.txt"
    assert payload["document"]["newline"] == "\r\n"
    assert payload["bytes"]["crlf"] - payload["bytes"]["lf"] == 3
    assert payload["document"]["line_count"] == 4


def test_cli_json_carries_the_measurements_and_checks(tmp_path, capsys):
    target = tmp_path / "document.json"
    assert cli.main(["--audit", "--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["measurements"]["atomic_kept"] == len(NOTE_BYTES)
    assert len(payload["checks"]) == 11
    assert all(check["ok"] for check in payload["checks"])


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_refuses_a_missing_file(tmp_path, capsys):
    assert cli.main(["--file", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_refuses_a_damaged_file(tmp_path, capsys):
    target = tmp_path / "damaged.txt"
    target.write_bytes(b"caf\xe9 au lait\n")
    assert cli.main(["--file", str(target)]) == 2
    assert "not valid UTF-8" in capsys.readouterr().err


def test_cli_refuses_an_unknown_newline_choice(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["--newline", "cr"])
    assert raised.value.code == 2


def test_the_module_exports_the_edit_the_demo_types():
    assert DEMO_EDIT == "Hello, editor."
    assert module.DEMO_EDIT == DEMO_EDIT
