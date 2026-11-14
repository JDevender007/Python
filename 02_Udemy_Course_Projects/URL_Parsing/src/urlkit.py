"""A URL parser written out by hand, and the three slices it replaces.

The legacy program took one URL and cut it with ``find``:

    url = 'https://www.kaggle.com/datasets'

    protocol_pos = url.find(":")
    dot1 = url.find(".")
    dot2 = url.find(".", dot1 + 1)

    protocol = url[:protocol_pos]
    domain = url[dot1 + 1:dot2]

    slash = url.find("/", dot2)
    page = url[slash:]

Three defects, and each one is a different kind of blindness.

**1. The domain is whatever sits between the first and second dot.** For the
URL in the file, that is ``"kaggle"``: the ``www.`` and the ``.com`` are both
thrown away, so the host cannot be resolved and the TLD is gone. A host with
four labels (``sub.domain.example.co.uk``) is cut down to ``"domain"``.

**2. When there is no second dot, ``find`` returns -1 and the slice silently
drops a character.** ``'https://example.com'`` has one dot, so
``url[dot1 + 1:dot2]`` is ``url[16:-1]`` - the last character is lost and the
"domain" is ``'co'``. ``slash = url.find("/", -1)`` then starts at the final
character, finds nothing, and ``page`` becomes ``url[-1:]``: the letter
``'m'``.

**3. Without a dot, the domain is the entire rest of the URL.**
``'http://localhost:8000/'`` has no dot at all, so ``dot1`` and ``dot2`` are
both -1 and ``domain = url[0:-1]`` is ``'http://localhost:8000'`` - scheme,
separator, host and port, with only the trailing slash removed.

The replacement parses the URL the way RFC 3986 describes it:

    scheme ":" "//" [ userinfo "@" ] host [ ":" port ] path
                   [ "?" query ] [ "#" fragment ]

with IPv6 hosts in brackets, ports validated as 1..65535, query parameters
percent-decoded (and repeated keys preserved), and a ``normalise`` step that
lowercases the scheme and host, drops the default port and turns an empty path
into ``/``.

The demo parses the twenty bundled URLs and compares six fields of every one
against ``urllib.parse.urlsplit``, so the hand-rolled parser is checked against
the standard library rather than against itself.

Standard library only -- no network, no third-party parser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "urls.txt"

#: Ports that add nothing to a URL and are removed by ``normalise``.
DEFAULT_PORTS = {"http": 80, "https": 443, "ftp": 21}

SCHEME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*")
IPV4_PATTERN = re.compile(
    r"(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)")
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


class URLParseError(ValueError):
    """A URL, port or percent escape that cannot be read."""


# --------------------------------------------------------------------------- #
# The parsed form
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class URL:
    """The seven components of a URL, plus whether ``//`` was present."""

    scheme: str | None = None
    userinfo: str | None = None
    host: str = ""
    port: int | None = None
    path: str = ""
    query: str = ""
    fragment: str = ""
    has_authority: bool = False

    def __post_init__(self) -> None:
        if self.scheme is not None:
            if not isinstance(self.scheme, str):
                raise URLParseError("scheme must be a string or None")
            if not SCHEME_PATTERN.fullmatch(self.scheme):
                raise URLParseError(f"{self.scheme!r} is not a valid scheme")
            object.__setattr__(self, "scheme", self.scheme.lower())
        if self.userinfo is not None and not isinstance(self.userinfo, str):
            raise URLParseError("userinfo must be a string or None")
        if not isinstance(self.host, str):
            raise URLParseError("host must be a string")
        if self.port is not None:
            if isinstance(self.port, bool) or not isinstance(self.port, int):
                raise URLParseError("port must be an integer or None")
            if not 1 <= self.port <= 65535:
                raise URLParseError(f"port {self.port} is outside 1..65535")
        for name in ("path", "query", "fragment"):
            if not isinstance(getattr(self, name), str):
                raise URLParseError(f"{name} must be a string")

    @property
    def authority(self) -> str:
        """``userinfo@host:port``, with brackets around an IPv6 host."""
        text = ""
        if self.userinfo is not None:
            text += self.userinfo + "@"
        if ":" in self.host and not self.host.startswith("["):
            text += "[" + self.host + "]"
        else:
            text += self.host
        if self.port is not None:
            text += ":" + str(self.port)
        return text

    def to_url(self) -> str:
        """Rebuild the URL.

        An empty query or fragment is not rendered, so the original ``?`` or
        ``#`` cannot be recovered from a URL that had nothing after it. Every
        non-empty component round-trips exactly.
        """
        text = f"{self.scheme}:" if self.scheme else ""
        if self.has_authority:
            text += "//" + self.authority
        text += self.path
        if self.query:
            text += "?" + self.query
        if self.fragment:
            text += "#" + self.fragment
        return text

    def to_dict(self) -> dict:
        return {"scheme": self.scheme, "userinfo": self.userinfo,
                "host": self.host, "port": self.port, "path": self.path,
                "query": self.query, "fragment": self.fragment,
                "has_authority": self.has_authority}


