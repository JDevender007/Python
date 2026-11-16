<div align="center">

# 📰 News API Dashboard

### The legacy reader wrapped one key in `try/except` and returned `[]`. Ten responses came back, **five of them as an empty list** — a rate limit, a 404, a proxy error wearing a `200`, a body with no `articles` field at all, and the one that really was empty. The 404's sentence "Nothing matches your query." was thrown away with them.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
def articles(payload):
    try:
        return payload["articles"]
    except (KeyError, TypeError):
        return []
```

**1 → `[]` is five different facts.** A rate limit, a 404 that says "nothing matches", a
body whose own `status` field says `error`, a body with no `articles` key, and a query
that genuinely matched nothing all reach that `except` and all come back as an empty list.
Four are failures and one is a successful empty result — and the caller cannot tell which:

```text
ok             HTTP 200 ok         3/3   all 3 article(s) arrived
empty          HTTP 200 empty      0/0   the query matched nothing, and the total agrees it is nothing
partial        HTTP 200 partial    2/20  2 of 20 arrived, so 18 are missing
rate-limited   HTTP 429 error      0/-   HTTP 429, and the body says: You have made too many requests recently.
not-found      HTTP 404 error      0/-   HTTP 404, and the body says: Nothing matches your query.
server-error   HTTP 500 error      0/-   HTTP 500, and the body says: <html><body>Upstream unavailable</body></html>
truncated      HTTP 200 malformed  0/-   the body is not JSON, at character 59: Unterminated string starting at
no-articles    HTTP 200 malformed  0/-   the body carries no 'articles' field, so it holds no answer
null-articles  HTTP 200 malformed  0/-   'articles' is NoneType, not a list, and a null is not an empty list
proxy-200-error HTTP 200 error     0/-   the status was 200 but the body says error: The request could not be satisfied.
```

**2 → The message is discarded with the list.** The 404 body says "Nothing matches your
query." That sentence is the most useful thing in the response, and the legacy code never
looked at it, because it only ever read one key.

**3 → `payload["articles"]` returns whatever is there.** A `null` is handed back as the
article list, and the loop that iterates it fails a hundred lines later, inside a function
that has never heard of the API. `None` is not `[]`.

**4 → A status code is half the story, and so is the body.** A proxy answers `200` with a
body whose `status` is `error`; a body arrives with `200` and does not parse at all. Each
half knows something the other does not, so both are read and both are kept.

**5 → `totalResults` is the only way to know you were cut off.** A `200` with two articles
and a total of twenty is a partial answer. The legacy reader calls it a success, because
the list is not empty.

What the legacy path actually did with the same ten bodies:

```text
5 bodies came back as exactly []: empty, rate-limited, not-found, no-articles, proxy-200-error
null-articles  None, which is not a list
server-error   json.loads raised before it could answer
truncated      json.loads raised before it could answer
```

Five empty lists, one `None`, two crashes — and not one of those outcomes distinguishes
"the wire told me no" from "the query found nothing".

| the `[]` | status | what really happened |
|---|---|---|
| `empty` | 200 | **correct** — the query matched nothing and the total agrees |
| `rate-limited` | 429 | failure — too many requests, try later |
| `not-found` | 404 | failure — nothing matches, and it said so in English |
| `no-articles` | 200 | no answer at all — the field is missing |
| `proxy-200-error` | 200 | failure that arrived with a good status |
| *(none — it is `None`)* | 200 | `null` is not an empty list |

The demonstration is offline: one bundled file of ten responses, status and body byte for
byte. Standard library only: no `requests`, no HTTP client, no API key.

---

# ✨ Features

- `Response` — a status and a body that travel **together**, because neither is the answer
  alone; refuses a status outside 100-599 and a body that is not text
- `classify()` — one response in, one of five outcomes out: `ok`, `empty`, `partial`,
  `error`, `malformed`
- `Outcome` — the rows, the `totalResults` it can be checked against, and **the sentence
  that says why** (`line()`, `sentence()`, `shortfall()`, `titles()`)
- Statuses are read first, bodies second: a `429` still gives up its message, and a `200`
  whose body says `"status": "error"` is an error
- A body that is not JSON is `malformed` and names the character it stopped at; a `null`
  `articles` is `malformed`, not empty; a total that is not a number is `malformed`
- `Bundle` — `by_name()`, `of_kind()`, `counts()`, `with_rows()`; refuses two responses
  with one name
- `parse_responses()` — `--- name`, `HTTP <status>`, then the body verbatim (multi-line,
  CRLF included)
- `legacy_articles` / `legacy_read` / `legacy_of` — the four legacy lines, executable, with
  a crash recorded as `"crash"` instead of raising
- `audit` — eleven named checks, every one falsifiable by handing in a corrupted outcome
- CLI: `--responses`, `--name`, `--body`, `--status`, `--kind`, `--audit`, `--json`,
  `--quiet`, `--demo`
- 147 passing pytest tests

---

# 📂 Folder Structure

```text
News_API_Dashboard/
│
├── src/
│   ├── main.py       # CLI: list, one name, one body, the audit
│   └── envelopes.py  # responses, outcomes, the legacy reader, the audit
│
├── tests/
│   └── test_envelopes.py
│
├── data/
│   └── responses.txt  # ten responses exactly as they came off the wire
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 08_API_Development/News_API_Dashboard

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: all ten responses classified, and the legacy reader beside them
python src/main.py --demo

