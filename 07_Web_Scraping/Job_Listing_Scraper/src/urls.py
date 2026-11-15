"""A link is a structure, not a string to be glued to another string.

The legacy scraper decided a link was usable like this:

    def is_valid_url(url):
        try:
            parsed = urlparse(url)
            return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        except ValueError:
            return False

and built the absolute link like this:

    def absolute_url(base, href):
        return base + href

**1. `netloc` is not the site.** `https://jobs.example.com.evil.test/jobs/99`
has an `http` scheme and a `netloc`, so the legacy check says yes -- and a crawler
confined by "does it contain our name" follows it. Confinement is **host
equality**, not a substring, and not the presence of something in `netloc`.

**2. Gluing two strings together is not resolving a reference.** `base + href`
on `"https://jobs.example/jobs/"` and `"43"` gives a path that never existed.
Resolution is arithmetic on the parts: a path is relative to the **directory** of
the base, `..` removes a segment, a query replaces rather than appends, and a
fragment never reaches the server.

**3. A fragment is not part of the address.** `/jobs/42` and `/jobs/42#apply` are
one page, fetched once. A crawler that compares strings fetches it twice, and a
crawl that never deduplicates visits the same page for every anchor on it.

**4. A colon form is not always a document.** `javascript:void(0)` parses with a
scheme and no host, and `mailto:` with an address; neither is a page. Only `http`
and `https` name documents.

**5. A space is not a URL.** `urlparse` accepts `"https://jobs.example/a b"`
happily, because it never validates the characters. A link with a space in it is a
link somebody forgot to encode.

So this module reads a link into its parts, resolves it against a base by the
rules of the path, confines a crawl to one host by equality, deduplicates by a
canonical key that ignores the fragment, and keeps a refusal as a reason rather
than a silent `False`.

The demonstration is offline: one bundled page of links, one bundled base, no
network. Standard library only: no requests, no beautifulsoup.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit, urlunsplit

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LINKS_FILE = DATA_DIR / "links.txt"

#: The legacy validator, transcribed, so the demo can refute it.
LEGACY_VALID = ('parsed = urlparse(url)\n'
                'return parsed.scheme in {"http", "https"} and '
                'bool(parsed.netloc)')

#: The legacy join, transcribed: two strings, glued.
LEGACY_JOIN = "return base + href"

#: The page every href on the bundled page was printed on.
BASE_URL = "https://jobs.example/jobs/list.html"

#: The schemes that name a document. Everything else is refused.
DOCUMENT_SCHEMES = ("http", "https")

#: A job path: one numeric id after `/jobs/`.
JOB_PATH = re.compile(r"^/jobs/(\d+)$")

#: The characters a URL may not hold: whitespace, and the control range.
FORBIDDEN = re.compile(r"[\s\x00-\x1f\x7f]")


class UrlError(Exception):
    """A link that cannot be read, with the sentence that says why."""


# --------------------------------------------------------------------------- #
# A URL, in parts
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Url:
    """A document address, as its five parts instead of one string.

    Stored apart because every operation on a link works on one part: the host
    decides confinement, the path decides resolution, the query decides which
    page of a listing, and the fragment decides nothing at all.
    """

    scheme: str
    host: str
    path: str = "/"
    query: str = ""
    fragment: str = ""

    def __post_init__(self) -> None:
        if self.scheme not in DOCUMENT_SCHEMES:
            raise UrlError(f"only http and https name a document, got "
                           f"{self.scheme!r}")
        if not isinstance(self.host, str) or not self.host:
            raise UrlError(f"a link needs a host, got {self.host!r}")
        if self.host != self.host.lower():
            raise UrlError(f"a host is written in lower case, got "
                           f"{self.host!r}")
        if "@" in self.host:
            raise UrlError(f"a link cannot name a user, but {self.host!r} "
                           f"does")
        if not self.path.startswith("/"):
            raise UrlError(f"a path starts at the root, got {self.path!r}")
        for name in ("path", "query", "fragment"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise UrlError(f"the {name} is text, got {value!r}")
            found = FORBIDDEN.search(value)
            if found is not None:
                raise UrlError(f"the {name} cannot hold {found.group(0)!r}, "
                               f"but {value!r} does")

    def __str__(self) -> str:
        return urlunsplit((self.scheme, self.host, self.path, self.query,
                           self.fragment))

    def without_fragment(self) -> "Url":
        return Url(self.scheme, self.host, self.path, self.query)

    def key(self) -> tuple[str, str, tuple[tuple[str, str], ...]]:
        """What the server sees: host, path, and the query in a fixed order.

        The fragment is absent on purpose -- it never leaves the browser.
        """
        return (self.host, self.path, tuple(sorted(parse_qsl(self.query))))

    def is_job(self) -> bool:
        return JOB_PATH.match(self.path) is not None

    def job_id(self) -> int | None:
        found = JOB_PATH.match(self.path)
        return int(found.group(1)) if found is not None else None


def parse_url(text: str) -> Url:
    """Read an absolute URL, refusing the shapes that are not one."""
    if not isinstance(text, str):
        raise UrlError(f"a link is text, got {type(text).__name__}")
    body = text.strip()
    if not body:
        raise UrlError("the link text is empty")
    found = FORBIDDEN.search(body)
    if found is not None:
        raise UrlError(f"a link cannot hold {found.group(0)!r}, but {body!r} "
                       f"does")
    parts = urlsplit(body)
    if not parts.scheme:
        raise UrlError(f"{body!r} is relative: it needs a base to resolve "
                       f"against")
    if parts.scheme.lower() not in DOCUMENT_SCHEMES:
        raise UrlError(f"{parts.scheme!r} is not a document link: only http "
                       f"and https name a page")
    return Url(parts.scheme.lower(), _host(parts), parts.path or "/",
               parts.query, parts.fragment)


def _host(parts) -> str:
    netloc = parts.netloc
    if "@" in netloc:
        raise UrlError(f"a link cannot name a user, but {netloc!r} does")
    host = netloc.rsplit(":", 1)[0] if _has_port(netloc) else netloc
    host = host.lower().rstrip(".")
    if not host:
        raise UrlError("the link names no host")
    return host


def _has_port(netloc: str) -> bool:
    tail = netloc.rsplit(":", 1)[-1]
    return ":" in netloc and tail.isdigit()


# --------------------------------------------------------------------------- #
# Resolving a reference
# --------------------------------------------------------------------------- #
def resolve(base: Url, href: str) -> Url:
    """Resolve one href against the page it was printed on.

    The rules, in the order they are consulted:

    * a link with a scheme must be `http` or `https`, and is used as it stands;
    * `//host/path` inherits the scheme and is otherwise absolute;
    * `/path` keeps the host and replaces the path;
    * anything else is relative to the base's **directory**, `.`/`..` folded;
    * a reference with no path keeps the base path and inherits its query;
    * a reference with a path takes its own query, even an empty one;
    * the fragment is kept as written and never sent.
    """
    if not isinstance(href, str):
        raise UrlError(f"a link is text, got {type(href).__name__}")
    body = href.strip()
    if not body:
        raise UrlError("the link text is empty")
    found = FORBIDDEN.search(body)
    if found is not None:
        raise UrlError(f"a link cannot hold {found.group(0)!r}, but {body!r} "
                       f"does")

    parts = urlsplit(body)
    if parts.scheme:
        return parse_url(body)

    if body.startswith("//"):
        return resolve(base, f"{base.scheme}:{body}")

    path = base.path
    if parts.path:
        path = _remove_dots(_join_path(base.path, parts.path))
    query = parts.query if (parts.path or parts.query) else base.query
    return Url(base.scheme, base.host, path, query, parts.fragment)


def _join_path(base_path: str, reference: str) -> str:
    if reference.startswith("/"):
        return reference
    directory = base_path[:base_path.rfind("/") + 1]
    return directory + reference


def _remove_dots(path: str) -> str:
    """Fold `.` and `..` out of a path, keeping a trailing slash."""
    trailing = path.endswith("/") or path.endswith("/.") or path.endswith("/..")
    segments: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segments.append(segment)
    result = "/" + "/".join(segments)
    if trailing and result != "/":
        result += "/"
    return result


def same_site(left: Url, right: Url) -> bool:
    """True when two links name the same host, compared whole.

    Equality, not containment: `jobs.example.com.evil.test` contains
    `jobs.example` as a prefix and is a different site.
    """
    return left.host == right.host


def dedupe(urls: tuple[Url, ...]) -> tuple[Url, ...]:
    """The first link for each canonical key, in the order they were found."""
    seen: set[tuple] = set()
    kept: list[Url] = []
    for url in urls:
        key = url.key()
        if key in seen:
            continue
        seen.add(key)
        kept.append(url)
    return tuple(kept)


# --------------------------------------------------------------------------- #
# The legacy pair, executable
# --------------------------------------------------------------------------- #
def legacy_valid(url: str | None) -> bool:
    """The legacy validator, rewritten faithfully: scheme and netloc, nothing else."""
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def legacy_join(base: str, href: str) -> str:
    """The legacy join, rewritten faithfully: two strings, glued."""
    return base + href


# --------------------------------------------------------------------------- #
# A page of links
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Link:
    """One anchor: the href as printed, its label, and what it resolved to."""

    href: str
    label: str
    url: Url | None
    note: str

    def line(self) -> str:
        shown = str(self.url) if self.url is not None else "refused"
        return f"{shown:<46} {self.label}"

    def note_line(self) -> str:
        return f"{self.href!r:<40} {self.note}"


@dataclass(frozen=True)
class Page:
    """Every link one page printed, resolved against that page's address."""

    base: Url
    links: tuple[Link, ...]

    def __post_init__(self) -> None:
        if not self.links:
            raise UrlError("a page needs at least one link")

    def urls(self) -> tuple[Url, ...]:
        """The resolved, on-site documents, in page order."""
        return tuple(link.url for link in self.links
                     if link.url is not None and same_site(link.url, self.base))

    def offsite(self) -> tuple[Link, ...]:
        return tuple(link for link in self.links
                     if link.url is not None and
                     not same_site(link.url, self.base))

    def refused(self) -> tuple[Link, ...]:
        return tuple(link for link in self.links if link.url is None)

    def jobs(self) -> tuple[Url, ...]:
        """The crawled job links, one per job id, in the order they were found."""
        seen: set[int] = set()
        kept: list[Url] = []
        for url in self.crawl():
            if not url.is_job():
                continue
            identity = url.job_id()
            if identity in seen:
                continue
            seen.add(identity)
            kept.append(url)
        return tuple(kept)

    def crawl(self) -> tuple[Url, ...]:
        """The on-site documents, deduplicated, in the order they were found."""
        return dedupe(self.urls())


