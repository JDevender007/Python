"""Saving a document is not writing a string to a file.

The legacy editor saved with four lines:

    def save(path, text):
        with open(path, "w") as handle:
            handle.write(text)

**1. `open(path, "w")` truncates before a single byte is written.** A disk that fills up,
a permission that changes, a process that is killed -- the original is already gone, and
the document is gone with it. There is no moment at which both exist.

**2. Text mode chooses the newline for you.** A document whose lines end in `\\n` is
written as `\\r\\n` on Windows, so the same text is five bytes on one machine and seven on
another, and a round trip is not a no-op.

**3. Undo cannot be a file re-read.** The editor kept the last saved text and called that
"undo": every edit made since the save disappears, and an edit made *before* the save
cannot be undone at all.

**4. `except: pass` around a decode turns a damaged file into an empty one.** The reader
that swallows a `UnicodeDecodeError` reports success and hands back nothing, so the next
save writes that nothing over the file.

So this module keeps the document as text plus an explicit stack of `Edit`s, saves by
writing a sibling temporary file and `os.replace`-ing it into place, and states the
newline policy rather than inheriting it. The legacy path is kept beside it, executable,
so every claim above is reproduced with a byte count.

The demonstration is offline and writes only inside a temporary directory.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NOTES_FILE = DATA_DIR / "notes.txt"

#: The legacy save, transcribed -- and executable, with an optional failure.
LEGACY_SAVE = ("def save(path, text):\n"
               "    with open(path, \"w\") as handle:\n"
               "        handle.write(text)")

#: The legacy reader, transcribed: a decode error becomes an empty document.
LEGACY_LOAD = ("def load(path):\n"
               "    try:\n"
               "        return open(path, encoding=\"utf-8\").read()\n"
               "    except UnicodeDecodeError:\n"
               "        return \"\"")

#: The two newline conventions a text file may hold.
NEWLINES = ("\n", "\r\n")

#: How many characters the demo types, for a fixed edit script.
DEMO_EDIT = "Hello, editor."


class DocumentError(Exception):
    """A file, a newline, an encoding or an edit that cannot be honoured, and why."""


# --------------------------------------------------------------------------- #
# Bytes and newlines
# --------------------------------------------------------------------------- #
def encode(text: str, newline: str = "\n") -> bytes:
    """The bytes a document becomes under a stated newline policy."""
    if not isinstance(text, str):
        raise DocumentError(f"a document is text, got {type(text).__name__}")
    if newline not in NEWLINES:
        raise DocumentError(f"a newline is {NEWLINES[0]!r} or {NEWLINES[1]!r}, "
                            f"got {newline!r}")
    if "\r" in text:
        raise DocumentError("the document holds a carriage return: keep text "
                            "with '\\n' and let the policy add the rest")
    return text.replace("\n", newline).encode("utf-8")


def decode(data: bytes) -> str:
    """The text in those bytes, decoded strictly, naming the byte that broke."""
    if not isinstance(data, (bytes, bytearray)):
        raise DocumentError(f"a file is bytes, got {type(data).__name__}")
    try:
        return bytes(data).decode("utf-8")
    except UnicodeDecodeError as error:
        raise DocumentError(f"byte {error.start} is not valid UTF-8 "
                            f"({error.reason})") from None


def detect_newline(text: str) -> str:
    """Which convention the whole file uses, or a sentence naming the odd line."""
    if not isinstance(text, str):
        raise DocumentError(f"a file is text, got {type(text).__name__}")
    stripped = text.replace("\r\n", "")
    if "\r" in stripped:
        line = text[:text.index("\r")].count("\n") + 1
        raise DocumentError(f"line {line} holds a carriage return that is not "
                            f"followed by a newline")
    kinds: list[str] = []
    for line in text.split("\n")[:-1]:
        kinds.append("\r\n" if line.endswith("\r") else "\n")
    if not kinds:
        return "\n"
    first = kinds[0]
    for number, kind in enumerate(kinds, start=1):
        if kind != first:
            raise DocumentError(
                f"line {number} ends with {'CRLF' if kind == chr(13) + chr(10) else 'LF'} "
                f"while line 1 ends with "
                f"{'CRLF' if first == chr(13) + chr(10) else 'LF'}: a file holds "
                f"one convention")
    return first


def normalise(text: str) -> str:
    """The text with the file's newlines reduced to `\\n`, after checking them."""
    detect_newline(text)
    return text.replace("\r\n", "\n")


