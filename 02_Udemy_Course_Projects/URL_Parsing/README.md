<div align="center">

# 🔗 URL Parsing

### The course version cut a URL into three pieces with `find()`. It reported the host `kaggle` for `www.kaggle.com`, `co` for `example.com`, and the entire string `http://localhost:8000` as a "domain" — because `find()` returns `-1` and Python slices accept it without complaint.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

The original program found three positions and sliced between them:

```python
url = "https://www.kaggle.com/datasets"

protocol_pos = url.find(":")
dot1 = url.find(".")
dot2 = url.find(".", dot1 + 1)

protocol = url[:protocol_pos]
domain = url[dot1 + 1:dot2]

slash = url.find("/", dot2)
page = url[slash:]
```

It works on the one URL in the lesson, which is exactly what makes it dangerous.

**1 · The domain is whatever sits between the first and second dot.** For the lesson URL that is `'kaggle'`: `www.` and `.com` are both discarded, so the host cannot be resolved and the TLD is gone. A four-label host collapses to one label:

```text
https://sub.domain.example.co.uk/a/b  ->  'domain'
```

**2 · When there is no second dot, `find` returns `-1` and the slice silently drops a character.** `https://example.com` has one dot, so `url[dot1 + 1:dot2]` is `url[16:-1]` — the last character is lost:

```text
legacy on 'https://example.com': domain 'co', page 'm'
```

`slash = url.find("/", -1)` searches from the final character, finds nothing, and `page` becomes `url[-1:]`: the letter `'m'`.

**3 · Without a dot, the "domain" is the whole rest of the string.** `http://localhost:8000/` has no dot, so both positions are `-1` and `url[0:-1]` is `'http://localhost:8000'` — scheme, separator, host and port, with only the trailing slash removed.

None of these raise. `-1` is a legal slice index, so the program prints a wrong answer with full confidence.

The replacement parses the grammar from RFC 3986:

```text
scheme ":" "//" [ userinfo "@" ] host [ ":" port ] path
               [ "?" query ] [ "#" fragment ]
```

```text
>>> parse("https://user:pass@example.com:8443/path?q=1#c")
scheme=https  userinfo=user:pass  host=example.com  port=8443
path=/path   query=q=1            fragment=c
```

**It is checked against the standard library, not against itself.** The demo parses all twenty bundled URLs and compares six fields of every one with `urllib.parse.urlsplit`, and every query string with `urllib.parse.parse_qsl`:

```text
20 of 20 bundled URLs agree with urllib.parse.urlsplit on 6 fields
... and 20/20 match parse_qsl
```

**The tricky parts are the ones a `split("/")` never gets right:**

- **IPv6 hosts** are bracketed, and the brackets are part of the syntax — not of the address. `https://[2001:db8::1]:8080/v1` parses to host `2001:db8::1`, port `8080`, and rebuilds with the brackets back. `http://::1/` is refused, because without brackets the colons are ambiguous.
- **Ports are numbers in 1..65535**, and an empty port (`example.com:/`) means *no* port rather than port zero.
- **Percent escapes are strict.** `%41%42` is `AB`, `%C3%AF` is `ï`, `+` is a space, and a stray `%` or `%zz` is an error — silently passing a broken escape through is how corrupt data reaches a database.
- **Repeated query keys survive.** `?q=a&q=b` is two pairs in order, and `?flag` is a key with an empty value. A dict would lose both facts.
- **`normalise` lowercases the scheme and host, drops the default port (80/443/21), and turns an empty path into `/`** — and is idempotent on all twenty URLs, which the demo asserts.
- **Byte-for-byte rebuilds.** `parse(raw).to_url() == raw` for all twenty URLs. The one thing that cannot round-trip is a bare `?` or `#` with nothing after it, and the docstring says so instead of pretending otherwise.

Standard library only — no network, no third-party parser.

---

# ✨ Features

- `parse` — scheme, userinfo, host, port, path, query, fragment, `has_authority`
- `URL` — frozen dataclass; scheme validated against the RFC pattern, port against 1..65535
- `URL.authority` — rebuilds `userinfo@host:port`, bracketing an IPv6 host
- `URL.to_url` — rebuilt string; empty query/fragment are omitted
- `percent_decode` — strict `%XX`, `+` as space, UTF-8 bytes, broken escapes refused
- `query_params` — decoded `(key, value)` pairs in order, repeats and blanks preserved
- `host_kind` — `domain`, `ipv4`, `ipv6`, `localhost`, `single-label`, `none`
- `normalise` — lowercase scheme and host, drop 80/443/21, empty path to `/`, idempotent
- `legacy_parts` — the original three `find()` slices, reproduced exactly
- `load_urls` — comments, blank lines, line-stripping, errors for missing/empty files
- `data/urls.txt` — 20 URLs covering ports, userinfo, IPv6, `file://`, repeats, escapes, mixed case
- CLI: `--parse`, `--normalise`, `--params`, `--legacy`, `--file`, `--json`, `--quiet`
- Exit `2` on a `URLParseError`; `--demo` always returns `0`
- 179 passing pytest tests

---