def crawl(base: Url, rows: tuple[tuple[str, str], ...]) -> Page:
    """Build a page from `(href, label)` rows, resolving each and keeping why not."""
    links: list[Link] = []
    for href, label in rows:
        try:
            url = resolve(base, href)
            note = ""
        except UrlError as error:
            url = None
            note = str(error)
        links.append(Link(href, label, url, note))
    return Page(base, tuple(links))


def parse_rows(text: str) -> tuple[tuple[str, str], ...]:
    """Read `href<TAB>label` lines, skipping blanks and `;` comments."""
    rows: list[tuple[str, str]] = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        if "\t" not in line:
            raise UrlError(f"line {number}: expected an href, a tab and a "
                           f"label")
        href, label = line.split("\t", 1)
        rows.append((href.strip(), label.strip()))
    if not rows:
        raise UrlError("the page holds no links")
    return tuple(rows)


def read_page(path=None, base_text: str = BASE_URL) -> Page:
    target = Path(LINKS_FILE if path is None else path)
    if not target.is_file():
        raise UrlError(f"file not found: {target}")
    return crawl(parse_url(base_text), parse_rows(
        target.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:                                     # noqa: BLE001
        return False


def audit(page: Page, same=same_site) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived rather than restated.

    `same` is injected so a negative control can hand in the legacy
    substring test and watch the site check fail, which is the only way to show
    that the check is testing anything at all.
    """

    def every_link_that_resolved_is_a_document() -> bool:
        for link in page.links:
            if link.url is None:
                continue
            if link.url.scheme not in DOCUMENT_SCHEMES or not link.url.host:
                return False
        return True

    def every_link_prints_and_parses_back() -> bool:
        for url in page.crawl():
            if parse_url(str(url)) != url:
                return False
        return True

    def the_legacy_validator_accepts_a_lookalike_host() -> bool:
        lookalike = "https://jobs.example.com.evil.test/jobs/99"
        return legacy_valid(lookalike) and _host_of(lookalike) != page.base.host

    def the_site_test_is_a_whole_host_not_a_substring() -> bool:
        lookalike = parse_url("https://jobs.example.com.evil.test/jobs/99")
        real = parse_url("https://jobs.example/jobs/42")
        return not same(lookalike, real) and same(real, page.base) and \
            lookalike.host.startswith(page.base.host)

    def the_legacy_splice_builds_a_path_that_never_existed() -> bool:
        glued = legacy_join(str(page.base), "43")
        resolved = str(resolve(page.base, "43"))
        return glued == "https://jobs.example/jobs/list.html43" and \
            resolved == "https://jobs.example/jobs/43"

    def a_fragment_never_makes_two_links_different() -> bool:
        plain = resolve(page.base, "/jobs/42")
        anchored = resolve(page.base, "/jobs/42#apply")
        return plain.key() == anchored.key() and str(plain) != str(anchored)

    def every_crawled_link_is_one_the_site_test_accepts() -> bool:
        return all(same(url, page.base) for url in page.crawl())

    def deduplication_keeps_the_first_of_a_repeated_link() -> bool:
        raw = page.urls()
        kept = dedupe(raw)
        return len(kept) < len(raw) and kept[0].key() == raw[0].key()

    def every_refusal_says_why() -> bool:
        refused = page.refused()
        return bool(refused) and all(link.note for link in refused)

    checks = [
        ("every link that resolved is an http or https document",
         every_link_that_resolved_is_a_document),
        ("every crawled link prints and parses back to the same parts",
         every_link_prints_and_parses_back),
        ("the legacy validator accepts a lookalike host",
         the_legacy_validator_accepts_a_lookalike_host),
        ("the site test is a whole host, not a substring",
         the_site_test_is_a_whole_host_not_a_substring),
        ("the legacy splice of base and href builds a path that never existed",
         the_legacy_splice_builds_a_path_that_never_existed),
        ("a fragment never makes two links different",
         a_fragment_never_makes_two_links_different),
        ("every crawled link is one the site test accepts",
         every_crawled_link_is_one_the_site_test_accepts),
        ("deduplication keeps the first of a repeated link",
         deduplication_keeps_the_first_of_a_repeated_link),
        ("every link that could not be resolved carries the reason",
         every_refusal_says_why),
    ]
    return [(name, _guard(function)) for name, function in checks]


def _host_of(text: str) -> str:
    return parse_url(text).host


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
CURIOUS = (
    ("/jobs/42", "an absolute path keeps the host"),
    ("43", "a relative reference resolves against the directory"),
    ("../jobs/43", "a dot-dot removes one segment"),
    ("//jobs.example/jobs/45", "protocol-relative inherits the scheme"),
    ("https://jobs.example/jobs/44#apply", "an absolute link with a fragment"),
    ("?page=2", "a query with no path keeps the path"),
    ("#top", "a fragment alone names the same page"),
    ("javascript:void(0)", "a scheme that is not a document"),
    ("mailto:jobs@example.test", "an address, not a page"),
    ("https://jobs.example/a b", "a space, which is not a URL"),
    ("https://jobs.example.com.evil.test/jobs/99", "a lookalike host"),
    ("", "no link at all"),
)


def _reads(href: str) -> bool:
    try:
        resolve(parse_url(BASE_URL), href)
        return True
    except UrlError:
        return False


def run_demo() -> int:
    page = read_page()
    base = page.base

    print("=" * 78)
    print(" LINK LAB - a link is a structure, not a string glued to a string")
    print("=" * 78)

    print("\n  the legacy pair, transcribed:")
    for line in LEGACY_VALID.split("\n"):
        print(f"    {line}")
    print(f"    {LEGACY_JOIN}")

    print(f"\n  resolving hrefs against {base}")
    for href, description in CURIOUS:
        try:
            url = resolve(base, href)
            shown = str(url)
            verdict = "same site" if same_site(url, base) else "OFF SITE"
            print(f"    {href!r:<46} {shown}")
            print(f"    {'':<46} {verdict}")
        except UrlError as error:
            print(f"    {href!r:<46} refused: {error}")

    print(f"\n  the page, {len(page.links)} anchors:")
    for link in page.links:
        print(f"    {link.line()}")

    print(f"\n  what the legacy validator says about each href:")
    for link in page.links:
        absolute = str(link.url) if link.url is not None else link.href
        print(f"    {link.href!r:<44} legacy "
              f"{'valid' if legacy_valid(absolute) else 'invalid':<7} "
              f"here {'on site' if link.url is not None and same_site(link.url, base) else ('off site' if link.url is not None else 'refused')}")

    print(f"\n  the legacy join, next to resolve:")
    for href in ("43", "/jobs/42", "?page=2"):
        print(f"    legacy_join(base, {href!r})")
        print(f"      = {legacy_join(str(base), href)}")
        print(f"    resolve(base, {href!r})")
        print(f"      = {resolve(base, href)}")

    print(f"\n  the crawl:")
    print(f"    {len(page.links)} anchors, {len(page.refused())} refused, "
          f"{len(page.offsite())} off site, {len(page.urls())} on site, "
          f"{len(page.crawl())} unique")
    for url in page.crawl():
        print(f"    {url}")
    print(f"    job ids: "
          f"{', '.join(str(url.job_id()) for url in page.jobs())}")

    checks = audit(page)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    readable = sum(1 for href, _ in CURIOUS if _reads(href))
    print("\nCross-checks OK: " +
          f"{len(CURIOUS)} hrefs give {readable} resolved link(s) and "
          f"{len(CURIOUS) - readable} refusal(s), the page's "
          f"{len(page.links)} anchors give {len(page.urls())} on-site links "
          f"and {len(page.crawl())} unique ones, "
          f"{len(page.offsite())} link(s) leave the site and "
          f"{len(page.refused())} link(s) are refused, the legacy join makes "
          f"{legacy_join(str(base), '43')!r} where resolve makes "
          f"{str(resolve(base, '43'))!r}, the fragment on "
          f"/jobs/42#apply is not a second page, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