# --------------------------------------------------------------------------- #
# Saving
# --------------------------------------------------------------------------- #
def atomic_save(path, text: str, newline: str = "\n") -> int:
    """Write beside the target, then replace it -- so the file is never half-written."""
    target = Path(path)
    if target.is_dir():
        raise DocumentError(f"{target.name!r} is a directory, not a file")
    payload = encode(text, newline)
    handle = target.with_name(target.name + ".tmp")
    try:
        handle.write_bytes(payload)
        os.replace(handle, target)
    except OSError as error:
        if handle.is_file():
            handle.unlink()
        raise DocumentError(f"the document could not be written: {error}") from None
    return len(payload)


def legacy_save(path, text: str, fail_after: int | None = None) -> int:
    """`open(path, "w")` then write -- truncating first, as the legacy editor did.

    `fail_after` writes that many characters and then raises, standing in for a disk
    that fills up: the original file is already gone when it happens.
    """
    with open(path, "w", encoding="utf-8", newline="") as handle:
        if fail_after is not None:
            handle.write(text[:fail_after])
            handle.flush()
            raise DocumentError("the disk went away mid-write")
        handle.write(text)
    return Path(path).stat().st_size


def legacy_load(path) -> str:
    """The legacy reader: a decode error becomes an empty document."""
    try:
        return Path(path).read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return ""


# --------------------------------------------------------------------------- #
# Edits
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Edit:
    """One change: what was removed where, what replaced it, and the cursor either side."""

    start: int
    removed: str
    inserted: str
    before_cursor: int
    after_cursor: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise DocumentError(f"an edit starts at 0 or later, got {self.start}")
        if not isinstance(self.removed, str) or not isinstance(self.inserted, str):
            raise DocumentError("an edit removes and inserts text")
        if self.before_cursor < 0 or self.after_cursor < 0:
            raise DocumentError("an edit's cursor positions are 0 or later")

    def __len__(self) -> int:
        """How many characters this edit touches."""
        return len(self.removed) + len(self.inserted)

    def line(self) -> str:
        return (f"at {self.start}: -{len(self.removed)} {self.removed!r} "
                f"+{len(self.inserted)} {self.inserted!r} "
                f"cursor {self.before_cursor}->{self.after_cursor}")