# Every response, one line each
python src/main.py

# Only the failures
python src/main.py --kind error

# One response, with its sentence
python src/main.py --name not-found
python src/main.py --name partial

# Classify a body you paste in
python src/main.py --body '{"status": "ok", "totalResults": 0, "articles": []}'
python src/main.py --body '<html>Down</html>' --status 500

# Every check
python src/main.py --audit

# All ten outcomes as JSON
python src/main.py --json outcomes.json
```

**Exit codes:** `0` = the response was readable and truthful · `1` = an audit check failed
· `2` = an error or malformed response, an unknown name, a body that cannot be classified,
a missing file, or a bundle that cannot be parsed.

---

# ⚙️ How It Works

```text
classify(response)
  ├── status outside 200-299 ?
  │     └── error, and the body's own message is kept
  ├── body does not parse, or is not an object ?
  │     └── malformed, naming the character
  ├── body's own "status" says error ?
  │     └── error, even though the status was 200
  ├── no "articles" key, or it is not a list ?
  │     └── malformed (a null is NOT an empty list)
  ├── "totalResults" is not a whole number ?
  │     └── malformed, because nothing can be checked
  ├── rows < total  -> partial, with the shortfall
  ├── rows == 0 and total == 0 -> empty   (the only honest empty)
  └── rows == total -> ok
```

Details worth knowing:

- **An empty list is a result, not a failure — and only `totalResults` can say which.**
  `{"articles": [], "totalResults": 0}` is `empty`; `{"articles": [], "totalResults": 5}`
  is `partial`, because five articles exist somewhere.
- **Five responses reach the same `[]` by five different roads.** The check
  `the five empty lists are five different facts` requires five distinct sentences, so a
  classifier that collapses them fails it.
- **`null` is not `[]`.** `legacy_articles({"articles": None})` returns `None`, and
  `None` breaks an iterator; the classifier calls it `malformed` and says why.
- **Two crashes are recorded, not raised.** `legacy_of` answers `"crash"` where
  `json.loads` would have raised, so the audit can *count* the bodies the legacy path
  could not even look at.
- **A message outlives its status.** The 404's sentence and the 429's sentence are both
  kept in `Outcome.note`, which is what a caller needs to print.
- **A broken body is a `FAIL`.** Every check runs behind a guard, because a negative
  control hands in an `Outcome` that is wrong in exactly the way the check is looking for
  — written past the constructor with `object.__new__`, since `Outcome` refuses to be
  built wrong on purpose.

---

# 🧪 Technologies

- Python 3 standard library: `json`, `dataclasses`, `pathlib`, `argparse`, `contextlib`
- pytest 9.1.1

No `requests`, no HTTP client, no network, no API key. The ten responses are bundled.

---

# 📚 Concepts Covered

- Separating "the call failed" from "the query found nothing"
- Reading a status code and a body as two witnesses, not one answer
- Keeping the server's explanation instead of reducing every failure to `[]`
- `null` versus `[]` versus a missing key — three different shapes
- A total that lets you detect a truncated page
- `try/except KeyError: return []` as a bug that hides four failures
- Audits whose negative controls are corrupted values rather than injected functions

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**147 tests passed** covering `Article` construction and its three refusals, article rows
and their two refusals, `Response` and its five refusals, `Outcome` and its eight refusals,
all five classifications and the malformed cases that produce them, the legacy reader's
five empty lists, its one `None` and its two crashes, the bundle parser and its seven
errors, a missing bundle, `Bundle` lookups and its two refusals, eleven audit checks each
with a negative control, the demo, and every CLI mode including six exit-code-2 paths and
one exit-code-1 path.

---

# 🎯 Learning Outcomes

- Explain why `except KeyError: return []` erases a rate limit, a 404 and a proxy error
- Say what an empty list means, and what it does not mean
- Keep the sentence a failing body carries, because it is the only useful part
- Treat `null` as a shape error instead of an empty collection
- Use `totalResults` to tell a complete answer from a truncated one
- Classify a `200` that carries an error body without trusting the status alone
- Distinguish "could not read the body" from "the body said no"

---

# 🚀 Future Improvements

- A retry policy that knows `429` and `5xx` are retryable and `401` is not (the next
  project, `REST_API_with_FastAPI`)
- A `Retry-After` reader, so a rate limit comes back with a time rather than a message
- A cache keyed by the request, so a repeated failure costs nothing
- A paging loop over `page`/`pageSize`, reusing the cursor findings from
  `GitHub_Profile_Analyzer`
- A JSON-schema check per endpoint, so `malformed` names the field that broke

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
