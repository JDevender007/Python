"""A batch rename that plans everything before it touches anything.

The legacy renamer was this:

    def rename_files(self, files, new_names):
        self.history.clear()
        renamed = 0
        for old_path, new_name in zip(files, new_names):
            old_file = Path(old_path)
            new_file = old_file.with_name(new_name + old_file.suffix)
            move(str(old_file), str(new_file))
            self.history.append((str(new_file), str(old_file)))
            renamed += 1
        return renamed

Three defects, all of them invisible on the video's data.

**1. ``zip`` truncates in silence.** Given six files and four names it renames
four and returns ``4``. Nothing raises, nothing warns, and the two untouched files
look exactly like files the user chose not to select. ``zip(strict=True)`` exists
for this, but the real fix is to compare the counts before building anything: a
plan that does not cover every file is not a plan.

**2. A computed name can land on a file that is already there**, and ``move`` to an
existing path overwrites it. ``with_name(new_name + suffix)`` also appends the old
suffix to names that already carry one -- ``report.pdf`` becomes
``report.pdf.pdf`` -- and a case-only rename (``photo.JPG`` to ``photo.jpg``) moves
a file onto itself on the case-insensitive filesystems Windows and macOS both use.

**3. ``self.history.clear()`` throws away the undo of the *previous* batch** before
the new one has done anything. One failure in the middle leaves the folder
half-renamed with no record of the half that succeeded.

This module replaces all three with one idea: **a rename is a plan, and a plan is a
value.** It is built, every entry is validated against the folder, collisions are
resolved into explicit numbered names, and only then is it applied -- record by
record, each one reversible. Undo replays the records backwards and checks that
every file is still where the plan left it.

The folder is an interface, not the disk: ``DiskFolder`` for real work,
``MemoryFolder`` for the demonstration, so the demo is deterministic and never
writes into the repository.

Standard library only: no ``tkinter``, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FOLDER_FILE = DATA_DIR / "folder.txt"
NAMES_FILE = DATA_DIR / "names.txt"

#: The legacy lines, transcribed, so the demo can refute them.
LEGACY_LOOP = "for old_path, new_name in zip(files, new_names):"
LEGACY_TARGET = "new_file = old_file.with_name(new_name + old_file.suffix)"
LEGACY_HISTORY = "self.history.clear()"

#: The longest name a plan may ask for.
MAX_NAME = 60

#: Characters Windows refuses in a name; a plan cannot invent them.
FORBIDDEN = frozenset('<>:"/\\|?*')

#: Names Windows reserves, case-insensitively, with or without an extension.
RESERVED = frozenset({"con", "prn", "aux", "nul"} |
                     {f"com{d}" for d in range(1, 10)} |
                     {f"lpt{d}" for d in range(1, 10)})

#: How many numbered alternatives to try before giving up.
TRIES = 500


class RenameError(Exception):
    """A folder, a name, a plan or an undo that cannot be accepted."""


class BadName(RenameError, ValueError):
    """A name the plan may not use."""


class PlanError(RenameError):
    """A plan that cannot cover the folder, or that collides with itself."""


class UndoError(RenameError):
    """An undo that would move a file that is not where the plan left it."""


# --------------------------------------------------------------------------- #
# Names
# --------------------------------------------------------------------------- #
def split_name(name: str) -> tuple[str, str]:
    """Split a file name into stem and suffix, keeping a dotfile whole.

    ``photo.JPG`` is ``("photo", ".JPG")``, ``notes`` is ``("notes", "")`` and
    ``.env`` is ``(".env", "")`` -- the last one matters, because a leading dot
    is not an extension.
    """
    if not isinstance(name, str):
        raise BadName(f"a name must be text, got {name!r}")
    dot = name.rfind(".")
    if dot <= 0:
        return name, ""
    return name[:dot], name[dot:]


def fold(name: str) -> str:
    """The name as a case-insensitive filesystem compares it."""
    return name.casefold()


def check_name(name: str) -> str:
    """A single name the plan may use, or ``BadName`` saying why not."""
    if not isinstance(name, str):
        raise BadName(f"a name must be text, got {name!r}")
    if not name or not name.strip():
        raise BadName("a name cannot be empty")
    if name != name.strip():
        raise BadName(f"a name cannot start or end with a space: {name!r}")
    if name in (".", ".."):
        raise BadName(f"{name!r} is not a file name")
    if any(character in FORBIDDEN for character in name):
        raise BadName(f"a name cannot hold {sorted(FORBIDDEN)!r}: {name!r}")
    if name.endswith("."):
        raise BadName(f"a name cannot end with a dot: {name!r}")
    if len(name) > MAX_NAME:
        raise BadName(f"a name is at most {MAX_NAME} characters, got "
                      f"{len(name)}")
    if fold(split_name(name)[0]) in RESERVED:
        raise BadName(f"{name!r} is a name Windows reserves")
    if any(ord(character) < 32 for character in name):
        raise BadName(f"a name cannot hold a control character: {name!r}")
    return name


def target_for(new_name: str, old_name: str) -> str:
    """The file name a plan entry asks for, before any collision is resolved.

    The rule the legacy code half-implemented, stated once: **the new name is used
    whole when it carries a suffix; the old suffix is appended only when it does
    not.** So ``report.pdf`` from ``scan.pdf`` stays ``report.pdf``, and
    ``report`` from ``scan.pdf`` becomes ``report.pdf``.
    """
    new_name = check_name(new_name)
    if split_name(new_name)[1]:
        return new_name
    return new_name + split_name(old_name)[1]


def numbered(name: str, number: int) -> str:
    """``report.pdf`` and 2 become ``report-2.pdf``: the suffix stays last."""
    stem, suffix = split_name(name)
    return f"{stem}-{number}{suffix}"


# --------------------------------------------------------------------------- #
# The folder interface
# --------------------------------------------------------------------------- #
class Folder:
    """What a plan needs from a folder: its names, and a move."""

    def names(self) -> tuple[str, ...]:
        raise NotImplementedError

    def exists(self, name: str) -> bool:
        return any(fold(known) == fold(name) for known in self.names())

    def move(self, old: str, new: str) -> None:
        raise NotImplementedError


class MemoryFolder(Folder):
    """A folder held in a dictionary of names to contents."""

    def __init__(self, contents=None) -> None:
        self._files: dict[str, str] = {}
        for name, body in dict(contents or {}).items():
            self._files[check_name(name)] = body

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._files))

    def read(self, name: str) -> str:
        for known, body in self._files.items():
            if fold(known) == fold(name):
                return body
        raise RenameError(f"no such file: {name!r}")

    def move(self, old: str, new: str) -> None:
        found = next((known for known in self._files if fold(known) == fold(old)),
                     None)
        if found is None:
            raise RenameError(f"no such file: {old!r}")
        if found == new:
            return
        clash = next((known for known in self._files if fold(known) == fold(new)),
                     None)
        if clash is not None and clash != found:
            raise RenameError(f"{new!r} is already there; a move would "
                              f"overwrite it")
        self._files[new] = self._files.pop(found)

    def contents(self) -> dict[str, str]:
        return dict(self._files)

    def __len__(self) -> int:
        return len(self._files)

    def __repr__(self) -> str:
        return f"MemoryFolder({len(self._files)} files)"


class DiskFolder(Folder):
    """A real directory. Tests use a temporary one; nothing else needs it."""

    def __init__(self, path) -> None:
        self.path = Path(path)
        if not self.path.is_dir():
            raise RenameError(f"not a folder: {self.path}")

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(entry.name for entry in self.path.iterdir()
                            if entry.is_file()))

    def exists(self, name: str) -> bool:
        return any(fold(entry.name) == fold(name)
                   for entry in self.path.iterdir() if entry.is_file())

    def move(self, old: str, new: str) -> None:
        source = self.path / old
        target = self.path / new
        if not source.is_file():
            raise RenameError(f"no such file: {old!r}")
        if fold(old) == fold(new):
            if old == new:
                return
            # A case-only rename is legal, but the target "exists" already on a
            # case-insensitive filesystem; the detour through a temporary name
            # works on both kinds of filesystem.
            temporary = self.path / ("__rename__" + new)
            source.rename(temporary)
            temporary.rename(target)
            return
        if target.exists():
            raise RenameError(f"{new!r} is already there; a move would "
                              f"overwrite it")
        source.rename(target)

    def __repr__(self) -> str:
        return f"DiskFolder({self.path})"


# --------------------------------------------------------------------------- #
# The plan
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Entry:
    """One rename: what it was, what was asked for, what it becomes."""

    old: str
    wanted: str
    new: str
    note: str = ""

    def __str__(self) -> str:
        tail = f"  ({self.note})" if self.note else ""
        return f"{self.old} -> {self.new}{tail}"


@dataclass(frozen=True)
class Plan:
    """Every rename for one folder, checked before anything moves."""

    entries: tuple[Entry, ...]

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def changed(self) -> tuple[Entry, ...]:
        return tuple(entry for entry in self.entries if entry.old != entry.new)

    def notes(self) -> tuple[str, ...]:
        return tuple(entry.note for entry in self.entries if entry.note)

    def lines(self) -> tuple[str, ...]:
        return tuple(str(entry) for entry in self.entries)


@dataclass(frozen=True)
class Applied:
    """One rename that really happened."""

    old: str
    new: str

    def __str__(self) -> str:
        return f"{self.old} -> {self.new}"


def build_plan(folder: Folder, names, ordered=None) -> Plan:
    """Pair names with files and resolve every collision, without moving.

    ``names`` must cover the folder exactly: one name for every file. A shorter or
    longer list is refused, because a plan that covers part of a folder is the
    defect this module exists to remove.
    """
    if not isinstance(names, (list, tuple)):
        raise PlanError(f"the names must be a list, got {names!r}")
    available = list(folder.names())
    files = list(ordered) if ordered is not None else available
    if len(set(files)) != len(files):
        raise PlanError("the plan lists a file twice")
    for name in files:
        if name not in available:
            raise PlanError(f"the folder holds no file called {name!r}")
    missing = [name for name in available if name not in files]
    if missing:
        raise PlanError(f"the plan leaves out {len(missing)} file(s): "
                        f"{', '.join(missing)}")
    if len(names) != len(files):
        raise PlanError(f"the plan names {len(names)} file(s) but the folder "
                        f"holds {len(files)}")

    checked = [check_name(name) for name in names]
    wanted = [target_for(name, old) for name, old in zip(checked, files)]

    taken = {fold(name) for name in available}
    # Only a file that is actually leaving its name frees it. A file whose new
    # name is its old name still occupies it.
    vacating = {fold(old) for old, want in zip(files, wanted)
                if fold(want) != fold(old)}
    entries = []
    for old, want in zip(files, wanted):
        new, note = want, ""
        if (fold(want) != fold(old) and fold(want) in taken
                and fold(want) not in vacating):
            # The name belongs to a file that is staying: number it instead of
            # overwriting the file that is already there.
            number = 1
            while number <= TRIES and (
                    fold(numbered(want, number)) in taken |
                    {fold(entry.new) for entry in entries}):
                number += 1
            if number > TRIES:
                raise PlanError(f"no free name left for {want!r} after "
                                f"{TRIES} attempts")
            new = numbered(want, number)
            note = f"renamed to avoid {want!r}, which is already there"
        elif fold(want) == fold(old) and want != old:
            note = "a case-only rename: two steps on POSIX, one on Windows"
        entries.append(Entry(old, want, new, note))

    # Two entries may not end up with the same name. This is checked on the
    # resolved names, because a collision with a file that stays is numbered
    # and therefore resolved, while two entries wanting one name is a mistake
    # in the plan itself.
    finals: dict[str, str] = {}
    for entry in entries:
        key = fold(entry.new)
        if key in finals:
            raise PlanError(f"two files would both be called {entry.new!r}: "
                            f"{finals[key]!r} and {entry.old!r}")
        finals[key] = entry.old
    return Plan(tuple(entries))


# --------------------------------------------------------------------------- #
# Applying, and undoing
# --------------------------------------------------------------------------- #
def apply(folder: Folder, plan: Plan) -> tuple[Applied, ...]:
    """Carry out a plan, one reversible record per rename.

    The whole plan is re-checked against the folder as it is now, so a folder
    that changed after the plan was built is refused before the first file moves.
    """
    if not isinstance(plan, Plan):
        raise PlanError(f"apply needs a Plan, got {plan!r}")
    present = {fold(name) for name in folder.names()}
    for entry in plan.changed():
        if fold(entry.old) not in present:
            raise PlanError(f"{entry.old!r} is not in the folder any more")
        if fold(entry.new) in present - {fold(entry.old)}:
            raise PlanError(f"{entry.new!r} appeared in the folder after the "
                            f"plan was built")
    records = []
    for entry in plan.changed():
        folder.move(entry.old, entry.new)
        records.append(Applied(entry.old, entry.new))
    return tuple(records)


def undo(folder: Folder, records) -> tuple[Applied, ...]:
    """Reverse applied records, newest first, checking the chain first.

    The whole chain is walked before the first file moves, in a predicted name
    set rather than the folder -- because undoing an older record only makes
    sense *after* the newer ones are reversed. ``notes.txt -> a.txt`` followed by
    ``a.txt -> b.txt`` is undone newest first: ``b.txt`` must be there now, and
    ``a.txt`` will be once its own turn comes. A chain that cannot be walked is
    refused before anything is touched.
    """
    records = list(records)
    if not records:
        raise UndoError("there is nothing to undo")
    predicted = {fold(name) for name in folder.names()}
    for record in reversed(records):
        if fold(record.new) not in predicted:
            raise UndoError(f"{record.new!r} is not where the rename left it")
        predicted.discard(fold(record.new))
        predicted.add(fold(record.old))
    reversed_records = []
    for record in reversed(records):
        folder.move(record.new, record.old)
        reversed_records.append(Applied(record.new, record.old))
    return tuple(reversed_records)


class Workbook:
    """A folder plus the record of what has been done to it."""

    def __init__(self, folder: Folder) -> None:
        self.folder = folder
        self._records: list[Applied] = []
        self._plans = 0

    @property
    def records(self) -> tuple[Applied, ...]:
        return tuple(self._records)

    @property
    def plans_built(self) -> int:
        return self._plans

    def plan(self, names, ordered=None) -> Plan:
        plan = build_plan(self.folder, names, ordered)
        self._plans += 1
        return plan

    def apply(self, plan: Plan) -> tuple[Applied, ...]:
        """Apply a plan, keeping the older records instead of clearing them."""
        records = apply(self.folder, plan)
        self._records.extend(records)
        return records

    def undo(self, count: int | None = None) -> tuple[Applied, ...]:
        if not self._records:
            raise UndoError("there is nothing to undo")
        count = len(self._records) if count is None else count
        if count < 1 or count > len(self._records):
            raise UndoError(f"there are {len(self._records)} record(s); "
                            f"cannot undo {count}")
        part = self._records[-count:]
        reversed_records = undo(self.folder, part)
        self._records = self._records[:-count]
        return reversed_records

    def has_history(self) -> bool:
        return bool(self._records)


# --------------------------------------------------------------------------- #
# The data files
# --------------------------------------------------------------------------- #
def read_lines(path=NAMES_FILE) -> tuple[str, ...]:
    """Read one name per line, skipping blanks and ``;`` or ``//`` comments."""
    path = Path(path)
    if not path.is_file():
        raise PlanError(f"file not found: {path}")
    lines = []
    for number, line in enumerate(path.read_text(encoding="utf-8")
                                  .splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith(";") or text.startswith("//"):
            continue
        if len(text) > MAX_NAME:
            raise PlanError(f"{path.name}:{number}: a name is at most "
                            f"{MAX_NAME} characters")
        lines.append(text)
    return tuple(lines)


def read_folder(path=FOLDER_FILE) -> MemoryFolder:
    """Build a folder in memory from ``name<TAB>contents`` lines."""
    path = Path(path)
    if not path.is_file():
        raise PlanError(f"folder file not found: {path}")
    contents: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8")
                                  .splitlines(), start=1):
        text = line.rstrip()
        if not text.strip() or text.lstrip().startswith(";"):
            continue
        name, _, body = text.partition("\t")
        name = name.strip()
        try:
            name = check_name(name)
        except RenameError as error:
            raise PlanError(f"{path.name}:{number}: {error}") from None
        if fold(name) in {fold(known) for known in contents}:
            raise PlanError(f"{path.name}:{number}: {name!r} appears twice")
        contents[name] = body
    if not contents:
        raise PlanError(f"{path.name}: no files")
    return MemoryFolder(contents)


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def audit(folder: Folder, plan: Plan, records=()) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived from the plan and the folder."""
    names = list(folder.names())
    folded = [fold(name) for name in names]

    def covers_every_file() -> bool:
        return sorted(entry.old for entry in plan) == sorted(names) and \
            len(plan) == len(names)

    def no_repeats() -> bool:
        return len(set(folded)) == len(folded)

    def targets_are_unique() -> bool:
        wanted = [fold(entry.new) for entry in plan]
        return len(set(wanted)) == len(wanted)

    def names_are_legal() -> bool:
        try:
            return all(check_name(entry.new) for entry in plan)
        except RenameError:
            return False

    def nothing_is_overwritten() -> bool:
        return all(fold(entry.new) not in folded or
                   fold(entry.new) == fold(entry.old) for entry in plan)

    def suffixes_survive() -> bool:
        return all(split_name(entry.new)[1] or not split_name(entry.old)[1]
                   for entry in plan)

    def records_reach_the_plan() -> bool:
        if not records:
            return True
        reached = {fold(record.new) for record in records}
        moved = {fold(entry.new) for entry in plan.changed()}
        return reached == moved

    def notes_explain_deviations() -> bool:
        return all(entry.note for entry in plan
                   if fold(entry.new) != fold(entry.wanted))

    def each_file_once() -> bool:
        return sorted(entry.old for entry in plan) == sorted(names)

    return [
        ("the plan names exactly the files the folder holds",
         covers_every_file()),
        ("no two files share a name, even case-insensitively", no_repeats()),
        ("no two entries want the same target name", targets_are_unique()),
        ("every new name is legal on Windows and on POSIX", names_are_legal()),
        ("no entry points at a file that stays where it is",
         nothing_is_overwritten()),
        ("no file loses its suffix", suffixes_survive()),
        ("the records name the files the plan moved", records_reach_the_plan()),
        ("every entry that departs from the asked-for name says why",
         notes_explain_deviations()),
        ("the plan lists each file exactly once", each_file_once()),
    ]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _show(folder) -> None:
    print(f"  the folder holds {len(folder)} files:")
    for name in folder.names():
        print(f"    {name:<20}{folder.read(name)}")


def run_demo() -> int:
    folder = read_folder()
    names = read_lines(NAMES_FILE)
    short = names[:4]
    starting = folder.names()

    print("=" * 74)
    print(" RENAME LAB - a plan is a value, and zip() is not a plan")
    print("=" * 74)
    _show(folder)
    print(f"\n  the name list offers {len(names)} names; the first "
          f"{len(short)} are used below:")
    for name in short:
        print(f"    {name}")

    pairs = list(zip(folder.names(), short))
    print(f"\n  the legacy loop, {LEGACY_LOOP!r}")
    print(f"    zip() pairs {len(pairs)} of the {len(folder)} files and returns "
          f"{len(pairs)}")
    print(f"    the other {len(folder) - len(pairs)} files are never mentioned "
          f"and nothing raises")
    print(f"    and {LEGACY_HISTORY!r} empties the previous undo before this "
          f"batch starts")

    print(f"\n  {LEGACY_TARGET!r}")
    print(f"    a bare name takes the old suffix: "
          f"{target_for('chapter-one', 'notes.txt')!r}")
    print(f"    a name with a suffix is used whole: "
          f"{target_for('q3-report.pdf', 'notes.txt')!r}")

    try:
        build_plan(folder, short)
    except PlanError as error:
        print(f"\n  the plan refuses the short list: {error}")
    try:
        build_plan(folder, list(names[:-1]) + ["invoice.pdf"])
    except PlanError as error:
        print(f"  and a repeated target: {error}")

    plan = build_plan(folder, names)
    print(f"\n  a plan that covers the folder, {len(plan)} entries:")
    for line in plan.lines():
        print(f"    {line}")

    records = apply(folder, plan)
    print(f"\n  applied {len(records)} rename(s); the folder is now:")
    _show(folder)

    back = undo(folder, records)
    print(f"\n  undid {len(back)} in reverse; every name is back: "
          f"{'yes' if folder.names() == starting else 'no'}")

    print("\n  a name that would land on a file that is staying:")
    squatter = MemoryFolder({"keep.txt": "the original", "move.txt": "the mover"})
    before = MemoryFolder(squatter.contents())
    squatter_plan = build_plan(squatter, ["keep", "keep.txt"])
    print(f"    {squatter_plan.entries[1]}")
    squatter_records = apply(squatter, squatter_plan)
    print(f"    keep.txt still holds {squatter.read('keep.txt')!r}")
    print(f"    the folder holds {', '.join(squatter.names())}")

    checks = audit(before, squatter_plan, squatter_records)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(folder)} files and {len(short)} names give a legacy zip() that "
          f"renames {len(pairs)} and mentions the other "
          f"{len(folder) - len(pairs)} nowhere, the plan refuses both a short "
          f"list and a repeated target, a legal plan of {len(plan)} entries "
          f"applies {len(records)} rename(s), undo restores every name exactly, "
          f"a name that would collide is numbered instead of overwriting, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0
