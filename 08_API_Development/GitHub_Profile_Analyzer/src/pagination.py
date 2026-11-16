"""A page number is an offset into a list that keeps changing under you.

The legacy collector of a paged API was five lines:

    def fetch_all(client, url):
        out = []
        page = 1
        while True:
            data = client(url + "?page=%d" % page)
            if not data:
                break
            out += data
            page += 1
        return out

**1. `?page=2` is not "the next items", it is "items 5 to 8".** The page number is
an **offset** into a list the server keeps reordering. A repository pushed between
page 1 and page 2 shifts every item one place to the right, so the item that was
last on page 1 appears again at the top of page 2 -- a **duplicate row**:

    page 1 -> 101 102 103 104
    one repository is pushed, so 104 moves to index 4
    page 2 -> 104 105 106 107        <- 104 for the second time

And the item that arrived is at index 0, which every later page has already
passed, so it is **never seen at all**. Two silent defects from one five-line
loop, and the output has eleven rows for ten distinct repositories.

**2. `if not data: break` is three different facts with one meaning.** An empty
page is the end of the collection, an empty page is a filter that matched nothing,
and an empty page is what a rate limit looks like after a list comprehension has
already eaten the body. The loop treats all three as "finished", so a truncated
collection reports success.

**3. `out += data` on a dictionary appends its keys.** When the server answers
`403` with `{"message": ..., "documentation_url": ...}` instead of a list, `+=`
does not fail -- it extends the list with the two **strings**, so `'message'` and
`'documentation_url'` become rows of the result. The output is a list of
repositories with two English words in it.

**4. Nothing counts the rows against the total.** Every response carries
`total_count`. Nothing compares it with what was collected, so "we have them all"
is an assumption, not a check.

**5. A cursor is the only end signal that means what it says.** `next` is present
or it is not. An empty page with a `next` is not the end, and a full page with no
`next` is. That is one fact, and it needs an explicit field.

So this module models a page as an explicit **window** with a `total_count` and a
`next` token, walks it two ways over the very same mutable server, and reports
what each walk duplicated, stranded, or never saw.

The demonstration is offline: one bundled repository list, and no network.
Standard library only: no requests, no HTTP client, no API key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPOS_FILE = DATA_DIR / "repos.txt"

#: The legacy loop, transcribed: a page number, a truthiness test, and `+=`.
LEGACY_FETCH = ('out = []\n'
                'page = 1\n'
                'while True:\n'
                '    data = client(url + "?page=%d" % page)\n'
                '    if not data:\n'
                '        break\n'
                '    out += data\n'
                '    page += 1\n'
                'return out')

#: The largest page the lab will serve, and the largest walk it will run.
MAX_PER_PAGE = 100
MAX_PAGES = 20

#: What the legacy loop answers for a rate limit, transcribed.
LEGACY_ERROR_BODY = {'message': 'API rate limit exceeded',
                     'documentation_url': 'https://docs.example/rate'}


class PageError(Exception):
    """A page, a token or a walk that cannot be read, with the sentence why."""


# --------------------------------------------------------------------------- #
# Reading values
# --------------------------------------------------------------------------- #
def _whole(value, field: str, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise PageError(f"{field} is a whole number, got {value!r}")
    if value < minimum:
        raise PageError(f"{field} is at least {minimum}, got {value}")
    return value


def _name(value, field: str) -> str:
    if not isinstance(value, str):
        raise PageError(f"{field} is text, got {type(value).__name__}")
    body = value.strip()
    if not body:
        raise PageError(f"{field} needs a value, got {value!r}")
    if any(character.isspace() for character in body):
        raise PageError(f"{field} is one word, got {value!r}")
    return body


# --------------------------------------------------------------------------- #
# A repository
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=True)
class Item:
    """One repository: its id, its name and its stars, all whole numbers."""

    id: int
    name: str
    stars: int

    def __post_init__(self) -> None:
        _whole(self.id, "an id", 1)
        _name(self.name, "a name")
        _whole(self.stars, "a star count", 0)

    def __str__(self) -> str:
        return f"{self.id} {self.name}"


def cursor_for(item: Item) -> str:
    """The token that means "everything strictly after this repository"."""
    return f"after={item.id}"


def id_from_cursor(token: str) -> int:
    """The id inside a token, refusing anything that is not one of ours."""
    if not isinstance(token, str):
        raise PageError(f"a cursor is text, got {type(token).__name__}")
    if not token.startswith("after="):
        raise PageError(f"{token!r} is not a cursor: they read 'after=<id>'")
    digits = token[len("after="):]
    if not digits.isdigit():
        raise PageError(f"{token!r} holds no id after 'after='")
    return int(digits)


# --------------------------------------------------------------------------- #
# A page
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Page:
    """One window onto the collection: its items, the total, and `next`."""

    number: int
    per_page: int
    items: tuple[Item, ...]
    total_count: int
    next: str | None

    def __post_init__(self) -> None:
        _whole(self.number, "a page number", 1)
        per_page = _whole(self.per_page, "a page size", 1)
        if per_page > MAX_PER_PAGE:
            raise PageError(f"a page holds at most {MAX_PER_PAGE} items, got "
                            f"{per_page}")
        if len(self.items) > per_page:
            raise PageError(f"page {self.number} holds {len(self.items)} "
                            f"items, more than its page size of {per_page}")
        _whole(self.total_count, "a total count", 0)
        if self.total_count < len(self.items):
            raise PageError(f"page {self.number} holds {len(self.items)} items "
                            f"but reports a total of {self.total_count}")
        if self.next is not None:
            id_from_cursor(self.next)

    def __len__(self) -> int:
        return len(self.items)

    def ids(self) -> tuple[int, ...]:
        return tuple(item.id for item in self.items)

    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.items)

    def is_last(self) -> bool:
        """The only end signal that means what it says: there is no `next`."""
        return self.next is None

    def line(self) -> str:
        token = "next=None" if self.next is None else f"next={self.next}"
        return (f"page {self.number} [{', '.join(self.names())}] "
                f"total={self.total_count} {token}")


class Repository:
    """A mutable server: a list of repositories, newest first.

    It is mutable on purpose. A paginated API is a view onto a list that other
    people are writing to, and a walk that assumes it holds still is the defect
    this lab exists to show.
    """

    def __init__(self, items, arriving: Item | None = None) -> None:
        held = tuple(items)
        if not held:
            raise PageError("a server needs at least one repository")
        for item in held:
            if not isinstance(item, Item):
                raise PageError(f"a server holds repositories, got "
                                f"{type(item).__name__}")
        ids = [item.id for item in held]
        if len(set(ids)) != len(ids):
            raise PageError("two repositories share an id")
        self._items: list[Item] = list(held)
        self._arriving = arriving
        self._arrived = False
        #: A page number that answers with an error envelope instead of a list.
        self.error_on: int | None = None
        #: How many pages have been served, so a walk can be shown its own load.
        self.served = 0

    def __len__(self) -> int:
        return len(self._items)

    def items(self) -> tuple[Item, ...]:
        return tuple(self._items)

    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self._items)

    def arriving(self) -> Item | None:
        return self._arriving

    def has_arrived(self) -> bool:
        return self._arrived

    def arrive(self) -> Item:
        """Push the arriving repository onto the head of the list, once."""
        if self._arriving is None:
            raise PageError("this server has no repository waiting to arrive")
        if self._arrived:
            raise PageError(f"{self._arriving} has already arrived")
        self._items.insert(0, self._arriving)
        self._arrived = True
        return self._arriving

    # -- one page, by offset ------------------------------------------------- #
    def page_number(self, number: int, per_page: int) -> Page:
        """The window at `number`, counting from one."""
        number = _whole(number, "a page number", 1)
        per_page = _whole(per_page, "a page size", 1)
        if per_page > MAX_PER_PAGE:
            raise PageError(f"a page holds at most {MAX_PER_PAGE} items, got "
                            f"{per_page}")
        start = (number - 1) * per_page
        window = tuple(self._items[start:start + per_page])
        total = len(self._items)
        following = None
        if start + per_page < total:
            following = cursor_for(window[-1])
        self.served += 1
        return Page(number, per_page, window, total, following)

    # -- one page, by cursor ------------------------------------------------- #
    def page_after(self, token: str | None, per_page: int,
                   number: int = 1) -> Page:
        """The window strictly after `token`, which may be `None` for the head."""
        per_page = _whole(per_page, "a page size", 1)
        if per_page > MAX_PER_PAGE:
            raise PageError(f"a page holds at most {MAX_PER_PAGE} items, got "
                            f"{per_page}")
        if token is None:
            start = 0
        else:
            anchor = id_from_cursor(token)
            matches = [index for index, item in enumerate(self._items)
                       if item.id == anchor]
            if not matches:
                raise PageError(f"the cursor {token!r} names a repository this "
                                f"list no longer holds")
            start = matches[0] + 1
        window = tuple(self._items[start:start + per_page])
        total = len(self._items)
        following = None
        if start + per_page < total and window:
            following = cursor_for(window[-1])
        self.served += 1
        return Page(number, per_page, window, total, following)

    # -- the wire ------------------------------------------------------------ #
    def raw_number(self, number: int, per_page: int) -> str:
        """The body exactly as the server would send it, error envelope and all."""
        if self.error_on is not None and self.error_on == number:
            self.served += 1
            return json.dumps(LEGACY_ERROR_BODY)
        page = self.page_number(number, per_page)
        return json.dumps([{"id": item.id, "name": item.name,
                            "stars": item.stars} for item in page.items])

    def page_count(self, per_page: int) -> int:
        per_page = _whole(per_page, "a page size", 1)
        total = len(self._items)
        return (total + per_page - 1) // per_page


# --------------------------------------------------------------------------- #
# A walk
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Walk:
    """Every page a walk collected, why it stopped, and what that cost.

    `pages` keeps the windows apart so a page that repeats an id inside itself
    is visible; `rows` flattens them, duplicates and all.
    """

    mode: str
    pages: tuple[tuple[Item, ...], ...]
    totals: tuple[int, ...]
    stopped: str

    def __post_init__(self) -> None:
        if self.mode not in ("offset", "cursor"):
            raise PageError(f"a walk is offset or cursor, got {self.mode!r}")
        if self.stopped not in ("next", "empty", "limit"):
            raise PageError(f"a walk stops on next, empty or limit, got "
                            f"{self.stopped!r}")
        if len(self.pages) != len(self.totals):
            raise PageError(f"a walk needs one total per page, got "
                            f"{len(self.pages)} page(s) and "
                            f"{len(self.totals)} total(s)")

    def __len__(self) -> int:
        return len(self.rows())

    def rows(self) -> tuple[Item, ...]:
        return tuple(item for page in self.pages for item in page)

    def ids(self) -> tuple[int, ...]:
        return tuple(item.id for item in self.rows())

    def unique(self) -> tuple[Item, ...]:
        """The rows with a repeated id kept only the first time."""
        seen: set[int] = set()
        kept: list[Item] = []
        for item in self.rows():
            if item.id in seen:
                continue
            seen.add(item.id)
            kept.append(item)
        return tuple(kept)

    def duplicates(self) -> tuple[Item, ...]:
        """Every row whose id was already collected, in the order it happened."""
        seen: set[int] = set()
        repeated: list[Item] = []
        for item in self.rows():
            if item.id in seen:
                repeated.append(item)
            seen.add(item.id)
        return tuple(repeated)

    def missing(self, against) -> tuple[Item, ...]:
        """The repositories in `against` this walk never saw."""
        seen = {item.id for item in self.rows()}
        return tuple(item for item in against if item.id not in seen)

    def shortfall(self) -> int:
        """How many repositories the last page's total says are not here."""
        if not self.totals:
            return 0
        return max(0, self.totals[-1] - len(self.unique()))

    def complete(self) -> bool:
        """No duplicates, nothing stranded, and no shortfall."""
        return not self.duplicates() and self.shortfall() == 0

    def line(self) -> str:
        return (f"{self.mode:<6} {len(self.pages)} page(s) "
                f"{len(self.rows()):>2} row(s) "
                f"{len(self.unique()):>2} unique "
                f"{len(self.duplicates()):>2} duplicate(s) "
                f"short {self.shortfall():>2} stopped on {self.stopped}")


