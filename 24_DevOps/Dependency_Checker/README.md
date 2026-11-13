<div align="center">

# 📦 Dependency Checker

### Parse `requirements.txt` and `pyproject.toml`, then verify every constraint against locally installed metadata — severity-ranked, deterministic, and fully offline.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Offline-No%20Index-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

# 📖 About

Pip resolves dependencies against an index; this project does the opposite — it checks a dependency list against **what is already installed**, without ever touching the network. That makes it useful as an audit tool: "does this environment actually match the pinned file?" rather than "what could be installed?"

Two source formats are parsed:

```text
requirements.txt          -> name[extras] OP version, OP version, ...
pyproject.toml [project]  -> dependencies = ["numpy>=1.24", ...]  (tomllib)
```

Every requirement is then classified into one of four states, with the state driving the severity:

| Status | Meaning | Severity rule |
| --- | --- | --- |
| `ok` | installed version satisfies every clause | `none` |
| `conflict` | installed, but violates a clause | `high` for an exact pin, `medium` for a range |
| `missing` | not installed at all | `high` if pinned, `medium` otherwise |
| `unpinned` | installed with no constraint | `low` |

**The PEP 440 subset is implemented, not delegated.** `compare_versions` tokenises both versions and pads the shorter one with zeros, so `1.0 == 1.0.0` and `2.10 > 2.9` (numeric, not lexical). `satisfies` applies comma-separated clauses with AND logic, and `clause_holds` covers `==`, `!=`, `>=`, `<=`, `>`, `<`, `~=` (compatible release, `~=1.2.3` → `>=1.2.3, <1.3`) and `==1.2.*` wildcards.

**Three subtle parsing bugs are pinned by tests**, each of which changes a verdict silently:

1. **Operators were found by substring scan.** `">=2.0,<3.0"` contains the characters `>=`, `>` **and** `<`, so the naive scan reported three operators for a two-clause specifier. `Requirement.operators` now tokenises with the same ordered regex the clause parser uses.
2. **`>=` with no version parsed as `>` plus `=`.** The alternation matched the single-character operator and handed `"="` to the version field, so the error was "invalid version" instead of a missing version. Empty and operator-leading versions are now rejected as malformed clauses — while `>=latest` still fails as an *invalid version*, which is the more precise message.
3. **Order of rejection mattered for options.** `--index-url https://example.com/simple` contains `://`, so the URL branch fired first and the message blamed VCS requirements. Options are now checked before URLs, so the error names the actual problem.

**Version tokens split numeric and alphabetic runs**, so a CUDA build tag is comparable instead of opaque: `2.11.0+cu128` → `[2, 11, 0, "cu", 128]`. The old tokeniser produced `[2, 11, 0, "cu128"]`.

**The demo runs the list twice on purpose.** Pass 1 checks the bundled `requirements.txt` against the *live* machine and reports it (informational, since every machine differs). Pass 2 checks both bundled files against the bundled `installed.json` snapshot through an injected resolver, and **asserts** the exact outcome — 10 checks: `ok 4`, `conflict 2`, `missing 3`, `unpinned 1`; severity `none 4`, `low 1`, `medium 2`, `high 3`. The resolver injection is what makes this reproducible: `check_requirements(..., resolver=...)` is the same code path the CLI uses with `importlib.metadata`, just fed a fixed mapping.

Two further invariants are asserted rather than assumed: re-running the check yields identical `CheckResult` objects, and `installed_version("acme-widget")` really is `None` locally — the tool cannot fabricate an install, because there is no network code to do it with.

No pip, no index, no downloads, no API keys.

---

# ✨ Features

- `requirements.txt` parsing: comments, inline `#` comments, blank lines, extras (`requests[socks]>=2.0`), duplicate detection, per-line error numbers
- `pyproject.toml` parsing via stdlib `tomllib`, with structural errors (no `[project]`, no `dependencies`, wrong types)
- Clear rejection of what this tool does **not** support: editable installs, URLs/VCS, environment markers, pip options
- PEP 440 subset: `==`, `!=`, `>=`, `<=`, `>`, `<`, `~=`, `==1.2.*` wildcards, comma-AND clauses
- Version comparison with zero padding (`1.0 == 1.0.0`) and split numeric/alpha tokens (`+cu128`)
- Four-state classification with severity: exact-pin conflicts outrank range conflicts
- Deterministic resolver injection for snapshot-based checks
- Severity-ranked text report with a "Needs attention" section
- `--json` export of per-result verdicts plus status/severity counts
- `--demo`, `--file`, `--json`, `--quiet` (and `--demo --quiet` prints nothing)
- Fail-fast: input is parsed before any metadata lookup, and `--demo` always exits `0`
- Deterministic bundled data: `requirements.txt`, `pyproject.toml`, `installed.json`
- 70 passing pytest tests

---

# 📂 Folder Structure

