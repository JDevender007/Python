"""A backup that is verified by content, not by counting.

The legacy manager verified like this:

    def verify_backup(self, source, backup):
        source_files = list(Path(source).rglob("*"))
        backup_files = list(Path(backup).rglob("*"))
        return len(source_files) == len(backup_files)

Three defects, none of them visible when the copy worked.

**1. Equal counts are not equal contents.** Delete one file and add another and
the count is unchanged; edit a file in place and the count never moves at all.
``rglob("*")`` also counts *directories*, so a backup missing a file but holding
a leftover empty folder scores equal. Verification has to compare the thing the
backup exists to preserve: every relative path, its size, and a digest of its
bytes -- and it has to say which path failed and how.

**2. ``current_timestamp()`` can collide, and ``dirs_exist_ok=True`` merges.**
Two backups in the same second land in the same folder, and ``copytree`` with
``dirs_exist_ok=True`` does not fail on an existing one: it *merges*. A file the
source no longer has survives inside the snapshot, and the result looks like a
clean backup of the current state. Here a name is chosen against the set of
names already taken, so a second backup is ``-2`` and never a merge.

**3. A backup is a diff, and copying everything hides a deletion.** The legacy
tool copied the tree every time and never compared it with the previous backup,
so "what changed since last time" could only be answered by looking. A ``Plan``
compares two trees by digest and says what is new, what changed, what is gone and
what is untouched -- and a same-size edit is a *change*, which a size-only or
timestamp-only comparison would miss.

The fourth thing in the legacy folder was a scheduler: ``while self.running:
time.sleep(interval); callback()``. A stop flag cannot interrupt a sleep, so
``stop()`` returns while one more backup is still on its way, and an exception in
the callback kills the thread while ``is_running()`` keeps saying ``True``. This
module replaces the thread with arithmetic: given a start, an interval and the
moment the window closes, ``due()`` says exactly which ticks happen -- no clock,
no thread, no flag to get out of step.

Everything runs on an in-memory tree, so the demonstration is deterministic and
never writes into the repository.

Standard library only: no ``shutil``, no ``threading``, no ``tkinter``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TREE_FILE = DATA_DIR / "tree.txt"
BACKUP_FILE = DATA_DIR / "backup.txt"
AFTER_FILE = DATA_DIR / "after.txt"

#: The legacy lines, transcribed, so the demo can refute them.
LEGACY_VERIFY = "return len(source_files) == len(backup_files)"
LEGACY_MERGE = "shutil.copytree(source, backup_folder, dirs_exist_ok=True)"
LEGACY_LOOP = "while self.running:\n    time.sleep(interval)\n    callback()"

#: How many hex characters of a digest the report prints.
SHORT_DIGEST = 8


class BackupError(Exception):
    """A tree, a plan, a verdict or a name that cannot be accepted."""


# --------------------------------------------------------------------------- #
# A file, and a tree
# --------------------------------------------------------------------------- #
def digest_of(data: str) -> str:
    """The SHA-256 of a file's bytes, as sixty-four hex characters."""
    if not isinstance(data, str):
        raise BackupError(f"a file holds text, got {data!r}")
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def check_path(path: str) -> str:
    """A relative path, written with forward slashes, and nothing clever."""
    if not isinstance(path, str) or not path.strip():
        raise BackupError(f"a path must be text, got {path!r}")
    if "\\" in path:
        raise BackupError(f"a path uses forward slashes, not backslashes: "
                          f"{path!r}")
    if path.startswith("/"):
        raise BackupError(f"a path is relative, not absolute: {path!r}")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise BackupError(f"a path cannot hold a blank, a dot or a double "
                          f"dot: {path!r}")
    if any(ord(character) < 32 for character in path):
        raise BackupError(f"a path cannot hold a control character: {path!r}")
    return path


@dataclass(frozen=True, order=True)
class File:
    """One file: its relative path, its text, and what a manifest recorded.

    ``size`` and ``digest`` are stored rather than recomputed on demand,
    because a backup is exactly that: content, plus a written-down record of
    what the content was supposed to be. A tree where the record is derived
    from the content can never disagree with it, so verification of such a
    tree would prove nothing -- the recorded values are what an audit checks
    against the bytes.
    """

    path: str
    data: str
    size: int = -1
    digest: str = ""

    def __post_init__(self) -> None:
        if self.size < 0:
            object.__setattr__(self, "size", len(self.data.encode("utf-8")))
        if not self.digest:
            object.__setattr__(self, "digest", digest_of(self.data))

    def short(self) -> str:
        return self.digest[:SHORT_DIGEST]


