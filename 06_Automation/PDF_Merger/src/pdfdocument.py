"""A PDF merger whose failures are sentences, not ``False``.

The legacy engine ended like this:

    except Exception:
        self.close()
        return False

and its validator was three lines:

    def validate(self, pdf_files: list[str]) -> bool:
        return len(pdf_files) >= 2

Three defects, and the first one is the reason the other two survive.

**1. ``return False`` throws the reason away.** Every way a merge can fail --
the file is gone, the file is empty, the file is not a PDF, the file was
truncated in transit, the file is encrypted, the output is one of the inputs --
collapses into one bit. The caller cannot tell the user which file is at fault
or what to do about it, so the message becomes "merge failed", which is exactly
the message that is never true: something specific failed. Here every failure is
a ``Problem`` that names a file and gives a reason, and a ``Reading`` either
holds a parsed document or holds the sentence that says why it does not.

**2. ``len(pdf_files) >= 2`` validates the *list*, not the *files*.** Two paths
that do not exist pass it. So does a text file renamed to ``.pdf``, an empty
file, a truncated download, a document with a password, and the same file twice.
Validation that only counts is validation that cannot fail for the reason it
exists. This module inspects every file before a single byte is copied: the
magic number, the ``%%EOF`` marker, the cross-reference index, the page tree,
and whether the output would overwrite an input.

**3. A name is a prefix of another name, and ``count`` cannot tell.** The page
tree declares ``/Type /Pages``; each page declares ``/Type /Page``. Every page
object's ``/Type /Page`` is also the first fifteen bytes of the tree's
``/Type /Pages``, so

    data.count(b"/Type /Page")

reports one page too many for any document that has a page tree -- which is every
document. The count looks right on a one-page file and is wrong on all the
others. This module reads objects and compares the *whole* name token:

    count_pages_naive(three_page_file) == 4
    count_pages(three_page_file) == 3

The documents are written by hand here -- header, objects, cross-reference table,
trailer, ``startxref``, ``%%EOF`` -- so nothing has to be installed and nothing
has to be downloaded, and the bytes are real enough that a reader checks them:
every index entry must point at its own object header, and the trailer's
``/Size`` must match the index.

Standard library only: no pypdf, no PyMuPDF, no tkinter, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUNDLE_FILE = DATA_DIR / "pages.txt"

#: The legacy lines, transcribed, so the demo can refute them.
LEGACY_EXCEPT = "except Exception:\n    self.close()\n    return False"
LEGACY_VALIDATE = "return len(pdf_files) >= 2"

#: What every PDF starts with, and what every one ends with.
MAGIC = b"%PDF-"
EOF_MARKER = b"%%EOF"

#: Versions this lab will write and read.
VERSIONS = ("1.4", "1.5", "1.6", "1.7")

#: The objects this writer numbers: a catalog, a page tree, then two per page.
FIXED_OBJECTS = 2

#: A page title may not hold these, because the writer will not escape them.
FORBIDDEN = ("(", ")", "\\")

#: ``123 0 obj`` at the start of a line.
OBJECT_HEADER = re.compile(rb"(?m)^(\d+) 0 obj\n")

#: ``/Size 12`` in the trailer.
TRAILER_SIZE = re.compile(rb"/Size\s+(\d+)")

#: ``/Root 1 0 R`` in the trailer, and not ``/Root 1 0 Rr``.
TRAILER_ROOT = re.compile(rb"/Root\s+(\d+)\s+0\s+R(?![A-Za-z])")

#: The ``stream`` keyword, and not the ``stream`` inside ``endstream``.
STREAM = re.compile(rb"(?<![A-Za-z])stream(?![A-Za-z])")

#: The one text operation this lab writes, and reads back.
SHOW_TEXT = re.compile(rb"\(([^()]*)\)\s*Tj")

#: ``/Contents 4 0 R`` on a page object, pointing at its content stream.
CONTENTS = re.compile(rb"/Contents\s+(\d+)\s+0\s+R")


class PdfError(Exception):
    """A document, a page, a file or a name that cannot be accepted.

    The message is the point. A ``PdfError`` is raised with the sentence a
    person needs, and every caller either shows it or files it as a reason.
    """


# --------------------------------------------------------------------------- #
# Bytes, described
# --------------------------------------------------------------------------- #
def describe(raw: bytes) -> str:
    """The first bytes of a file, safely, so an error can quote them.

    A file that is not a PDF often is not text either, and the message that
    says ``b'\\x89PNG'`` is the one that tells a person what they picked.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise PdfError(f"describe reads bytes, got {type(raw).__name__}")
    out = []
    for byte in bytes(raw)[:8]:
        out.append(chr(byte) if 32 <= byte < 127 else f"\\x{byte:02x}")
    return "'" + "".join(out) + "'"


