"""One-way mirroring: a size is not a file, and a mirror means deletion too.

The legacy project hashed both sides of every pair and copied what differed:

    def files_are_different(source: Path, destination: Path) -> bool:
        if not destination.exists():
            return True
        return calculate_hash(source) != calculate_hash(destination)

    for source_file in tqdm(files):
        relative_path = source_file.relative_to(SOURCE_FOLDER)
        destination_file = DESTINATION_FOLDER / relative_path
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            if files_are_different(source_file, destination_file):
                shutil.copy2(source_file, destination_file)
                self.synced_files.append(...)
        except Exception as error:
            logger.error(f"{source_file}: {error}")

    print("Synchronization Complete.")
    print(f"Files Copied/Updated: {len(self.synced_files)}")

Four things follow.

**1. A size is not a file.** The obvious speed-up to a hash is "same size, same
file". The bundled tree holds ``x,y / 1,2 / 3,4 / 5,6`` and ``x,y / 1,2 / 3,4 /
9,9`` -- 17 bytes each, different bytes. A size check calls them equal and the
stale copy stays stale forever. This module hashes whenever the sizes agree, and
only skips the hash when they cannot agree.

**2. A timestamp is not a file either.** ``shutil.copy2`` preserves ``mtime``, so
a copied file and its source share a timestamp *by design*; and a file edited
twice inside one timestamp tick keeps its ``mtime`` while its bytes change. The
demo builds exactly that pair -- equal size, equal ``mtime_ns``, different bytes
-- and shows the timestamp check calling it identical while the digest does not.

**3. A one-way mirror is not a copy job, it is a copy *and a delete* job.** The
legacy never deletes, so a file removed from the source lives in the destination
forever, and the tool still prints "Synchronization Complete." After a legacy
run the destination still holds the three orphans, and ``verify_mirror`` fails on
"no extra files". Deletion is destructive, so it is opt-in here (``--delete``)
and every orphan is reported whether or not it will be removed.

**4. ``except Exception: logger.error(...)`` plus "Complete" is a lie.** A run
that failed on three files prints the same two lines as a run that failed on
none. Here failures are collected, counted, printed, and the exit status is
non-zero. And a copy is not trusted until the bytes are read back: the file goes
to a temporary name, its digest is compared with the source, and only then does
``os.replace`` put it in place, so a half-written mirror is never visible.

Standard library only: ``hashlib``, ``shutil``, ``os``, no ``tqdm``.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SOURCE = DATA_DIR / "source"
DESTINATION = DATA_DIR / "destination"

#: How much of a file is read at a time.
CHUNK = 65536

#: The four decisions a change can carry, plus the orphan.
COPY = "copy"
UPDATE = "update"
SKIP = "skip"
DELETE = "delete"
ORPHAN = "orphan"
ACTIONS = (COPY, UPDATE, SKIP, DELETE, ORPHAN)

#: The legacy lines, kept executable.
LEGACY_ALWAYS = ("return calculate_hash(source) != "
                 "calculate_hash(destination)")
LEGACY_COPY = "shutil.copy2(source_file, destination_file)"
LEGACY_SWALLOW = "except Exception as error: logger.error(f'{source_file}: {error}')"
LEGACY_NEVER_DELETES = "FILES IN DESTINATION NOT IN SOURCE ARE LEFT ALONE"


class SyncError(ValueError):
    """A folder, a path, a plan or a copy that is refused."""


# --------------------------------------------------------------------------- #
# Reading one file
# --------------------------------------------------------------------------- #
def digest(path, chunk: int = CHUNK) -> str:
    """The SHA-256 of a file's bytes, read in chunks."""
    path = Path(path)
    if not path.is_file():
        raise SyncError(f"not a file: {path}")
    sha = hashlib.sha256()
    try:
        with open(path, "rb") as stream:
            while True:
                block = stream.read(chunk)
                if not block:
                    break
                sha.update(block)
    except OSError as exc:
        raise SyncError(f"cannot read {path}: {exc}") from None
    return sha.hexdigest()