@dataclass(frozen=True, order=True)
class Entry:
    """What a manifest records about a file: a path, a size and a digest."""

    path: str
    size: int
    digest: str

    def short(self) -> str:
        return self.digest[:SHORT_DIGEST]

    def line(self) -> str:
        return f"{self.path:<16}{self.size:>5} bytes  {self.short()}"


@dataclass(frozen=True)
class Tree:
    """A folder's files, in the order the manifest lists them."""

    files: tuple[File, ...]

    def __post_init__(self) -> None:
        seen = set()
        for entry in self.files:
            check_path(entry.path)
            if entry.path in seen:
                raise BackupError(f"{entry.path!r} appears twice in the tree")
            seen.add(entry.path)

    def __len__(self) -> int:
        return len(self.files)

    def by_path(self) -> dict:
        return {entry.path: entry for entry in self.files}

    def entries(self) -> tuple[Entry, ...]:
        return tuple(Entry(entry.path, entry.size, entry.digest)
                     for entry in self.files)

    def manifest(self) -> tuple[Entry, ...]:
        return tuple(sorted(self.entries()))

    def get(self, path: str) -> File:
        found = self.by_path().get(path)
        if found is None:
            raise BackupError(f"the tree holds no file called {path!r}")
        return found

    def lines(self) -> tuple[str, ...]:
        return tuple(entry.line() for entry in self.manifest())


def copy_tree(tree: Tree) -> Tree:
    """A copy of a tree as a new value, so identity cannot stand in for proof."""
    return Tree(tuple(File(entry.path, entry.data, entry.size, entry.digest)
                      for entry in tree.files))


# --------------------------------------------------------------------------- #
# Reading a tree
# --------------------------------------------------------------------------- #
def parse_tree(text: str) -> Tree:
    """Read ``path<TAB>text`` lines; ``;`` and ``//`` start a comment."""
    files = []
    for number, line in enumerate(text.replace("\r\n", "\n")
                                  .replace("\r", "\n").split("\n"), start=1):
        if not line.strip() or line.lstrip().startswith(";") or \
                line.lstrip().startswith("//"):
            continue
        if "\t" not in line:
            raise BackupError(f"line {number}: expected a path, a tab, and the "
                              f"file's text")
        path, data = line.split("\t", 1)
        try:
            files.append(File(check_path(path.strip()), data))
        except BackupError as error:
            raise BackupError(f"line {number}: {error}") from None
    if not files:
        raise BackupError("the tree holds no files")
    return Tree(tuple(sorted(files)))


