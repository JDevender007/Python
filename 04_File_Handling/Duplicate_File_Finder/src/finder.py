"""Duplicate files: content identity, and the two ways a "copy" is not one.

The legacy project walked a folder and hashed everything it found:

    def scan_files(self):
        files = [file for file in SCAN_FOLDER.rglob("*") if file.is_file()]
        for file in tqdm(files, desc="Scanning"):
            if file.stat().st_size == 0:
                continue
            try:
                file_hash = calculate_hash(file)
                if file_hash in self.hash_map:
                    self.duplicates.setdefault(file_hash, []).append(file)
                else:
                    self.hash_map[file_hash] = file
            except Exception as error:
                logger.error(f"{file}: {error}")
        return self.duplicates

Three things follow, and a fourth that is arithmetic.

**1. Emptiness is decided by size, and then thrown away.** ``if
file.stat().st_size == 0: continue`` means every empty file is invisible to the
scan, although two empty files are the most equal pair of files there is. Here a
zero-byte file is scanned like any other: it has a digest, and it is grouped.

**2. A path is not a copy.** A hard link -- ``os.link(a, b)`` -- is two names for
one inode. Both paths are files, both hash the same, and deleting one frees
*nothing*, because the bytes are still there under the other name. The legacy
scan reports such a pair as a duplicate and offers to reclaim its size twice.
This module compares ``(st_dev, st_ino)`` first and reports the extra name as an
*alias*, not as a copy.

**3. The finder keeps state between scans.** ``self.duplicates`` is never
cleared, so calling ``scan_files()`` twice appends the same duplicates again and
the second report is twice the size of the first. ``scan()`` here is a function
that returns a fresh ``ScanResult``; running it twice gives the same answer, not
twice the answer.

**4. "Reclaimable" is ``size * (copies - 1)``, per group, counting physical
files.** That is the only number that means anything: the bytes that would come
back if every copy but one were deleted. The demo pins it, including the empty
group, whose honest answer is zero bytes and two duplicate files at the same
time.

Size is checked before content, so only files of equal length are ever read.
That is not an optimisation -- equal content implies equal size, so the grouping
is exact either way -- but it keeps a 4 GB video out of the hasher when nothing
else in the folder is 4 GB.

Standard library only: no network, no third-party hashing.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "files"

#: The hash the report is built on.
ALGORITHM = "sha256"

#: How much of a file is read at a time.
CHUNK = 65536

#: The legacy skip: an empty file is not scanned at all.
LEGACY_SKIP = "if file.stat().st_size == 0: continue"

#: The legacy grouping: one dictionary that is never cleared.
LEGACY_STATE = "self.duplicates.setdefault(file_hash, []).append(file)"

#: The legacy identity: a path is a copy.
LEGACY_IDENTITY = "file"


class FindError(ValueError):
    """A folder, a file or a group that is refused."""


# --------------------------------------------------------------------------- #
# Reading one file
# --------------------------------------------------------------------------- #
def digest(path, chunk: int = CHUNK) -> str:
    """The SHA-256 of a file's bytes, read in chunks."""
    path = Path(path)
    if not path.exists():
        raise FindError(f"no such file: {path}")
    if path.is_dir():
        raise FindError(f"{path} is a directory, not a file")
    sha = hashlib.sha256()
    try:
        with open(path, "rb") as stream:
            while True:
                block = stream.read(chunk)
                if not block:
                    break
                sha.update(block)
    except OSError as exc:
        raise FindError(f"cannot read {path}: {exc}") from None
    return sha.hexdigest()


def empty_digest() -> str:
    """The SHA-256 of nothing, which is a real digest."""
    return hashlib.sha256(b"").hexdigest()


def physical_key(path):
    """``(device, inode)``: the identity of the bytes, not of the name.

    A filesystem that reports an inode of 0 (some network shares) cannot answer
    the question, so the resolved path is used instead and two hard links look
    like two files there. That is stated rather than guessed.
    """
    path = Path(path)
    try:
        stat = path.stat()
    except OSError as exc:
        raise FindError(f"cannot stat {path}: {exc}") from None
    if stat.st_ino == 0:
        return (stat.st_dev, os.path.realpath(path))
    return (stat.st_dev, stat.st_ino)