@dataclass(frozen=True)
class FileState:
    """What a ``stat`` call knows: a size and a timestamp, not the bytes."""

    path: Path
    size: int
    mtime_ns: int

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            object.__setattr__(self, "path", Path(self.path))
        if self.size < 0:
            raise SyncError("a file cannot have a negative size")

    def to_dict(self) -> dict:
        return {"path": self.path.name, "size": self.size,
                "mtime_ns": self.mtime_ns}


def state(path) -> FileState:
    path = Path(path)
    if not path.is_file():
        raise SyncError(f"not a file: {path}")
    stat = path.stat()
    return FileState(path, stat.st_size, stat.st_mtime_ns)


def scan_tree(root) -> dict[str, FileState]:
    """Every file under ``root``, keyed by its forward-slash relative path."""
    root = Path(root)
    if not root.exists():
        raise SyncError(f"folder not found: {root}")
    if not root.is_dir():
        raise SyncError(f"{root} is a file, not a folder")
    found = {}
    for path in sorted(root.rglob("*"),
                       key=lambda item: str(item).casefold()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        found[relative] = state(path)
    return found


# --------------------------------------------------------------------------- #
# One change
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Change:
    """One decision about one relative path."""

    action: str
    path: str
    size: int
    other_size: int | None
    reason: str

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise SyncError(f"{self.action!r} is not an action")
        if self.size < 0 or (self.other_size is not None and
                             self.other_size < 0):
            raise SyncError("a change cannot carry a negative size")
        if not self.path:
            raise SyncError("a change needs a path")

    @property
    def writes(self) -> bool:
        """Does this change touch the destination's contents?"""
        return self.action in (COPY, UPDATE, DELETE)

    @property
    def bytes(self) -> int:
        """The size this change is about: the source's, or the orphan's."""
        if self.action in (DELETE, ORPHAN):
            return self.other_size or 0
        return self.size

    def __str__(self) -> str:
        return f"{self.action:<6} {self.path}  ({self.reason})"

    def to_dict(self) -> dict:
        return {"action": self.action, "path": self.path, "size": self.size,
                "other_size": self.other_size, "reason": self.reason}


# --------------------------------------------------------------------------- #
# The plan
# --------------------------------------------------------------------------- #
class Plan:
    """Every decision for one mirror, made before any file is touched."""

    def __init__(self, source, dest, changes, hashes: int,
                 allowed_delete: bool = False):
        self.source = Path(source)
        self.dest = Path(dest)
        self._changes = tuple(changes)
        self.hashes = hashes
        # Whether the person running this said deletion was allowed. Derived
        # from the changes it would be a check that can never fail.
        self.allowed_delete = allowed_delete

    @property
    def changes(self) -> tuple[Change, ...]:
        return self._changes

    def __len__(self) -> int:
        return len(self._changes)

    def __iter__(self):
        return iter(self._changes)

    def __repr__(self) -> str:
        counts = self.counts()
        return (f"<Plan {len(self)} changes: {counts[COPY]} copy, "
                f"{counts[UPDATE]} update, {counts[SKIP]} skip, "
                f"{counts[DELETE]} delete, {counts[ORPHAN]} orphan>")

    def counts(self) -> dict[str, int]:
        counts = {action: 0 for action in ACTIONS}
        for change in self._changes:
            counts[change.action] += 1
        return counts

    def by_action(self) -> dict[str, tuple[Change, ...]]:
        grouped: dict[str, list[Change]] = {}
        for change in self._changes:
            grouped.setdefault(change.action, []).append(change)
        return {action: tuple(grouped[action]) for action in ACTIONS
                if action in grouped}

    @property
    def to_copy(self) -> tuple[Change, ...]:
        return tuple(change for change in self._changes
                     if change.action in (COPY, UPDATE))

    @property
    def bytes_to_copy(self) -> int:
        return sum(change.size for change in self.to_copy)

    @property
    def orphans(self) -> tuple[Change, ...]:
        return tuple(change for change in self._changes
                     if change.action in (DELETE, ORPHAN))

    def summary(self) -> dict:
        counts = self.counts()
        return {"source": self.source.name, "dest": self.dest.name,
                "changes": len(self), "copy": counts[COPY],
                "update": counts[UPDATE], "skip": counts[SKIP],
                "delete": counts[DELETE], "orphan": counts[ORPHAN],
                "bytes_to_copy": self.bytes_to_copy,
                "bytes_to_delete": sum(change.other_size or 0
                                       for change in self.orphans),
                "hashes": self.hashes}

    def to_dict(self) -> dict:
        return {"summary": self.summary(),
                "changes": [change.to_dict() for change in self._changes]}

    # -- checks ------------------------------------------------------------- #
    def audit(self) -> list[tuple[str, bool]]:
        checks = []

        def safe(change: Change) -> bool:
            pure = PurePosixPath(change.path)
            return (not pure.is_absolute() and ".." not in pure.parts and
                    "\\" not in change.path and change.path not in ("", "."))

        checks.append(("every path is relative and climbs nowhere",
                       all(safe(change) for change in self._changes)))

        paths = [change.path.casefold() for change in self._changes]
        checks.append(("no two changes share a path",
                       len(paths) == len(set(paths))))

        sourced = all((self.source / change.path).is_file()
                      for change in self._changes
                      if change.action in (COPY, UPDATE, SKIP))
        checks.append(("every copy, update or skip has a source file", sourced))

        dest_only = all(not (self.source / change.path).exists() and
                        (self.dest / change.path).is_file()
                        for change in self._changes
                        if change.action in (DELETE, ORPHAN))
        checks.append(("every delete or orphan is only in the destination",
                       dest_only))

        allowed = all(change.action != DELETE or self.allowed_delete
                      for change in self._changes)
        checks.append(("a delete is planned only when deletion is allowed",
                       allowed))

        inside = all(_under(self.dest, change.path)
                     for change in self._changes)
        checks.append(("no change reaches outside the destination",
                       inside))

        return checks

    def problems(self) -> list[str]:
        return [name for name, passed in self.audit() if not passed]


def _under(root: Path, relative: str) -> bool:
    """Does ``root/relative`` stay inside ``root``?"""
    root = root.resolve()
    target = (root / relative).resolve()
    return target == root or root in target.parents


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
def _inside(child: Path, parent: Path) -> bool:
    child, parent = child.resolve(), parent.resolve()
    return child == parent or parent in child.parents


def build_plan(source=SOURCE, dest=DESTINATION, delete: bool = False) -> Plan:
    """Decide every copy, update, skip, delete and orphan, and count the reads.

    The size decides first, because equal content implies equal size: a pair
    whose sizes differ cannot be equal, so only the source is hashed. The hash
    decides the rest, because a size cannot tell ``5,6`` from ``9,9``.
    """
    source, dest = Path(source), Path(dest)
    if _inside(dest, source):
        raise SyncError("the destination is inside the source: a mirror there "
                        "would copy itself")
    if _inside(source, dest):
        raise SyncError("the source is inside the destination: a delete here "
                        "would reach the source")

    from_source = scan_tree(source)
    from_dest = scan_tree(dest) if dest.exists() else {}
    hashes = 0

    def read(path: Path) -> str:
        nonlocal hashes
        hashes += 1
        return digest(path)

    changes: list[Change] = []
    for relative in sorted(set(from_source) | set(from_dest)):
        origin = from_source.get(relative)
        copy = from_dest.get(relative)

        if origin is not None and copy is not None:
            if origin.size != copy.size:
                read(source / relative)
                changes.append(Change(
                    UPDATE, relative, origin.size, copy.size,
                    f"size {origin.size} vs {copy.size}"))
            elif read(source / relative) == read(dest / relative):
                changes.append(Change(SKIP, relative, origin.size, copy.size,
                                      "identical"))
            else:
                changes.append(Change(
                    UPDATE, relative, origin.size, copy.size,
                    f"same size, different bytes"))
        elif origin is not None:
            read(source / relative)
            changes.append(Change(COPY, relative, origin.size, None,
                                  "not in the destination"))
        else:
            changes.append(Change(DELETE if delete else ORPHAN, relative, 0,
                                  copy.size, "only in the destination"))

    return Plan(source, dest, changes, hashes, allowed_delete=delete)


# --------------------------------------------------------------------------- #
# Applying
# --------------------------------------------------------------------------- #
def apply_plan(plan: Plan) -> tuple[Change, ...]:
    """Copy, verify, replace; then delete. A failed copy leaves no partial file.

    A partial apply is safe: everything it did is a SKIP the next time, so the
    fix is to run it again.
    """
    applied: list[Change] = []
    for change in plan.to_copy:
        origin = plan.source / change.path
        target = plan.dest / change.path
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".syncing")
        try:
            shutil.copy2(origin, temporary)
            if digest(temporary) != digest(origin):
                raise SyncError(f"{change.path} arrived with different bytes")
            os.replace(temporary, target)
        except OSError as exc:
            raise SyncError(f"cannot copy {change.path}: {exc}") from None
        finally:
            if temporary.exists():
                temporary.unlink()
        applied.append(change)

    for change in (item for item in plan.changes if item.action == DELETE):
        target = plan.dest / change.path
        if not target.is_file():
            raise SyncError(f"{change.path} is no longer there to delete")
        target.unlink()
        applied.append(change)

    _prune(plan.dest)
    return tuple(applied)