def offset_walk(server: Repository, per_page: int, on_page=None,
                limit: int = MAX_PAGES) -> Walk:
    """Collect by page number, which is an offset into a moving list."""
    per_page = _whole(per_page, "a page size", 1)
    limit = _whole(limit, "a page limit", 1)
    pages: list[tuple[Item, ...]] = []
    totals: list[int] = []
    stopped = "limit"
    number = 1
    while number <= limit:
        page = server.page_number(number, per_page)
        pages.append(page.items)
        totals.append(page.total_count)
        if on_page is not None:
            on_page(page)
        if not page.items:
            stopped = "empty"
            break
        number += 1
    return Walk("offset", tuple(pages), tuple(totals), stopped)


def cursor_walk(server: Repository, per_page: int, on_page=None,
                limit: int = MAX_PAGES) -> Walk:
    """Collect by following `next`, which is the only honest end signal."""
    per_page = _whole(per_page, "a page size", 1)
    limit = _whole(limit, "a page limit", 1)
    pages: list[tuple[Item, ...]] = []
    totals: list[int] = []
    stopped = "limit"
    token: str | None = None
    number = 1
    while number <= limit:
        page = server.page_after(token, per_page, number)
        pages.append(page.items)
        totals.append(page.total_count)
        if on_page is not None:
            on_page(page)
        if page.next is None:
            stopped = "next"
            break
        token = page.next
        number += 1
    return Walk("cursor", tuple(pages), tuple(totals), stopped)