def read_tree(path=TREE_FILE) -> Tree:
    path = Path(path)
    if not path.is_file():
        raise BackupError(f"file not found: {path}")
    return parse_tree(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Verifying
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Difference:
    """One path where the backup and the source disagree, and how."""

    path: str
    kind: str          # "missing" | "size" | "digest" | "extra"
    detail: str

    def line(self) -> str:
        return f"{self.kind:<8}{self.path:<16}{self.detail}"


@dataclass(frozen=True)
class Verdict:
    """How much of a backup is what it claims to be."""

    checked: int
    identical: int
    differences: tuple[Difference, ...] = ()

    def mismatches(self) -> int:
        return sum(1 for entry in self.differences if entry.kind != "extra")

    def extras(self) -> int:
        return sum(1 for entry in self.differences if entry.kind == "extra")

    def ok(self) -> bool:
        return not self.differences and self.checked == self.identical

    def counts(self) -> tuple[int, int, int, int]:
        return self.checked, self.identical, self.mismatches(), self.extras()

    def summary(self) -> str:
        checked, identical, mismatches, extras = self.counts()
        return (f"{checked} file(s) checked, {identical} identical, "
                f"{mismatches} different, {extras} extra")

    def lines(self) -> tuple[str, ...]:
        return tuple(entry.line() for entry in self.differences)


def verify(source: Tree, backup: Tree) -> Verdict:
    """Compare every file by path, size and digest -- and name the failures.

    The order of the three tests is the lesson: a missing file is not a size
    mismatch, and a same-size edit is not identical just because ``st_size`` and
    ``st_mtime`` agree about it.
    """
    if not isinstance(source, Tree) or not isinstance(backup, Tree):
        raise BackupError("verify needs two trees")
    there = backup.by_path()
    here = source.by_path()
    differences = []
    identical = 0
    for entry in source.manifest():
        other = there.get(entry.path)
        if other is None:
            differences.append(Difference(entry.path, "missing",
                                          "the backup holds no such file"))
        elif other.size != entry.size:
            differences.append(Difference(
                entry.path, "size",
                f"{entry.size} bytes in the source, {other.size} in the backup"))
        elif other.digest != entry.digest:
            differences.append(Difference(
                entry.path, "digest",
                f"the same {entry.size} bytes, different content"))
        else:
            identical += 1
    for path in sorted(set(there) - set(here)):
        differences.append(Difference(path, "extra",
                                      "the backup holds a file the source "
                                      "does not"))
    return Verdict(len(source.files), identical, tuple(differences))


def count_only(source: Tree, backup: Tree) -> bool:
    """The legacy check, executable: do both sides have the same count?"""
    return len(source.files) == len(backup.files)


# --------------------------------------------------------------------------- #
# Planning an incremental backup
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Plan:
    """What copying ``source`` over ``previous`` has to do."""

    added: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()

    def counts(self) -> tuple[int, int, int, int]:
        return (len(self.added), len(self.changed), len(self.removed),
                len(self.unchanged))

    def total(self) -> int:
        return sum(self.counts())

    def summary(self) -> str:
        added, changed, removed, unchanged = self.counts()
        return (f"{added} added, {changed} changed, {removed} removed, "
                f"{unchanged} unchanged")

    def lines(self) -> tuple[str, ...]:
        out = []
        for kind, paths in (("added", self.added), ("changed", self.changed),
                            ("removed", self.removed),
                            ("unchanged", self.unchanged)):
            for path in paths:
                out.append(f"{kind:<10}{path}")
        return tuple(out)

    def paths(self) -> tuple[str, ...]:
        return (self.added + self.changed + self.removed + self.unchanged)


def plan(source: Tree, previous: Tree) -> Plan:
    """Diff two trees by digest, so a same-size edit is still a change."""
    if not isinstance(source, Tree) or not isinstance(previous, Tree):
        raise BackupError("plan needs two trees")
    now, then = source.by_path(), previous.by_path()
    added = tuple(sorted(set(now) - set(then)))
    removed = tuple(sorted(set(then) - set(now)))
    changed, unchanged = [], []
    for path in sorted(set(now) & set(then)):
        if now[path].digest == then[path].digest:
            unchanged.append(path)
        else:
            changed.append(path)
    return Plan(added, tuple(changed), removed, tuple(unchanged))


# --------------------------------------------------------------------------- #
# Naming a backup
# --------------------------------------------------------------------------- #
def next_name(base: str, taken=()) -> str:
    """``base`` if it is free, else the first free ``base-2``, ``base-3`` ...

    A name is a promise that nothing is joined to what is already there. The
    legacy name came from the clock, so two backups inside one second were one
    folder -- and ``dirs_exist_ok=True`` made that a merge instead of a refusal.
    """
    base = (base or "").strip()
    if not base:
        raise BackupError("a backup needs a name")
    if "\\" in base or "/" in base:
        raise BackupError(f"a backup name is one folder name, got {base!r}")
    taken = {str(name).casefold() for name in taken}
    if base.casefold() not in taken:
        return base
    number = 2
    while f"{base}-{number}".casefold() in taken:
        number += 1
    return f"{base}-{number}"


def name_backups(source_name: str, stamp: str, count: int) -> tuple[str, ...]:
    """The names ``count`` backups taken in the same second would receive."""
    names: list[str] = []
    for _ in range(count):
        names.append(next_name(f"{source_name}_{stamp}", names))
    return tuple(names)


# --------------------------------------------------------------------------- #
# Scheduling, without a clock
# --------------------------------------------------------------------------- #
def due(start: int, interval: int, until: int) -> tuple[int, ...]:
    """Which ticks happen when a window closes at ``until``.

    The legacy loop slept first and called afterwards, so a stop that arrives
    during the sleep does not stop the callback that sleep was waiting for.
    Stated as arithmetic: a tick happens only if it falls inside the window.
    """
    if interval <= 0:
        raise BackupError(f"an interval is positive, got {interval}")
    if until < start:
        raise BackupError(f"a window cannot close before it opens: {start} "
                          f"to {until}")
    ticks = []
    moment = start + interval
    while moment <= until:
        ticks.append(moment)
        moment += interval
    return tuple(ticks)


def would_fire_early(start: int, interval: int, stop_at: int) -> bool:
    """True when the legacy loop fires a tick after the stop was requested.

    ``while running: sleep(interval); callback()`` tests the flag once per
    cycle, *before* the sleep. A stop that arrives during the sleep cannot be
    seen until the sleep ends, so the callback that sleep was waiting for runs
    anyway -- one tick past the moment somebody asked it to stop.
    """
    if stop_at < start:
        raise BackupError(f"a stop cannot arrive before the start: {start} "
                          f"to {stop_at}")
    return stop_at < start + interval


# --------------------------------------------------------------------------- #
# A whole session
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Session:
    """Everything the audit looks at: two trees, a verdict, a plan, some names."""

    source: Tree
    backup: Tree
    verdict: Verdict
    previous: Tree
    plan: Plan
    taken: tuple[str, ...] = ()


def build_session(source: Tree, backup: Tree, previous: Tree,
                  taken=()) -> Session:
    return Session(source, backup, verify(source, backup), previous,
                   plan(source, previous), tuple(taken))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    """Run one check, and report a structural break as a failure."""
    try:
        return bool(check())
    except Exception:                                    # noqa: BLE001
        return False


def audit(session: Session) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived from the trees rather than restated."""
    source, backup, verdict = session.source, session.backup, session.verdict

    def digests_match_the_content() -> bool:
        for tree in (source, backup):
            for entry in tree.files:
                if entry.digest != digest_of(entry.data):
                    return False
        return True

    def sizes_match_the_content() -> bool:
        for tree in (source, backup):
            for entry in tree.files:
                if entry.size != len(entry.data.encode("utf-8")):
                    return False
        return True

    def every_tree_is_sorted_and_unique() -> bool:
        for tree in (source, backup, session.previous):
            paths = [entry.path for entry in tree.files]
            if paths != sorted(paths):
                return False
            if len(set(paths)) != len(paths):
                return False
        return True

    def every_missing_file_is_named() -> bool:
        named = {entry.path for entry in verdict.differences
                 if entry.kind == "missing"}
        wanted = set(source.by_path()) - set(backup.by_path())
        return named == wanted

    def every_extra_file_is_named() -> bool:
        named = {entry.path for entry in verdict.differences
                 if entry.kind == "extra"}
        wanted = set(backup.by_path()) - set(source.by_path())
        return named == wanted

    def every_same_size_edit_is_a_digest_difference() -> bool:
        named = {entry.path: entry.kind for entry in verdict.differences}
        now, then = source.by_path(), backup.by_path()
        for path in set(now) & set(then):
            if now[path].size != then[path].size:
                continue
            if now[path].digest == then[path].digest:
                continue
            if named.get(path) != "digest":
                return False
        return True

    def the_counts_add_up() -> bool:
        if verdict.identical + verdict.mismatches() != verdict.checked:
            return False
        if verdict.checked != len(source.files):
            return False
        return verdict.ok() == (verdict.differences == ())

    def the_plan_partitions_every_path() -> bool:
        counted = session.plan.paths()
        union = set(source.by_path()) | set(session.previous.by_path())
        return (len(counted) == len(set(counted)) and
                set(counted) == union)

    def every_taken_name_is_unique() -> bool:
        folded = [name.casefold() for name in session.taken]
        return len(set(folded)) == len(folded)

    checks = [
        ("every digest is the digest of that file's own bytes",
         digests_match_the_content),
        ("every recorded size is the size of that file's own bytes",
         sizes_match_the_content),
        ("every tree is sorted by path and holds no path twice",
         every_tree_is_sorted_and_unique),
        ("the verdict names every file the backup is missing",
         every_missing_file_is_named),
        ("the verdict names every file the backup holds and the source does not",
         every_extra_file_is_named),
        ("a same-size edit is reported as a digest difference",
         every_same_size_edit_is_a_digest_difference),
        ("the verdict's counts add up, and ok means no difference at all",
         the_counts_add_up),
        ("the plan puts every path in exactly one of its four lists",
         the_plan_partitions_every_path),
        ("no two backups share a name, even case-insensitively",
         every_taken_name_is_unique),
    ]
    return [(name, _guard(check)) for name, check in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    source = read_tree()
    damaged = read_tree(BACKUP_FILE)
    after = read_tree(AFTER_FILE)
    good = copy_tree(source)
    names = name_backups("docs", "20240101_120000", 3)

    print("=" * 74)
    print(" BACKUP LAB - a count of paths is not a copy of a folder")
    print("=" * 74)

    print(f"\n  the source folder, {len(source)} file(s):")
    for line in source.lines():
        print(f"    {line}")
    print(f"\n  the backup folder somebody handed you, {len(damaged)} file(s):")
    for line in damaged.lines():
        print(f"    {line}")

    print(f"\n  {LEGACY_VERIFY}")
    print(f"    the source holds {len(source)} path(s) and the backup holds "
          f"{len(damaged)}")
    print(f"    so the legacy check answers {count_only(source, damaged)} -- "
          f"a corrupted backup passes")

    verdict = verify(source, damaged)
    print(f"\n  verify by path, size and digest: {verdict.summary()}")
    for line in verdict.lines():
        print(f"    {line}")
    print(f"    every count is equal and every size is equal; only the bytes "
          f"differ, so")
    print(f"    a size-based or timestamp-based check would pass this too")

    print(f"\n  a real copy verifies clean: {verify(source, good).summary()} "
          f"-> {verify(source, good).ok()}")

    print(f"\n  {LEGACY_MERGE}")
    print(f"    a second backup in the same second reuses the folder and "
          f"merges into it")
    for name in names:
        print(f"    {name}")
    print(f"    three backups, three names, no merge: "
          f"{len(set(names)) == len(names)}")

    print(f"\n  the folder after some work, {len(after)} file(s) against the "
          f"previous backup:")
    print(f"    the legacy count still says "
          f"{count_only(after, source)}: {len(after)} path(s) then, "
          f"{len(source)} now")
    step = plan(after, source)
    print(f"    {step.summary()}")
    for line in step.lines():
        print(f"    {line}")
    edited = plan(after, source).changed
    print(f"    {edited[0]!r} kept its size and changed its text, so only a "
          f"digest finds it")

    print(f"\n  {LEGACY_LOOP!r}")
    print(f"    a stop that arrives at t=10 with an interval of 60 leaves the "
          f"tick at t=60")
    print(f"    already sleeping, so the callback still runs: "
          f"{would_fire_early(0, 60, 10)}")
    print(f"    as arithmetic, a window 0 to 10 has ticks {due(0, 60, 10)}")
    print(f"    a window 0 to 180 has ticks {due(0, 60, 180)}")

    session = build_session(source, damaged_after(damaged, after), after,
                            names)
    checks = audit(session)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(source)} file(s) against {len(damaged)} pass the legacy count "
          f"and fail {verdict.mismatches()} content check, a real copy is "
          f"{verify(source, good).ok()}, three backups in one second get "
          f"{len(set(names))} distinct name(s), the plan against the previous "
          f"backup is {step.summary()} and finds the same-size edit, a stop at "
          f"t=10 leaves {len(due(0, 60, 10))} due tick(s) where the legacy loop "
          f"runs one more, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0


def damaged_after(damaged: Tree, after: Tree) -> Tree:
    """A backup of ``after`` that carries the damaged copy of one file.

    The audit needs a tree to compare against, and a verdict computed from the
    source; this keeps the damaged file in place so the verdict has something
    real to name.
    """
    files = []
    for entry in after.files:
        if entry.path in damaged.by_path() and entry.digest != \
                damaged.get(entry.path).digest:
            files.append(damaged.get(entry.path))
        else:
            files.append(entry)
    return Tree(tuple(files))