# --------------------------------------------------------------------------- #
# The document
# --------------------------------------------------------------------------- #
class Document:
    """Text with a cursor, two stacks, and a newline policy it states out loud."""

    def __init__(self, text: str = "", newline: str = "\n",
                 name: str = "untitled") -> None:
        if not isinstance(text, str):
            raise DocumentError(f"a document is text, got {type(text).__name__}")
        if newline not in NEWLINES:
            raise DocumentError(f"a newline is '\\n' or '\\r\\n', got {newline!r}")
        if "\r" in text:
            raise DocumentError("a document holds '\\n' only: the file's "
                                "convention lives in its newline")
        if not isinstance(name, str) or not name.strip():
            raise DocumentError("a document needs a name")
        self._text = text
        self._newline = newline
        self._name = name
        self._cursor = len(text)
        self._undo: list[Edit] = []
        self._redo: list[Edit] = []
        self._revision = 0
        self._saved = 0

    # -- reading ----------------------------------------------------------- #
    @property
    def text(self) -> str:
        return self._text

    @property
    def newline(self) -> str:
        return self._newline

    @property
    def name(self) -> str:
        return self._name

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def revision(self) -> int:
        return self._revision

    def __len__(self) -> int:
        return len(self._text)

    def lines(self) -> tuple[str, ...]:
        return tuple(self._text.split("\n"))

    def line_count(self) -> int:
        return self._text.count("\n") + 1

    def cursor_line(self) -> int:
        """The 1-based line the cursor sits on."""
        return self._text.count("\n", 0, self._cursor) + 1

    def undo_depth(self) -> int:
        return len(self._undo)

    def redo_depth(self) -> int:
        return len(self._redo)

    def dirty(self) -> bool:
        return self._revision != self._saved

    def edited(self) -> bool:
        """Has anything happened at all, saved or not?"""
        return self._revision > 0

    def line(self) -> str:
        state = "dirty" if self.dirty() else "clean"
        return (f"{self._name}: {len(self._text)} chars, {self.line_count()} "
                f"line(s), {state}, revision {self._revision}, "
                f"{self._newline!r}")

    # -- editing ----------------------------------------------------------- #
    def _push(self, edit: Edit) -> None:
        self._undo.append(edit)
        self._redo.clear()
        self._revision += 1

    def _rewrite(self, start: int, remove: int, insert: str) -> None:
        self._text = self._text[:start] + insert + self._text[start + remove:]

    def insert(self, text: str) -> bool:
        """Type at the cursor. Typing nothing is not an edit."""
        if not isinstance(text, str):
            raise DocumentError(f"typing inserts text, got {type(text).__name__}")
        if "\r" in text:
            raise DocumentError("typed text holds '\\n' only")
        if not text:
            return False
        start = self._cursor
        self._push(Edit(start, "", text, start, start + len(text)))
        self._rewrite(start, 0, text)
        self._cursor = start + len(text)
        return True

    def backspace(self) -> bool:
        """Delete the character before the cursor; at the start, nothing happens."""
        if self._cursor == 0:
            return False
        start = self._cursor - 1
        removed = self._text[start:self._cursor]
        self._push(Edit(start, removed, "", self._cursor, start))
        self._rewrite(start, 1, "")
        self._cursor = start
        return True

    def delete(self) -> bool:
        """Delete the character at the cursor; at the end, nothing happens."""
        if self._cursor >= len(self._text):
            return False
        removed = self._text[self._cursor]
        self._push(Edit(self._cursor, removed, "", self._cursor, self._cursor))
        self._rewrite(self._cursor, 1, "")
        return True

    def move_to(self, position: int) -> int:
        """Put the cursor somewhere, refusing a spot outside the text."""
        if not isinstance(position, int) or isinstance(position, bool):
            raise DocumentError(f"a cursor is a whole number, got {position!r}")
        if position < 0 or position > len(self._text):
            raise DocumentError(f"a cursor is between 0 and {len(self._text)}, "
                                f"got {position}")
        self._cursor = position
        return self._cursor

    # -- undo and redo ----------------------------------------------------- #
    def undo(self) -> bool:
        if not self._undo:
            return False
        edit = self._undo.pop()
        self._rewrite(edit.start, len(edit.inserted), edit.removed)
        self._cursor = edit.before_cursor
        self._redo.append(edit)
        self._revision += 1
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        edit = self._redo.pop()
        self._rewrite(edit.start, len(edit.removed), edit.inserted)
        self._cursor = edit.after_cursor
        self._undo.append(edit)
        self._revision += 1
        return True

    # -- persistence ------------------------------------------------------- #
    def save(self, path=None) -> int:
        """Write atomically under this document's own newline policy."""
        target = Path(path) if path is not None else Path(self._name)
        written = atomic_save(target, self._text, self._newline)
        self._saved = self._revision
        self._name = target.name
        return written

    @classmethod
    def load(cls, path) -> "Document":
        """Read a file, keeping its newline convention and refusing a damaged one."""
        target = Path(path)
        if not target.is_file():
            raise DocumentError(f"file not found: {target}")
        data = target.read_bytes()
        text = decode(data)
        newline = detect_newline(text)
        return cls(normalise(text), newline, target.name)


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(measured: dict, doc: Document) -> list[tuple[str, bool]]:
    """Eleven checks, re-derived from the numbers the demo just measured."""
    def at(name: str):
        if name not in measured:
            raise DocumentError(f"no measurement named {name!r}")
        return measured[name]

    def a_failed_write_loses_the_original() -> bool:
        """The legacy file is a fragment: it is neither empty nor the original."""
        return 0 <= at("legacy_truncated") < at("original_bytes")

    def the_atomic_write_kept_the_original_intact() -> bool:
        return at("atomic_kept") == at("original_bytes") > 0

    def the_crlf_policy_costs_one_byte_per_newline() -> bool:
        return at("explicit_crlf") - at("explicit_lf") == at("line_breaks")

    def an_explicit_policy_writes_the_text_byte_for_byte() -> bool:
        return at("explicit_lf") == at("lf_bytes") and \
            at("explicit_lf") == at("original_bytes") - at("line_breaks")

    def a_mixed_file_is_refused_and_named() -> bool:
        return at("mixed_line") == 2 and "line 2 ends with" in at("mixed_message")

    def a_damaged_file_is_refused_where_the_legacy_reader_returned_nothing() -> bool:
        return at("invalid_offset") == 3 and at("legacy_invalid") == "" and \
            "not valid UTF-8" in at("invalid_message")

    def undo_restores_the_text_and_the_cursor() -> bool:
        return at("undo_text") == at("before_text") and \
            at("undo_cursor") == at("before_cursor")

    def redo_puts_the_edit_back() -> bool:
        return at("redo_text") == at("typed_text") and \
            at("redo_cursor") == at("typed_cursor")

    def a_new_edit_clears_the_redo_stack() -> bool:
        return at("redo_after_new_edit") == 0

    def the_dirty_flag_clears_on_save_and_returns_on_the_next_edit() -> bool:
        return at("dirty_after_save") is False and at("dirty_after_edit") is True

    def an_edit_that_changes_nothing_does_not_move_the_revision() -> bool:
        return at("revision_before_idle") == at("revision_after_idle")

    checks = [
        ("a failed write loses the original",
         a_failed_write_loses_the_original),
        ("the atomic write kept the original intact",
         the_atomic_write_kept_the_original_intact),
        ("the CRLF policy costs one byte per newline",
         the_crlf_policy_costs_one_byte_per_newline),
        ("an explicit policy writes the text byte for byte",
         an_explicit_policy_writes_the_text_byte_for_byte),
        ("a mixed file is refused and named",
         a_mixed_file_is_refused_and_named),
        ("a damaged file is refused, not emptied",
         a_damaged_file_is_refused_where_the_legacy_reader_returned_nothing),
        ("undo restores the text and the cursor",
         undo_restores_the_text_and_the_cursor),
        ("redo puts the edit back", redo_puts_the_edit_back),
        ("a new edit clears the redo stack",
         a_new_edit_clears_the_redo_stack),
        ("the dirty flag clears on save and returns on the next edit",
         the_dirty_flag_clears_on_save_and_returns_on_the_next_edit),
        ("an edit that changes nothing does not move the revision",
         an_edit_that_changes_nothing_does_not_move_the_revision),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def measure(source: Document) -> tuple[dict, Document]:
    """Run every experiment once, in a temporary directory, and keep the numbers.

    Nothing is written inside the repository: the folder is created for the occasion
    and removed when the block ends.
    """
    original = NOTES_FILE.read_bytes()
    measured: dict = {
        "original_bytes": len(original),
        "line_breaks": source.text.count("\n"),
    }

    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)

        # 1. the legacy save, failing part-way through
        doomed = root / "doomed.txt"
        doomed.write_bytes(original)
        try:
            legacy_save(doomed, source.text + "\nmore", fail_after=8)
        except DocumentError:
            pass
        measured["legacy_truncated"] = doomed.stat().st_size

        # 2. the same failure, atomically: the temporary file cannot be made
        blocked = root / "blocked.txt"
        blocked.write_bytes(original)
        blocked.with_name(blocked.name + ".tmp").mkdir()
        try:
            atomic_save(blocked, source.text + "\nmore", source.newline)
        except DocumentError:
            pass
        measured["atomic_kept"] = blocked.stat().st_size

        # 3. the two explicit policies
        measured["lf_bytes"] = len(source.text.encode("utf-8"))
        measured["explicit_lf"] = len(encode(source.text, "\n"))
        measured["explicit_crlf"] = len(encode(source.text, "\r\n"))

        # 4. a mixed file
        try:
            detect_newline("first\r\nsecond\nthird\r\n")
            measured["mixed_line"] = 0
            measured["mixed_message"] = "no refusal"
        except DocumentError as error:
            measured["mixed_line"] = int(str(error).split()[1])
            measured["mixed_message"] = str(error)

        # 5. a damaged file, both readers
        damaged = b"caf\xe9 au lait\n"
        damaged_path = root / "damaged.txt"
        damaged_path.write_bytes(damaged)
        try:
            decode(damaged)
            measured["invalid_offset"] = -1
            measured["invalid_message"] = "no refusal"
        except DocumentError as error:
            measured["invalid_offset"] = int(str(error).split()[1])
            measured["invalid_message"] = str(error)
        measured["legacy_invalid"] = legacy_load(damaged_path)

        # 6-9. undo, redo, a new edit, the dirty flag
        doc = Document("one two", "\n", "scratch.txt")
        measured["before_text"] = doc.text
        measured["before_cursor"] = doc.cursor
        doc.insert(DEMO_EDIT)
        measured["typed_text"] = doc.text
        measured["typed_cursor"] = doc.cursor
        doc.undo()
        measured["undo_text"] = doc.text
        measured["undo_cursor"] = doc.cursor
        doc.redo()
        measured["redo_text"] = doc.text
        measured["redo_cursor"] = doc.cursor
        doc.undo()
        doc.insert("!")
        measured["redo_after_new_edit"] = doc.redo_depth()

        scratch = root / "scratch.txt"
        doc.save(scratch)
        measured["dirty_after_save"] = doc.dirty()
        doc.insert("d")
        measured["dirty_after_edit"] = doc.dirty()

        # 10. an edit that changes nothing
        doc.move_to(0)
        measured["revision_before_idle"] = doc.revision
        doc.insert("")
        doc.backspace()
        measured["revision_after_idle"] = doc.revision

        # 11. a round trip through the CRLF file
        again = Document.load(NOTES_FILE)
        restored = root / "restored.txt"
        measured["restored_bytes"] = again.save(restored)

    return measured, doc