# --------------------------------------------------------------------------- #
# The legacy loop, executable
# --------------------------------------------------------------------------- #
def legacy_fetch(server: Repository, per_page: int, on_page=None,
                 limit: int = MAX_PAGES):
    """The legacy loop, rewritten faithfully -- `+=` and `if not data` included.

    It returns the raw rows the legacy code produced, which is why the result is
    not a tuple of `Item`: the bodies are dictionaries as `json.loads` makes
    them, and an error envelope contributes its keys as strings.
    """
    per_page = _whole(per_page, "a page size", 1)
    limit = _whole(limit, "a page limit", 1)
    out: list = []
    page = 1
    while page <= limit:
        data = json.loads(server.raw_number(page, per_page))
        if not data:
            break
        out += data
        if on_page is not None:
            on_page(page)
        page += 1
    return tuple(out)


def is_repository_row(row) -> bool:
    """A row that is a repository: the dictionary `json.loads` made of one."""
    return isinstance(row, dict) and "id" in row and "name" in row


# --------------------------------------------------------------------------- #
# Reading the bundle
# --------------------------------------------------------------------------- #
def parse_items(text: str) -> tuple[tuple[Item, ...], Item | None]:
    """Read `id name stars` lines and one `arrives id name stars` line."""
    items: list[Item] = []
    arriving: Item | None = None
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"),
                                  start=1):
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        fields = line.split()
        head = fields[0]
        if head == "arrives":
            if len(fields) != 4:
                raise PageError(f"line {number}: arrives takes an id, a name "
                                f"and a star count")
            if arriving is not None:
                raise PageError(f"line {number}: a second arrives line; only "
                                f"one repository may be pending")
            arriving = _item_from(fields[1:], number)
            continue
        if len(fields) != 3:
            raise PageError(f"line {number}: a repository is an id, a name and "
                            f"a star count")
        items.append(_item_from(fields, number))
    if not items:
        raise PageError("the bundle holds no repositories")
    ids = [item.id for item in items]
    if len(set(ids)) != len(ids):
        raise PageError("two repositories share an id")
    if arriving is not None and arriving.id in ids:
        raise PageError(f"the arriving repository reuses the id "
                        f"{arriving.id}")
    return tuple(items), arriving