# --------------------------------------------------------------------------- #
# Percent decoding
# --------------------------------------------------------------------------- #
def percent_decode(text) -> str:
    """Decode ``%XX`` escapes and ``+`` as a space, strictly.

    A stray ``%`` is refused rather than passed through: silently keeping it
    is how a broken escape reaches a database. Bytes are decoded as UTF-8, so
    ``na%C3%AFve`` becomes the six-character word.
    """
    if not isinstance(text, str):
        raise URLParseError(f"text must be a string, got {type(text).__name__}")
    raw = bytearray()
    index = 0
    while index < len(text):
        character = text[index]
        if character == "%":
            escape = text[index + 1:index + 3]
            if len(escape) != 2 or any(digit not in HEX_DIGITS
                                       for digit in escape):
                raise URLParseError(
                    f"'%{escape}' is not a valid percent escape")
            raw.append(int(escape, 16))
            index += 3
        elif character == "+":
            raw.append(0x20)
            index += 1
        else:
            raw.extend(character.encode("utf-8"))
            index += 1
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise URLParseError("the decoded bytes are not valid UTF-8") from None


def query_params(value) -> list[tuple[str, str]]:
    """Decoded ``(key, value)`` pairs, in order, repeated keys preserved."""
    url = parse(value) if isinstance(value, str) else value
    if not isinstance(url, URL):
        raise URLParseError("query_params needs a URL or a string")
    if not url.query:
        return []
    pairs: list[tuple[str, str]] = []
    for piece in url.query.split("&"):
        if not piece:
            continue
        key, _, value_part = piece.partition("=")
        pairs.append((percent_decode(key), percent_decode(value_part)))
    return pairs


# --------------------------------------------------------------------------- #
# Ports and authorities
# --------------------------------------------------------------------------- #
def _parse_port(raw: str) -> int | None:
    if raw == "":
        return None
    if not (raw.isascii() and raw.isdigit()):
        raise URLParseError(f"port {raw!r} is not a number")
    port = int(raw)
    if not 1 <= port <= 65535:
        raise URLParseError(f"port {port} is outside 1..65535")
    return port