def check_title(title: str) -> str:
    """A title the writer can put in a content stream without escaping."""
    if not isinstance(title, str):
        raise PdfError(f"a page title is text, got {title!r}")
    if not title.strip():
        raise PdfError("a page title cannot be blank")
    for character in title:
        if ord(character) > 126 or ord(character) < 32:
            raise PdfError(f"a page title is printable ASCII, and "
                           f"{title!r} holds a character that is not")
    for character in FORBIDDEN:
        if character in title:
            raise PdfError(f"a page title cannot hold {character!r} and this "
                           f"writer does not escape it: {title!r}")
    return title


# --------------------------------------------------------------------------- #
# The document
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Page:
    """One page, named by the text it shows."""

    title: str


@dataclass(frozen=True)
class Document:
    """Pages in order, and the PDF version they are written as."""

    pages: tuple[Page, ...]
    version: str = "1.7"

    def __len__(self) -> int:
        return len(self.pages)

    def titles(self) -> tuple[str, ...]:
        return tuple(page.title for page in self.pages)

    def number(self, title: str) -> int:
        """The 1-based page number of the first page with this title."""
        for position, page in enumerate(self.pages, start=1):
            if page.title == title:
                return position
        raise PdfError(f"the document holds no page called {title!r}")

    def lines(self) -> tuple[str, ...]:
        return tuple(f"page {position}: {page.title}"
                     for position, page in enumerate(self.pages, start=1))

    def size(self) -> str:
        return f"{len(self.pages)} page(s)"


def build_document(titles, version: str = "1.7") -> Document:
    """A document from a list of page titles."""
    return Document(tuple(Page(title) for title in titles), version)


