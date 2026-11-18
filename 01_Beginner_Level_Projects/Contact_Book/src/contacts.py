"""An address book: validated contacts, an in-memory repository, search, merge
and CSV/JSON persistence.

The interesting part is not storing names -- it is deciding what a *valid*
contact is, and refusing to store anything else:

    email   one '', a non-empty local part, a domain with a dot, no spaces
    phone   digits with optional '+', separators and brackets stripped,
            between 7 and 15 digits (ITU E.164 upper bound)
    name    non-empty, at most 60 characters
    tags    lower-case, unique, 1..20 characters, letters/digits/hyphen

Every violation raises ``ContactError`` with a message that says which field
and which value. Duplicate emails raise ``ConflictError`` because two contacts
you cannot tell apart are not two contacts.

Fully offline: JSON and CSV files in, JSON and CSV files out.
"""

from __future__ import annotations

import csv
import json
import re
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Sequence

MAX_NAME = 60
MIN_PHONE_DIGITS = 7
MAX_PHONE_DIGITS = 15

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")
_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PHONE_KEEP = re.compile(r"[\d+]")
_PHONE_ALLOWED = re.compile(r"^[\d\s()+\-.]+$")

CSV_FIELDS = ("id", "name", "email", "phone", "company", "tags")


class ContactError(ValueError):
    """A contact, query or file that cannot be used."""


class ConflictError(ContactError):
    """Two contacts share the identity field (email)."""


class NotFoundError(ContactError):
    """A lookup by id found nothing."""


# --------------------------------------------------------------------------- #
# Contact
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Contact:
    """An immutable, self-validating contact record."""

    id: str
    name: str
    email: str
    phone: str
    company: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _clean_name(self.name))
        object.__setattr__(self, "email", clean_email(self.email))
        object.__setattr__(self, "phone", clean_phone(self.phone))
        object.__setattr__(self, "company", _clean_company(self.company))
        object.__setattr__(self, "tags", clean_tags(self.tags))
        if not str(self.id).strip():
            raise ContactError("id must not be empty")
        object.__setattr__(self, "id", str(self.id).strip())

    # -- helpers ---------------------------------------------------------- #
    @property
    def sort_key(self) -> tuple[str, str]:
        return (self.name.casefold(), self.email)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "Contact":
        if not isinstance(payload, dict):
            raise ContactError("a contact must be a mapping")
        missing = [key for key in ("id", "name", "email", "phone")
                   if key not in payload]
        if missing:
            raise ContactError(f"contact is missing {', '.join(missing)}")
        tags = payload.get("tags") or ()
        if isinstance(tags, str):
            tags = tuple(part for part in tags.replace(";", ",").split(","))
        return cls(
            id=payload["id"],
            name=payload["name"],
            email=payload["email"],
            phone=payload["phone"],
            company=payload.get("company") or "",
            tags=tuple(tags),
        )


def _clean_name(value: str) -> str:
    if not isinstance(value, str):
        raise ContactError("name must be text")
    name = " ".join(value.split())
    if not name:
        raise ContactError("name must not be empty")
    if len(name) > MAX_NAME:
        raise ContactError(f"name is longer than {MAX_NAME} characters")
    return name


