<div align="center">

# 🔗 Job Listing Scraper

### The legacy scraper approved any link with a scheme and a `netloc`, so `https://jobs.example.com.evil.test/` — a domain that merely *contains* the site's name — was followed. And it built the absolute link with `base + href`, which on a real page produces `.../list.html43`.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False

def absolute_url(base, href):
    return base + href
```

**1 → `netloc` is not the site.** `https://jobs.example.com.evil.test/jobs/99` has
an `http` scheme and a non-empty `netloc`, so the legacy check says yes. A crawler
confined by *containment* — "does the host contain our name" — follows it. A
crawler confined by **host equality** does not:

```text
'https://jobs.example.com.evil.test/jobs/99'
legacy valid          here OFF SITE
the lookalike host starts with the real one: True
```

**2 → Gluing two strings together is not resolving a reference.** `base + href`
on the page `https://jobs.example/jobs/list.html` and the href `43` gives
`.../list.html43`, a page that never existed. Resolution is arithmetic on the
parts: a relative reference is joined to the **directory** of the base, `..`
removes one segment, a rooted path replaces the path, and a query replaces rather
than appends:

```text
legacy_join(base, '43')   = https://jobs.example/jobs/list.html43
resolve(base, '43')       = https://jobs.example/jobs/43
```

**3 → A fragment is not part of the address.** `/jobs/42` and `/jobs/42#apply` are
one page, fetched once. Comparing strings fetches it twice; a crawl with no
deduplication visits the same page for every anchor on it. The bundled page has
nine anchors, seven on site, and **six** unique pages:

```text
9 anchors, 1 refused, 1 off site, 7 on site, 6 unique
job ids: 42, 43, 44, 45
```

**4 → A scheme is not always a document.** `javascript:void(0)` parses with a
scheme and no host; `mailto:` with an address. Neither is a page, and the legacy
validator rejects the first only by accident of `netloc` — it would accept any
`http` link whatever its characters.

**5 → A space is not a URL.** `urlparse` never validates characters, so
`"https://jobs.example/a b"` parses happily. A link with a space in it is a link
somebody forgot to encode, and it is refused here by name.

| href, against `.../jobs/list.html` | legacy `base + href` | here |
|---|---|---|
| `43` | `.../list.html43` | `https://jobs.example/jobs/43` |
| `/jobs/42` | `.../list.html/jobs/42` | `https://jobs.example/jobs/42` |
| `//jobs.example/jobs/45` | `.../list.html//jobs.example/jobs/45` | `https://jobs.example/jobs/45` |
| `#top` | `.../list.html#top` | `.../list.html#top`, same page as the base |
| `?page=2` | `.../list.html?page=2` | `.../list.html?page=2`, path kept |
| `javascript:void(0)` | `.../list.htmljavascript:void(0)` | refused: not a document |
| `https://...com.evil.test/jobs/99` | accepted by legacy | refused by host equality |
| a page printed twice with a different fragment | fetched twice | one canonical key, fetched once |

The demonstration is offline: one bundled page of anchors, one bundled base, and
no network anywhere. Standard library only: no `requests`, no `beautifulsoup`.

---

# ✨ Features

- `Url` — a link as its five parts (`scheme`, `host`, `path`, `query`,
  `fragment`), validated at construction: only `http`/`https`, a lower-case host,
  no user, a rooted path, and no whitespace or control characters anywhere
- `Key` — `host`, `path` and the query in sorted order, with the fragment
  deliberately absent, so two anchors to one page are one page
- `parse_url` — reads an absolute link, lower-cases the host, drops a trailing
  dot and a numeric port, and refuses the seven shapes that are not a document
- `resolve` — absolute, protocol-relative, rooted, relative, dot-dot, fragment
  only, query only, and the query-replacement rule
- `_remove_dots` / `_join_path` — the two pieces of path arithmetic, exposed and
  tested on their own
- `same_site` — **host equality**, not a substring and not a prefix
- `dedupe` — the first link for each canonical key, in the order found
- `legacy_valid` / `legacy_join` — the two legacy functions, executable, so the
  demo can refute them
- `Link` / `Page` — every anchor with what it resolved to, or the reason it did
  not, and `urls()`, `offsite()`, `refused()`, `jobs()`, `crawl()`
- `parse_rows` — `href<TAB>label` with line-numbered errors
- `audit` — nine named checks with a guard, and `same` injected so a negative
  control can hand in the substring test
- CLI: `--links`, `--base`, `--resolve`, `--audit`, `--json`, `--quiet`, `--demo`
- 170 passing pytest tests

---

# 📂 Folder Structure

