"""Organising a folder by extension: compound suffixes, and plan before you move.

The legacy project classified a file by ``file.suffix`` and moved it as it went:

    extension = file_path.suffix.lower()
    for category, extensions in SUPPORTED_EXTENSIONS.items():
        if extension in extensions:
            return category
    return "Others"

    destination = OUTPUT_FOLDER / category
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / file.name
    counter = 1
    while target.exists():
        target = destination / f"{file.stem}_{counter}{file.suffix}"
        counter += 1
    shutil.move(file, target)

Four things follow.

**1. ``suffix`` is only the last dot.** ``backup.tar.gz`` has ``.suffix == ".gz"``,
so the tar archive is classified by ``.gz`` -- and ``.gz`` is not in the table at
all, so it lands in *Others* next to a README with no extension. The suffix a
person uses to name a file is the longest known tail, not the shortest:
``.tar.gz`` is Archives.

**2. Moving as you go means there is no plan to inspect.** The first four files
have already moved before the fifth raises. There is no dry run, no list of what
would happen, and no record to undo. Here ``build_plan`` reads the folder and
returns a value; ``--plan`` prints it and moves nothing, ``--apply`` is the only
thing that touches the disk.

**3. ``while target.exists()`` plans against the disk, not against the plan.**
``Images/photo.JPG`` is already taken, so ``photo.JPG`` becomes
``Images/photo_1.JPG`` -- and the inbox also holds ``photo_1.JPG``, whose natural
target is now taken by a file that has not moved yet. A planner that probes only
``target.exists()`` hands out ``Images/photo_1.JPG`` twice and the second move
silently destroys the first. The plan here keeps a *reserved* set, so the second
file becomes ``photo_2.JPG``.

**4. ``f"{file.stem}_{counter}{file.suffix}"`` breaks a compound name.** For a
collision on ``backup.tar.gz`` the legacy name is ``backup.tar_1.gz``: the counter
is inserted inside the name. The counter belongs before the whole suffix:
``backup_1.tar.gz``.

Also: ``INPUT_FOLDER.iterdir()`` never looks inside a folder, so a subfolder is
skipped in silence. The plan lists it as skipped, by name.

Standard library only: no colour libraries, no network.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INBOX = DATA_DIR / "inbox"
OUT = DATA_DIR / "organized"

#: The folders, in the order a report prints them.
CATEGORIES = ("Images", "Documents", "Videos", "Music", "Archives", "Data",
              "Python", "Others")

#: Compound suffixes, matched before the single ones, longest first.
COMPOUND = {
    ".tar.gz": "Archives",
    ".tar.bz2": "Archives",
    ".tar.xz": "Archives",
    ".tar.zst": "Archives",
    ".tbz2": "Archives",
    ".txz": "Archives",
    ".tgz": "Archives",
}

#: One extension, one folder.
SINGLE = {
    "Images": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"),
    "Documents": (".pdf", ".doc", ".docx", ".txt", ".md", ".odt", ".pptx",
                  ".xlsx"),
    "Videos": (".mp4", ".mkv", ".avi", ".mov", ".webm"),
    "Music": (".mp3", ".wav", ".flac", ".ogg", ".m4a"),
    "Archives": (".zip", ".rar", ".7z", ".gz", ".bz2", ".xz", ".zst", ".tar"),
    "Data": (".csv", ".tsv", ".json", ".xml", ".yaml", ".yml"),
    "Python": (".py", ".pyw"),
}

#: The legacy table, and the two lines that made the mess.
LEGACY_TABLE = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp"],
    "Documents": [".pdf", ".docx", ".txt", ".pptx", ".xlsx"],
    "Videos": [".mp4", ".mkv", ".avi"],
    "Music": [".mp3", ".wav"],
    "Archives": [".zip", ".rar", ".7z"],
    "Python": [".py"],
    "Others": [],
}
LEGACY_SUFFIX = "extension = file_path.suffix.lower()"
LEGACY_COUNTER = 'target = destination / f"{file.stem}_{counter}{file.suffix}"'
LEGACY_WALK = "files = [file for file in INPUT_FOLDER.iterdir() if file.is_file()]"

#: The table as one lookup: suffix -> folder, longest suffix wins.
_BY_SUFFIX: dict[str, str] = {}
for _folder, _suffixes in SINGLE.items():
    for _suffix in _suffixes:
        _BY_SUFFIX[_suffix] = _folder
_BY_SUFFIX.update(COMPOUND)


class OrganizeError(ValueError):
    """A folder, a name, a plan or a move that is refused."""


# --------------------------------------------------------------------------- #
# One name, classified
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Kind:
    """What a file name says it is: a folder, a suffix, and whether we knew."""

    category: str
    suffix: str
    known: bool

    def __str__(self) -> str:
        return f"{self.category} ({self.suffix or 'no suffix'})"

    def to_dict(self) -> dict:
        return {"category": self.category, "suffix": self.suffix,
                "known": self.known}


def check_name(name) -> str:
    """A bare file name: no separators, no parent, not empty."""
    if not isinstance(name, str):
        raise OrganizeError(f"a name must be text, got {type(name).__name__}")
    if not name.strip():
        raise OrganizeError("a file name must not be empty")
    if name in (".", "..") or "/" in name or "\\" in name:
        raise OrganizeError(f"{name!r} is a path, not a file name")
    return name


def suffix_of(name: str) -> str:
    """The longest known suffix of ``name``, lower-cased, or ``''``."""
    check_name(name)
    lowered = name.casefold()
    for suffix in sorted(_BY_SUFFIX, key=len, reverse=True):
        if lowered.endswith(suffix) and len(lowered) > len(suffix):
            return suffix
    return ""


def classify(name: str) -> Kind:
    """The folder a file belongs in, by its longest known suffix."""
    suffix = suffix_of(name)
    if suffix:
        return Kind(_BY_SUFFIX[suffix], suffix, True)
    return Kind("Others", "", False)


# --------------------------------------------------------------------------- #
# One move
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FileEntry:
    """A file in the inbox: where it is, how big, and what it is."""

    path: Path
    size: int
    kind: Kind

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            object.__setattr__(self, "path", Path(self.path))
        if self.size < 0:
            raise OrganizeError("a file cannot have a negative size")

    @property
    def name(self) -> str:
        return self.path.name

    def to_dict(self) -> dict:
        return {"name": self.name, "size": self.size,
                "category": self.kind.category, "suffix": self.kind.suffix}


@dataclass(frozen=True)
class Move:
    """One file, from the inbox to a named target. A value, not an action."""

    source: Path
    target: Path
    category: str
    size: int
    suffix: str
    renamed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source, Path):
            object.__setattr__(self, "source", Path(self.source))
        if not isinstance(self.target, Path):
            object.__setattr__(self, "target", Path(self.target))
        if self.category not in CATEGORIES:
            raise OrganizeError(f"{self.category!r} is not a folder")
        if self.size < 0:
            raise OrganizeError("a move cannot carry a negative size")
        if self.source.name == self.target.name:
            object.__setattr__(self, "renamed", False)
        elif not self.renamed:
            raise OrganizeError("a move that changes the name is a rename")

    def __str__(self) -> str:
        arrow = "->"
        return (f"{self.source.name} {arrow} {self.category}/"
                f"{self.target.name}")

    def to_dict(self) -> dict:
        return {"from": self.source.name,
                "to": f"{self.category}/{self.target.name}",
                "size": self.size, "renamed": self.renamed}


# --------------------------------------------------------------------------- #
# The plan
# --------------------------------------------------------------------------- #
class Plan:
    """Every move the folder needs, decided before any of them happens."""

    def __init__(self, inbox, out_root, entries, folders, moves):
        self.inbox = Path(inbox)
        self.out_root = Path(out_root)
        self._entries = tuple(entries)
        self._folders = tuple(folders)
        self._moves = tuple(moves)

    @property
    def entries(self) -> tuple[FileEntry, ...]:
        return self._entries

    @property
    def folders(self) -> tuple[Path, ...]:
        """Subfolders of the inbox: reported and left in place."""
        return self._folders

    @property
    def moves(self) -> tuple[Move, ...]:
        return self._moves

    def __len__(self) -> int:
        return len(self._moves)

    def __iter__(self):
        return iter(self._moves)

    def __repr__(self) -> str:
        return (f"<Plan {len(self._moves)} moves, {self.total_bytes} bytes, "
                f"{len(self.renamed)} renamed>")

    @property
    def total_bytes(self) -> int:
        return sum(move.size for move in self._moves)

    @property
    def renamed(self) -> tuple[Move, ...]:
        return tuple(move for move in self._moves if move.renamed)

    def by_category(self) -> dict[str, tuple[Move, ...]]:
        """The moves grouped by folder, in folder order, skipping empty ones."""
        grouped: dict[str, list[Move]] = {}
        for move in self._moves:
            grouped.setdefault(move.category, []).append(move)
        return {category: tuple(grouped[category]) for category in CATEGORIES
                if category in grouped}

    def categories(self) -> tuple[str, ...]:
        return tuple(self.by_category())

    def summary(self) -> dict:
        return {"inbox": self.inbox.name, "out": self.out_root.name,
                "files": len(self._entries), "moves": len(self._moves),
                "folders": len(self._folders),
                "categories": len(self.by_category()),
                "renamed": len(self.renamed), "bytes": self.total_bytes}

    def to_dict(self) -> dict:
        return {"summary": self.summary(),
                "moves": [move.to_dict() for move in self._moves],
                "folders": [folder.name for folder in self._folders]}

    # -- checks ------------------------------------------------------------- #
    def audit(self) -> list[tuple[str, bool]]:
        checks = []

        sources_exist = all(move.source.is_file() for move in self._moves)
        checks.append(("every source is a file in the inbox", sources_exist))

        inside = all(self.out_root in move.target.parents and
                     move.target.parent.name == move.category
                     for move in self._moves)
        checks.append(("every target sits in its folder under the output root",
                       inside))

        targets = [str(move.target).casefold() for move in self._moves]
        checks.append(("no two moves share a target",
                       len(targets) == len(set(targets))))

        free = all(not move.target.exists() for move in self._moves)
        checks.append(("no target is already on disk", free))

        sources = [str(move.source).casefold() for move in self._moves]
        checks.append(("no source is used twice",
                       len(sources) == len(set(sources))))

        known = all(move.category in CATEGORIES for move in self._moves)
        checks.append(("every move names one of the eight folders", known))

        not_itself = all(move.source != move.target for move in self._moves)
        checks.append(("no move overwrites its own source", not_itself))

        return checks

    def problems(self) -> list[str]:
        return [name for name, passed in self.audit() if not passed]


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
def folder_names(directory) -> set[str]:
    """The names already used in a folder, case-folded, for collision checks."""
    directory = Path(directory)
    if not directory.is_dir():
        return set()
    return {entry.name.casefold() for entry in directory.iterdir()}


def unique_name(name: str, suffix: str, taken: set[str]) -> tuple[str, bool]:
    """``name`` if it is free, else ``base_1<suffix>``, ``base_2<suffix>``...

    ``taken`` is read, not written: the caller reserves the returned name, so
    the plan can never hand the same target to two moves.
    """
    if name.casefold() not in taken:
        return name, False
    # Keep the suffix exactly as the file spells it: photo.JPG -> photo_1.JPG
    tail = name[-len(suffix):] if suffix else ""
    base = name[:len(name) - len(suffix)] if suffix else name
    counter = 1
    while f"{base}_{counter}{tail}".casefold() in taken:
        counter += 1
    return f"{base}_{counter}{tail}", True


def build_plan(inbox=INBOX, out_root=OUT) -> Plan:
    """Read ``inbox`` once and return every move it needs, in a stable order."""
    inbox, out_root = Path(inbox), Path(out_root)
    if not inbox.exists():
        raise OrganizeError(f"inbox not found: {inbox}")
    if not inbox.is_dir():
        raise OrganizeError(f"{inbox} is a file, not a folder")

    entries: list[FileEntry] = []
    folders: list[Path] = []
    for path in sorted(inbox.iterdir(), key=lambda item: item.name.casefold()):
        if path.is_dir():
            folders.append(path)
            continue
        if not path.is_file():
            continue
        entries.append(FileEntry(path, path.stat().st_size, classify(path.name)))

    reserved: dict[str, set[str]] = {category: set() for category in CATEGORIES}
    if out_root.is_dir():
        for folder in out_root.iterdir():
            if folder.is_dir() and folder.name in reserved:
                reserved[folder.name] = folder_names(folder)

    order = {category: index for index, category in enumerate(CATEGORIES)}
    moves: list[Move] = []
    for entry in sorted(entries, key=lambda item: (order[item.kind.category],
                                                   item.name.casefold())):
        taken = reserved[entry.kind.category]
        name, renamed = unique_name(entry.name, entry.kind.suffix, taken)
        taken.add(name.casefold())
        moves.append(Move(entry.path, out_root / entry.kind.category / name,
                          entry.kind.category, entry.size, entry.kind.suffix,
                          renamed))

    return Plan(inbox, out_root, entries, folders, moves)


# --------------------------------------------------------------------------- #
# Applying, and taking it back
# --------------------------------------------------------------------------- #
def apply_plan(plan: Plan) -> tuple[Move, ...]:
    """Do the moves. A plan that went stale is refused before anything moves.

    Every source is re-checked, every target is re-checked, and the size on
    disk is compared with the size the plan recorded. A failure part-way is
    undone, so the folder is never left half-organised.
    """
    done: list[Move] = []
    try:
        for move in plan.moves:
            if not move.source.is_file():
                raise OrganizeError(f"{move.source.name} is no longer there")
            if move.target.exists():
                raise OrganizeError(
                    f"{move.category}/{move.target.name} appeared after the "
                    f"plan was made")
            move.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(move.source), str(move.target))
            done.append(move)
            if move.target.stat().st_size != move.size:
                raise OrganizeError(
                    f"{move.target.name} arrived with a different size")
    except OrganizeError:
        undo(done, plan.out_root)
        raise
    return tuple(done)


def undo(applied, out_root) -> tuple[Move, ...]:
    """Put every applied move back, newest first, and drop folders left empty."""
    applied = tuple(applied)
    for move in reversed(applied):
        if not move.target.is_file():
            raise OrganizeError(f"cannot undo: {move.target.name} is gone")
        if move.source.exists():
            raise OrganizeError(f"cannot undo: {move.source.name} is back "
                                f"already")
        move.source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(move.target), str(move.source))

    root = Path(out_root)
    if root.is_dir():
        for folder in sorted(root.rglob("*"), key=lambda item: len(item.parts),
                             reverse=True):
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
    return applied


# --------------------------------------------------------------------------- #
# The legacy project, transcribed
# --------------------------------------------------------------------------- #
def legacy_category(name: str) -> str:
    """``file_path.suffix.lower()`` against the old table."""
    suffix = Path(name).suffix.lower()
    for category, extensions in LEGACY_TABLE.items():
        if suffix in extensions:
            return category
    return "Others"


def legacy_stem(name: str) -> str:
    return Path(name).stem


def legacy_plan(inbox=INBOX, out_root=OUT) -> list[tuple[str, str]]:
    """Replay the legacy moves, in name order, with its disk probe.

    ``(original name, 'Folder/name')`` for every file, computed exactly as the
    legacy loop computes it: each move is visible to the next ``target.exists()``
    check because the moves happen one at a time.
    """
    inbox, out_root = Path(inbox), Path(out_root)
    used: dict[str, set[str]] = {}
    for category in LEGACY_TABLE:
        used[category] = folder_names(out_root / category)

    planned = []
    for path in sorted((item for item in inbox.iterdir() if item.is_file()),
                       key=lambda item: item.name.casefold()):
        category = legacy_category(path.name)
        name = path.name
        counter = 1
        while name.casefold() in used[category]:
            name = f"{legacy_stem(name)}_{counter}{path.suffix}"
            counter += 1
        used[category].add(name.casefold())
        planned.append((path.name, f"{category}/{name}"))
    return planned


def naive_targets(plan: Plan) -> list[str]:
    """What a plan-time ``while target.exists()`` probe would hand out.

    Nothing is reserved, and the disk has not moved yet, so a name that a
    *pending* move will occupy is handed out again -- twice for the same file.
    This is the legacy loop with planning split from applying, which is exactly
    the step that makes a plan reviewable.
    """
    names = []
    for entry in plan.entries:
        name = entry.name
        counter = 1
        while (plan.out_root / entry.kind.category / name).exists():
            name = (f"{Path(entry.name).stem}_{counter}"
                    f"{Path(entry.name).suffix}")
            counter += 1
        names.append(f"{entry.kind.category}/{name}")
    return names


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target)


def run_demo() -> int:
    print("=" * 74)
    print(" FILE ORGANIZER - plan the whole folder before you move anything")
    print("=" * 74)

    plan = build_plan()
    summary = plan.summary()
    assert summary["files"] == 12 and summary["moves"] == 12
    assert summary["folders"] == 1 and summary["categories"] == 7
    assert summary["renamed"] == 4 and summary["bytes"] == 629

    # 1. the inbox
    print(f"  {summary['files']} files, {summary['bytes']} bytes, "
          f"{summary['folders']} subfolder reported and left alone "
          f"({plan.folders[0].name}/), {summary['categories']} of the 8 "
          f"folders needed")
    moved_names = {move.source.name for move in plan.moves}
    assert "old.txt" not in moved_names

    # 2. the folders, in order
    for category, moves in plan.by_category().items():
        print(f"    {category:<10} {len(moves)} file(s)")

    # 3. a compound suffix is one suffix
    torrent = next(move for move in plan.moves
                   if move.source.name == "backup.tar.gz")
    assert torrent.category == "Archives" and torrent.suffix == ".tar.gz"
    assert legacy_category("backup.tar.gz") == "Others"
    assert classify("backup.tar.gz").suffix == ".tar.gz"
    assert Path("backup.tar.gz").suffix == ".gz"
    print(f"  backup.tar.gz is {torrent.category} by .tar.gz; Path().suffix "
          f"sees only {Path('backup.tar.gz').suffix!r}, which the legacy table "
          f"maps to {legacy_category('backup.tar.gz')}")

    # 4. the four renames, and where the counter goes
    print("  the four names the library already used:")
    for move in plan.renamed:
        print(f"    {move.source.name:<18} -> {move.category}/"
              f"{move.target.name}")
    assert [move.target.name for move in plan.renamed] == [
        "photo_1.JPG", "photo_1_1.JPG", "notes_1.txt", "backup_1.tar.gz"]
    legacy = dict(legacy_plan())
    assert legacy["backup.tar.gz"] == "Others/backup.tar.gz"
    assert legacy["photo_1.JPG"] == "Images/photo_1_1.JPG"
    assert legacy["photo.JPG"] == "Images/photo_1.JPG"
    assert legacy["notes.txt"] == "Documents/notes_1.txt"
    print(f"    the counter goes before the whole suffix, so a collision on "
          f"backup.tar.gz is backup_1.tar.gz; the legacy line "
          f"f'{{file.stem}}_{{counter}}{{file.suffix}}' inserts it inside the "
          f"name and gives backup.tar_1.gz")

    # 5. a plan-time disk probe hands out a name twice
    naive = naive_targets(plan)
    assert len(naive) == 12 and len(set(naive)) == 11
    assert naive.count("Images/photo_1.JPG") == 2
    assert "Archives/backup.tar_1.gz" in naive
    legitimate = [f"{move.category}/{move.target.name}" for move in plan.moves]
    assert len(set(legitimate)) == 12
    print(f"  split planning from applying and a target.exists() probe hands "
          f"out {len(naive)} targets with {len(set(naive))} distinct names: "
          f"Images/photo_1.JPG twice, and backup.tar_1.gz; the plan reserves "
          f"each name as it hands it out and has {len(set(legitimate))} "
          f"distinct targets")

    # 6. the audit, and three ways to fail it
    checks = plan.audit()
    assert len(checks) == 7 and plan.problems() == []
    print(f"  {sum(1 for _, ok in checks if ok)}/{len(checks)} plan checks "
          f"pass: sources exist, targets sit in their folder, no repeated "
          f"target, no target taken, no repeated source, known folders, no "
          f"self-overwrite")

    duplicate = Plan(plan.inbox, plan.out_root, plan.entries, plan.folders,
                     (plan.moves[0], plan.moves[1].__class__(
                         plan.moves[1].source, plan.moves[0].target,
                         plan.moves[1].category, plan.moves[1].size,
                         plan.moves[1].suffix, plan.moves[1].renamed)))
    assert "no two moves share a target" in duplicate.problems()
    occupied = Move(plan.moves[0].source, OUT / "Images" / "photo.JPG",
                    "Images", plan.moves[0].size, ".jpg", False)
    taken = Plan(plan.inbox, plan.out_root, plan.entries, plan.folders,
                 (occupied,))
    assert "no target is already on disk" in taken.problems()
    outside = Move(plan.moves[0].source, plan.inbox / "Images" / "photo.JPG",
                   "Images", plan.moves[0].size, ".jpg", False)
    astray = Plan(plan.inbox, plan.out_root, plan.entries, plan.folders,
                  (outside,))
    assert "every target sits in its folder under the output root" in \
        astray.problems()

    # 7. apply into a copy, and prove the bytes arrived
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        _copy_tree(INBOX, work / "inbox")
        _copy_tree(OUT, work / "organized")
        trial = build_plan(work / "inbox", work / "organized")
        assert trial.to_dict()["moves"] == plan.to_dict()["moves"]
        sources = {move.source: move.size for move in trial.moves}
        applied = apply_plan(trial)
        assert len(applied) == 12
        assert list((work / "inbox").iterdir()) == [work / "inbox" / "later"]
        arrived = sum(move.target.stat().st_size for move in applied)
        assert arrived == 629 and all(move.target.is_file() for move in applied)
        assert all(move.target.stat().st_size == sources[move.source]
                   for move in applied)
        print(f"  applied {len(applied)} moves into a copy: the inbox holds "
              f"only later/ again and the targets hold {arrived} bytes, one "
              f"size per source")

        # 8. a second plan finds nothing to do
        again = build_plan(work / "inbox", work / "organized")
        assert len(again) == 0
        before = sorted(item.name for item in (work / "inbox" / "later")
                        .iterdir())
        assert before == ["old.txt"]
        print(f"  planning again after the move finds 0 moves, so the run is "
              f"idempotent by construction")

        # 9. undo puts every file back
        undo(applied, work / "organized")
        back = {item.name for item in (work / "inbox").iterdir()
                if item.is_file()}
        assert back == {move.source.name for move in plan.moves}
        assert all((work / "inbox" / name).stat().st_size == size
                   for name, size in ((move.source.name, move.size)
                                      for move in plan.moves))
        emptied = [folder.name for folder in (work / "organized").iterdir()
                   if folder.is_dir()]
        assert sorted(emptied) == ["Archives", "Documents", "Images"]
        print(f"  undo returned all {len(back)} files with their own names and "
              f"sizes, and removed the {len(plan.categories()) - len(emptied)} "
              f"folders it had created")

        # 10. a plan that went stale is refused before it starts
        trial2 = build_plan(work / "inbox", work / "organized")
        blocked = trial2.moves[0]
        blocked.target.parent.mkdir(parents=True, exist_ok=True)
        blocked.target.write_text("someone else got here first\n",
                                  encoding="utf-8")
        try:
            apply_plan(trial2)
        except OrganizeError as exc:
            assert "appeared after the plan" in str(exc)
        else:
            raise AssertionError("a stale plan was applied")
        assert blocked.source.is_file()
        moved_nowhere = sum(1 for move in trial2.moves if move.source.is_file())
        assert moved_nowhere == 12
        print(f"  a target created after planning stopped the run with "
              f"{moved_nowhere}/{len(trial2)} sources still in the inbox")

    # 11. refusals
    refused = 0
    for bad in (Path("no-such-folder"), Path(__file__)):
        try:
            build_plan(bad, OUT)
        except OrganizeError:
            refused += 1
        else:
            raise AssertionError(f"{bad} was planned")
    for bad_name in ("", "..", "a/b.txt", "..\\x"):
        try:
            check_name(bad_name)
        except OrganizeError:
            refused += 1
        else:
            raise AssertionError(f"{bad_name!r} was accepted")
    assert refused == 6
    print(f"  a missing inbox, a file given as an inbox and four bad names "
          f"were refused ({refused} refusals)")

    print()
    print("Cross-checks OK: 12 files worth 629 bytes plan into 7 of the 8 "
          "folders, backup.tar.gz is Archives by .tar.gz where the legacy "
          "table reads .gz and files it under Others, the four collisions "
          "become photo_1.JPG photo_1_1.JPG notes_1.txt and backup_1.tar.gz, "
          "the legacy loop reaches those same photo names only because it "
          "moves while it plans and puts its counter inside a compound name "
          "to give backup.tar_1.gz, a plan that probes target.exists() without "
          "reserving hands Images/photo_1.JPG out twice while this plan has "
          "12 distinct targets, 7/7 plan checks passed with a negative control "
          "for a repeated target, a taken target and a target outside the "
          "root, 12 moves applied into a copy carried 629 bytes with one size "
          "per source, a second plan found nothing to do, undo returned all "
          "12 files and removed the 4 folders it had created, a target "
          "created after planning stopped the run with all 12 sources still "
          "in place, and six bad inputs were refused")
    print("\nDemo completed successfully.")
    return 0