# 📂 Folder Structure

```text
URL_Parsing/
│
├── src/
│   ├── main.py   # CLI: parse, normalise, params, legacy view, list
│   └── urlkit.py # URL, parse, percent decoding, query params, normalise
│
├── tests/
│   └── test_urlkit.py
│
├── data/
│   └── urls.txt  # 20 URLs
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 02_Udemy_Course_Projects/URL_Parsing

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo
python src/main.py --demo

# The bundled twenty URLs, classified
python src/main.py

# One URL, component by component
python src/main.py --parse "https://user:pass@example.com:8443/path?q=1#frag"

# Lowercase, drop the default port, fill the path
python src/main.py --normalise "HTTPS://Example.COM:443"

# Decoded query parameters, repeats preserved
python src/main.py --params "https://example.com/search?q=a%20b&q=c%26d&flag"

# What the original three slices would have produced
python src/main.py --legacy "https://www.kaggle.com/datasets"
python src/main.py --legacy "https://example.com"
```

**Exit codes:** `0` = the command ran · `2` = not a string, empty input, raw whitespace, an invalid scheme, a bad port, an unclosed IPv6 bracket, a broken percent escape, or a missing/empty URL list.

---

# 🧠 How It Works

```text
url
 │
 ├── split on '#'  -> fragment   (first '#', the rest is kept)
 ├── split on '?'  -> query      (first '?', the rest is kept)
 ├── scheme?       -> a ':' before the first '/'
 ├── '//'?         -> authority = [userinfo '@'] host [':' port]
 │                     └── IPv6 host must be bracketed
 └── remainder     -> path
```

Details worth knowing:

- **The fragment is split off before the query**, because `#` ends the query — a `?` inside a fragment is not a query, and a `#` inside a query is not a fragment. Splitting on the first occurrence of each, in that order, gets both right.
- **The scheme test is a position test, not a pattern test.** `mailto:user@example.com` has a scheme; `/a:b` does not, because the first `/` comes before the `:`. Only then is the RFC pattern applied to the candidate.
- **Userinfo is split on the *last* `@`**, so a password containing `@` survives: `user:p@ss@example.com` gives `userinfo = "user:p@ss"`.
- **`find` returning `-1` is the whole bug class.** `s[a:-1]` is "everything except the last character", and `s[-1:]` is "the last character" — both are valid expressions, so a wrong answer looks like a right one.
- **`host_kind` refuses to guess.** `999.1.1.1` is not a valid address, so it is `single-label` rather than `ipv4`; a trailing root dot (`example.com.`) is still a domain.
- **Normalisation only drops a default port when the scheme has one.** `gopher://example.com:80/x` keeps its port, because 80 means nothing for `gopher`.

---

# 🛠 Technologies

- Python 3 standard library: `re`, `dataclasses`, `pathlib`, `argparse`, `json`, `contextlib`, `io`
- `urllib.parse.urlsplit` and `parse_qsl` — used as the reference the parser is tested against
- pytest

No requests library, no browser, no network.

---

# 📚 Concepts Covered

- The URL grammar: scheme, authority, userinfo, host, port, path, query, fragment
- Why `-1` from `find` is the classic silent-slice bug
- Bracketed IPv6 literals versus unbracketed addresses
- Empty port versus port zero
- Percent-encoding and decoding, `+` as space, UTF-8 byte sequences
- Strict versus lenient validation, and why leniency loses data
- Query strings as an ordered list of pairs rather than a dict
- Normalisation and idempotence
- Property-style cross-checks against a reference implementation
- Frozen dataclasses as validated records

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**179 tests passed** covering percent decoding (plain, upper/lower escapes, space, `+`, `%2B`, UTF-8, multibyte, empty, seven broken escapes, a non-UTF-8 byte, non-text), `URL` validation (default, scheme lowercasing, five invalid schemes, five non-string fields, the port range with both ends, booleans and strings, immutability, `to_dict`), authority and rendering (userinfo, port, IPv6 brackets, empty authority, empty query/fragment elision, `file:///`), parsing (scheme, host case, empty and trailing path, ports, empty port, userinfo with an `@` inside, query, fragment, both orders, `?` and `#` inside the other, IPv6, IPv4, `mailto:`, protocol-relative, `file://`, double slashes, a colon after a slash, five rejected inputs, four non-strings, three bad schemes, three bad ports, three IPv6 errors), query parameters (no query, one and two pairs, both sides decoded, `+`, repeats, valueless key, empty value, skipped empties, a parsed `URL`, UTF-8, a broken escape, a meaningless argument), host kinds (eleven cases plus a non-string), normalisation (scheme and host case, three default ports, a non-default port, the empty path, path/query/fragment, userinfo case, IPv6 brackets, a parsed URL, idempotence on all twenty URLs, an unknown scheme, and the defaults table), the legacy slices (six shapes plus a non-string), the bundled list (twenty unique, the pinned first entry, IPv6/`file://`/repeated-key presence, `urlsplit` and `parse_qsl` agreement on all twenty, comments, stripping, two loader errors), the demo, and every CLI mode including JSON and quiet.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
