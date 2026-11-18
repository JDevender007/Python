"""An empty list is not an answer, and a status code is half of the response.

The legacy reader of a news response was four lines:

    def articles(payload):
        try:
            return payload["articles"]
        except (KeyError, TypeError):
            return []

**1. `[]` is five different facts.** A rate limit, a 404 that says "nothing matches",
a body whose own `status` field says `error`, a query that genuinely matched nothing, and
a body that simply has no `articles` key all reach the same `except`, and all come back as
an empty list. Four of those are failures and one is a successful empty result, and the
caller cannot tell them apart:

    HTTP 429  {"code": "rateLimited", ...}   -> []
    HTTP 404  {"code": "notFound", ...}      -> []
    HTTP 200  {"status": "error", ...}       -> []
    HTTP 200  {"totalResults": 0, ...}       -> []     (this one is correct)
    HTTP 200  {"totalResults": 0}            -> []     (the key is missing)

**2. The message is thrown away with the list.** The 404 body says "Nothing matches your
query." That sentence is the most useful thing in the response and it is discarded, because
the code only ever looked at one key.

**3. `payload["articles"]` returns whatever is there.** A `null` is returned as the article
list, and the code that iterates it fails a hundred lines later, in a function that has
never heard of the API. `None` is not an empty list.

**4. A status code is not the whole story, and neither is the body.** A proxy answers `200`
with a body whose `status` is `error`; a body arrives with `200` and does not parse at all.
The status and the body each know something the other does not, and both have to be read.

**5. `totalResults` is the only way to know you were cut off.** A `200` with two articles
and a total of twenty is a partial answer. The legacy code calls it a success, because the
list is not empty.

So this module keeps the **status and the body together**, classifies every response into
one of five outcomes (`ok`, `empty`, `partial`, `error`, `malformed`), keeps the sentence
that explains a failure, and refuses to call a body readable when it is not.

The demonstration is offline: one bundled file of ten responses exactly as they arrived.
Standard library only: no requests, no HTTP client, no API key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESPONSES_FILE = DATA_DIR / "responses.txt"

#: The legacy reader, transcribed: four different facts, one empty list.
LEGACY_ARTICLES = ('try:\n'
                   '    return payload["articles"]\n'
                   'except (KeyError, TypeError):\n'
                   '    return []')

#: The five things a response can turn out to be.
KINDS = ("ok", "empty", "partial", "error", "malformed")

#: The shortest sentence kept from a body that is not JSON.
NOTE_LIMIT = 60


class ResponseError(Exception):
    """A response, a body or a bundle that cannot be read, and why not."""


# --------------------------------------------------------------------------- #
# Reading values
# --------------------------------------------------------------------------- #
def _whole(value, field: str, minimum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ResponseError(f"{field} is a whole number, got {value!r}")
    if value < minimum:
        raise ResponseError(f"{field} is at least {minimum}, got {value}")
    return value


def _text(value, field: str) -> str:
    if not isinstance(value, str):
        raise ResponseError(f"{field} is text, got {type(value).__name__}")
    body = value.strip()
    if not body:
        raise ResponseError(f"{field} needs a value, got {value!r}")
    return body


# --------------------------------------------------------------------------- #
# An article
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=True)
class Article:
    """One headline, and the source that carried it."""

    title: str
    source: str = ""

    def __post_init__(self) -> None:
        _text(self.title, "a title")
        if not isinstance(self.source, str):
            raise ResponseError(f"a source is text, got "
                                f"{type(self.source).__name__}")

    def __str__(self) -> str:
        return self.title if not self.source else f"{self.title} ({self.source})"


def parse_article(raw) -> Article:
    """One row of `articles`, refusing a row that carries no title."""
    if not isinstance(raw, dict):
        raise ResponseError(f"an article is a JSON object, got "
                            f"{type(raw).__name__}")
    if "title" not in raw:
        raise ResponseError("an article carries no 'title'")
    source = raw.get("source", "")
    if isinstance(source, dict):
        source = source.get("name", "")
    return Article(raw["title"], source)


# --------------------------------------------------------------------------- #
# A response and its outcome
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Response:
    """A status and a body, exactly as they came off the wire.

    They travel together because neither is the answer on its own: a `200` can carry
    an error body, and a `404` can carry a perfectly readable explanation.
    """

    name: str
    status: int
    body: str

    def __post_init__(self) -> None:
        _text(self.name, "a response name")
        _whole(self.status, "a status", 100)
        if self.status > 599:
            raise ResponseError(f"a status is at most 599, got {self.status}")
        if not isinstance(self.body, str):
            raise ResponseError(f"a body is text, got "
                                f"{type(self.body).__name__}")

    def line(self) -> str:
        return f"HTTP {self.status}  {self.body[:NOTE_LIMIT]}"


@dataclass(frozen=True)
class Outcome:
    """What one response actually turned out to be, and the sentence why."""

    name: str
    status: int
    kind: str
    rows: tuple[Article, ...]
    total: int | None
    note: str

    def __post_init__(self) -> None:
        _text(self.name, "an outcome name")
        _whole(self.status, "a status", 100)
        if self.kind not in KINDS:
            raise ResponseError(f"an outcome is one of {', '.join(KINDS)}, got "
                                f"{self.kind!r}")
        if not isinstance(self.rows, tuple):
            raise ResponseError(f"rows are a tuple, got "
                                f"{type(self.rows).__name__}")
        for row in self.rows:
            if not isinstance(row, Article):
                raise ResponseError(f"a row is an article, got "
                                    f"{type(row).__name__}")
        if self.total is not None:
            _whole(self.total, "a total", 0)
            if self.total < len(self.rows):
                raise ResponseError(f"{self.name} holds {len(self.rows)} "
                                    f"article(s) but reports a total of "
                                    f"{self.total}")
        if self.kind in ("ok", "empty", "partial") and self.total is None:
            raise ResponseError(f"{self.name} is {self.kind}, so it needs a "
                                f"total to be checked against")
        if self.kind == "ok" and self.total != len(self.rows):
            raise ResponseError(f"{self.name} is ok but holds {len(self.rows)} "
                                f"of {self.total}")
        if self.kind == "empty" and self.rows:
            raise ResponseError(f"{self.name} is empty but holds "
                                f"{len(self.rows)} row(s)")
        if self.kind == "partial" and not (len(self.rows) < (self.total or 0)):
            raise ResponseError(f"{self.name} is partial but holds "
                                f"{len(self.rows)} of {self.total}")
        if not self.note.strip():
            raise ResponseError(f"{self.name} needs the sentence that says why")

    def __len__(self) -> int:
        return len(self.rows)

    def is_ok(self) -> bool:
        return self.kind == "ok"

    def has_rows(self) -> bool:
        return bool(self.rows)

    def shortfall(self) -> int:
        """How many articles the total promises and this response does not hold."""
        if self.total is None:
            return 0
        return max(0, self.total - len(self.rows))

    def titles(self) -> tuple[str, ...]:
        return tuple(article.title for article in self.rows)

    def line(self) -> str:
        total = "-" if self.total is None else str(self.total)
        return (f"{self.name:<14} HTTP {self.status} {self.kind:<9} "
                f"{len(self.rows):>2}/{total:<3} {self.note}")

    def sentence(self) -> str:
        return (f"{self.name}: HTTP {self.status}, {self.kind}, "
                f"{len(self.rows)} article(s) of {self.total}, {self.note}")


def _note_from(payload, fallback: str) -> str:
    """The sentence a body carries, or a short quote of it if it has none."""
    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        code = payload.get("code")
        if isinstance(code, str) and code.strip():
            return f"the body names the code {code.strip()} and no message"
    return fallback


def _short(text: str) -> str:
    body = " ".join(text.split())
    if len(body) <= NOTE_LIMIT:
        return body
    return body[:NOTE_LIMIT - 3] + "..."


def classify(response: Response) -> Outcome:
    """One response in, one of five outcomes out, with the sentence why.

    The status is read first and the body second, and both are kept: a `429` whose
    body explains itself still gives up its message, and a `200` whose body says
    `"status": "error"` is an error that happens to have arrived with a good status.
    """
    if not isinstance(response, Response):
        raise ResponseError(f"a classification needs a response, got "
                            f"{type(response).__name__}")

    try:
        payload = json.loads(response.body)
    except json.JSONDecodeError as error:
        payload = None
        broken = (f"the body is not JSON, at character {error.pos}: "
                  f"{error.msg}")
    else:
        broken = ""

    if not 200 <= response.status <= 299:
        # A failed status is explained by whatever the body actually says: a JSON
        # message when there is one, and otherwise the body itself, quoted.
        note = _note_from(payload, _short(response.body) or broken)
        return Outcome(response.name, response.status, "error", (), None,
                       f"HTTP {response.status}, and the body says: {note}")

    if broken:
        return Outcome(response.name, response.status, "malformed", (), None,
                       broken)

    if not isinstance(payload, dict):
        return Outcome(response.name, response.status, "malformed", (), None,
                       f"a body is a JSON object, got "
                       f"{type(payload).__name__}")

    inner = payload.get("status")
    if isinstance(inner, str) and inner.strip().lower() == "error":
        note = _note_from(payload, "the body says error and gives no message")
        return Outcome(response.name, response.status, "error", (), None,
                       f"the status was {response.status} but the body says "
                       f"error: {note}")

    if "articles" not in payload:
        return Outcome(response.name, response.status, "malformed", (), None,
                       "the body carries no 'articles' field, so it holds no "
                       "answer")

    raw_rows = payload["articles"]
    if not isinstance(raw_rows, list):
        return Outcome(response.name, response.status, "malformed", (), None,
                       f"'articles' is {type(raw_rows).__name__}, not a list, "
                       f"and a null is not an empty list")

    total = payload.get("totalResults")
    if not isinstance(total, int) or isinstance(total, bool):
        return Outcome(response.name, response.status, "malformed", (), None,
                       f"'totalResults' is {type(total).__name__}, so the "
                       f"answer cannot be checked against anything")

    rows: list[Article] = []
    for number, raw in enumerate(raw_rows, start=1):
        try:
            rows.append(parse_article(raw))
        except ResponseError as error:
            return Outcome(response.name, response.status, "malformed", (),
                           None, f"article {number}: {error}")

    if len(rows) > total:
        return Outcome(response.name, response.status, "malformed", (), None,
                       f"the body holds {len(rows)} article(s) but reports a "
                       f"total of {total}")

    if not rows:
        if total == 0:
            return Outcome(response.name, response.status, "empty", (), 0,
                           "the query matched nothing, and the total agrees "
                           "it is nothing")
        return Outcome(response.name, response.status, "partial", (), total,
                       f"no articles arrived but the total is {total}")

    if len(rows) < total:
        return Outcome(response.name, response.status, "partial", tuple(rows),
                       total,
                       f"{len(rows)} of {total} arrived, so "
                       f"{total - len(rows)} are missing")

    return Outcome(response.name, response.status, "ok", tuple(rows), total,
                   f"all {total} article(s) arrived")


# --------------------------------------------------------------------------- #
# The legacy reader, executable
# --------------------------------------------------------------------------- #
def legacy_articles(payload):
    """The legacy reader, rewritten faithfully: unreadable means an empty list."""
    try:
        return payload["articles"]
    except (KeyError, TypeError):
        return []


def legacy_read(body: str):
    """The legacy path from a body: `json.loads`, then one key, then `[]`."""
    return legacy_articles(json.loads(body))


# --------------------------------------------------------------------------- #
# A bundle of responses
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Bundle:
    """Every response in one file, in the order the file holds them."""

    outcomes: tuple[Outcome, ...]

    def __post_init__(self) -> None:
        if not self.outcomes:
            raise ResponseError("a bundle needs at least one response")
        names = [outcome.name for outcome in self.outcomes]
        if len(set(names)) != len(names):
            raise ResponseError("two responses share a name")

    def __len__(self) -> int:
        return len(self.outcomes)

    def by_name(self, name: str) -> Outcome:
        for outcome in self.outcomes:
            if outcome.name == name:
                return outcome
        raise ResponseError(f"no response named {name!r} in this bundle")

    def of_kind(self, kind: str) -> tuple[Outcome, ...]:
        if kind not in KINDS:
            raise ResponseError(f"a kind is one of {', '.join(KINDS)}, got "
                                f"{kind!r}")
        return tuple(item for item in self.outcomes if item.kind == kind)

    def counts(self) -> dict[str, int]:
        return {kind: sum(1 for item in self.outcomes if item.kind == kind)
                for kind in KINDS}

    def with_rows(self) -> tuple[Outcome, ...]:
        return tuple(item for item in self.outcomes if item.has_rows())

    def lines(self) -> tuple[str, ...]:
        return tuple(outcome.line() for outcome in self.outcomes)


def parse_responses(text: str) -> tuple[Response, ...]:
    """Read `--- name`, then `HTTP <status>`, then the body, byte for byte."""
    responses: list[Response] = []
    name: str | None = None
    lines: list[str] = []

    def flush(number: int) -> None:
        if name is None:
            return
        if not any(line.strip() for line in lines):
            raise ResponseError(f"response {name!r} before line {number} has "
                                f"no status line")
        head = lines[0].strip()
        if not head.startswith("HTTP "):
            raise ResponseError(f"response {name!r} starts with {head!r}, not "
                                f"'HTTP <status>'")
        digits = head[len("HTTP "):].strip()
        if not digits.isdigit():
            raise ResponseError(f"response {name!r} has {digits!r} where the "
                                f"status belongs")
        body = "\n".join(lines[1:])
        if not body.strip():
            raise ResponseError(f"response {name!r} has no body")
        responses.append(Response(name, int(digits), body))

    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"),
                                  start=1):
        if line.lstrip().startswith(";"):
            continue
        if line.startswith("---"):
            flush(number)
            name = line[3:].strip()
            if not name:
                raise ResponseError(f"line {number}: a response header needs a "
                                    f"name")
            lines = []
            continue
        if name is None:
            if line.strip():
                raise ResponseError(f"line {number}: a body before the first "
                                    f"'--- name' header")
            continue
        lines.append(line)
    flush(len(text.split("\n")))
    if not responses:
        raise ResponseError("the bundle holds no responses")
    return tuple(responses)


def read_all(path=None) -> tuple["Bundle", tuple[Response, ...]]:
    """The classified bundle and the raw responses it came from."""
    target = Path(RESPONSES_FILE if path is None else path)
    if not target.is_file():
        raise ResponseError(f"file not found: {target}")
    responses = parse_responses(target.read_text(encoding="utf-8"))
    return Bundle(tuple(classify(response) for response in responses)), responses


def read_bundle(path=None) -> "Bundle":
    return read_all(path)[0]


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def legacy_of(bodies) -> tuple:
    """The legacy result for each body, with a crash recorded as `"crash"`."""
    out = []
    for body in bodies:
        try:
            out.append(legacy_read(body))
        except json.JSONDecodeError:
            out.append("crash")
    return tuple(out)


def audit(bundle: Bundle, responses: tuple[Response, ...]) -> list[tuple[str, bool]]:
    """Ten checks, each re-derived from the bundle and the raw bodies.

    The bodies are passed in as well as the outcomes, so a check can ask what the
    legacy reader made of the same bytes rather than restating the outcome.
    """
    bodies = tuple(response.body for response in responses)
    legacy = legacy_of(bodies)

    def every_outcome_names_a_status_and_a_kind() -> bool:
        for outcome in bundle.outcomes:
            if outcome.kind not in KINDS or not 200 <= outcome.status <= 599:
                return False
        return True

    def the_five_empty_lists_are_five_different_facts() -> bool:
        blanks = [outcome for outcome in bundle.outcomes
                  if legacy[bundle.outcomes.index(outcome)] == []]
        if len(blanks) != 5:
            return False
        return len({outcome.note for outcome in blanks}) == 5

    def a_not_found_keeps_the_sentence_that_explains_it() -> bool:
        gone = bundle.by_name("not-found")
        return gone.kind == "error" and "Nothing matches your query." in \
            gone.note

    def a_rate_limit_keeps_its_message_too() -> bool:
        limited = bundle.by_name("rate-limited")
        return limited.kind == "error" and \
            "too many requests" in limited.note

    def a_body_that_says_error_with_a_200_is_an_error() -> bool:
        proxy = bundle.by_name("proxy-200-error")
        return proxy.status == 200 and proxy.kind == "error" and \
            "could not be satisfied" in proxy.note

    def a_genuinely_empty_result_is_empty_and_not_an_error() -> bool:
        empty = bundle.by_name("empty")
        return empty.kind == "empty" and empty.total == 0 and \
            empty.status == 200

    def a_partial_answer_reports_the_shortfall_it_has() -> bool:
        part = bundle.by_name("partial")
        return part.kind == "partial" and part.total == 20 and \
            len(part) == 2 and part.shortfall() == 18

    def three_malformed_bodies_carry_three_different_reasons() -> bool:
        broken = bundle.of_kind("malformed")
        if len(broken) != 3:
            return False
        return len({outcome.note for outcome in broken}) == 3

    def the_legacy_reader_answers_five_empty_lists_and_one_none() -> bool:
        return legacy.count([]) == 5 and legacy.count(None) == 1

    def the_legacy_reader_crashes_on_two_bodies() -> bool:
        return legacy.count("crash") == 2

    def every_outcome_with_rows_reports_a_total_that_holds_them() -> bool:
        for outcome in bundle.with_rows():
            if outcome.total is None or len(outcome) > outcome.total:
                return False
        return True

    checks = [
        ("every outcome names a status and a kind",
         every_outcome_names_a_status_and_a_kind),
        ("the five empty lists are five different facts",
         the_five_empty_lists_are_five_different_facts),
        ("a 404 keeps the sentence that explains it",
         a_not_found_keeps_the_sentence_that_explains_it),
        ("a 429 keeps its message too",
         a_rate_limit_keeps_its_message_too),
        ("a 200 whose body says error is an error",
         a_body_that_says_error_with_a_200_is_an_error),
        ("a genuinely empty result is empty, not an error",
         a_genuinely_empty_result_is_empty_and_not_an_error),
        ("a partial answer reports the shortfall it has",
         a_partial_answer_reports_the_shortfall_it_has),
        ("three malformed bodies carry three different reasons",
         three_malformed_bodies_carry_three_different_reasons),
        ("the legacy reader answers five empty lists and one None",
         the_legacy_reader_answers_five_empty_lists_and_one_none),
        ("the legacy reader crashes on two bodies",
         the_legacy_reader_crashes_on_two_bodies),
        ("every outcome with rows reports a total that holds them",
         every_outcome_with_rows_reports_a_total_that_holds_them),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    bundle = read_bundle()
    responses = parse_responses(RESPONSES_FILE.read_text(encoding="utf-8"))

    print("=" * 78)
    print(" ENVELOPE LAB - an empty list is not an answer")
    print("=" * 78)

    print("\n  the legacy reader, transcribed:")
    for line in LEGACY_ARTICLES.split("\n"):
        print(f"    {line}")

    print(f"\n  {len(bundle)} responses, each classified by its status and its "
          f"body:")
    print(f"    {'name':<14} {'status':>6} {'kind':<9} {'rows':>7}  note")
    for outcome in bundle.outcomes:
        print(f"    {outcome.line()}")

    counts = bundle.counts()
    print(f"\n  {', '.join(f'{counts[kind]} {kind}' for kind in KINDS)}")

    print("\n  what the legacy reader made of the same ten bodies:")
    legacy = legacy_of(tuple(response.body for response in responses))
    for response, value in zip(responses, legacy):
        if value == "crash":
            shown = "json.loads raised before it could answer"
        elif isinstance(value, list):
            shown = f"[] a list of {len(value)}"
        elif value is None:
            shown = "None, which is not a list"
        else:
            shown = repr(value)
        print(f"    {response.name:<14} {shown}")
    empties = [name for name, value in
               zip([response.name for response in responses], legacy)
               if value == []]
    blank_kinds = [bundle.by_name(name).kind for name in empties]
    print(f"    {len(empties)} bodies came back as exactly []: "
          f"{', '.join(empties)}")
    print(f"    of those, {blank_kinds.count('empty')} is a legitimate empty "
          f"result, {blank_kinds.count('error')} are failures the status named "
          f"and {blank_kinds.count('malformed')} is a body with no answer in "
          f"it")

    print("\n  the five facts behind one []:")
    for name in ("rate-limited", "not-found", "proxy-200-error", "empty",
                 "no-articles"):
        outcome = bundle.by_name(name)
        print(f"    {name:<14} {outcome.kind:<9} {outcome.note}")

    print("\n  a body that explains a failure, and is kept:")
    gone = bundle.by_name("not-found")
    print(f"    legacy returns {legacy_read(responses[4].body)!r} and loses the "
          f"sentence")
    print(f"    here           {gone.kind}: {gone.note}")

    print("\n  a partial answer:")
    part = bundle.by_name("partial")
    print(f"    {part.sentence()}")
    print(f"    the legacy reader sees a list of {len(part)} and calls it a "
          f"success")

    checks = audit(bundle, responses)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(bundle)} responses give {counts['ok']} ok, {counts['empty']} "
          f"empty, {counts['partial']} partial, {counts['error']} error and "
          f"{counts['malformed']} malformed, the legacy reader answers exactly "
          f"[] for {len(empties)} of them, one of which is the only correct "
          f"answer, keeps no message from the 404 that says "
          f"'{bundle.by_name('not-found').note.partition('and the body says: ')[2]}', "
          f"returns {legacy_read(responses[8].body)!r} for a null articles "
          f"field, crashes on {legacy.count('crash')} bodies, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("Demo completed successfully.")
    return 0