# --------------------------------------------------------------------------- #
# One scanned file
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ScannedFile:
    """A path, its size and the digest of its bytes."""

    path: Path
    size: int
    digest: str
    device: int
    inode: int

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            object.__setattr__(self, "path", Path(self.path))
        if self.size < 0:
            raise FindError("a file cannot have a negative size")
        if not isinstance(self.digest, str) or len(self.digest) != 64:
            raise FindError("a digest is 64 hexadecimal characters")

    @property
    def key(self) -> tuple[int, int]:
        return (self.device, self.inode)

    def __str__(self) -> str:
        return f"{self.path.name:<24} {self.size:>6} bytes  {self.digest[:12]}"

    def to_dict(self) -> dict:
        return {"path": self.path.name, "size": self.size,
                "digest": self.digest}


@dataclass(frozen=True)
class DuplicateGroup:
    """Files whose bytes are identical, by inode, so each copy is counted once."""

    digest: str
    size: int
    copies: tuple[Path, ...]

    def __post_init__(self) -> None:
        if len(self.copies) < 2:
            raise FindError("a duplicate group needs at least two copies")
        if self.size < 0:
            raise FindError("a duplicate group cannot hold a negative size")

    @property
    def reclaimable(self) -> int:
        """The bytes that deleting every copy but one would return."""
        return self.size * (len(self.copies) - 1)

    def to_dict(self) -> dict:
        return {"digest": self.digest, "size": self.size,
                "copies": [path.name for path in self.copies],
                "reclaimable": self.reclaimable}


@dataclass(frozen=True)
class Alias:
    """A second name for one physical file: a hard link, not a copy.

    A hard link has no original. Two names, one inode, and no way to say which
    came first -- so the scan keeps whichever name sorts first and reports the
    others with the name it kept. Nothing here claims to be the source.
    """

    path: Path
    kept: Path

    @property
    def reclaimable(self) -> int:
        """Deleting this name frees nothing: the bytes stay under ``kept``."""
        return 0

    def to_dict(self) -> dict:
        return {"path": self.path.name, "kept": self.kept.name}


class ScanResult:
    """What one scan found, as a value: files, aliases and duplicate groups."""

    def __init__(self, root, files, aliases, groups):
        self.root = Path(root)
        self._files = tuple(files)
        self._aliases = tuple(aliases)
        self._groups = tuple(groups)

    # -- what was found ----------------------------------------------------- #
    @property
    def files(self) -> tuple[ScannedFile, ...]:
        return self._files

    @property
    def aliases(self) -> tuple[Alias, ...]:
        return self._aliases

    @property
    def groups(self) -> tuple[DuplicateGroup, ...]:
        return self._groups

    def __len__(self) -> int:
        """How many paths the scan looked at, aliases included."""
        return len(self._files) + len(self._aliases)

    def __iter__(self):
        return iter(self._groups)

    def __repr__(self) -> str:
        return (f"<ScanResult {len(self)} files, {len(self._groups)} duplicate "
                f"groups, {self.reclaimable} bytes reclaimable>")

    # -- the numbers -------------------------------------------------------- #
    @property
    def physical(self) -> tuple[ScannedFile, ...]:
        """One entry per inode: the files that actually hold bytes.

        An alias never becomes a ``ScannedFile``, so the scan's file list is
        already one entry per physical file.
        """
        return self._files

    @property
    def total_bytes(self) -> int:
        return sum(file.size for file in self.physical)

    @property
    def reclaimable(self) -> int:
        return sum(group.reclaimable for group in self._groups)

    @property
    def duplicate_files(self) -> int:
        """How many files could be deleted: every copy but one, per group."""
        return sum(len(group.copies) - 1 for group in self._groups)

    def by_digest(self) -> dict[str, DuplicateGroup]:
        return {group.digest: group for group in self._groups}

    def summary(self) -> dict:
        return {"root": self.root.name, "paths": len(self),
                "files": len(self.physical), "aliases": len(self._aliases),
                "groups": len(self._groups),
                "duplicate_files": self.duplicate_files,
                "bytes": self.total_bytes, "reclaimable": self.reclaimable}

    def to_dict(self) -> dict:
        return {"summary": self.summary(),
                "groups": [group.to_dict() for group in self._groups],
                "aliases": [alias.to_dict() for alias in self._aliases]}

    # -- checks ------------------------------------------------------------- #
    def verify(self) -> list[tuple[str, bool]]:
        """Re-read every group and prove the members still agree."""
        checks = []
        same_digest = all(digest(group.copies[0]) == group.digest
                          for group in self._groups)
        checks.append(("every group's first copy still hashes to its digest",
                       same_digest))
        agree = all(len({digest(path) for path in group.copies}) == 1
                    for group in self._groups)
        checks.append(("every copy in a group hashes the same", agree))
        sizes = all(path.stat().st_size == group.size
                    for group in self._groups for path in group.copies)
        checks.append(("every copy in a group has its size", sizes))
        no_group_of_one = all(len(group.copies) > 1 for group in self._groups)
        checks.append(("no group holds a single file", no_group_of_one))
        return checks

    def problems(self) -> list[str]:
        return [name for name, passed in self.verify() if not passed]