```text
Job_Listing_Scraper/
│
├── src/
│   ├── main.py  # CLI: the page and its crawl, one href, the audit
│   └── urls.py  # URLs, resolution, dot folding, confinement, dedupe
│
├── tests/
│   └── test_urls.py
│
├── data/
│   └── links.txt # nine anchors: relative, lookalike host, script link, repeat
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 07_Web_Scraping/Job_Listing_Scraper

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the legacy splice, the lookalike host, the crawl
python src/main.py --demo

# Read the bundled page and crawl it
python src/main.py

# Resolve one href against the bundled base
python src/main.py --resolve "43"

# Resolve several
python src/main.py --resolve "/jobs/42" "//jobs.example/jobs/45" "#top"

# Every check
python src/main.py --audit

# The crawl as JSON
python src/main.py --json crawl.json

# Your own page and your own base
python src/main.py --links .\links.txt --base "https://jobs.example/jobs/list.html"
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed · `2` = a
base that cannot be read, an href that cannot be resolved, a missing file, or a
line without a tab.

---

# ⚙️ How It Works

```text
parse_url(text)
  ├── no whitespace and no control characters
  ├── a scheme is required: a bare href is relative, and needs a base
  ├── the scheme must be http or https
  ├── the host is lower-cased, with a trailing dot and a numeric port removed
  ├── a host cannot name a user ("user:password@...")
  └── the path starts at the root, and defaults to "/"

resolve(base, href)
  ├── has a scheme       -> used as it stands
  ├── starts with "//"   -> the base scheme, otherwise absolute
  ├── starts with "/"    -> the base host, a new path
  ├── anything else      -> joined to the base's DIRECTORY, "." and ".." folded
  ├── no path            -> the base path and the base query
  └── a path             -> its own query, even an empty one; fragment kept

Page.crawl()
  ├── resolve every anchor, keeping the refusal reason
  ├── keep the links whose host EQUALS the base host
  └── dedupe by (host, path, sorted query) -- the fragment is not an identity
```

Details worth knowing:

- **Confinement is equality.** `jobs.example.com.evil.test` has `jobs.example` as a
  prefix and is a different site. It is also why the site test is injected into
  `audit`: a negative control hands in the substring test and watches the check
  fail, which is the only evidence that the check tests anything.
- **Resolution is arithmetic.** The base's *directory* is `path` up to its last
  `/`, never the file name. That one rule is the difference between
  `.../jobs/43` and `.../list.html43`.
- **`..` cannot climb above the root.** `/a/../../b` is `/b`, because there is no
  page above `/`.
- **A fragment never reaches the server.** It is kept so the link prints back
  exactly as written, and excluded from the key so the page is fetched once.
- **The query is sorted into the key.** `?b=2&a=1` and `?a=1&b=2` are the same
  request.
- **A refusal is a sentence, not a `False`.** Every anchor keeps its reason, so a
  page of links can be audited without a debugger.
- **A job is one id, whatever its query.** Two anchors to `/jobs/42` with
  different tracking parameters are one job, and the crawl reports it once.
- **A broken link is a `FAIL`.** Every audit check runs behind a guard, because
  a negative control plants the defect exactly where the check looks.

---

# 🧪 Technologies

- Python 3 standard library: `urllib.parse`, `posixpath`, `re`, `dataclasses`,
  `pathlib`, `json`, `argparse`, `contextlib`
- pytest 9.1.1

No `requests`, no `beautifulsoup4`, no network.

---

# 📚 Concepts Covered

- A URL as five parts, and which operation touches which part
- Resolution rules: directory-relative joins, rooted paths, `..`, protocol-relative
- Fragments as browser state, not part of the address or the identity
- Crawl confinement by host **equality** against containment and prefix matching
- Canonical keys, and deduplication that keeps first-seen order
- Query-field ordering, so one request has one key
- Refusing a scheme, a space, a user, and a relative href by name
- Audits with an injected predicate, so a check can be shown to test something

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**170 tests passed** covering `Url` construction and eleven refusals, printing and
parsing back, the canonical key and its query ordering, all eight resolution
rules, dot folding, the directory join, host equality against subdomains and
lookalikes, deduplication, the two legacy functions, `Link` and `Page` accessors,
the bundled page's nine anchors / seven on site / six unique / four jobs, the
line-numbered file errors, nine audit checks with seven negative controls, the
demo, and every CLI mode including six exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Resolve a link against the page it was printed on, by the rules of the path
- Confine a crawl with host equality instead of a substring test
- Explain why `.../list.html` + `43` is not `.../jobs/43`
- Treat the fragment as browser state and deduplicate on what the server sees
- Canonicalise a query so one request has one key
- Report a refused link with the sentence that says why

---

# 🚀 Future Improvements

- A crawl frontier, so the unique links are followed breadth-first
- `robots.txt` and a per-host politeness delay, read from the same parts
- Percent-encoding, so a space is encoded rather than refused
- Internationalised host names, lower-cased under IDNA rules
- A `mailto:` classification, since an address is a link even when it is not a page

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