def _parse_authority(authority: str) -> tuple[str | None, str, int | None]:
    userinfo = None
    if "@" in authority:
        userinfo, authority = authority.rsplit("@", 1)
    if authority.startswith("["):
        close = authority.find("]")
        if close == -1:
            raise URLParseError("an IPv6 host needs a closing ']'")
        host = authority[1:close]
        remainder = authority[close + 1:]
        if remainder and not remainder.startswith(":"):
            raise URLParseError(
                f"unexpected text after an IPv6 host: {remainder!r}")
        port = _parse_port(remainder[1:]) if remainder else None
        return userinfo, host, port
    if ":" in authority:
        host, raw_port = authority.rsplit(":", 1)
        if ":" in host:
            raise URLParseError(
                "an IPv6 address must be enclosed in brackets")
        return userinfo, host, _parse_port(raw_port)
    return userinfo, authority, None


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse(url) -> URL:
    """Split a URL into scheme, userinfo, host, port, path, query, fragment."""
    if not isinstance(url, str):
        raise URLParseError(f"a URL must be a string, got "
                            f"{type(url).__name__}")
    if not url:
        raise URLParseError("the URL is empty")
    if any(character in url for character in " \t\r\n"):
        raise URLParseError("the URL contains raw whitespace; percent-encode it")

    text = url
    fragment = ""
    if "#" in text:
        text, fragment = text.split("#", 1)
    query = ""
    if "?" in text:
        text, query = text.split("?", 1)

    scheme = None
    rest = text
    colon = text.find(":")
    slash = text.find("/")
    if colon != -1 and (slash == -1 or colon < slash):
        candidate = text[:colon]
        if not SCHEME_PATTERN.fullmatch(candidate):
            raise URLParseError(f"{candidate!r} is not a valid scheme")
        scheme = candidate
        rest = text[colon + 1:]

    has_authority = rest.startswith("//")
    userinfo = None
    host = ""
    port = None
    path = rest
    if has_authority:
        rest = rest[2:]
        end = rest.find("/")
        if end == -1:
            end = len(rest)
        authority = rest[:end]
        path = rest[end:]
        userinfo, host, port = _parse_authority(authority)

    return URL(scheme=scheme, userinfo=userinfo, host=host, port=port,
               path=path, query=query, fragment=fragment,
               has_authority=has_authority)


# --------------------------------------------------------------------------- #
# Classification and normalisation
# --------------------------------------------------------------------------- #
def host_kind(host) -> str:
    """``ipv6``, ``ipv4``, ``domain``, ``localhost``, ``single-label`` or ``none``."""
    if not isinstance(host, str):
        raise URLParseError("the host must be a string")
    if not host:
        return "none"
    if ":" in host:
        return "ipv6"
    if IPV4_PATTERN.fullmatch(host):
        return "ipv4"
    if host.casefold() == "localhost":
        return "localhost"
    labels = host.rstrip(".").split(".")
    if len(labels) >= 2 and len(labels[-1]) >= 2 and labels[-1].isalpha():
        return "domain"
    return "single-label"


def normalise(url) -> str:
    """Lowercase scheme and host, drop the default port, empty path to ``/``."""
    parsed = parse(url) if isinstance(url, str) else url
    if not isinstance(parsed, URL):
        raise URLParseError("normalise needs a URL or a string")
    scheme = parsed.scheme.lower() if parsed.scheme else None
    host = parsed.host.lower()
    port = parsed.port
    if scheme in DEFAULT_PORTS and port == DEFAULT_PORTS[scheme]:
        port = None
    path = parsed.path
    if parsed.has_authority and path == "":
        path = "/"
    return URL(scheme=scheme, userinfo=parsed.userinfo, host=host, port=port,
               path=path, query=parsed.query, fragment=parsed.fragment,
               has_authority=parsed.has_authority).to_url()


# --------------------------------------------------------------------------- #
# The legacy program
# --------------------------------------------------------------------------- #
def legacy_parts(url) -> dict:
    """The original three ``find`` slices, reproduced exactly."""
    if not isinstance(url, str):
        raise URLParseError("a URL must be a string")
    protocol_pos = url.find(":")
    dot1 = url.find(".")
    dot2 = url.find(".", dot1 + 1)

    protocol = url[:protocol_pos]
    domain = url[dot1 + 1:dot2]

    slash = url.find("/", dot2)
    page = url[slash:]
    return {"protocol": protocol, "domain": domain, "page": page}