# --------------------------------------------------------------------------- #
# The scan
# --------------------------------------------------------------------------- #
def scan(root=DATA_DIR, chunk: int = CHUNK) -> ScanResult:
    """Walk ``root`` once and group the files by size and then by content."""
    root = Path(root)
    if not root.exists():
        raise FindError(f"folder not found: {root}")
    if not root.is_dir():
        raise FindError(f"{root} is a file, not a folder")
    paths = sorted((path for path in root.rglob("*") if path.is_file()),
                   key=lambda path: str(path).casefold())

    by_identity: dict[tuple[int, int], ScannedFile] = {}
    aliases: list[Alias] = []
    for path in paths:
        stat = path.stat()
        key = physical_key(path)
        if key in by_identity:
            aliases.append(Alias(path, by_identity[key].path))
            continue
        file = ScannedFile(path, stat.st_size, digest(path, chunk),
                           key[0], key[1])
        by_identity[key] = file

    grouped: dict[tuple[int, str], list[ScannedFile]] = {}
    for file in by_identity.values():
        grouped.setdefault((file.size, file.digest), []).append(file)

    groups = []
    for (size, content), members in sorted(grouped.items(),
                                           key=lambda pair: (
                                               -pair[0][0], pair[0][1])):
        if len(members) < 2:
            continue
        groups.append(DuplicateGroup(
            content, size,
            tuple(sorted((file.path for file in members),
                         key=lambda path: str(path).casefold()))))

    return ScanResult(root, by_identity.values(), aliases, groups)


def report_rows(result: ScanResult) -> list[dict]:
    """One line per group, for a report that can be written or printed."""
    rows = []
    for index, group in enumerate(result.groups, start=1):
        rows.append({"group": index, "digest": group.digest[:12],
                     "size": group.size, "copies": len(group.copies),
                     "reclaimable": group.reclaimable,
                     "files": [path.name for path in group.copies]})
    return rows


def report_text(result: ScanResult) -> str:
    """The report as CSV text, with a header that says what each column is."""
    lines = ["Group,Digest,Bytes,Copies,Reclaimable,Files"]
    for row in report_rows(result):
        lines.append(",".join([str(row["group"]), row["digest"],
                               str(row["size"]), str(row["copies"]),
                               str(row["reclaimable"]),
                               " ".join(row["files"])]))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# The legacy project, transcribed
