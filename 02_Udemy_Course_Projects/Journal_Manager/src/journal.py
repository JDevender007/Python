"""A dated journal stored as JSON Lines, plus the legacy file it replaces.

The course version kept one line per entry in ``journal.txt`` and offered a
menu. It has two defects that the demo proves rather than describes.

**It never ran.** ``main_menu`` ends each branch with a ``break``, and the only
``if`` that contains it is not inside a loop:

    if choice == 4:
        print('Exiting...')
        break                 # SyntaxError: 'break' outside loop

That is a compile-time error, so the whole file is dead. ``LEGACY_SOURCE``
below keeps it verbatim and ``run_demo`` calls ``compile()`` on it to show the
interpreter rejecting it.

**Its search always said "No entries found".** The message sat in a ``for``
``else`` branch, and a ``for`` ``else`` runs when the loop finishes *without* a
``break`` — not when the loop found nothing. There was no ``break`` anywhere,
so the message printed after every search, including successful ones:

    for line in file:
        if search in line:
            print(line)
    else:
        print('No entries found')     # runs even when a line matched

**The replacement is a data format, not a menu.** Each entry is one JSON
object per line with an explicit ISO date, an integer id and a list of tags:

    {"id": 1, "date": "2024-03-04", "title": "First light",
     "body": "Set up the workbench.", "tags": ["workshop"]}

JSONL rather than a single JSON array because a damaged line is a line number
you can report, not a file you have to rewrite; and rather than free text
because a date you cannot parse is a date you cannot sort.

Titles and bodies are stored as written (trimmed), tags are case-folded and
sorted, ids are unique, and a save replaces the file atomically so a crash
cannot leave half a journal behind.

Fully offline, standard library only.
"""

from __future__ import annotations

import datetime
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

DATE_FORMAT = "%Y-%m-%d"


class JournalError(ValueError):
    """An entry, file or query that cannot be used."""


# --------------------------------------------------------------------------- #
# The legacy program, preserved so it can be proven dead
# --------------------------------------------------------------------------- #
#: Verbatim. Note the ``else:`` sits at four spaces while its ``for`` sits at
#: eight, so this is a syntax error before any of the logic matters.
LEGACY_SOURCE = '''filename = 'journal.txt'
def write_entry():
    entry = input('Enter your entry: ')
    with open(filename, 'a') as file:
        file.write(entry + '\\n')
    print('Entry added successfully')

def search_entry():
    search = input('Enter the search term: ')
    with open(filename, 'r') as file:
        for line in file:
            if search in line:
                print(line)
    else:
        print('No entries found')

def main_menu():
    choice = int(input('Enter your choice: '))
    if choice == 1:
        write_entry()
    elif choice == 4:
        print('Exiting...')
        break
if __name__ == '__main__':
    main_menu()
'''

#: First fix: ``else`` aligned under its ``for``. Now the ``break`` outside a
#: loop is the error the parser reports.
LEGACY_ALIGNED = LEGACY_SOURCE.replace(
    "                print(line)\n    else:\n        print('No entries found')",
    "                print(line)\n        else:\n            print('No entries found')")

#: Second fix: the ``break`` becomes a ``return``. It compiles, and the search
#: still prints "No entries found" after every query — the logic bug.
LEGACY_RUNNABLE = LEGACY_ALIGNED.replace(
    "        print('Exiting...')\n        break",
    "        print('Exiting...')\n        return")


def legacy_search(needle: str, lines: list[str]) -> list[str]:
    """The legacy search, printing replaced by a list so it can be asserted.

    Returns the matching lines *and* ``"No entries found"`` whenever the loop
    finishes, which is always — there is no ``break`` for the ``else`` to skip.
    """
    found: list[str] = []
    for line in lines:
        if needle in line:
            found.append(line)
    else:
        found.append("No entries found")
    return found