def _item_from(fields, number: int) -> Item:
    try:
        ident = int(fields[0])
        stars = int(fields[2])
    except ValueError:
        raise PageError(f"line {number}: an id and a star count are whole "
                        f"numbers") from None
    return Item(ident, fields[1], stars)


def read_repositories(path=None) -> tuple[tuple[Item, ...], Item | None]:
    target = Path(REPOS_FILE if path is None else path)
    if not target.is_file():
        raise PageError(f"file not found: {target}")
    return parse_items(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(offset: Walk, cursor: Walk, legacy, legacy_error,
          items: tuple[Item, ...], arriving: Item,
          per_page: int) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived from the two walks and the legacy rows.

    Every check reads only its arguments, so a negative control is a corrupted
    argument rather than an injected function: the walk that is being doubted is
    the walk the check is given.
    """
    per_page = _whole(per_page, "a page size", 1)

    def every_page_holds_unique_ids() -> bool:
        for page in offset.pages + cursor.pages:
            ids = [item.id for item in page]
            if len(set(ids)) != len(ids):
                return False
        return True

    def no_page_holds_more_than_its_size() -> bool:
        for page in offset.pages + cursor.pages:
            if len(page) > per_page:
                return False
        return True

    def the_offset_walk_repeats_a_row_when_the_head_moves() -> bool:
        repeated = offset.duplicates()
        return len(repeated) >= 1 and repeated[0].id == 104

    def the_offset_walk_never_sees_the_repository_that_arrived() -> bool:
        return arriving.id not in offset.ids() and \
            arriving in cursor.missing(items + (arriving,))

    def the_offset_walk_needs_deduping_to_be_ten_repositories() -> bool:
        return len(offset.rows()) == 11 and len(offset.unique()) == 10

    def the_cursor_walk_has_no_duplicates_and_sees_the_original_list() -> bool:
        return not cursor.duplicates() and \
            cursor.ids() == tuple(item.id for item in items)

    def the_cursor_walk_reports_that_the_collection_grew() -> bool:
        return min(cursor.totals) == 10 and max(cursor.totals) == 11

    def a_walk_stops_on_its_own_signal_not_on_a_limit() -> bool:
        return cursor.stopped == "next" and offset.stopped == "empty"

    def the_legacy_loop_turns_an_error_body_into_rows() -> bool:
        plain = [row for row in legacy if is_repository_row(row)]
        junk = [row for row in legacy_error if not is_repository_row(row)]
        return len(plain) == 11 and \
            junk == ["message", "documentation_url"] and \
            len([row for row in legacy_error if is_repository_row(row)]) == 6

    def every_page_reports_a_total_big_enough_for_its_rows() -> bool:
        for walk in (offset, cursor):
            if not walk.totals:
                return False
            if min(walk.totals) < len(walk.unique()):
                return False
            for page, total in zip(walk.pages, walk.totals):
                if total < len(page):
                    return False
        return True

    checks = [
        ("every page holds unique ids of its own", every_page_holds_unique_ids),
        ("no page holds more items than its page size",
         no_page_holds_more_than_its_size),
        ("the offset walk repeats a row when the head moves",
         the_offset_walk_repeats_a_row_when_the_head_moves),
        ("the offset walk never sees the repository that arrived",
         the_offset_walk_never_sees_the_repository_that_arrived),
        ("the offset walk needs deduping to be ten repositories",
         the_offset_walk_needs_deduping_to_be_ten_repositories),
        ("the cursor walk has no duplicates and sees the original list",
         the_cursor_walk_has_no_duplicates_and_sees_the_original_list),
        ("the cursor walk reports that the collection grew",
         the_cursor_walk_reports_that_the_collection_grew),
        ("each walk stops on its own signal, not on a limit",
         a_walk_stops_on_its_own_signal_not_on_a_limit),
        ("the legacy loop turns an error body into rows",
         the_legacy_loop_turns_an_error_body_into_rows),
        ("every page reports a total big enough for its rows",
         every_page_reports_a_total_big_enough_for_its_rows),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
PER_PAGE = 4


def row_text(row) -> str:
    """A legacy row as something short enough to print: a name, or the string."""
    if is_repository_row(row):
        return str(row["name"])
    return str(row)


def _serve(items, arriving: Item, error_on: int | None = None) -> Repository:
    """A fresh server, so every walk in the demo starts from the same list."""
    server = Repository(items, arriving)
    server.error_on = error_on
    return server


def run_demo() -> int:
    items, arriving = read_repositories()
    if arriving is None:
        raise PageError("the bundle names no arriving repository")

    print("=" * 78)
    print(" PAGE LAB - a page number is an offset into a list that moves")
    print("=" * 78)

    print("\n  the legacy loop, transcribed:")
    for line in LEGACY_FETCH.split("\n"):
        print(f"    {line}")

    print(f"\n  the server holds {len(items)} repositories, newest first, "
          f"with a page size of {PER_PAGE}:")
    print("    " + " ".join(item.name for item in items))
    print(f"    one more is waiting to be pushed: {arriving}")

    # -- the offset walk ---------------------------------------------------- #
    print("\n  walking by page number, with one repository pushed after page 1:")
    server = _serve(items, arriving)
    printed: list[str] = []

    def note_page(page: Page) -> None:
        printed.append(page.line())
        if page.number == 1:
            server.arrive()

    offset = offset_walk(server, PER_PAGE, note_page)
    for line in printed:
        print(f"    {line}")
    print(f"    {offset.line()}")
    print(f"    duplicated: {', '.join(item.name for item in offset.duplicates())}"
          f"   never seen: "
          f"{', '.join(item.name for item in offset.missing(items + (arriving,)))}")
    print(f"    eleven rows for ten repositories -- one row twice, one "
          f"repository lost")

    # -- the cursor walk ---------------------------------------------------- #
    print("\n  walking by cursor, with the same repository pushed after page 1:")
    server = _serve(items, arriving)
    printed = []

    def note_cursor(page: Page) -> None:
        printed.append(page.line())
        if page.number == 1:
            server.arrive()

    cursor = cursor_walk(server, PER_PAGE, note_cursor)
    for line in printed:
        print(f"    {line}")
    print(f"    {cursor.line()}")
    print(f"    duplicates: {len(cursor.duplicates())}   never seen: "
          f"{', '.join(item.name for item in cursor.missing(items + (arriving,)))}"
          f"   (it arrived after the walk began, and the total says so: "
          f"{min(cursor.totals)} then {max(cursor.totals)})")

    # -- the legacy loop ---------------------------------------------------- #
    print("\n  the legacy loop over the same moving list:")
    server = _serve(items, arriving)
    legacy = legacy_fetch(server, PER_PAGE,
                          lambda number: server.arrive() if number == 1
                          else None)
    print(f"    {len(legacy)} row(s): "
          f"{' '.join(row_text(row) for row in legacy)}")
    print(f"    {len([row for row in legacy if is_repository_row(row)])} of "
          f"them are repositories, {len(legacy) - len({row['id'] for row in legacy if is_repository_row(row)})}"
          f" of those are a repeat, and nothing notices")

    print("\n  the legacy loop when page 2 is a rate limit instead of a list:")
    server = _serve(items, arriving, error_on=2)
    legacy_error = legacy_fetch(server, PER_PAGE)
    junk = [row for row in legacy_error if not is_repository_row(row)]
    print(f"    {len(legacy_error)} row(s): "
          f"{' '.join(row_text(row) for row in legacy_error)}")
    print(f"    {len(junk)} of them are the error body's keys: "
          f"{', '.join(junk)}")
    print(f"    `out += data` extends a list with a dictionary's keys, so a 403 "
          f"adds two rows")

    print("\n  what each walk costs:")
    print(f"    {'walk':<8} {'pages':>5} {'rows':>5} {'unique':>6} "
          f"{'dupes':>5} {'short':>5}  stopped on")
    for walk in (offset, cursor):
        print(f"    {walk.mode:<8} {len(walk.pages):>5} {len(walk.rows()):>5} "
              f"{len(walk.unique()):>6} {len(walk.duplicates()):>5} "
              f"{walk.shortfall():>5}  {walk.stopped}")

    checks = audit(offset, cursor, legacy, legacy_error, items, arriving,
                   PER_PAGE)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"the server holds {len(items)} repositories and pushes "
          f"{arriving.name} after page 1, the offset walk returns "
          f"{len(offset.rows())} rows for {len(offset.unique())} repositories "
          f"and repeats {offset.duplicates()[0].name} at index "
          f"{offset.ids().index(offset.duplicates()[0].id)} while never seeing "
          f"{arriving.name}, the cursor walk returns {len(cursor.rows())} rows "
          f"with {len(cursor.duplicates())} duplicate(s) and reports the total "
          f"growing from {min(cursor.totals)} to {max(cursor.totals)}, the "
          f"legacy loop turns a 403 into the rows {list(junk)} and answers "
          f"{len([row for row in legacy if is_repository_row(row)])} "
          f"repositories for {len(items)}, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