# --------------------------------------------------------------------------- #
def legacy_scan(paths) -> dict[str, list[str]]:
    """The legacy grouping: skip empty files, no identity check, no state reset."""
    hash_map: dict[str, str] = {}
    duplicates: dict[str, list[str]] = {}
    for path in paths:
        path = Path(path)
        if path.stat().st_size == 0:
            continue                        # the empty-file skip
        content = digest(path)
        if content in hash_map:
            duplicates.setdefault(content, []).append(str(path))
        else:
            hash_map[content] = str(path)
    return duplicates


class LegacyFinder:
    """The legacy class, with the bug the class had: state between scans."""

    def __init__(self):
        self.hash_map: dict[str, str] = {}
        self.duplicates: dict[str, list[str]] = {}

    def scan_files(self, paths) -> dict[str, list[str]]:
        for path in paths:
            path = Path(path)
            if path.stat().st_size == 0:
                continue
            content = digest(path)
            if content in self.hash_map:
                self.duplicates.setdefault(content, []).append(str(path))
            else:
                self.hash_map[content] = str(path)
        return self.duplicates

    @property
    def reclaimable(self) -> int:
        """What the legacy report implies: every listed duplicate is bytes."""
        total = 0
        for content, duplicates in self.duplicates.items():
            size = Path(duplicates[0]).stat().st_size
            total += size * len(duplicates)
        return total


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 74)
    print(" DUPLICATES - a name is not a copy, and an empty file is still a file")
    print("=" * 74)

    result = scan()
    summary = result.summary()
    assert summary["paths"] == 8 and summary["files"] == 8
    assert summary["groups"] == 3 and summary["duplicate_files"] == 3
    assert len(result) == 8

    # 1. the loaded folder, counted
    sizes = {file.path.name: file.size for file in result.files}
    assert sizes["report.txt"] == sizes["report-copy.txt"]
    assert sizes["notes.txt"] == sizes["notes-backup.txt"]
    assert sizes["empty-a.txt"] == sizes["empty-b.txt"] == 0
    print(f"  {summary['paths']} paths, {summary['files']} files, "
          f"{summary['groups']} duplicate groups, "
          f"{summary['duplicate_files']} deletable copies, "
          f"{summary['reclaimable']} bytes reclaimable")

    # 2. size first: 8 files but only 5 distinct sizes get hashed
    distinct_sizes = len({file.size for file in result.files})
    assert distinct_sizes == 5
    print(f"  the 8 files have {distinct_sizes} distinct sizes, so only those "
          f"size buckets were read: equal content implies equal size")

    # 3. two empty files are a duplicate group
    empty = [group for group in result.groups if group.size == 0]
    assert len(empty) == 1 and len(empty[0].copies) == 2
    assert empty[0].digest == empty_digest() and empty[0].reclaimable == 0
    legacy = legacy_scan(sorted(DATA_DIR.glob("*")))
    assert all(len(group.copies) > 0 for group in result.groups)
    assert empty[0].digest not in legacy
    print(f"  the two empty files are one group of {len(empty[0].copies)} "
          f"(sha256 of nothing is {empty[0].digest[:12]}...) and reclaim "
          f"{empty[0].reclaimable} bytes; the legacy skip "
          f"'st_size == 0' never saw them")

    # 4. a hard link is one file with two names
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        original = root / "original.txt"
        original.write_text("the same bytes\n", encoding="utf-8")
        linked = root / "linked.txt"
        try:
            os.link(original, linked)
        except OSError:
            linked = original               # a filesystem without hard links
        linked_result = scan(root)
        if linked != original:
            assert len(linked_result.aliases) == 1
            assert linked_result.groups == ()
            assert linked_result.reclaimable == 0
            legacy_linked = legacy_scan([original, linked])
            assert len(legacy_linked) == 1
            assert list(legacy_linked.values())[0] == [str(linked)]
            same_inode = physical_key(original) == physical_key(linked)
            assert same_inode
            print(f"  a hard link has the same (device, inode) as its other "
                  f"name, so it is one file with two names and reclaims 0 "
                  f"bytes; the legacy scan called it a duplicate")
        else:
            print("  this filesystem refused a hard link; the alias check was "
                  "skipped")

    # 5. the legacy class never resets its state, so a second scan is nonsense
    finder = LegacyFinder()
    paths = sorted(DATA_DIR.glob("*"))
    first = {content: list(members)
             for content, members in finder.scan_files(paths).items()}
    second = finder.scan_files(paths)
    assert len(first) == 2 and len(second) == 4
    assert sum(len(members) for members in first.values()) == 2
    assert sum(len(members) for members in second.values()) == 8
    names = {Path(member).name
             for members in second.values() for member in members}
    assert {"budget.csv", "unique.txt", "empty-a.txt"} - names == \
        {"empty-a.txt"}
    assert {"budget.csv", "unique.txt"} <= names
    print(f"  one legacy scan lists 2 duplicates; a second call lists 8, one "
          f"for every path in the folder, because 'self.duplicates' and "
          f"'self.hash_map' still hold the first scan: budget.csv and "
          f"unique.txt have no copy at all and are now reported as their own "
          f"duplicates")

    # 6. the arithmetic, both ways
    assert result.reclaimable == 343
    assert sum(group.size for group in result.groups) == 343
    assert result.reclaimable == sum(group.size * (len(group.copies) - 1)
                                     for group in result.groups)
    legacy_bytes = finder.reclaimable
    assert legacy_bytes == 1315 and legacy_bytes > result.reclaimable
    print(f"  reclaimable is size x (copies - 1) per group: 170 + 173 + 0 = "
          f"{result.reclaimable} bytes, because deleting one of two copies "
          f"returns exactly one file; the same folder read by the legacy "
          f"finder implies {legacy_bytes} bytes")

    # 7. verify re-reads the bytes
    checks = result.verify()
    assert len(checks) == 4 and result.problems() == []
    print(f"  {sum(1 for _, ok in checks if ok)}/{len(checks)} checks pass "
          f"after re-reading every group from disk")

    # 8. a scan is a value, not a session
    again = scan()
    assert again.to_dict() == result.to_dict()
    assert again.summary() == summary
    print(f"  scanning twice gives the same summary, not twice the groups: "
          f"{again.summary()['groups']} groups both times")

    # 9. the report
    rows = report_rows(result)
    assert len(rows) == 3
    assert [row["copies"] for row in rows] == [2, 2, 2]
    assert report_text(result).splitlines()[0] == \
        "Group,Digest,Bytes,Copies,Reclaimable,Files"
    print(f"  the report is {len(rows)} rows with a digest, a size, a copy "
          f"count and the bytes each group would return")

    # 10. refusal
    refused = 0
    for bad in (Path("no-such-folder"), Path(__file__)):
        try:
            scan(bad)
        except FindError:
            refused += 1
        else:
            raise AssertionError(f"{bad} was scanned")
    try:
        digest(DATA_DIR)
    except FindError:
        refused += 1
    assert refused == 3
    print(f"  a missing folder, a file and a directory were all refused "
          f"({refused} refusals) instead of scanning nothing quietly")

    print()
    print("Cross-checks OK: 8 paths hold 8 physical files in 5 size buckets "
          "and 3 duplicate groups with 3 deletable copies worth 343 "
          "reclaimable bytes, the two empty files are one group of 2 worth 0 "
          "bytes that the legacy 'st_size == 0' skip never saw, a hard link "
          "shares its other name's inode so it is one file with two names and "
          "reclaims nothing where the legacy scan called it a duplicate, a "
          "legacy finder that keeps its hash map calls all 8 paths "
          "duplicates on a second scan -- including budget.csv and "
          "unique.txt, which have no copy -- and implies 1315 reclaimable "
          "bytes where 343 exist, 4/4 verification checks passed after "
          "re-reading every group, a second scan returned the same value "
          "rather than more groups, and a missing folder, a file and a "
          "directory were all refused")
    print("Demo completed successfully.")
    return 0