# --------------------------------------------------------------------------- #
# Entries
# --------------------------------------------------------------------------- #
def parse_date(value) -> datetime.date:
    """An ISO date, or a ``JournalError`` naming what was wrong."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if not isinstance(value, str):
        raise JournalError(f"date must be a string, got {type(value).__name__}")
    text = value.strip()
    try:
        parsed = datetime.datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        raise JournalError(f"date {value!r} is not {DATE_FORMAT}") from None
    if parsed.strftime(DATE_FORMAT) != text:
        # strptime accepts "2024-3-4"; the round trip does not, so the format
        # really is YYYY-MM-DD rather than merely parseable.
        raise JournalError(f"date {value!r} is not zero padded {DATE_FORMAT}")
    return parsed


def clean_tags(tags) -> tuple[str, ...]:
    """Case-folded, de-duplicated, sorted, non-empty tags."""
    if tags is None:
        return ()
    if isinstance(tags, str):
        tags = [part for part in tags.replace(",", " ").split()]
    try:
        items = list(tags)
    except TypeError:
        raise JournalError("tags must be a list or a string") from None
    cleaned: set[str] = set()
    for tag in items:
        if not isinstance(tag, str):
            raise JournalError(f"tag {tag!r} is not a string")
        name = tag.strip().casefold().lstrip("#")
        if not name:
            continue
        if any(character.isspace() for character in name):
            raise JournalError(f"tag {tag!r} contains whitespace")
        cleaned.add(name)
    return tuple(sorted(cleaned))


@dataclass(frozen=True)
class Entry:
    """One journal entry. Frozen, so a stored entry cannot drift."""

    id: int
    date: datetime.date
    title: str
    body: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.id, int) or isinstance(self.id, bool):
            raise JournalError("id must be an integer")
        if self.id < 1:
            raise JournalError(f"id must be positive, got {self.id}")
        if not isinstance(self.date, datetime.date):
            raise JournalError("date must be a datetime.date")
        title = self.title.strip() if isinstance(self.title, str) else ""
        if not title:
            raise JournalError("title must not be empty")
        if not isinstance(self.body, str):
            raise JournalError("body must be a string")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "body", self.body.strip())
        object.__setattr__(self, "tags", clean_tags(self.tags))

    # ----------------------------------------------------------------- #
    def words(self) -> int:
        """Body and title split on whitespace, empty words ignored."""
        text = f"{self.title} {self.body}".strip()
        return len(text.split()) if text else 0

    def matches(self, term: str) -> bool:
        """Case-insensitive substring match over title, body and tags."""
        needle = term.strip().casefold()
        if not needle:
            raise JournalError("search term must not be empty")
        haystack = " ".join([self.title, self.body, *self.tags]).casefold()
        return needle in haystack

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date.strftime(DATE_FORMAT),
            "title": self.title,
            "body": self.body,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Entry":
        if not isinstance(raw, dict):
            raise JournalError("entry must be a JSON object")
        missing = [key for key in ("id", "date", "title") if key not in raw]
        if missing:
            raise JournalError(f"entry is missing {', '.join(missing)}")
        extra = sorted(set(raw) - {"id", "date", "title", "body", "tags"})
        if extra:
            raise JournalError(f"entry has unknown field(s): {', '.join(extra)}")
        return cls(id=raw["id"], date=parse_date(raw["date"]),
                   title=raw["title"], body=raw.get("body", ""),
                   tags=raw.get("tags", ()))


def sort_entries(entries: list[Entry]) -> list[Entry]:
    """Chronological, then by id, so equal dates stay in creation order."""
    return sorted(entries, key=lambda entry: (entry.date, entry.id))


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
def load(path: str | Path) -> list[Entry]:
    """Read a JSONL journal. A bad line is reported with its number."""
    path = Path(path)
    if not path.exists():
        raise JournalError(f"journal not found: {path}")
    entries: list[Entry] = []
    for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JournalError(f"{path.name} line {number}: {exc.msg}") from None
        try:
            entries.append(Entry.from_dict(raw))
        except JournalError as exc:
            raise JournalError(f"{path.name} line {number}: {exc}") from None
    duplicate = _duplicate_ids(entries)
    if duplicate is not None:
        raise JournalError(f"{path.name} repeats id {duplicate}")
    return sort_entries(entries)


def _duplicate_ids(entries: list[Entry]) -> int | None:
    seen: set[int] = set()
    for entry in entries:
        if entry.id in seen:
            return entry.id
        seen.add(entry.id)
    return None


def dumps(entries: list[Entry]) -> str:
    """One JSON object per line, deterministic key order, trailing newline."""
    return "".join(json.dumps(entry.to_dict(), sort_keys=True) + "\n"
                   for entry in sort_entries(entries))


def save(path: str | Path, entries: list[Entry]) -> Path:
    """Write the journal atomically: a temporary file, then a replace.

    A crash mid-write leaves the old journal intact rather than a truncated
    one, which matters because a journal is append-only in spirit.
    """
    path = Path(path)
    duplicate = _duplicate_ids(entries)
    if duplicate is not None:
        raise JournalError(f"cannot save: id {duplicate} appears twice")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dumps(entries)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".journal-",
                                         suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return path


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
def next_id(entries: list[Entry]) -> int:
    """One past the highest id, so a deleted entry's id is not reused."""
    return max((entry.id for entry in entries), default=0) + 1


