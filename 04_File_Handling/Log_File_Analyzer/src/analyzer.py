"""Reading a log file: a level is a field, and an entry is more than a line.

The legacy project counted occurrences of words in every line it read:

    for line in self.logs:
        upper = line.upper()
        if "INFO" in upper:
            self.counter["INFO"] += 1
        elif "WARNING" in upper:
            self.counter["WARNING"] += 1
        elif "ERROR" in upper:
            self.counter["ERROR"] += 1
        elif "CRITICAL" in upper:
            self.counter["CRITICAL"] += 1
        else:
            self.counter["UNKNOWN"] += 1

Five things follow.

**1. A level is a field, not a substring.** ``DEBUG Informational banner rendered``
contains the letters ``INFO`` inside ``INFORMATIONAL``, so the legacy scan files a
debug line under INFO. ``WARNING User info record missing`` does the same. And
``DEBUG Validation finished, errors 0`` contains ``ERROR`` inside ``ERRORS``, so a
line reporting *zero* errors is counted as an error. The level sits in one fixed
field after the timestamp; that field is the answer, and nothing else is.

**2. The order of the ``elif`` chain silently decides ties.** A line with two
level words is counted as whichever is tested first. ``CRITICAL Worker 1 shutting
down, error in loop`` is filed under ERROR, because ``ERROR`` is tested before
``CRITICAL`` -- so the one critical entry in this corpus disappears into ERROR.

**3. There is no DEBUG branch at all.** Nothing in the chain can ever produce
``DEBUG``, so a whole level is invisible: 4 of the 18 entries here vanish from the
legacy summary and one of them is later re-counted as ERROR.

**4. An entry is more than one line, and a line is not always an entry.** A Python
traceback is three lines that belong to the ERROR above them. The legacy loop
counts each one as its own ``UNKNOWN`` entry, and ``PermissionError`` as an
``ERROR``. A timestamped line with no level, or a prose file with a ``.log``
suffix, is not an entry either. This module keeps *entries* (timestamp, level,
message, continuation lines) and *malformed lines* (kept, named, and counted) and
never equates the two.

**5. ``SUPPORTED_EXTENSIONS = [".log", ".txt"]`` treats a suffix as a promise.**
``notes.log`` here holds two sentences and no entries at all. That is a fact worth
reporting, not a file to skip in silence.

Standard library only: ``re``, ``datetime``, ``csv``, no ``colorama``, no
``tabulate``, no network.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOGS = DATA_DIR / "logs"

#: The five levels, in the order a report prints them.
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

#: The timestamp every entry starts with, and nothing else accepts.
STAMP = "%Y-%m-%d %H:%M:%S"
LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\S+)(?: (.*))?$")

#: The legacy code, kept executable.
LEGACY_CHAIN = ('if "INFO" in upper: ... elif "WARNING" in upper: ... '
                'elif "ERROR" in upper: ... elif "CRITICAL" in upper: ...')
LEGACY_EXTENSIONS = 'SUPPORTED_EXTENSIONS = [".log", ".txt"]'
LEGACY_LINE = 'upper = line.upper()'


class LogError(ValueError):
    """A folder, a file, a word or an analysis that is refused."""


# --------------------------------------------------------------------------- #
# One entry, one bad line
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Entry:
    """One log entry: its first line, and the lines that continue it."""

    file: str
    line: int
    when: datetime
    level: str
    message: str
    continuations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise LogError(f"{self.level!r} is not a level")
        if self.line < 1:
            raise LogError("a line number starts at 1")
        if not isinstance(self.when, datetime):
            raise LogError("an entry needs a timestamp")

    @property
    def text(self) -> str:
        """The message and every line that continues it, as one string."""
        return "\n".join((self.message,) + self.continuations)

    @property
    def lines(self) -> int:
        """How many physical lines this entry occupies."""
        return 1 + len(self.continuations)

    def mentions(self) -> tuple[str, ...]:
        """Which level names appear in the *text*, as whole words, in order."""
        upper = self.text.upper()
        return tuple(level for level in LEVELS
                     if re.search(rf"\b{level}\b", upper))

    def __str__(self) -> str:
        stamp = self.when.strftime(STAMP)
        return f"{stamp} {self.level:<8} {self.message}"

    def to_dict(self) -> dict:
        return {"file": self.file, "line": self.line,
                "when": self.when.strftime(STAMP), "level": self.level,
                "message": self.message,
                "continuations": list(self.continuations)}


@dataclass(frozen=True)
class BadLine:
    """A line that is neither an entry nor part of one, with the reason."""

    file: str
    line: int
    text: str
    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise LogError("a malformed line needs a reason")
        if self.line < 1:
            raise LogError("a line number starts at 1")

    def __str__(self) -> str:
        return f"{self.file}:{self.line}  {self.text}  ({self.reason})"

    def to_dict(self) -> dict:
        return {"file": self.file, "line": self.line, "text": self.text,
                "reason": self.reason}


@dataclass(frozen=True)
class FileReport:
    """What one file gave the analysis: entries, bad lines, and its shape."""

    name: str
    entries: tuple[Entry, ...]
    bad: tuple[BadLine, ...]
    nonblank: int
    blobs: int

    @property
    def continuations(self) -> int:
        return sum(len(entry.continuations) for entry in self.entries)

    def counts(self) -> dict[str, int]:
        """All five levels, zeros included: a level that never happened is 0."""
        counted = Counter(entry.level for entry in self.entries)
        return {level: counted.get(level, 0) for level in LEVELS}

    def to_dict(self) -> dict:
        return {"file": self.name, "entries": len(self.entries),
                "levels": self.counts(), "continuations": self.continuations,
                "malformed": len(self.bad), "nonblank": self.nonblank,
                "bytes": self.blobs}


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def check_folder(folder) -> Path:
    folder = Path(folder)
    if not folder.exists():
        raise LogError(f"folder not found: {folder}")
    if not folder.is_dir():
        raise LogError(f"{folder} is a file, not a folder")
    return folder


def split_line(text: str) -> tuple[datetime, str, str]:
    """``(when, level, message)`` for an entry line, or raise ``LogError``.

    The level is whatever single token follows the timestamp. It is *not*
    searched for anywhere else in the line, and it is not upper-cased to be
    guessed at: a token that is not one of the five is refused.
    """
    match = LINE.match(text.rstrip("\n"))
    if match is None:
        raise LogError("the line does not start with a timestamp")
    stamp, level, message = match.groups()
    try:
        when = datetime.strptime(stamp, STAMP)
    except ValueError as exc:
        raise LogError(f"not a real date: {stamp}") from None
    if level not in LEVELS:
        raise LogError(f"{level!r} is not a level")
    return when, level, message or ""


def read_file(path) -> FileReport:
    """Read one log file into entries and malformed lines, in file order."""
    path = Path(path)
    if not path.is_file():
        raise LogError(f"not a file: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise LogError(f"cannot read {path}: {exc}") from None
    text = raw.decode("utf-8", errors="replace")

    entries: list[Entry] = []
    bad: list[BadLine] = []
    open_entry: Entry | None = None
    waiting: list[str] = []
    nonblank = 0

    def close() -> None:
        nonlocal open_entry, waiting
        if open_entry is not None:
            entries.append(Entry(open_entry.file, open_entry.line,
                                 open_entry.when, open_entry.level,
                                 open_entry.message, tuple(waiting)))
        open_entry, waiting = None, []

    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip("\r")
        if not line.strip():
            continue                          # a blank line is not a line here
        nonblank += 1
        try:
            when, level, message = split_line(line)
        except LogError as exc:
            if "does not start with a timestamp" in str(exc) and \
                    open_entry is not None:
                waiting.append(line)          # a traceback line continues
                continue
            close()
            bad.append(BadLine(path.name, number, line, str(exc)))
            continue
        close()
        open_entry = Entry(path.name, number, when, level, message)
        waiting = []
    close()

    return FileReport(path.name, tuple(entries), tuple(bad), nonblank, len(raw))


# --------------------------------------------------------------------------- #
# The whole folder
# --------------------------------------------------------------------------- #
class Analysis:
    """Every entry and every bad line under one folder, as a value."""

    def __init__(self, root, files):
        self.root = Path(root)
        self._files = tuple(files)

    @property
    def files(self) -> tuple[FileReport, ...]:
        return self._files

    @property
    def entries(self) -> tuple[Entry, ...]:
        return tuple(entry for report in self._files for entry in report.entries)

    @property
    def bad(self) -> tuple[BadLine, ...]:
        return tuple(line for report in self._files for line in report.bad)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def __repr__(self) -> str:
        counts = self.counts()
        return (f"<Analysis {len(self._files)} files, {len(self)} entries, "
                f"{sum(counts.values())} counted, {len(self.bad)} malformed>")

    # -- the numbers -------------------------------------------------------- #
    def counts(self) -> dict[str, int]:
        counted = Counter(entry.level for entry in self.entries)
        return {level: counted.get(level, 0) for level in LEVELS}

    def file_counts(self) -> dict[str, dict[str, int]]:
        return {report.name: report.counts() for report in self._files}

    @property
    def continuations(self) -> int:
        return sum(report.continuations for report in self._files)

    @property
    def nonblank(self) -> int:
        return sum(report.nonblank for report in self._files)

    @property
    def blobs(self) -> int:
        return sum(report.blobs for report in self._files)

    def span(self) -> tuple[datetime, datetime, int]:
        """First timestamp, last timestamp, and the seconds between them."""
        stamps = [entry.when for entry in self.entries]
        if not stamps:
            raise LogError("an empty analysis has no span")
        first, last = min(stamps), max(stamps)
        return first, last, int((last - first).total_seconds())

    def summary(self) -> dict:
        counts = self.counts()
        return {"root": self.root.name, "files": len(self._files),
                "entries": len(self.entries),
                "nonblank": self.nonblank, "blobs": self.blobs,
                "continuations": self.continuations,
                "malformed": len(self.bad), **counts}

    def to_dict(self) -> dict:
        return {"summary": self.summary(),
                "files": [report.to_dict() for report in self._files],
                "entries": [entry.to_dict() for entry in self.entries],
                "malformed": [line.to_dict() for line in self.bad]}

    # -- checks ------------------------------------------------------------- #
    def verify(self) -> list[tuple[str, bool]]:
        entries = self.entries
        checks = []

        known = all(entry.level in LEVELS for entry in entries)
        checks.append(("every entry names one of the five levels", known))

        ordered = True
        for report in self._files:
            stamps = [entry.when for entry in report.entries]
            if stamps != sorted(stamps):
                ordered = False
        checks.append(("no file's timestamps go backwards", ordered))

        names = [report.name for report in self._files]
        checks.append(("the files are listed in name order",
                       names == sorted(names, key=str.lower)))

        shared = [(line.file, line.line) for line in self.bad]
        taken = [(entry.file, entry.line) for entry in entries]
        checks.append(("no line is both an entry and a malformed line",
                       not set(shared) & set(taken)))

        # The conservation law: every non-blank line is a start, a
        # continuation, or malformed. Nothing is dropped and nothing is
        # counted twice.
        checks.append((
            "entries + continuations + malformed equals the non-blank lines",
            len(entries) + self.continuations + len(self.bad) == self.nonblank))

        checks.append(("every malformed line has text and a reason",
                       all(line.text.strip() and line.reason
                           for line in self.bad)))

        return checks

    def problems(self) -> list[str]:
        return [name for name, passed in self.verify() if not passed]


def analyze(folder=LOGS) -> Analysis:
    """Read every file in ``folder`` that looks like a log, in name order."""
    folder = check_folder(folder)
    files = [path for path in sorted(folder.iterdir(), key=lambda p: p.name.lower())
             if path.is_file()]
    return Analysis(folder, [read_file(path) for path in files])


# --------------------------------------------------------------------------- #
# Searching
# --------------------------------------------------------------------------- #
def search(analysis: Analysis, word: str) -> list[Entry]:
    """Entries whose *message* contains ``word`` as a whole word.

    Whole-word matching is the point: ``cat`` does not match ``category``, and
    ``error`` does not match ``errors 0``. The level is not searched -- use the
    level counts for that.
    """
    if not isinstance(word, str):
        raise LogError(f"a search word must be text, got {type(word).__name__}")
    if not word.strip():
        raise LogError("a search word must not be empty")
    pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
    return [entry for entry in analysis.entries if pattern.search(entry.text)]


# --------------------------------------------------------------------------- #
# The legacy project
# --------------------------------------------------------------------------- #
def legacy_counts(lines) -> Counter:
    """The legacy ``if/elif`` chain, applied to raw lines exactly as written."""
    counter = Counter()
    for line in lines:
        upper = line.upper()
        if "INFO" in upper:
            counter["INFO"] += 1
        elif "WARNING" in upper:
            counter["WARNING"] += 1
        elif "ERROR" in upper:
            counter["ERROR"] += 1
        elif "CRITICAL" in upper:
            counter["CRITICAL"] += 1
        else:
            counter["UNKNOWN"] += 1
    return counter


def legacy_lines(analysis: Analysis) -> list[str]:
    """Every non-blank line the legacy loader would have handed to the chain."""
    lines = []
    for report in analysis.files:
        path = Path(analysis.root) / report.name
        text = path.read_bytes().decode("utf-8", errors="replace")
        lines.extend(line.rstrip("\r") for line in text.splitlines()
                     if line.strip())
    return lines


def legacy_classify(text: str) -> str:
    """One line, through the legacy chain, as a level name or ``UNKNOWN``."""
    return next(iter(legacy_counts([text])), "UNKNOWN")


def legacy_unknowns(analysis: Analysis) -> tuple[list, list]:
    """Split the chain's UNKNOWNs into real entry starts and everything else.

    ``(entries, others)``, each a list of ``(file, line, text)``. A line that
    the chain could not classify is not automatically junk: two of them here are
    genuine DEBUG entries the chain has no branch for.
    """
    entries, others = [], []
    for report in analysis.files:
        text = (Path(analysis.root) / report.name).read_bytes() \
            .decode("utf-8", errors="replace")
        starts = {entry.line for entry in report.entries}
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip() or legacy_classify(line) != "UNKNOWN":
                continue
            where = (report.name, number, line)
            (entries if number in starts else others).append(where)
    return entries, others


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
def report_rows(analysis: Analysis) -> list[list[str]]:
    """One row per file plus a total, every level present, zeros included."""
    rows = []
    for report in analysis.files:
        counts = report.counts()
        rows.append([report.name, str(len(report.entries))]
                    + [str(counts[level]) for level in LEVELS]
                    + [str(report.continuations), str(len(report.bad))])
    counts = analysis.counts()
    rows.append(["TOTAL", str(len(analysis))]
                + [str(counts[level]) for level in LEVELS]
                + [str(analysis.continuations), str(len(analysis.bad))])
    return rows


def report_text(analysis: Analysis) -> str:
    header = (["File", "Entries"] + list(LEVELS)
              + ["Continued", "Malformed"])
    lines = [",".join(header)]
    lines.extend(",".join(row) for row in report_rows(analysis))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 74)
    print(" LOG ANALYSIS - a level is a field, and an entry is not a line")
    print("=" * 74)

    analysis = analyze()
    summary = analysis.summary()
    assert summary["files"] == 3 and summary["entries"] == 18
    assert summary["nonblank"] == 28 and summary["continuations"] == 6
    assert summary["malformed"] == 4
    assert summary["DEBUG"] == 4 and summary["INFO"] == 7
    assert summary["WARNING"] == 3 and summary["ERROR"] == 3
    assert summary["CRITICAL"] == 1

    # 1. the corpus
    print(f"  {summary['files']} files, {summary['blobs']} bytes, "
          f"{summary['nonblank']} non-blank lines: {summary['entries']} "
          f"entries, {summary['continuations']} continuation lines, "
          f"{summary['malformed']} malformed lines")

    # 2. every level, per file, with the zero shown
    print("  level counts per file, zeros included:")
    for report in analysis.files:
        counts = report.counts()
        shown = "  ".join(f"{level} {counts[level]}"
                          for level in LEVELS)
        print(f"    {report.name:<16} {len(report.entries):>2} entries  "
              f"{shown}")
    assert analysis.file_counts()["application.log"]["CRITICAL"] == 0
    assert analysis.file_counts()["notes.log"]["INFO"] == 0
    print(f"    application.log never logs CRITICAL, so its CRITICAL is 0, "
          f"not missing; notes.log ends in .log and holds 0 entries")

    # 3. the substring misreadings
    samples = [
        ("2026-05-11 08:04:00 DEBUG Informational banner rendered", "DEBUG",
         "INFO", "INFORMATIONAL contains INFO"),
        ("2026-05-11 08:08:00 WARNING User info record missing", "WARNING",
         "INFO", "INFO RECORD contains INFO"),
        ("2026-05-11 08:07:00 DEBUG Validation finished, errors 0", "DEBUG",
         "ERROR", "ERRORS contains ERROR"),
        ("2026-05-11 09:00:12 CRITICAL Worker 1 shutting down, error in loop",
         "CRITICAL", "ERROR", "the elif chain tests ERROR first"),
    ]
    print("  four lines the legacy chain misreads:")
    for text, truth, legacy, why in samples:
        assert split_line(text)[1] == truth
        assert legacy_classify(text) == legacy
        assert truth != legacy
        print(f"    {truth:<8} read as {legacy:<8} {why}")

    # 4. DEBUG is invisible to the chain
    counts = legacy_counts(legacy_lines(analysis))
    assert "DEBUG" not in counts
    print(f"  the chain has no DEBUG branch at all, so its DEBUG count is "
          f"absent, not 0, and 4 of the 18 entries leave the summary")

    # 5. one entry, three continuation lines
    traceback = next(entry for entry in analysis.entries
                     if entry.file == "application.log" and
                     entry.level == "ERROR")
    assert traceback.lines == 4 and len(traceback.continuations) == 3
    assert traceback.continuations[0] == "Traceback (most recent call last):"
    assert "PermissionError" in traceback.text
    assert legacy_classify("PermissionError: [Errno 13] Permission denied") == \
        "ERROR"
    print(f"  the error at application.log line {traceback.line} occupies "
          f"{traceback.lines} lines: 1 entry, not 4, and the chain counts the "
          f"traceback as 2 UNKNOWNs and PermissionError as an ERROR")

    # 6. a timestamp inside a message is not a new entry
    embedded = next(entry for entry in analysis.entries
                    if "disk full" in entry.message)
    assert embedded.level == "INFO"
    assert "2026-05-11 08:00:00 ERROR" in embedded.message
    assert len(analysis) == 18
    print(f"  one message quotes another timestamp and level; the analysis "
          f"still holds {len(analysis)} entries, so scanning for a level "
          f"anywhere would invent a 19th")

    # 7. the legacy totals against the truth
    print(f"  the legacy chain, over the same {summary['nonblank']} "
          f"non-blank lines:")
    for level in ("INFO", "WARNING", "ERROR", "CRITICAL", "UNKNOWN"):
        print(f"    {level:<9} {counts.get(level, 0):>2}    "
              f"(this module: {summary.get(level, 'n/a')})")
    assert counts["UNKNOWN"] == 10
    assert counts["INFO"] == 9 and counts["ERROR"] == 7
    assert counts["WARNING"] == 2 and counts.get("CRITICAL", 0) == 0
    real, others = legacy_unknowns(analysis)
    assert len(real) == 2 and len(others) == 8
    assert len(real) + len(others) == counts["UNKNOWN"]
    assert {text for _, _, text in real} == {
        "2026-05-11 08:00:02 DEBUG Configuration loaded from config.json",
        "2026-05-11 09:00:01 DEBUG Claimed job 41"}
    print(f"    {counts['UNKNOWN']} UNKNOWNs: {len(others)} are not entries at "
          f"all (4 continuations, 4 malformed) and {len(real)} are real DEBUG "
          f"entries; the only CRITICAL is counted as ERROR")

    # 8. the conservation law
    checks = analysis.verify()
    assert len(checks) == 6 and analysis.problems() == []
    assert len(analysis) + analysis.continuations + len(analysis.bad) == \
        analysis.nonblank
    print(f"  {sum(1 for _, ok in checks if ok)}/{len(checks)} checks pass: "
          f"{len(analysis)} entries + {analysis.continuations} continuations "
          f"+ {len(analysis.bad)} malformed = {analysis.nonblank} non-blank "
          f"lines, so nothing is dropped and nothing is counted twice")

    # 9. the span
    first, last, seconds = analysis.span()
    assert first.strftime(STAMP) == "2026-05-11 08:00:01"
    assert last.strftime(STAMP) == "2026-05-11 09:00:13"
    assert seconds == 3612
    print(f"  the entries span {first.strftime(STAMP)} to "
          f"{last.strftime(STAMP)}, {seconds} seconds")

    # 10. the report, and the word search
    lines = report_text(analysis).splitlines()
    assert len(lines) == 5                    # header, 3 files, total
    assert lines[0] == ("File,Entries,DEBUG,INFO,WARNING,ERROR,CRITICAL,"
                        "Continued,Malformed")
    assert lines[-1].startswith("TOTAL,18,4,7,3,3,1,6,4")
    hits = search(analysis, "error")
    assert len(hits) == 3
    assert {entry.message for entry in hits} == {
        "Health check passed, no error detected",
        "Worker 1 shutting down, error in loop",
        'Upstream said "2026-05-11 08:00:00 ERROR disk full"; ignored'}
    assert len(search(analysis, "errors")) == 1
    assert search(analysis, "errors")[0].message == \
        "Validation finished, errors 0"
    assert [entry.message for entry in search(analysis, "info")] == \
        ["User info record missing"]
    print(f"  the report is {len(lines) - 1} rows with all five levels; "
          f"search('error') finds {len(hits)} entries as whole words, "
          f"'errors' finds {len(search(analysis, 'errors'))}, and 'info' does "
          f"not match 'Informational'")

    # 11. a second analysis is the same analysis
    assert analyze().to_dict() == analysis.to_dict()
    print(f"  a second analysis returned the same value, so the run is "
          f"read-only and repeatable")

    # 12. refusals
    refused = 0
    for bad in (Path("no-such-folder"), Path(__file__)):
        try:
            analyze(bad)
        except LogError:
            refused += 1
        else:
            raise AssertionError(f"{bad} was analysed")
    for word in ("", "   ", None):
        try:
            search(analysis, word)
        except LogError:
            refused += 1
        else:
            raise AssertionError(f"{word!r} was searched for")
    for text in ("2026-05-11 08:00:01 TRACE something", "not a log line"):
        try:
            split_line(text)
        except LogError:
            refused += 1
        else:
            raise AssertionError(f"{text!r} was parsed")
    assert refused == 7
    print(f"  a missing folder, a file given as a folder, three bad search "
          f"words and two unparseable lines were refused ({refused} refusals)")

    print()
    print("Cross-checks OK: 3 files holding 28 non-blank lines parse into 18 "
          "entries, 6 continuation lines and 4 malformed lines with nothing "
          "dropped, the level counts are DEBUG 4 INFO 7 WARNING 3 ERROR 3 "
          "CRITICAL 1 with application.log showing CRITICAL 0 rather than "
          "omitting it, the legacy substring chain sees 'Informational' as "
          "INFO and 'errors 0' as ERROR and files the only CRITICAL under "
          "ERROR, it has no DEBUG branch so 4 entries leave its summary, it "
          "counts a 4-line traceback as 4 entries where 1 exists and reads "
          "PermissionError as an ERROR, its 10 UNKNOWNs include 8 lines that "
          "are not entries at all, a timestamp quoted inside a message "
          "creates no 19th entry, 6/6 checks hold the line count exactly "
          "(18 + 6 + 4 = 28), the entries span 3612 seconds, the report keeps "
          "all five levels per file, search('error') finds 3 whole words and "
          "'errors' only 1 because a word boundary follows the s, a second "
          "analysis returned the same value, and seven bad inputs were "
          "refused")
    print("\nDemo completed successfully.")
    return 0