```text
Dependency_Checker/
│
├── src/
│   ├── main.py        # CLI: --demo, --file, --json, --quiet
│   └── depcheck.py    # parsing, PEP 440 subset, classification, report, demo
│
├── tests/
│   └── test_depcheck.py
│
├── data/
│   ├── requirements.txt   # 7 requirements: ok/conflict/missing/unpinned
│   ├── pyproject.toml     # 3 dependencies parsed with tomllib
│   └── installed.json     # {package: version} snapshot resolver
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# ⚙️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 24_DevOps/Dependency_Checker

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: live pass + deterministic snapshot pass + cross-checks
python src/main.py --demo

# Check the bundled requirements against this machine
python src/main.py --file data/requirements.txt

# Check pyproject dependencies instead (parsed with tomllib)
python src/main.py --file data/pyproject.toml

# Machine-readable verdicts and counts
python src/main.py --file data/requirements.txt --json out.json
```

**Bundled sample:**

```text
numpy>=1.24              # ok       (installed 2.5.2)
pytest>=6                # ok       (installed 9.1.1)
pandas<1.0               # conflict (installed 2.3.3)
scipy==0.1.0             # conflict (installed 1.18.0, exact pin -> high)
acme-widget==1.0.0       # missing  (high, pinned)
sample-lib>=2.0          # missing  (medium)
pyyaml                   # unpinned (installed 6.0.3)
```

**Exit codes:** `0` = success (including a check that found conflicts) · `2` = usage, parse or IO error.

Conflicts are *findings*, not failures: the exit code reports whether the tool ran, and `--json` carries the verdicts for a CI gate to act on.

---

# 🧠 How It Works

```text
requirements.txt ─┐
                  ├─► parse ─► Requirement(name, specifier)
pyproject.toml  ──┘                │
                                   ▼
                     resolver(name) -> installed version | None
                       (importlib.metadata locally, or an injected
                        snapshot mapping for deterministic runs)
                                   │
                                   ▼
                              classify()
        installed is None ───────────────► missing  (high if pinned, else medium)
        specifier empty  ───────────────► unpinned (low)
        satisfies(...)   ───────────────► ok       (none)
        otherwise        ───────────────► conflict (high if exact pin, else medium)
                                   │
                                   ▼
                 render_report() ── severity ranked ──► text / --json
```

The specifier engine, in order:

```text
">=2.0,<3.0" ──► clauses [">=2.0", "<3.0"] ──► all() must hold
                     │
                     ▼
            _parse_clause -> (operator, version)
            version must start with a digit (or '*' or a wildcard)
                     │
                     ▼
            clause_holds -> version_tokens -> zero-padded compare
```

Details worth knowing:

- **`~=` needs at least two segments** and is rejected otherwise, rather than silently behaving like `==`.
- **Wildcards are only legal with `==`/`!=`** — `>=1.*` raises instead of comparing text.
- **Severity distinguishes *how* a conflict happened**: an exact pin (`scipy==0.1.0` vs `1.18.0`) is `high`, a range (`pandas<1.0` vs `2.3.3`) is `medium`, because the exact pin is more likely to be a deliberate, load-bearing constraint.
- **`--demo` never fails on user input.** A missing bundled file is reported to stderr but still exits `0`, and `--demo --quiet` suppresses both the banner and the demo body.
- **Duplicate detection is case-insensitive**, so `numpy>=1.0` followed by `Numpy==2.5.2` is an error rather than two contradictory verdicts.

---

# 🛠 Technologies

- Python 3 standard library: `tomllib`, `re`, `json`, `importlib.metadata`, `dataclasses`, `argparse`, `pathlib`, `logging`, `contextlib`
- pytest

No pip, no packaging library, no PyPI client, no network access.

---

# 📚 Concepts Covered

- Requirements-file and `pyproject.toml` parsing with stdlib `tomllib`
- PEP 440 version comparison: zero padding, numeric-vs-lexical ordering, local/build tags
- Specifier operators, comma-AND semantics and compatible-release (`~=`) expansion
- Wildcard matching (`==1.2.*`) and why it is only valid for equality operators
- Classifying findings into ok/conflict/missing/unpinned with severity rules
- Dependency injection of a resolver to make environment checks reproducible
- Fast-fail validation ordering (structure before values before lookups)
- Regex tokenisation pitfalls: substring scans vs ordered alternation
- Distinguishing "malformed" from "invalid version" in error messages
- Self-asserting deterministic demos with negative controls

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**70 tests passed** covering every requirement-line form (pinned, ranged, bare, extras, comments) and every rejection path (editable, URL, VCS, environment marker, pip option, malformed specifier, non-numeric version, versionless operator, empty clause), requirements-file behaviour (missing file, duplicates, empty file, line numbers), pyproject parsing and its structural errors, version tokenisation and comparison, all operators including `~=` and wildcards, `satisfies` AND logic, all four classifications with both severities, snapshot loading and resolver case-insensitivity, report ordering and "Needs attention", demo idempotency and `--quiet`, and every CLI path including `--demo` with a missing bundle.

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