# --------------------------------------------------------------------------- #
# The bundled list
# --------------------------------------------------------------------------- #
def load_urls(path: str | Path = DATA_FILE) -> list[str]:
    """One URL per line; ``#`` starts a comment, blank lines are skipped."""
    path = Path(path)
    if not path.exists():
        raise URLParseError(f"URL list not found: {path}")
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text and not text.startswith("#"):
            urls.append(text)
    if not urls:
        raise URLParseError(f"{path.name} has no URLs")
    return urls


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    from urllib.parse import parse_qsl, urlsplit

    print("=" * 70)
    print(" URL PARSING - three find() slices, and a parser that reads the grammar")
    print("=" * 70)

    # 1. the kaggle URL loses www and .com
    kaggle = "https://www.kaggle.com/datasets"
    legacy = legacy_parts(kaggle)
    assert legacy == {"protocol": "https", "domain": "kaggle",
                      "page": "/datasets"}, legacy
    fixed = parse(kaggle)
    assert fixed.host == "www.kaggle.com"
    assert fixed.path == "/datasets" and fixed.port is None
    print(f"  legacy: domain {legacy['domain']!r} - www and .com gone; "
          f"fixed: host {fixed.host!r}")

    # 2. no second dot: find returns -1 and the slice drops the last character
    bare = "https://example.com"
    legacy = legacy_parts(bare)
    assert legacy["domain"] == "co"
    assert legacy["page"] == "m"
    assert parse(bare).path == ""
    print(f"  legacy on {bare!r}: domain {legacy['domain']!r}, "
          f"page {legacy['page']!r}; fixed: an empty path")

    # 3. no dot at all: the domain is the whole rest of the string
    local = "http://localhost:8000/"
    legacy = legacy_parts(local)
    assert legacy["domain"] == "http://localhost:8000"
    assert legacy["page"] == "/"
    assert parse(local).host == "localhost"
    assert parse(local).port == 8000
    print(f"  legacy on {local!r}: domain {legacy['domain']!r} "
          f"(scheme and port included)")

    # 4. four labels become one
    deep = "https://sub.domain.example.co.uk/a/b?x=1&y=2#top"
    assert legacy_parts(deep)["domain"] == "domain"
    assert parse(deep).host == "sub.domain.example.co.uk"
    print("  four labels: legacy 'domain', fixed "
          "'sub.domain.example.co.uk'")

    # 5. every bundled URL is parsed, and compared with urlsplit
    urls = load_urls()
    assert len(urls) == 20, len(urls)
    assert len(set(urls)) == 20
    fields = ("scheme", "host", "port", "path", "query", "fragment")
    agreements = 0
    for raw in urls:
        ours = parse(raw)
        reference = urlsplit(raw)
        mine = (ours.scheme or "", ours.host.casefold() or None, ours.port,
                ours.path, ours.query, ours.fragment)
        theirs = (reference.scheme.lower(),
                  reference.hostname.lower() if reference.hostname else None,
                  reference.port, reference.path, reference.query,
                  reference.fragment)
        assert mine == theirs, (raw, mine, theirs)
        agreements += 1
    assert agreements == 20
    print(f"  {agreements} of {agreements} bundled URLs agree with "
          f"urllib.parse.urlsplit on {len(fields)} fields")

    # 6. query parameters: decoded, ordered, repeated keys kept
    repeated = parse("https://example.com/search?q=a%20b&q=c%26d&flag")
    assert query_params(repeated) == [("q", "a b"), ("q", "c&d"),
                                      ("flag", "")]
    utf8 = query_params("https://example.com/?name=na%C3%AFve")
    assert utf8 == [("name", "na\u00efve")]
    assert len(utf8[0][1]) == 5
    for raw in urls:
        expected = parse_qsl(urlsplit(raw).query, keep_blank_values=True)
        assert query_params(parse(raw)) == expected, raw
    print("  query params decoded ('a%20b' -> 'a b', '+' -> space), "
          "repeated keys kept, blank values kept, 20/20 match parse_qsl")

    # 7. percent escapes are strict
    refused = 0
    for bad in ("%zz", "%4", "%G0"):
        try:
            percent_decode(bad)
        except URLParseError:
            refused += 1
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    assert percent_decode("%41%42") == "AB"
    assert percent_decode("a+b") == "a b"
    print(f"  {refused} broken percent escapes refused; "
          f"'%41%42' -> 'AB', 'a+b' -> 'a b'")

    # 8. ports are numbers in 1..65535, and empty means absent
    assert parse("http://example.com:8080/").port == 8080
    assert parse("http://example.com:/").port is None
    for bad in ("http://example.com:0/", "http://example.com:65536/",
                "http://example.com:http/"):
        try:
            parse(bad)
        except URLParseError:
            pass
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    print("  8080 accepted, an empty port means none, 0 / 65536 / 'http' "
          "refused")

    # 9. IPv6 hosts need brackets and are rebuilt with them
    address = parse("https://[2001:db8::1]:8080/v1/items")
    assert address.host == "2001:db8::1"
    assert address.port == 8080
    assert address.to_url() == "https://[2001:db8::1]:8080/v1/items"
    assert parse("http://[::1]/").host == "::1"
    for bad in ("https://[::1/", "http://::1/"):
        try:
            parse(bad)
        except URLParseError:
            pass
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    print("  IPv6: '[2001:db8::1]:8080' parsed and rebuilt; a missing ']' "
          "and an unbracketed address refused")

    # 10. normalise: case, default ports, empty path
    assert normalise("HTTPS://Example.COM:443") == "https://example.com/"
    assert normalise("http://example.com:80/plain") == \
        "http://example.com/plain"
    assert normalise("ftp://example.com:21/pub") == "ftp://example.com/pub"
    assert normalise("http://example.com:8080/x") == \
        "http://example.com:8080/x"
    assert normalise("https://example.com/a?b=1#c") == \
        "https://example.com/a?b=1#c"
    for raw in urls:
        once = normalise(raw)
        assert normalise(once) == once, raw
    print("  normalise lowercases the host, drops 80/443/21, adds the empty "
          "path, and is idempotent on all 20 URLs")

    # 11. host kinds
    assert host_kind("example.com") == "domain"
    assert host_kind("192.168.0.1") == "ipv4"
    assert host_kind("2001:db8::1") == "ipv6"
    assert host_kind("localhost") == "localhost"
    assert host_kind("intranet") == "single-label"
    assert host_kind("") == "none"
    assert host_kind("999.1.1.1") == "single-label"   # not a valid address
    assert host_kind("example.com.") == "domain"      # a trailing root dot
    print("  host kinds: domain, ipv4, ipv6, localhost, single-label, none")

    # 12. a URL without a scheme, and one without an authority
    relative = parse("//example.com/x")
    assert relative.scheme is None and relative.host == "example.com"
    assert relative.has_authority is True
    mail = parse("mailto:user@example.com")
    assert mail.scheme == "mailto" and mail.host == ""
    assert mail.path == "user@example.com"
    assert mail.has_authority is False
    assert parse("file:///C:/temp/report.txt").path == "/C:/temp/report.txt"
    print("  '//example.com/x', 'mailto:...' and 'file:///C:/...' all parse")

    # 13. bad input is refused, not guessed at
    for bad in ("", "   ", None, 42, "https://example.com/a b"):
        try:
            parse(bad)
        except URLParseError:
            pass
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    for bad in ("1http://example.com/", "ht tp://example.com/"):
        try:
            parse(bad)
        except URLParseError:
            pass
        else:
            raise AssertionError(f"{bad!r} should have been refused")
    print("  5 non-URL inputs and 2 bad schemes refused")

    # 14. the rebuilt URL is stable
    for raw in urls:
        rebuilt = parse(raw).to_url()
        assert rebuilt == raw, (raw, rebuilt)
    print("  all 20 URLs rebuild byte for byte from their components")

    print()
    print("Cross-checks OK: the legacy slices produced 'kaggle' for "
          "www.kaggle.com, 'co' and 'm' for a bare host, and the whole "
          "'http://localhost:8000' string as the domain, 20 bundled URLs "
          "agreed with urllib.parse.urlsplit on 6 fields each, query "
          "parameters were decoded with repeated keys preserved and 20/20 "
          "matched parse_qsl, 3 broken percent escapes refused, 3 bad ports "
          "refused, IPv6 hosts parsed and rebuilt with brackets, normalise "
          "lowercased and dropped default ports and was idempotent, 6 host "
          "kinds classified, 3 unusual shapes parsed, 7 bad inputs refused, "
          "and every URL rebuilt byte for byte")
    print("\nDemo completed successfully.")
    return 0