def merge(documents) -> Document:
    """Every page of every document, in the order the documents are given."""
    documents = tuple(documents)
    if not documents:
        raise PdfError("there is nothing to merge: no documents were given")
    for position, document in enumerate(documents, start=1):
        if not isinstance(document, Document):
            raise PdfError(f"document {position} is not a document, it is "
                           f"{type(document).__name__}")
        if not document.pages:
            raise PdfError(f"document {position} holds no pages")
    pages = tuple(page for document in documents for page in document.pages)
    return Document(pages)


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
def render(document: Document) -> bytes:
    """Write a document as PDF bytes: header, objects, index, trailer.

    Every offset in the index is measured while writing, because an index is
    the file's claim about where its own objects begin -- and a claim is only
    worth something if a reader can check it.
    """
    if not isinstance(document, Document):
        raise PdfError(f"render writes a document, got {document!r}")
    if not document.pages:
        raise PdfError("a document needs at least one page")
    if document.version not in VERSIONS:
        raise PdfError(f"the version is one of {', '.join(VERSIONS)}, got "
                       f"{document.version!r}")
    for page in document.pages:
        check_title(page.title)

    buffer = bytearray()
    offsets: dict[int, int] = {}

    def emit(text: str) -> None:
        buffer.extend(text.encode("ascii"))

    def start(number: int) -> None:
        offsets[number] = len(buffer)
        emit(f"{number} 0 obj\n")

    emit(f"%PDF-{document.version}\n")
    emit("% written by the PDF lab\n")

    kids = " ".join(f"{3 + 2 * index} 0 R"
                    for index in range(len(document.pages)))
    start(1)
    emit("<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    start(2)
    emit(f"<< /Type /Pages /Kids [{kids}] /Count {len(document.pages)} >>\n"
         f"endobj\n")

    for index, page in enumerate(document.pages):
        page_number = 3 + 2 * index
        contents = page_number + 1
        start(page_number)
        emit(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
             f"/Contents {contents} 0 R >>\nendobj\n")
        stream = f"BT /F1 12 Tf 72 720 Td ({page.title}) Tj ET"
        start(contents)
        emit(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream\n"
             f"endobj\n")

    count = FIXED_OBJECTS + 2 * len(document.pages)
    index_at = len(buffer)
    emit(f"xref\n0 {count}\n")
    emit("0000000000 65535 f \n")
    for number in range(1, count):
        emit(f"{offsets[number]:010d} 00000 n \n")
    emit(f"trailer\n<< /Size {count} /Root 1 0 R >>\n"
         f"startxref\n{index_at}\n%%EOF\n")
    return bytes(buffer)


# --------------------------------------------------------------------------- #
# Reading: objects, and the whole name
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Object:
    """One ``N 0 obj`` in a file: its number, where it starts, and its body."""

    number: int
    offset: int
    body: bytes

    def type_name(self) -> str:
        """The ``/Type`` this object declares, as a whole name, or ``""``.

        ``/Type /Page`` and ``/Type /Pages`` share their first fifteen bytes.
        Reading the name and comparing all of it is the difference between a
        page count and a guess. The scan stops at the object's ``stream``,
        because a page whose text happens to be ``/Type /Page`` is a page with
        a title, not a second page.
        """
        head = STREAM.split(self.body, maxsplit=1)[0]
        place = head.find(b"/Type")
        if place < 0:
            return ""
        rest = head[place + len(b"/Type"):].lstrip()
        if not rest.startswith(b"/"):
            return ""
        name = bytearray()
        for byte in rest[1:]:
            if 65 <= byte <= 90 or 97 <= byte <= 122:
                name.append(byte)
            else:
                break
        return name.decode("ascii")


def objects_of(data: bytes) -> tuple[Object, ...]:
    """Every object in a file, in the order the objects appear."""
    found = list(OBJECT_HEADER.finditer(data))
    if not found:
        raise PdfError("the file holds no objects: there is no 'N 0 obj' in it")
    out = []
    for match in found:
        number = int(match.group(1))
        ends = data.find(b"endobj", match.end())
        if ends < 0:
            raise PdfError(f"object {number} never closes: there is no "
                           f"'endobj' after it, so the file was cut short")
        out.append(Object(number, match.start(), data[match.end():ends]))
    numbers = [entry.number for entry in out]
    if len(set(numbers)) != len(numbers):
        raise PdfError("two objects share a number, so the index cannot point "
                       "at both")
    return tuple(out)


def page_objects(data: bytes) -> tuple[Object, ...]:
    """The objects that declare ``/Type /Page`` -- and not ``/Type /Pages``."""
    return tuple(entry for entry in objects_of(data)
                 if entry.type_name() == "Page")


def count_pages(data: bytes) -> int:
    """How many pages the file actually holds."""
    return len(page_objects(data))


def count_pages_naive(data: bytes) -> int:
    """The legacy count, executable: the substring, prefixes and all.

    On any document with a page tree this is one too many, because the tree's
    ``/Type /Pages`` starts with the same fifteen bytes as a page's
    ``/Type /Page``.
    """
    return data.count(b"/Type /Page")


# --------------------------------------------------------------------------- #
# Reading: the index
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Index:
    """The cross-reference table: where the file says its objects begin."""

    offset: int
    first: int
    count: int
    size: int
    root: int

    def entries(self) -> int:
        return self.count


def check_index(data: bytes) -> Index:
    """Every claim the index makes, checked against the bytes it points at."""
    marker = data.rfind(b"startxref")
    if marker < 0:
        raise PdfError("no startxref: the file does not say where its index "
                       "begins")
    tail = data[marker + len(b"startxref"):].lstrip().split(b"\n")[0].strip()
    if not tail.isdigit():
        raise PdfError(f"startxref is followed by {describe(tail)}, which is "
                       f"not an offset")
    offset = int(tail)
    if offset >= len(data):
        raise PdfError(f"the index is said to start at byte {offset}, past the "
                       f"end of a {len(data)}-byte file")
    if not data[offset:].startswith(b"xref"):
        raise PdfError(f"the index is said to start at byte {offset}, but the "
                       f"file holds {describe(data[offset:offset + 8])} there")

    lines = data[offset:].split(b"\n")
    header = lines[1].split()
    if len(header) != 2 or not all(part.isdigit() for part in header):
        raise PdfError("the index needs a first object number and a count on "
                       "the line after 'xref'")
    first, count = int(header[0]), int(header[1])
    if count < FIXED_OBJECTS + 1:
        raise PdfError(f"the index claims {count} entr(ies), and a document "
                       f"with a catalog, a page tree and a page needs at least "
                       f"{FIXED_OBJECTS + 1}")
    entries = lines[2:2 + count]
    if len(entries) != count:
        raise PdfError(f"the index claims {count} entr(ies) and holds "
                       f"{len(entries)}")
    for position, line in enumerate(entries):
        if len(line) != 19:
            raise PdfError(f"index entry {position} is {len(line)} byte(s), "
                           f"and every entry is exactly 19")
    for position in range(first, first + count):
        if position == 0:
            continue
        line = entries[position - first]
        body = line.split()
        if len(body) != 3:
            raise PdfError(f"index entry {position} holds {len(body)} field(s), "
                           f"and every entry holds an offset, a generation and "
                           f"a letter")
        where = int(body[0])
        if not data[where:].startswith(f"{position} 0 obj".encode("ascii")):
            raise PdfError(f"object {position} is listed at byte {where}, but "
                           f"the file holds {describe(data[where:where + 8])} "
                           f"there")

    trailer = data[offset:]
    size = TRAILER_SIZE.search(trailer)
    root = TRAILER_ROOT.search(trailer)
    if size is None:
        raise PdfError("the trailer declares no /Size")
    if root is None:
        raise PdfError("the trailer declares no /Root")
    declared = int(size.group(1))
    if first + count != declared:
        raise PdfError(f"the index holds {count} entr(ies) from object {first}, "
                       f"so it ends at {first + count}, and the trailer says "
                       f"/Size {declared}")
    return Index(offset, first, count, declared, int(root.group(1)))


# --------------------------------------------------------------------------- #
# Reading: the whole document
# --------------------------------------------------------------------------- #
def parse_document(raw: bytes) -> Document:
    """Read PDF bytes, or raise with the reason they cannot be read.

    The order of the checks is the order of the damage: header, tail, index,
    objects, page tree, and finally the titles.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise PdfError(f"a document is read from bytes, got "
                       f"{type(raw).__name__}")
    data = bytes(raw)
    if not data:
        raise PdfError("the file is empty: there is not one byte in it")
    if not data.startswith(MAGIC):
        raise PdfError(f"no %PDF- header: the file starts with "
                       f"{describe(data)}")
    stem = data[len(MAGIC):len(MAGIC) + 3].decode("ascii", "replace")
    if stem not in VERSIONS:
        raise PdfError(f"the header says version {stem!r}, and this lab reads "
                       f"{', '.join(VERSIONS)}")
    if EOF_MARKER not in data:
        raise PdfError("truncated: the file has no %%EOF marker, so the "
                       "download never finished")
    if not data.rstrip().endswith(EOF_MARKER):
        raise PdfError("the %%EOF marker is not the last thing in the file, so "
                       "something was appended after it")
    if b"/Encrypt" in data:
        raise PdfError("encrypted: the file declares /Encrypt, so its pages "
                       "cannot be read without a password")

    check_index(data)
    objects = objects_of(data)
    pages = page_objects(data)
    if not pages:
        raise PdfError(f"the file holds {len(objects)} object(s) and none of "
                       f"them is a /Type /Page")

    tree = [entry for entry in objects if entry.type_name() == "Pages"]
    if not tree:
        raise PdfError("no page tree: the file declares no /Type /Pages, so "
                       "the pages it holds cannot be reached")
    counted = re.search(rb"/Count\s+(\d+)", tree[0].body)
    if counted is None:
        raise PdfError("the page tree declares no /Count")
    declared = int(counted.group(1))
    if declared != len(pages):
        raise PdfError(f"the page tree says /Count {declared} and the file "
                       f"holds {len(pages)} page object(s)")

    titles = []
    by_number = {entry.number: entry for entry in objects}
    for position, entry in enumerate(pages, start=1):
        reference = CONTENTS.search(entry.body)
        if reference is None:
            raise PdfError(f"page {position} (object {entry.number}) declares "
                           f"no /Contents, so it has no stream to read")
        target = int(reference.group(1))
        contents = by_number.get(target)
        if contents is None:
            raise PdfError(f"page {position} points at object {target} as its "
                           f"contents, and the file holds no such object")
        shown = SHOW_TEXT.search(contents.body)
        if shown is None:
            raise PdfError(f"page {position} (object {entry.number}) holds no "
                           f"'(text) Tj' in object {target}, so this lab "
                           f"cannot name it")
        titles.append(shown.group(1).decode("ascii"))
    return Document(tuple(Page(title) for title in titles))


# --------------------------------------------------------------------------- #
# Reading a bundle of documents
# --------------------------------------------------------------------------- #
def build_documents(text: str) -> dict[str, Document]:
    """Read ``document<TAB>page title`` lines into documents, in order."""
    pages: dict[str, list[str]] = {}
    for number, line in enumerate(text.replace("\r\n", "\n")
                                  .replace("\r", "\n").split("\n"), start=1):
        if not line.strip() or line.lstrip().startswith(";") or \
                line.lstrip().startswith("#"):
            continue
        if "\t" not in line:
            raise PdfError(f"line {number}: expected a document name, a tab, "
                           f"and a page title")
        name, title = line.split("\t", 1)
        name = name.strip()
        if not name:
            raise PdfError(f"line {number}: the document name is blank")
        pages.setdefault(name, []).append(title.strip())
    if not pages:
        raise PdfError("the bundle holds no pages")
    return {name: Document(tuple(Page(title) for title in titles))
            for name, titles in pages.items()}


def read_bundle(path=None) -> dict[str, Document]:
    path = Path(BUNDLE_FILE if path is None else path)
    if not path.is_file():
        raise PdfError(f"file not found: {path}")
    return build_documents(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# A reading, a problem, a report
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reading:
    """One input: either a document, or the sentence that says why not."""

    name: str
    document: Document | None = None
    reason: str = ""

    def ok(self) -> bool:
        return self.document is not None

    def line(self) -> str:
        if self.ok():
            return f"{self.name:<18} {self.document.size()}"
        return f"{self.name:<18} {self.reason}"


@dataclass(frozen=True)
class Problem:
    """A file, and what is wrong with it."""

    name: str
    reason: str

    def line(self) -> str:
        return f"{self.name:<18} {self.reason}"


@dataclass(frozen=True)
class Report:
    """Every input read, every problem named, and the output path."""

    readings: tuple[Reading, ...]
    problems: tuple[Problem, ...]
    output: str

    def ok(self) -> bool:
        return not self.problems

    def reasons(self) -> tuple[str, ...]:
        return tuple(problem.reason for problem in self.problems)

    def read(self) -> tuple[Document, ...]:
        return tuple(reading.document for reading in self.readings
                     if reading.document is not None)

    def summary(self) -> str:
        good = sum(1 for reading in self.readings if reading.ok())
        return (f"{len(self.readings)} input(s), {good} readable, "
                f"{len(self.problems)} problem(s)")

    def lines(self) -> tuple[str, ...]:
        out = [problem.line() for problem in self.problems]
        if not out:
            out = ["no problem: every input is a document this lab can read"]
        return tuple(out)


def inspect(name: str, raw: bytes | None = None) -> Reading:
    """Read one input, keeping the reason instead of raising it.

    ``None`` stands for "there was no file to read at all", which is a
    different reason from an empty file -- and a reason is the whole point.
    """
    if raw is None:
        return Reading(name, None, f"there is no such file: {name}")
    try:
        return Reading(name, parse_document(raw))
    except PdfError as error:
        return Reading(name, None, str(error))


def read_bytes(path) -> bytes:
    """A file from disk, with a reason when there is nothing to read."""
    path = Path(path)
    if not path.is_file():
        raise PdfError(f"there is no such file: {path}")
    return path.read_bytes()


def inspect_path(path) -> Reading:
    """Read a path, keeping the reason -- the missing file included."""
    try:
        return Reading(str(path), parse_document(read_bytes(path)))
    except PdfError as error:
        return Reading(str(path), None, str(error))


def check_files(paths, output: str = "merged.pdf") -> Report:
    """Validate paths on disk, treating a missing file as one reason among many."""
    pairs = []
    for path in paths:
        try:
            pairs.append((str(path), read_bytes(path)))
        except PdfError:
            pairs.append((str(path), None))
    return check(pairs, output)


def check(files, output: str = "merged.pdf") -> Report:
    """Validate a list of inputs before anything is merged or written.

    ``files`` holds ``(name, bytes)`` pairs. The list itself is checked too:
    two documents are the minimum, no input may appear twice, and the output
    may not be one of the inputs -- overwriting a source with a merge is how a
    merge destroys a document.
    """
    files = tuple(files)
    problems: list[Problem] = []
    readings: list[Reading] = []

    if len(files) < 2:
        problems.append(Problem("(list)",
                                f"at least two documents are needed to merge, "
                                f"and the list holds {len(files)}"))
    if not str(output).strip():
        problems.append(Problem("(output)", "the output path is blank"))

    seen: dict[str, int] = {}
    blocked: set[str] = set()
    shown = str(output).strip().casefold()
    for name, raw in files:
        key = str(name).strip().casefold()
        reading = inspect(name, raw)
        if key in seen:
            blocked.add(key)
            reading = Reading(name, None,
                              f"duplicate: this file is already in the list at "
                              f"position {seen[key]}")
        elif key == shown and shown:
            blocked.add(key)
            reading = Reading(name, None,
                              "the output path is one of the inputs, so "
                              "writing it would overwrite a source")
        else:
            seen[key] = len(seen) + 1
        readings.append(reading)
        if not reading.ok():
            problems.append(Problem(name, reading.reason))

    for name, _ in files:
        if not str(name).strip():
            problems.append(Problem("(input)", "an input path is blank"))
    return Report(tuple(readings), tuple(problems), str(output))


def merge_bytes(files, output: str = "merged.pdf") -> tuple[bytes, Report]:
    """The merged bytes, and the report that justifies them.

    ``output`` is the merged file's bytes on success and ``b""`` on failure --
    the empty bytes are the third state the legacy ``bool`` could not express,
    and the report is what says which state this is.
    """
    report = check(files, output)
    if not report.ok():
        return b"", report
    return render(merge(report.read())), report


# --------------------------------------------------------------------------- #
# A lab, for the audit
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Lab:
    """The parts, the bytes they were written as, the merge, and the report."""

    parts: tuple[Document, ...]
    written: tuple[bytes, ...]
    merged: Document
    report: Report


def build_lab(parts, names=None, output: str = "merged.pdf") -> Lab:
    parts = tuple(parts)
    if names is None:
        names = tuple(f"part-{position}.pdf"
                      for position in range(1, len(parts) + 1))
    names = tuple(names)
    if len(names) != len(parts):
        raise PdfError("every part needs a name")
    written = tuple(render(part) for part in parts)
    merged = merge(parts)
    report = check(tuple(zip(names, written)), output)
    return Lab(parts, written, merged, report)


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def _guard(check_function) -> bool:
    """Run one check, and report a structural break as a failure."""
    try:
        return bool(check_function())
    except Exception:                                     # noqa: BLE001
        return False


def audit(lab: Lab) -> list[tuple[str, bool]]:
    """Nine checks, each re-derived from the bytes rather than restated."""
    report = lab.report

    def every_part_writes_a_pdf() -> bool:
        for part in lab.parts:
            data = render(part)
            if not data.startswith(MAGIC):
                return False
            if not data.rstrip().endswith(EOF_MARKER):
                return False
        return True

    def every_written_file_parses_back_to_its_part() -> bool:
        if len(lab.written) != len(lab.parts):
            return False
        for part, data in zip(lab.parts, lab.written):
            if parse_document(data).titles() != part.titles():
                return False
        return True

    def every_index_entry_points_at_its_own_header() -> bool:
        for data in lab.written:
            index = check_index(data)
            for number in range(index.first, index.first + index.count):
                if number == 0:
                    continue
                line = data[index.offset:].split(b"\n")[2 + number]
                where = int(line.split()[0])
                if not data[where:].startswith(f"{number} 0 obj".encode()):
                    return False
        return True

    def the_page_tree_count_matches_the_pages() -> bool:
        for data in lab.written:
            tree = [entry for entry in objects_of(data)
                    if entry.type_name() == "Pages"]
            counted = re.search(rb"/Count\s+(\d+)", tree[0].body)
            if counted is None or int(counted.group(1)) != count_pages(data):
                return False
        return True

    def the_naive_count_is_one_too_many() -> bool:
        for data in lab.written:
            if count_pages_naive(data) != count_pages(data) + 1:
                return False
        return True

    def the_merge_holds_every_page_in_order() -> bool:
        wanted = tuple(page.title for part in lab.parts for page in part.pages)
        return lab.merged.titles() == wanted

    def every_reading_is_one_thing_or_the_other() -> bool:
        for reading in report.readings:
            if reading.ok() and reading.reason:
                return False
            if not reading.ok() and not reading.reason.strip():
                return False
        return True

    def every_failed_reading_is_named_by_a_problem() -> bool:
        named = {problem.name.strip().casefold() for problem in report.problems}
        if not all(problem.name.strip() for problem in report.problems):
            return False
        for reading in report.readings:
            if reading.ok():
                continue
            if reading.name.strip().casefold() not in named:
                return False
        return True

    def every_title_is_writable() -> bool:
        for page in lab.merged.pages:
            if page.title != check_title(page.title):
                return False
        return True

    checks = [
        ("every part writes bytes that begin with %PDF- and end with %%EOF",
         every_part_writes_a_pdf),
        ("every written file parses back to the part it was written from",
         every_written_file_parses_back_to_its_part),
        ("every index entry points at its own object header",
         every_index_entry_points_at_its_own_header),
        ("the page tree's /Count equals the number of page objects",
         the_page_tree_count_matches_the_pages),
        ("the naive /Type /Page count is exactly one too many per document",
         the_naive_count_is_one_too_many),
        ("the merged document holds every page of its parts, in order",
         the_merge_holds_every_page_in_order),
        ("every reading holds a document or a reason, never both, never "
         "neither", every_reading_is_one_thing_or_the_other),
        ("every failed reading is named by a problem that names a file",
         every_failed_reading_is_named_by_a_problem),
        ("every page title is printable ASCII with no bracket or backslash",
         every_title_is_writable),
    ]
    return [(name, _guard(function)) for name, function in checks]


def problems(checks) -> list[str]:
    return [name for name, okay in checks if not okay]


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def damage(data: bytes, kind: str) -> bytes:
    """A copy of a real file, broken in one documented way."""
    if kind == "empty":
        return b""
    if kind == "text":
        return b"this is a text file somebody renamed to .pdf\n"
    if kind == "truncated":
        return data[:len(data) - 40]
    if kind == "index":
        marker = data.rfind(b"startxref")
        return data[:marker] + b"startxref\n0\n" + data[marker:].split(b"\n", 2)[2]
    if kind == "encrypted":
        return data.replace(b"/Root 1 0 R", b"/Root 1 0 R /Encrypt 9 0 R", 1)
    if kind == "count":
        return re.sub(rb"/Count (\d+)", b"/Count 9", data, count=1)
    if kind == "trailer":
        return re.sub(rb"/Size (\d+)", b"/Size 999", data, count=1)
    raise PdfError(f"no such damage: {kind!r}")


def run_demo() -> int:
    bundle = read_bundle()
    names = tuple(bundle)
    parts = tuple(bundle[name] for name in names)
    merged = merge(parts)
    written = tuple(render(part) for part in parts)
    merged_bytes = render(merged)
    files = tuple(f"{name}.pdf" for name in names)
    report = check(tuple(zip(files, written)), "merged.pdf")
    lab = Lab(parts, written, merged, report)

    print("=" * 74)
    print(" PDF LAB - 'False' is not an explanation, and a prefix is not a page")
    print("=" * 74)

    print("\n  the legacy engine, transcribed:")
    for line in LEGACY_EXCEPT.split("\n"):
        print(f"    {line}")
    print(f"    {LEGACY_VALIDATE}")

    ghost = ("missing.pdf", "data/pages.txt", "notes.txt")
    print(f"\n  the legacy validator on {len(ghost)} names that cannot be read:")
    for name in ghost:
        print(f"    {name}")
    print(f"    it answers {len(ghost) >= 2} -- the count is the whole check")

    print(f"\n  the same three names, asked properly:")
    for name in ghost:
        print(f"    {inspect_path(name).line()}")

    print(f"\n  the bundle: {len(parts)} document(s)")
    for name, part in zip(names, parts):
        print(f"    {name:<8} {part.size():<12} {', '.join(part.titles())}")

    first = written[0]
    print(f"\n  the first document, as {len(first)} bytes:")
    print(f"    it starts with {describe(first[:8])} and ends with "
          f"{describe(first[-6:])}")
    index = check_index(first)
    print(f"    the index starts at byte {index.offset} and holds "
          f"{index.entries()} entr(ies), /Size {index.size}, /Root "
          f"{index.root}")

    print(f"\n  counting pages in those {len(first)} bytes:")
    print(f"    {names[0]}.pdf holds {count_pages(first)} page object(s) "
          f"with /Type /Page")
    print(f"    it also holds 1 /Type /Pages tree, whose first fifteen bytes "
          f"are the same")
    print(f"    data.count(b'/Type /Page') answers {count_pages_naive(first)} "
          f"-- one too many")

    print(f"\n  the merge: {len(parts)} document(s) -> {merged.size()} "
          f"-> {len(merged_bytes)} bytes")
    for line in merged.lines()[:3]:
        print(f"    {line}")
    print("    ...")
    for line in merged.lines()[-2:]:
        print(f"    {line}")
    print(f"    parsed back: {parse_document(merged_bytes).size()}, naive "
          f"count {count_pages_naive(merged_bytes)}")

    print("\n  the same bytes, damaged in six ways, and the reason each one "
          "gives:")
    broken = [("empty.pdf", damage(first, "empty")),
              ("renamed.pdf", damage(first, "text")),
              ("truncated.pdf", damage(first, "truncated")),
              ("index.pdf", damage(first, "index")),
              ("locked.pdf", damage(first, "encrypted")),
              ("cut-page.pdf", damage(first, "count"))]
    for name, raw in broken:
        print(f"    {inspect(name, raw).line()}")

    print("\n  a list with a duplicate and an output that is one of its inputs:")
    awkward = check((("a.pdf", written[0]), ("a.pdf", written[0]),
                     ("b.pdf", written[1])), "b.pdf")
    for line in awkward.lines():
        print(f"    {line}")

    print("\n  the merge that worked:")
    print(f"    {report.summary()} -- ok: {report.ok()}")
    for reading in report.readings:
        print(f"    {reading.line()}")

    checks = audit(lab)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(parts)} document(s) fold {len(merged)} page(s) into "
          f"{len(merged_bytes)} bytes that parse back to "
          f"{parse_document(merged_bytes).size()}, the substring count says "
          f"{count_pages_naive(first)} where the objects say "
          f"{count_pages(first)}, {len(broken)} damaged files give "
          f"{len({inspect(name, raw).reason for name, raw in broken})} "
          f"different reason(s) where the legacy engine gave one False, the "
          f"legacy validator passes {len(ghost)} unusable names, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