def add(entries: list[Entry], date, title: str, body: str = "",
        tags=()) -> list[Entry]:
    """A new list with one more entry. The input list is not modified."""
    entry = Entry(id=next_id(entries), date=parse_date(date), title=title,
                  body=body, tags=tags)
    return sort_entries([*entries, entry])


def search(entries: list[Entry], term: str) -> list[Entry]:
    """Every entry matching ``term``, in journal order."""
    if not isinstance(term, str) or not term.strip():
        raise JournalError("search term must not be empty")
    return [entry for entry in sort_entries(entries) if entry.matches(term)]


def by_tag(entries: list[Entry], tag: str) -> list[Entry]:
    """Every entry carrying ``tag``, compared case-insensitively."""
    wanted = clean_tags(tag)
    if not wanted:
        raise JournalError("tag must not be empty")
    if len(wanted) != 1:
        raise JournalError(f"expected one tag, got {len(wanted)}")
    return [entry for entry in sort_entries(entries) if wanted[0] in entry.tags]


def between(entries: list[Entry], start, end) -> list[Entry]:
    """Entries whose date falls in ``[start, end]``, inclusive."""
    first, last = parse_date(start), parse_date(end)
    if first > last:
        raise JournalError(f"start {first} is after end {last}")
    return [entry for entry in sort_entries(entries)
            if first <= entry.date <= last]


def tag_counts(entries: list[Entry]) -> dict[str, int]:
    """How many entries carry each tag, most used first then alphabetical."""
    counts: dict[str, int] = {}
    for entry in entries:
        for tag in entry.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def stats(entries: list[Entry]) -> dict:
    """Counts a reader would ask for, with honest nulls when empty."""
    ordered = sort_entries(entries)
    return {
        "entries": len(ordered),
        "first": ordered[0].date.strftime(DATE_FORMAT) if ordered else None,
        "last": ordered[-1].date.strftime(DATE_FORMAT) if ordered else None,
        "words": sum(entry.words() for entry in ordered),
        "tags": len(tag_counts(ordered)),
        "longest": max((entry.words() for entry in ordered), default=0),
    }


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_entry(entry: Entry) -> str:
    tags = f"  [{' '.join(entry.tags)}]" if entry.tags else ""
    lines = [f"#{entry.id:<3} {entry.date.strftime(DATE_FORMAT)}  "
             f"{entry.title}{tags}"]
    if entry.body:
        lines.append(f"     {entry.body}")
    return "\n".join(lines)


def render(entries: list[Entry]) -> str:
    if not entries:
        return "  (no entries)"
    return "\n\n".join(render_entry(entry) for entry in sort_entries(entries))