def _clean_company(value: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ContactError("company must be text")
    return " ".join(value.split())


def clean_email(value: str) -> str:
    if not isinstance(value, str):
        raise ContactError("email must be text")
    email = value.strip().lower()
    if not email:
        raise ContactError("email must not be empty")
    if " " in email:
        raise ContactError(f"email {value!r} contains a space")
    if email.count("@") != 1:
        raise ContactError(f"email {value!r} must contain exactly one '@'")
    if not _EMAIL_RE.match(email):
        raise ContactError(f"email {value!r} is not a valid address")
    return email


def clean_phone(value: str) -> str:
    if not isinstance(value, str):
        raise ContactError("phone must be text")
    text = value.strip()
    if not text:
        raise ContactError("phone must not be empty")
    if not _PHONE_ALLOWED.match(text):
        raise ContactError(f"phone {value!r} contains unsupported characters")
    digits = "".join(_PHONE_KEEP.findall(text))
    has_plus = digits.startswith("+")
    digits = digits.replace("+", "")
    if not digits.isdigit():
        raise ContactError(f"phone {value!r} contains no digits")
    if not MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS:
        raise ContactError(
            f"phone {value!r} must have between {MIN_PHONE_DIGITS} and "
            f"{MAX_PHONE_DIGITS} digits, got {len(digits)}")
    return ("+" if has_plus else "") + digits


def clean_tags(tags: Iterable[str]) -> tuple[str, ...]:
    if isinstance(tags, str):
        raise ContactError("tags must be a sequence, not a string")
    cleaned: list[str] = []
    for raw in tags:
        if not isinstance(raw, str):
            raise ContactError("each tag must be text")
        tag = raw.strip().lower()
        if not tag:
            raise ContactError("tags must not be blank")
        if len(tag) > 20:
            raise ContactError(f"tag {tag!r} is longer than 20 characters")
        if not _TAG_RE.match(tag):
            raise ContactError(f"tag {tag!r} must be letters, digits or '-'")
        if tag not in cleaned:
            cleaned.append(tag)
    return tuple(cleaned)


# --------------------------------------------------------------------------- #
# Repository
# --------------------------------------------------------------------------- #
class ContactBook:
    """An in-memory address book with stable, sequential ids."""

    def __init__(self, contacts: Iterable[Contact] = ()) -> None:
        self._contacts: dict[str, Contact] = {}
        self._emails: dict[str, str] = {}
        self._next = 1
        for contact in contacts:
            self.add(contact)

    # -- reading ---------------------------------------------------------- #
    def __len__(self) -> int:
        return len(self._contacts)

    def __iter__(self):
        return iter(self.all())

    def __contains__(self, contact_id: object) -> bool:
        return contact_id in self._contacts

    def all(self) -> list[Contact]:
        return sorted(self._contacts.values(), key=lambda c: c.sort_key)

    def get(self, contact_id: str) -> Contact:
        try:
            return self._contacts[contact_id]
        except KeyError:
            raise NotFoundError(f"no contact with id {contact_id!r}") from None

    def by_email(self, email: str) -> Contact:
        key = clean_email(email)
        try:
            return self._contacts[self._emails[key]]
        except KeyError:
            raise NotFoundError(f"no contact with email {key!r}") from None

    def next_id(self) -> str:
        return f"C-{self._next:03d}"

    # -- writing ---------------------------------------------------------- #
    def add(self, contact: Contact | dict) -> Contact:
        record = contact if isinstance(contact, Contact) else Contact.from_dict(
            contact)
        if record.id in self._contacts:
            raise ConflictError(f"contact id {record.id!r} already exists")
        if record.email in self._emails:
            owner = self._emails[record.email]
            raise ConflictError(
                f"email {record.email!r} is already used by {owner}")
        self._contacts[record.id] = record
        self._emails[record.email] = record.id
        self._bump(record.id)
        return record

    def create(self, name: str, email: str, phone: str,
               company: str = "", tags: Sequence[str] = ()) -> Contact:
        record = Contact(id=self.next_id(), name=name, email=email,
                         phone=phone, company=company, tags=tuple(tags))
        return self.add(record)

    def update(self, contact_id: str, **changes) -> Contact:
        current = self.get(contact_id)
        if not changes:
            raise ContactError("no fields to update")
        unknown = set(changes) - set(CSV_FIELDS)
        if unknown:
            raise ContactError(
                f"unknown field(s): {', '.join(sorted(unknown))}")
        if "id" in changes and changes["id"] != contact_id:
            raise ContactError("id cannot be changed")
        changes.pop("id", None)
        if "tags" in changes:
            changes["tags"] = tuple(changes["tags"])
        candidate = replace(current, **changes)
        old_email = current.email
        if candidate.email != old_email:
            owner = self._emails.get(candidate.email)
            if owner is not None and owner != contact_id:
                raise ConflictError(
                    f"email {candidate.email!r} is already used by {owner}")
        # replace() re-runs __post_init__, so nothing invalid can be stored
        self._contacts[contact_id] = candidate
        if candidate.email != old_email:
            self._emails.pop(old_email, None)
            self._emails[candidate.email] = contact_id
        return candidate

    def remove(self, contact_id: str) -> Contact:
        record = self.get(contact_id)
        del self._contacts[contact_id]
        self._emails.pop(record.email, None)
        return record

    def clear(self) -> None:
        self._contacts.clear()
        self._emails.clear()
        self._next = 1

    def _bump(self, contact_id: str) -> None:
        prefix, _, number = contact_id.partition("-")
        if prefix == "C" and number.isdigit():
            self._next = max(self._next, int(number) + 1)

    # -- search ----------------------------------------------------------- #
    def search(self, query: str = "", tag: str | None = None,
               company: str | None = None) -> list[Contact]:
        """All contacts matching every whitespace-separated term (AND)."""
        if not isinstance(query, str):
            raise ContactError("query must be text")
        terms = [term for term in query.casefold().split() if term]
        wanted_tag = tag.strip().lower() if tag else None
        wanted_company = company.strip().casefold() if company else None
        hits: list[Contact] = []
        for contact in self.all():
            haystack = " ".join((
                contact.name, contact.email, contact.phone, contact.company,
                " ".join(contact.tags))).casefold()
            if any(term not in haystack for term in terms):
                continue
            if wanted_tag is not None and wanted_tag not in contact.tags:
                continue
            if wanted_company is not None and wanted_company not in \
                    contact.company.casefold():
                continue
            hits.append(contact)
        return hits

    # -- merge ------------------------------------------------------------ #
    def merge(self, other: "ContactBook",
              policy: str = "prefer-existing") -> dict:
        """Fold ``other`` into this book and report what happened.

        ``prefer-existing`` keeps this book's values for duplicate emails;
        ``prefer-incoming`` takes the other book's non-empty values.
        """
        if policy not in ("prefer-existing", "prefer-incoming"):
            raise ContactError(
                f"unknown merge policy {policy!r} "
                "(use 'prefer-existing' or 'prefer-incoming')")
        report = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0}
        for incoming in other.all():
            existing = self._emails.get(incoming.email)
            if existing is None:
                self._contacts[incoming.id] = incoming
                self._emails[incoming.email] = incoming.id
                self._bump(incoming.id)
                report["added"] += 1
                continue
            mine = self._contacts[existing]
            if policy == "prefer-existing":
                report["unchanged"] += 1
                continue
            merged = replace(
                mine,
                name=incoming.name or mine.name,
                phone=incoming.phone or mine.phone,
                company=incoming.company or mine.company,
                tags=tuple(dict.fromkeys(mine.tags + incoming.tags)),
            )
            if merged == mine:
                report["unchanged"] += 1
            else:
                self._contacts[existing] = merged
                report["updated"] += 1
        return report

    # -- persistence ------------------------------------------------------ #
    def to_dicts(self) -> list[dict]:
        return [contact.to_dict() for contact in self.all()]

    def save(self, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dicts(), indent=2),
                          encoding="utf-8")
        return target

    def export_csv(self, path: Path | str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for contact in self.all():
                row = contact.to_dict()
                row["tags"] = ";".join(contact.tags)
                writer.writerow(row)
        return target

    @classmethod
    def load(cls, path: Path | str) -> "ContactBook":
        source = Path(path)
        if not source.exists():
            raise ContactError(f"file not found: {source}")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ContactError(f"{source.name} is not valid JSON: {exc}") from exc
        if not isinstance(payload, list):
            raise ContactError(f"{source.name} must contain a list of contacts")
        book = cls()
        for index, item in enumerate(payload):
            try:
                book.add(Contact.from_dict(item))
            except ContactError as exc:
                raise ContactError(f"contact {index}: {exc}") from exc
        return book

    @classmethod
    def from_csv(cls, path: Path | str) -> "ContactBook":
        source = Path(path)
        if not source.exists():
            raise ContactError(f"file not found: {source}")
        book = cls()
        with source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [name for name in CSV_FIELDS
                       if name not in (reader.fieldnames or [])]
            if missing:
                raise ContactError(
                    f"CSV is missing column(s): {', '.join(missing)}")
            for index, row in enumerate(reader, start=1):
                try:
                    book.add(Contact.from_dict(row))
                except ContactError as exc:
                    raise ContactError(f"row {index}: {exc}") from exc
        return book


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
SEED = (
    {"id": "C-001", "name": "Ana Silva", "email": "ana.silva@example.com",
     "phone": "+351 912 345 678", "company": "Northwind",
     "tags": ["friend", "lisbon"]},
    {"id": "C-002", "name": "Bruno Costa", "email": "bruno@example.com",
     "phone": "912-345-679", "company": "Northwind", "tags": ["work"]},
    {"id": "C-003", "name": "Carla Mendes", "email": "carla@example.org",
     "phone": "(21) 98765-4321", "company": "Acme", "tags": ["work", "vip"]},
    {"id": "C-004", "name": "Diogo Alves", "email": "diogo@example.net",
     "phone": "+1 415 555 0100", "company": "Acme", "tags": ["vendor"]},
    {"id": "C-005", "name": "Elena Rossi", "email": "elena@example.com",
     "phone": "+39 06 1234 5678", "company": "Studio", "tags": ["friend"]},
    {"id": "C-006", "name": "Ana Ferreira", "email": "ana.ferreira@example.com",
     "phone": "967654321", "company": "Northwind", "tags": ["friend", "work"]},
)


def seed_book() -> ContactBook:
    return ContactBook(Contact.from_dict(item) for item in SEED)


def run_demo() -> int:
    print("=" * 68)
    print(" CONTACT BOOK - validated records, search, merge, CSV/JSON")
    print("=" * 68)

    book = seed_book()

    # 1. every seed contact loaded, with normalised fields
    assert len(book) == 6
    ana = book.get("C-001")
    assert ana.email == "ana.silva@example.com"
    assert ana.phone == "+351912345678", ana.phone
    assert book.get("C-002").phone == "912345679"
    assert book.get("C-003").phone == "21987654321"
    print(f"  loaded {len(book)} contacts; phones normalised to digits")

    # 2. ids continue after the seed rather than colliding
    assert book.next_id() == "C-007"
    created = book.create("Farid Haddad", "farid@example.com", "+33 1 23 45 67 89",
                          "Acme", ["vendor"])
    assert created.id == "C-007"
    assert len(book) == 7
    print(f"  created {created.id} -> {created.email}")

    # 3. negative controls: bad values are refused, nothing is stored
    for bad_field, payload, needle in (
        ("email", dict(email="ana@"), "not a valid address"),
        ("email", dict(email="two@@example.com"), "exactly one '@'"),
        ("phone", dict(phone="12-34"), "between 7 and 15 digits"),
        ("name", dict(name="   "), "name must not be empty"),
        ("tags", dict(tags=["Bad Tag!"]), "must be letters, digits or '-'"),
    ):
        before = len(book)
        try:
            book.update("C-002", **payload)
        except ContactError as exc:
            assert needle in str(exc), (payload, str(exc))
        else:
            raise AssertionError(f"update {payload} should have failed")
        assert len(book) == before
    print("  5 invalid updates rejected; the book was not touched")

    # 4. duplicate email is a conflict, duplicate id too
    try:
        book.create("Copy Cat", "ana.silva@example.com", "912345680")
    except ConflictError as exc:
        assert "already used by C-001" in str(exc)
    else:
        raise AssertionError("duplicate email should be a conflict")
    try:
        book.add(Contact(id="C-002", name="Duplicate Id",
                         email="fresh@example.com", phone="912345681"))
    except ConflictError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("duplicate id should be a conflict")

    # 5. search: every term must match, tags narrow it further
    assert [c.id for c in book.search("ana")] == ["C-006", "C-001"]
    assert [c.id for c in book.search("northwind")] == \
        ["C-006", "C-001", "C-002"]
    assert [c.id for c in book.search("ana", tag="work")] == ["C-006"]
    assert book.search("nobody") == []
    print("  search 'ana' -> C-006, C-001;  'ana' + tag work -> C-006")

    # 6. company filter and case-insensitive matching
    assert [c.id for c in book.search(company="acme")] == \
        ["C-003", "C-004", "C-007"]
    assert [c.id for c in book.search("ANA")] == ["C-006", "C-001"]

    # 7. update re-validates through the frozen dataclass
    updated = book.update("C-004", company="Acme Labs", tags=["vendor", "vip"])
    assert updated.company == "Acme Labs"
    assert updated.tags == ("vendor", "vip")
    assert book.get("C-004").company == "Acme Labs"

    # 8. merge: prefer-existing keeps mine, prefer-incoming takes theirs
    incoming = ContactBook([
        Contact(id="X-001", name="Ana Silva", email="ana.silva@example.com",
                phone="+351999999999", company="Elsewhere", tags=["new"]),
        Contact(id="X-002", name="Gita Patel", email="gita@example.com",
                phone="+44 20 7946 0000", company="Acme", tags=["vendor"]),
    ])
    keep = book.merge(incoming, policy="prefer-existing")
    assert keep == {"added": 1, "updated": 0, "unchanged": 1, "skipped": 0}
    assert book.get("C-001").company == "Northwind"

    incoming2 = ContactBook([
        Contact(id="Y-001", name="Ana Silva", email="ana.silva@example.com",
                phone="+351999999999", company="Elsewhere", tags=["new"]),
        Contact(id="Y-002", name="Hugo Bento", email="hugo@example.com",
                phone="+351911111111", tags=["friend"]),
    ])
    take = book.merge(incoming2, policy="prefer-incoming")
    assert take["added"] == 1 and take["updated"] == 1
    refreshed = book.get("C-001")
    assert refreshed.company == "Elsewhere"
    assert refreshed.tags == ("friend", "lisbon", "new")
    assert refreshed.phone == "+351999999999"
    print(f"  merge prefer-existing -> {keep}")
    print(f"  merge prefer-incoming -> {take}")

    # 9. an unknown merge policy is refused before anything changes
    size = len(book)
    try:
        book.merge(incoming, policy="last-writer-wins")
    except ContactError as exc:
        assert "unknown merge policy" in str(exc)
    assert len(book) == size

    # 10. JSON round-trip is lossless and order-stable, CSV keeps tags too
    with tempfile.TemporaryDirectory(prefix="contacts-") as folder:
        root = Path(folder)
        json_path = book.save(root / "contacts.json")
        csv_path = book.export_csv(root / "contacts.csv")
        first = json.dumps(book.to_dicts(), sort_keys=True)
        again = ContactBook.load(json_path)
        assert json.dumps(again.to_dicts(), sort_keys=True) == first
        assert again.all() == book.all()

        csv_book = ContactBook.from_csv(csv_path)
        assert csv_book.all() == book.all()
        assert csv_book.get("C-001").tags == ("friend", "lisbon", "new")
        assert "friend;lisbon;new" in csv_path.read_text(encoding="utf-8")

    # 11. remove is the inverse of add
    removed = book.remove("C-007")
    assert removed.email == "farid@example.com"
    assert "C-007" not in book
    assert len(book) == 8
    try:
        book.get("C-007")
    except NotFoundError as exc:
        assert "no contact with id" in str(exc)
    else:
        raise AssertionError("removed contact should not be found")

    # 13. loading the bundled file is deterministic
    assert seed_book().all() == seed_book().all()

    print()
    print("Cross-checks OK: 6 seed contacts loaded and normalised, sequential "
          "ids, 5 invalid updates refused with the book untouched, duplicate "
          "email and duplicate id both conflicted, 6 search queries, updates "
          "re-validated, 2 merge policies with exact counts, unknown policy "
          "refused, JSON and CSV round-trips lossless, remove and missing-id "
          "lookup, deterministic seed")
    print("Demo completed successfully.")
    return 0