def _prune(root: Path) -> None:
    """Remove directories left empty, deepest first."""
    for folder in sorted((item for item in root.rglob("*") if item.is_dir()),
                         key=lambda item: len(item.parts), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()


def verify_mirror(source=SOURCE, dest=DESTINATION) -> list[tuple[str, bool]]:
    """Read both trees and prove the destination is a mirror."""
    from_source = scan_tree(source)
    from_dest = scan_tree(dest) if Path(dest).exists() else {}
    source, dest = Path(source), Path(dest)

    present = all(relative in from_dest for relative in from_source)
    same = all(relative in from_dest and
               digest(source / relative) == digest(dest / relative)
               for relative in from_source)
    extras = not set(from_dest) - set(from_source)
    return [("every source file is present in the destination", present),
            ("every source file has the same bytes in the destination", same),
            ("the destination holds no extra files", extras)]


def problems(source=SOURCE, dest=DESTINATION) -> list[str]:
    return [name for name, passed in verify_mirror(source, dest) if not passed]


# --------------------------------------------------------------------------- #
# The legacy project, and the two shortcuts
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LegacyReport:
    """What the legacy run did, and how many full reads it took to do it."""

    copied: tuple[str, ...]
    already: tuple[str, ...]
    hashes: int

    @property
    def total(self) -> int:
        return len(self.copied) + len(self.already)


def legacy_mirror(source=SOURCE, dest=DESTINATION) -> LegacyReport:
    """Replay the legacy loop: hash both sides, copy what differs, delete none."""
    source, dest = Path(source), Path(dest)
    copied, already = [], []
    hashes = 0
    for relative, origin in scan_tree(source).items():
        target = dest / relative
        if not target.is_file():
            hashes += 1                      # the source hash
            copied.append(relative)
            continue
        hashes += 2                          # the legacy hashes both sides
        if digest(source / relative) != digest(target):
            copied.append(relative)
        else:
            already.append(relative)
    return LegacyReport(tuple(copied), tuple(already), hashes)


def naive_size_plan(source=SOURCE, dest=DESTINATION) -> list[tuple[str, str]]:
    """``same size, same file`` -- and the bundled tree proves it is not."""
    source, dest = Path(source), Path(dest)
    decisions = []
    for relative, origin in scan_tree(source).items():
        target = dest / relative
        if not target.is_file():
            decisions.append((relative, "copy"))
        elif target.stat().st_size == origin.size:
            decisions.append((relative, "same"))
        else:
            decisions.append((relative, "update"))
    return decisions


def naive_mtime_plan(source=SOURCE, dest=DESTINATION) -> list[tuple[str, str]]:
    """``same size and same timestamp, same file`` -- also not true."""
    source, dest = Path(source), Path(dest)
    decisions = []
    for relative, origin in scan_tree(source).items():
        target = dest / relative
        if not target.is_file():
            decisions.append((relative, "copy"))
            continue
        stat = target.stat()
        if stat.st_size == origin.size and stat.st_mtime_ns == origin.mtime_ns:
            decisions.append((relative, "same"))
        else:
            decisions.append((relative, "update"))
    return decisions


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 74)
    print(" SYNCHRONIZATION - a size is not a file, and a mirror deletes")
    print("=" * 74)

    plan = build_plan()
    summary = plan.summary()
    assert summary["changes"] == 12
    assert (summary["copy"], summary["update"], summary["skip"]) == (4, 2, 3)
    assert (summary["orphan"], summary["delete"]) == (3, 0)
    assert summary["bytes_to_copy"] == 374 - 60 - 50 - 37

    # 1. the two trees
    origin = scan_tree(SOURCE)
    copy = scan_tree(DESTINATION)
    print(f"  source {len(origin)} files, {sum(s.size for s in origin.values())} "
          f"bytes; destination {len(copy)} files, "
          f"{sum(s.size for s in copy.values())} bytes, so "
          f"{summary['orphan']} of them are only in the destination")

    # 2. the plan, and the reads it takes
    print(f"  the plan: {summary['copy']} copy, {summary['update']} update, "
          f"{summary['skip']} skip, {summary['orphan']} orphan; "
          f"{summary['hashes']} files hashed")
    legacy = legacy_mirror()
    assert legacy.hashes == 14 and len(legacy.copied) == 6
    assert legacy.already == ("notes.txt", "report.csv", "settings.json")
    assert summary["hashes"] == 13
    print(f"  the legacy hashes both sides of every pair and reads "
          f"{legacy.hashes} files; the size gate spends the destination read "
          f"only where the sizes agree, so this plan reads "
          f"{summary['hashes']}. One read is all the gate can save here -- the "
          f"digest decides the other twelve")

    # 3. equal size, different bytes
    points = next(change for change in plan if change.path == "data/points.csv")
    assert points.action == UPDATE and points.size == points.other_size == 17
    assert digest(SOURCE / "data/points.csv") != \
        digest(DESTINATION / "data/points.csv")
    naive_size = dict(naive_size_plan())
    assert naive_size["data/points.csv"] == "same"
    print(f"  data/points.csv is 17 bytes on both sides and the bytes differ, "
          f"so it is an update here; a size check calls it "
          f"'{naive_size['data/points.csv']}'")

    # 4. equal size and equal mtime, different bytes
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        shutil.copytree(SOURCE, work / "source")
        shutil.copytree(DESTINATION, work / "dest")
        edited = work / "dest" / "report.csv"
        original = work / "source" / "report.csv"
        text = edited.read_bytes()
        edited.write_bytes(b"X" + text[1:])          # same size, new bytes
        stamp = original.stat()
        os.utime(edited, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        assert state(edited).size == state(original).size
        assert state(edited).mtime_ns == state(original).mtime_ns
        assert digest(edited) != digest(original)
        assert dict(naive_mtime_plan(work / "source",
                                     work / "dest"))["report.csv"] == "same"
        probe = build_plan(work / "source", work / "dest")
        caught = next(change for change in probe
                      if change.path == "report.csv")
        assert caught.action == UPDATE and "different bytes" in caught.reason
        print(f"  report.csv edited in place, same 50 bytes, mtime pinned to "
              f"the source's: a size+mtime check says 'same', the digest "
              f"says UPDATE")

        # 5. the mirror, without deleting
        applied = apply_plan(build_plan(work / "source", work / "dest"))
        assert len(applied) == 7                      # 4 copies, 3 updates
        copied_now = {change.path for change in applied}
        assert "docs/guide.txt" in copied_now and "docs/api.txt" in copied_now
        assert "report.csv" in copied_now             # the edited one
        assert "data/points.csv" in copied_now
        checks = verify_mirror(work / "source", work / "dest")
        assert [ok for _, ok in checks] == [True, True, False]
        left = sorted(problems(work / "source", work / "dest"))
        assert left == ["the destination holds no extra files"]
        print(f"  copied and updated {len(applied)} file(s) into a copy of the "
              f"destination, the edited report.csv among them; the mirror now "
              f"fails one check: {left[0]}")

        # 6. the legacy run leaves exactly those stale bytes behind
        legacy_here = legacy_mirror(work / "source", work / "dest")
        assert legacy_here.copied == ()
        assert len(legacy_here.already) == 9
        still = sorted(problems(work / "source", work / "dest"))
        assert still == ["the destination holds no extra files"]
        print(f"  the legacy loop, run again, copies nothing and still leaves "
              f"{len(scan_tree(work / 'dest')) - len(scan_tree(work / 'source'))} "
              f"extra file(s) behind")

        # 7. deletion is the missing half
        deleting = build_plan(work / "source", work / "dest", delete=True)
        assert deleting.counts()[DELETE] == 3
        assert deleting.counts()[SKIP] == 9
        removed = apply_plan(deleting)
        assert len(removed) == 3
        assert not (work / "dest" / "old").exists()
        final = verify_mirror(work / "source", work / "dest")
        assert all(passed for _, passed in final)
        print(f"  with deletion allowed, the plan names "
              f"{deleting.counts()[DELETE]} delete(s), the apply removes them, "
              f"and the empty old/ folder goes with them: "
              f"{sum(1 for _, ok in final if ok)}/{len(final)} checks pass")

        # 8. a second run has nothing left to do
        again = build_plan(work / "source", work / "dest", delete=True)
        assert again.counts()[SKIP] == 9
        assert len(again.to_copy) == 0 and again.counts()[DELETE] == 0
        print(f"  a second plan finds {again.counts()[SKIP]} skips and nothing "
              f"to copy or delete, so a rerun is harmless")

        # 9. an edited destination file is repaired, and no temporary is left
        (work / "dest" / "docs" / "guide.txt").write_text("edited\n",
                                                          encoding="utf-8")
        stale = build_plan(work / "source", work / "dest", delete=True)
        assert next(change for change in stale
                    if change.path == "docs/guide.txt").action == UPDATE
        apply_plan(stale)
        assert not list((work / "dest").rglob("*.syncing"))
        assert digest(work / "dest" / "docs" / "guide.txt") == \
            digest(work / "source" / "docs" / "guide.txt")
        print(f"  a file edited in the destination is planned as an update, "
              f"the copy goes through a .syncing name and is renamed into "
              f"place, and no .syncing file is left anywhere")

    # 10. refusals
    refused = 0
    for bad in (Path("no-such-folder"), Path(__file__)):
        try:
            scan_tree(bad)
        except SyncError:
            refused += 1
        else:
            raise AssertionError(f"{bad} was scanned")
    for source, dest in ((SOURCE, SOURCE / "mirror"), (SOURCE, DATA_DIR)):
        try:
            build_plan(source, dest)
        except SyncError as exc:
            assert "inside" in str(exc)
            refused += 1
        else:
            raise AssertionError(f"{dest} was accepted as a destination")
    bad_plan = Plan(SOURCE, DESTINATION,
                    (Change(COPY, "../escape.txt", 1, None, "made up"),), 0)
    assert "every path is relative and climbs nowhere" in bad_plan.problems()
    assert "no change reaches outside the destination" in bad_plan.problems()
    refused += 1
    print(f"  a missing folder, a file given as a folder, a destination inside "
          f"the source, a source inside the destination and a '../' path were "
          f"all refused ({refused} refusals)")

    # 11. the audit
    checks = plan.audit()
    assert len(checks) == 6 and plan.problems() == []
    print(f"  {sum(1 for _, ok in checks if ok)}/{len(checks)} plan checks "
          f"pass: paths stay inside, one change per path, copies have "
          f"sources, orphans are destination-only, no delete without "
          f"permission, nothing reaches outside")

    print()
    print("Cross-checks OK: 9 source files worth 374 bytes against 8 "
          "destination files, 4 copies and 2 updates and 3 skips and 3 "
          "orphans, data/points.csv is 17 bytes on both sides with different "
          "bytes so a size check calls it 'same' while the digest updates it, "
          "report.csv edited in place with its mtime pinned to the source's "
          "own reads as 'same' by size and timestamp and UPDATE by digest, the "
          "legacy loop hashes both sides of every pair for 14 reads against "
          "13, a legacy run leaves all 3 orphans in place so the mirror fails "
          "'no extra files', allowing deletion removes all 3 and takes the "
          "empty folder with it for 3/3 checks, a second plan finds 9 skips "
          "and nothing to do, 6/6 plan checks passed, and a missing folder, a "
          "file given as a folder, a destination inside the source, a source "
          "inside the destination and a climbing path were all refused")
    print("Demo completed successfully.")
    return 0