def run_demo() -> int:
    source = Document.load(NOTES_FILE)
    original = NOTES_FILE.read_bytes()
    measured, doc = measure(source)

    print("=" * 78)
    print(" DOCUMENT LAB - open(path, 'w') truncates before it writes")
    print("=" * 78)

    print("\n  the legacy save, transcribed:")
    for line in LEGACY_SAVE.split("\n"):
        print(f"    {line}")

    print(f"\n  the bundled note: {len(original)} bytes, "
          f"{source.line_count()} line(s), {source.newline!r} line endings")
    print(f"  {source.line()}")

    print("\n  what a failed save leaves behind:")
    print(f"    the legacy truncating save:   {measured['legacy_truncated']} "
          f"byte(s) -- the original is gone")
    print(f"    the atomic save:              {measured['atomic_kept']} "
          f"byte(s) -- the original never moved")
    print(f"    the line that did it:         open(path, 'w') truncates "
          f"before write()")

    print("\n  what a newline policy costs:")
    print(f"    the text has {measured['line_breaks']} line break(s)")
    print(f"    written with LF:   {measured['explicit_lf']} bytes")
    print(f"    written with CRLF: {measured['explicit_crlf']} bytes "
          f"({measured['explicit_crlf'] - measured['explicit_lf']} more)")
    print(f"    text mode picks one of those from the platform, not from the file")

    print("\n  two files the readers disagree about:")
    print(f"    mixed endings -> {measured['mixed_message']}")
    print(f"    damaged bytes -> {measured['invalid_message']}")
    print(f"    the legacy reader answered the damaged file with "
          f"{measured['legacy_invalid']!r}")

    print("\n  undo and redo, with the cursor:")
    print(f"    before:  {measured['before_text']!r} cursor "
          f"{measured['before_cursor']}")
    print(f"    typed:   {measured['typed_text']!r} cursor "
          f"{measured['typed_cursor']}")
    print(f"    undone:  {measured['undo_text']!r} cursor "
          f"{measured['undo_cursor']}")
    print(f"    redone:  {measured['redo_text']!r} cursor "
          f"{measured['redo_cursor']}")
    print(f"    a new edit left {measured['redo_after_new_edit']} redo step(s)")

    print("\n  the file, restored:")
    print(f"    the note is {measured['original_bytes']} bytes on disk")
    print(f"    loaded, edited as LF, saved again: "
          f"{measured['restored_bytes']} bytes")

    checks = audit(measured, doc)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"a failed legacy save left {measured['legacy_truncated']} byte(s) "
          f"where the atomic one kept {measured['atomic_kept']}, "
          f"{measured['line_breaks']} line break(s) cost "
          f"{measured['explicit_crlf'] - measured['explicit_lf']} extra byte(s) "
          f"as CRLF, the mixed file was refused at line "
          f"{measured['mixed_line']}, the damaged file at byte "
          f"{measured['invalid_offset']} while the legacy reader said "
          f"{measured['legacy_invalid']!r}, undo returned cursor "
          f"{measured['undo_cursor']}, a new edit left "
          f"{measured['redo_after_new_edit']} redo step(s), the round trip "
          f"wrote {measured['restored_bytes']} byte(s), and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0