# --------------------------------------------------------------------------- #
# Bundled data
# --------------------------------------------------------------------------- #
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "journal.jsonl"


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 70)
    print(" JOURNAL MANAGER - the file that never compiled, on JSON Lines")
    print("=" * 70)

    # 1. the legacy program does not compile, and there are two reasons
    try:
        compile(LEGACY_SOURCE, "<legacy journal>", "exec")
    except SyntaxError as exc:
        assert "invalid syntax" in str(exc), str(exc)
        first_error = str(exc)
    else:
        raise AssertionError("the legacy source should not compile")
    assert LEGACY_ALIGNED != LEGACY_SOURCE
    try:
        compile(LEGACY_ALIGNED, "<legacy journal>", "exec")
    except SyntaxError as exc:
        assert "outside loop" in str(exc), str(exc)
        second_error = str(exc)
    else:
        raise AssertionError("the aligned source should still not compile")
    compile(LEGACY_RUNNABLE, "<legacy journal>", "exec")   # no exception
    print(f"  legacy source: {first_error}")
    print(f"  else aligned:  {second_error}")
    print("  break removed: compiles, so the logic bug can be seen")

    # 2. and its search message printed after every query, matches included
    lines = ["bought coffee", "wrote an entry"]
    hit = legacy_search("coffee", lines)
    miss = legacy_search("banana", lines)
    assert hit == ["bought coffee", "No entries found"], hit
    assert miss == ["No entries found"], miss
    print(f"  a search that matched still appended 'No entries found' "
          f"({len(hit)} items for 1 match)")

    # 3. the replacement: explicit dates, ids, tags
    entries: list[Entry] = []
    entries = add(entries, "2024-03-04", "First light",
                  "Set up the workbench and labelled the drawers.",
                  ["workshop", "setup"])
    entries = add(entries, "2024-03-06", "Rain all day",
                  "Stayed in, read the manual, sketched a shelf.",
                  ["reading"])
    entries = add(entries, "2024-03-09", "Shelf done",
                  "Cut, drilled, sanded. Two shelves fit.",
                  ["workshop", "build"])
    assert [entry.id for entry in entries] == [1, 2, 3]
    assert [entry.date.strftime(DATE_FORMAT) for entry in entries] == \
        ["2024-03-04", "2024-03-06", "2024-03-09"]
    print(f"  {len(entries)} entries added with ids "
          f"{[entry.id for entry in entries]}")

    # 4. tags are case-folded, de-duplicated and sorted
    tagged = Entry(id=9, date=datetime.date(2024, 4, 1), title="Tag rules",
                   body="", tags=[" Build ", "build", "#workShop", ""])
    assert tagged.tags == ("build", "workshop"), tagged.tags
    assert Entry(id=9, date=datetime.date(2024, 4, 1), title="x").tags == ()
    print(f"  tags normalised: {tagged.tags}")

    # 5. bad entries are refused at construction, not at read time
    for kwargs, needle in (
            ({"id": 0, "date": datetime.date(2024, 1, 1), "title": "x"},
             "must be positive"),
            ({"id": 1, "date": datetime.date(2024, 1, 1), "title": "   "},
             "must not be empty"),
            ({"id": 1, "date": "2024-01-01", "title": "x"},
             "must be a datetime.date"),
            ({"id": 1, "date": datetime.date(2024, 1, 1), "title": "x",
              "tags": ["two words"]}, "contains whitespace")):
        try:
            Entry(**kwargs)
        except JournalError as exc:
            assert needle in str(exc), (kwargs, str(exc))
        else:
            raise AssertionError(f"{kwargs} should have been refused")

    # 6. dates are parsed, not guessed
    assert parse_date("2024-03-04") == datetime.date(2024, 3, 4)
    for bad in ("2024-3-4", "04/03/2024", "2024-02-31", ""):
        try:
            parse_date(bad)
        except JournalError as exc:
            assert "is not" in str(exc)
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    print("  4 non-ISO dates refused; only YYYY-MM-DD is accepted")

    # 7. save and reload round-trips byte for byte
    with tempfile.TemporaryDirectory(prefix="journal-") as folder:
        path = Path(folder) / "journal.jsonl"
        save(path, entries)
        first_bytes = path.read_bytes()
        assert first_bytes.decode("utf-8").count("\n") == 3
        reloaded = load(path)
        assert reloaded == entries, "round trip changed the entries"
        save(path, reloaded)
        assert path.read_bytes() == first_bytes, "a second save differed"
        print(f"  saved {len(entries)} entries, reloaded identical, "
              f"{len(first_bytes)} bytes")

        # 8. a damaged line is reported by number, not silently skipped
        path.write_text(first_bytes.decode("utf-8") + "{not json}\n",
                        encoding="utf-8")
        try:
            load(path)
        except JournalError as exc:
            assert "line 4" in str(exc), str(exc)
        else:
            raise AssertionError("a damaged line should have been refused")

        # 9. a duplicate id is refused on load and on save
        path.write_text('{"id": 1, "date": "2024-01-01", "title": "a"}\n'
                        '{"id": 1, "date": "2024-01-02", "title": "b"}\n',
                        encoding="utf-8")
        try:
            load(path)
        except JournalError as exc:
            assert "repeats id 1" in str(exc)
        else:
            raise AssertionError("a duplicate id should have been refused")
        try:
            save(path, [entries[0], entries[0]])
        except JournalError as exc:
            assert "appears twice" in str(exc)
        else:
            raise AssertionError("saving a duplicate id should have been refused")
        print("  a damaged line names its line number; duplicate ids refused")

    # 10. search is case-insensitive across title, body and tags
    assert [entry.id for entry in search(entries, "SHELF")] == [2, 3]
    assert [entry.id for entry in search(entries, "workshop")] == [1, 3]
    assert search(entries, "banana") == []
    for bad in ("", "   ", None):
        try:
            search(entries, bad)
        except JournalError as exc:
            assert "must not be empty" in str(exc)
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    print(f"  search 'shelf' -> ids {[e.id for e in search(entries, 'shelf')]},"
          f" 'banana' -> none")

    # 11. tag and date queries
    assert [entry.id for entry in by_tag(entries, "WORKSHOP")] == [1, 3]
    assert by_tag(entries, "reading") == [entries[1]]
    assert [entry.id for entry in between(entries, "2024-03-05",
                                          "2024-03-09")] == [2, 3]
    assert between(entries, "2024-03-04", "2024-03-04") == [entries[0]]
    try:
        between(entries, "2024-03-09", "2024-03-01")
    except JournalError as exc:
        assert "is after end" in str(exc)
    else:
        raise AssertionError("a reversed range should have been refused")
    assert tag_counts(entries) == {"workshop": 2, "build": 1, "reading": 1,
                                  "setup": 1}
    print(f"  tag counts {tag_counts(entries)}")

    # 12. stats and the empty case, with nulls rather than invented zeros
    summary = stats(entries)
    assert summary["entries"] == 3
    assert summary["first"] == "2024-03-04" and summary["last"] == "2024-03-09"
    assert summary["tags"] == 4
    assert summary["longest"] == entries[1].words()
    empty = stats([])
    assert empty["entries"] == 0 and empty["first"] is None
    assert empty["words"] == 0 and empty["longest"] == 0
    print(f"  stats {summary}")

    # 13. next_id does not reuse a removed id
    assert next_id([]) == 1
    assert next_id(entries) == 4
    assert next_id([entries[0], entries[2]]) == 4

    # 14. the bundled journal loads and satisfies its own invariants
    bundled = load(DATA_FILE)
    assert len(bundled) == 6, len(bundled)
    assert [entry.id for entry in bundled] == [1, 2, 3, 4, 5, 6]
    assert bundled == sort_entries(bundled), "bundled file is not sorted"
    dates = [entry.date for entry in bundled]
    assert dates == sorted(dates)
    assert sum(entry.words() for entry in bundled) == stats(bundled)["words"]
    assert all(entry.title for entry in bundled)
    assert len(search(bundled, "shelf")) >= 1
    print(f"  bundled journal: {len(bundled)} entries, "
          f"{stats(bundled)['words']} words, {stats(bundled)['tags']} tags")

    # 15. validation happens before anything is written
    missing = Path(tempfile.gettempdir()) / "definitely-not-a-journal.jsonl"
    try:
        load(missing)
    except JournalError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("a missing journal should have been refused")

    print()
    print("Cross-checks OK: the legacy file is a SyntaxError twice over (an "
          "else at the wrong depth, then a break outside its loop) and its "
          "for/else search appended 'No entries found' even after a match, "
          "3 entries added with sequential ids, tags case-folded and sorted, "
          "4 bad entries and 4 non-ISO dates refused, a save/reload round "
          "trip byte-identical, a damaged line reported by number, duplicate "
          "ids refused on load and save, case-insensitive search and tag/date "
          "queries, stats with honest nulls when empty, ids never reused, and "
          "a 6-entry bundled journal in date order")
    print("\nDemo completed successfully.")
    return 0
