"""A mail merge that builds one message per person, and proves it did.

The legacy sender built a single message and put every address in its To
header:

    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)
    ...
    self.server.send_message(message)

and derived attachment names like this:

    filename=file.split("\\\\")[-1]

Two defects, both invisible on the tutorial's one-recipient run.

**1. One message for many people is a disclosure, not a merge.** Every
recipient receives a header naming every other recipient. That is a privacy
leak on a good day and a ready-made reply-all list on a bad one, and it makes
personalisation impossible: there is one body, so it cannot say anybody's
name. Here a message carries an ``Address`` object -- a frozen pair of local
part and domain -- so a comma cannot get into it. The type makes the defect
unrepresentable rather than merely discouraged.

**2. ``split("\\\\")[-1]`` is a Windows-only rule stated as a general one.** On
a path written with forward slashes the split finds nothing and returns the
*whole path*, so ``reports/q3.pdf`` becomes an attachment whose file name is
``reports/q3.pdf``. Mail clients may read that as a directory, and a slash in a
header value is at best a nuisance. The rebuild splits on both separators,
then refuses the result if anything that is not a bare file name survives.

A third, quieter defect: ``send_email`` returns ``None``. One call for N people
means the caller cannot tell how many arrived, and a failure in the middle
raises out of a loop that has already delivered the earlier messages. The
rebuild returns a ``Report`` that accounts for every row it was given --
sent, skipped (a duplicate address) or failed (with the transport's reason).

The transport is an interface, not SMTP. ``RecordingTransport`` records the
envelope, ``RefusingTransport`` fails one address on purpose, and neither opens
a socket, so the demonstration is deterministic and offline.

Standard library only: no ``smtplib``, no ``tkinter``, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TEMPLATE_FILE = DATA_DIR / "template.txt"
RECIPIENTS_FILE = DATA_DIR / "recipients.txt"
ATTACHMENTS_FILE = DATA_DIR / "attachments.txt"

#: The legacy lines, transcribed, so the demo can refute them.
LEGACY_TO = 'message["To"] = ", ".join(recipients)'
LEGACY_FILENAME = 'filename=file.split("\\\\")[-1]'
LEGACY_SEND = "self.server.send_message(message)"

#: Who the campaign is from when nobody says otherwise.
DEFAULT_SENDER = "team@example.com"

#: A field name inside a placeholder: lowercase, digits, underscores.
FIELD = re.compile(r"[a-z_][a-z0-9_]*\Z")

#: What an attachment's file name may not contain.
FORBIDDEN_IN_NAME = frozenset('<>:"/\\|?*')

#: The longest file name a plan will issue.
MAX_ATTACHMENT_NAME = 80


class MailError(Exception):
    """A template, an address, a campaign or a transport that cannot proceed."""


class BadAddress(MailError, ValueError):
    """An address that is not one address."""


class BadTemplate(MailError):
    """A template that cannot be read, or that no recipient can fill."""


class TransportError(MailError):
    """A message that a transport will not accept, or refused to deliver."""


# --------------------------------------------------------------------------- #
# Addresses
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, order=True)
class Address:
    """One mailbox: a local part and a domain, and nothing else.

    The pair is the whole point. ``"a@x.com, b@y.com"`` cannot be stored in an
    ``Address`` because a comma is neither a local character nor a domain
    character, so ``", ".join(recipients)`` has nowhere to go.
    """

    local: str
    domain: str

    @classmethod
    def parse(cls, text) -> "Address":
        if not isinstance(text, str):
            raise BadAddress(f"an address must be text, got {text!r}")
        text = text.strip()
        if not text:
            raise BadAddress("an address cannot be empty")
        if "," in text or ";" in text:
            raise BadAddress(f"an address cannot hold a comma or a semicolon -- "
                             f"that is more than one address: {text!r}")
        if text.count("@") != 1:
            raise BadAddress(f"an address needs exactly one '@': {text!r}")
        local, domain = text.split("@")
        if not local:
            raise BadAddress(f"an address needs a name before the '@': {text!r}")
        if not domain:
            raise BadAddress(f"an address needs a domain after the '@': {text!r}")
        if any(character.isspace() for character in text):
            raise BadAddress(f"an address cannot hold a space: {text!r}")
        if local.startswith(".") or local.endswith(".") or ".." in local:
            raise BadAddress(f"a dot may not sit at either end of the name, or "
                             f"twice in a row: {text!r}")
        if "." not in domain:
            raise BadAddress(f"a domain needs a dot: {text!r}")
        if domain.startswith(".") or domain.endswith(".") or ".." in domain:
            raise BadAddress(f"a dot may not sit at either end of the domain, "
                             f"or twice in a row: {text!r}")
        for part in (local, domain):
            for character in part:
                if not (character.isalnum() or character in "._+-"):
                    raise BadAddress(f"{character!r} is not allowed in an "
                                     f"address: {text!r}")
        return cls(local, domain)

    def __str__(self) -> str:
        return f"{self.local}@{self.domain}"

    def key(self) -> str:
        """The address as a duplicate check compares it: case-insensitively."""
        return str(self).casefold()


# --------------------------------------------------------------------------- #
# A recipient
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Recipient:
    """A name, one address, and the values this person's mail may use."""

    name: str
    address: Address
    fields: tuple[tuple[str, str], ...] = ()

    def value(self, name: str):
        for key, value in self.fields:
            if key == name:
                return value
        return None

    def keys(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self.fields)

    def __str__(self) -> str:
        return f"{self.name} <{self.address}>"


def parse_recipient(name: str, address, pairs) -> Recipient:
    """Build a recipient, checking the name and every field name."""
    name = (name or "").strip()
    if not name:
        raise MailError("a recipient needs a name")
    fields = []
    seen = set()
    for pair in pairs:
        if "=" not in pair:
            raise MailError(f"a field looks like name=value, got {pair!r}")
        key, _, value = pair.partition("=")
        key = key.strip()
        if not FIELD.match(key):
            raise MailError(f"{key!r} is not a field name (lowercase letters, "
                            f"digits and underscores)")
        if key in seen:
            raise MailError(f"{name!r} gives {key!r} twice")
        seen.add(key)
        if not value.strip():
            raise MailError(f"{name!r} gives {key!r} an empty value")
        fields.append((key, value.strip()))
    return Recipient(name, Address.parse(address), tuple(fields))


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
def placeholders(text: str) -> tuple[str, ...]:
    """Every field a text asks for, in the order it asks, or ``BadTemplate``.

    The brackets are counted by hand rather than by a regular expression, so an
    unclosed placeholder is reported with the character where it opened instead
    of quietly matching nothing.
    """
    if not isinstance(text, str):
        raise BadTemplate(f"a text must be text, got {text!r}")
    found = []
    index = 0
    while True:
        start = text.find("{{", index)
        stray = text.find("}}", index)
        if stray != -1 and (start == -1 or stray < start):
            raise BadTemplate(f"a closing bracket pair ends nothing at "
                              f"character {stray}")
        if start == -1:
            return tuple(found)
        end = text.find("}}", start + 2)
        if end == -1:
            raise BadTemplate(f"an opening bracket pair never closes "
                              f"(character {start})")
        name = text[start + 2:end]
        if not FIELD.match(name):
            raise BadTemplate(f"{name!r} is not a field name (lowercase "
                              f"letters, digits and underscores)")
        found.append(name)
        index = end + 2


@dataclass(frozen=True)
class Template:
    """A subject and a body, with placeholders a recipient has to fill."""

    subject: str
    body: str

    @property
    def fields(self) -> tuple[str, ...]:
        wanted: list[str] = []
        for name in placeholders(self.subject) + placeholders(self.body):
            if name not in wanted:
                wanted.append(name)
        return tuple(wanted)

    def check(self, recipients) -> None:
        """Refuse a template that some recipient cannot fill.

        A merge that renders for the first three people and raises on the fourth
        has already sent three messages by the time it fails. The template is
        therefore checked against *every* recipient up front, and the first gap
        is named.
        """
        recipients = list(recipients)
        if not recipients:
            raise BadTemplate("a campaign needs at least one recipient")
        wanted = self.fields
        if not wanted:
            raise BadTemplate("the template asks for nothing; every recipient "
                              "would receive the same message")
        supplied = {key for recipient in recipients for key in recipient.keys()}
        for name in wanted:
            if name not in supplied:
                raise BadTemplate(f"no recipient supplies {name!r}; the "
                                  f"template may use {sorted(supplied)!r}")
        for recipient in recipients:
            for name in wanted:
                if recipient.value(name) is None:
                    raise BadTemplate(f"{recipient.address} has no value for "
                                      f"{name!r}")

    def render_text(self, text: str, recipient: Recipient) -> str:
        placeholders(text)
        out = []
        index = 0
        while True:
            start = text.find("{{", index)
            if start == -1:
                out.append(text[index:])
                return "".join(out)
            out.append(text[index:start])
            end = text.find("}}", start + 2)
            name = text[start + 2:end]
            value = recipient.value(name)
            if value is None:
                raise BadTemplate(f"{recipient.address} has no value for "
                                  f"{name!r}")
            out.append(value)
            index = end + 2

    def render(self, recipient: Recipient, sender=DEFAULT_SENDER,
               attachments=()) -> "Message":
        """One message for one person, with every placeholder filled."""
        subject = self.render_text(self.subject, recipient)
        body = self.render_text(self.body, recipient)
        for text in (subject, body):
            if "{{" in text or "}}" in text:
                raise BadTemplate("a placeholder survived rendering")
        return Message(sender=Address.parse(sender), to=recipient.address,
                       subject=subject, body=body,
                       attachments=tuple(attachments))


# --------------------------------------------------------------------------- #
# A message
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Message:
    """One delivered mail: one sender, **one** recipient, one body."""

    sender: Address
    to: Address
    subject: str
    body: str
    attachments: tuple[str, ...] = field(default=())

    def envelope(self) -> str:
        return f"{self.sender} -> {self.to}  |  {self.subject}"

    def text(self) -> str:
        """Everything a mail client would show, for the leak check."""
        return " ".join((str(self.sender), str(self.to), self.subject,
                         self.body, " ".join(self.attachments)))


def addresses_in(text: str, known) -> set:
    """Which of ``known`` appear in ``text``, compared case-insensitively."""
    folded = text.casefold()
    return {address for address in known if address.casefold() in folded}


# --------------------------------------------------------------------------- #
# Attachments
# --------------------------------------------------------------------------- #
def attachment_name(path) -> str:
    """The file name of a path, whichever separator it was written with.

    ``reports/q3.pdf`` and ``reports\\q3.pdf`` must give the same answer, and
    neither may give the directory back.
    """
    text = str(path).strip()
    if not text:
        raise MailError("an attachment needs a path")
    if any(ord(character) < 32 for character in text):
        raise MailError(f"a path cannot hold a control character: {text!r}")
    name = text.replace("\\", "/").rsplit("/", 1)[-1]
    if name in ("", ".", ".."):
        raise MailError(f"{text!r} does not name a file")
    if any(character in FORBIDDEN_IN_NAME for character in name):
        raise MailError(f"a file name cannot hold "
                        f"{sorted(FORBIDDEN_IN_NAME)!r}: {name!r}")
    if len(name) > MAX_ATTACHMENT_NAME:
        raise MailError(f"a file name is at most {MAX_ATTACHMENT_NAME} "
                        f"characters, got {len(name)}")
    return name


# --------------------------------------------------------------------------- #
# Transports
# --------------------------------------------------------------------------- #
class Transport:
    """What a campaign needs from a mail server: one send, one message."""

    def send(self, message: Message) -> None:
        raise NotImplementedError


class RecordingTransport(Transport):
    """A transport that records envelopes instead of opening a socket."""

    def __init__(self) -> None:
        self.messages: list[Message] = []

    def send(self, message: Message) -> None:
        if not isinstance(message, Message):
            raise TransportError(f"a transport sends a Message, got "
                                 f"{message!r}")
        if not isinstance(message.to, Address):
            raise TransportError(f"a message must name one address object, "
                                 f"got {message.to!r}")
        if "," in str(message.to) or ";" in str(message.to):
            raise TransportError(f"one message names more than one address: "
                                 f"{message.to}")
        self.messages.append(message)

    def addresses(self) -> tuple[str, ...]:
        return tuple(str(message.to) for message in self.messages)

    def __len__(self) -> int:
        return len(self.messages)


class RefusingTransport(RecordingTransport):
    """A transport that refuses chosen addresses, to show a partial failure."""

    def __init__(self, refuse=()) -> None:
        super().__init__()
        self.refuse = {str(Address.parse(address)).casefold()
                       for address in refuse}

    def send(self, message: Message) -> None:
        if str(message.to).casefold() in self.refuse:
            raise TransportError(f"the server refused {message.to}: mailbox "
                                 f"unavailable")
        super().send(message)


# --------------------------------------------------------------------------- #
# The campaign
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Skipped:
    """A row that was read and deliberately not sent."""

    address: str
    reason: str


@dataclass(frozen=True)
class Failed:
    """A row that was sent and refused, with the transport's reason."""

    address: str
    reason: str


@dataclass(frozen=True)
class Report:
    """Every row accounted for: sent, skipped, or failed with a reason."""

    rows: int
    sent: tuple[Message, ...] = ()
    skipped: tuple[Skipped, ...] = ()
    failed: tuple[Failed, ...] = ()

    def counts(self) -> tuple[int, int, int, int]:
        return (self.rows, len(self.sent), len(self.skipped), len(self.failed))

    def adds_up(self) -> bool:
        return len(self.sent) + len(self.skipped) + len(self.failed) == self.rows

    def summary(self) -> str:
        rows, sent, skipped, failed = self.counts()
        return (f"{sent} sent, {skipped} skipped, {failed} failed, "
                f"{rows} row(s) read")

    def reasons(self) -> tuple[str, ...]:
        return tuple(entry.reason for entry in self.skipped + self.failed)


def dedupe(recipients) -> tuple[list, list]:
    """Split rows into the first entry per address and the repeats."""
    unique, dropped, seen = [], [], set()
    for recipient in recipients:
        key = recipient.address.key()
        if key in seen:
            dropped.append(Skipped(str(recipient.address),
                                   f"a second entry for the same address "
                                   f"({recipient.name!r})"))
            continue
        seen.add(key)
        unique.append(recipient)
    return unique, dropped


def send_campaign(template: Template, recipients, transport: Transport,
                  sender=DEFAULT_SENDER, attachments=()) -> Report:
    """Render, send and account for one message per unique address."""
    rows = list(recipients)
    unique, skipped = dedupe(rows)
    template.check(unique)
    names = tuple(attachment_name(path) for path in attachments)
    sent, failed = [], []
    for recipient in unique:
        message = template.render(recipient, sender, names)
        try:
            transport.send(message)
        except TransportError as error:
            failed.append(Failed(str(recipient.address), str(error)))
        else:
            sent.append(message)
    return Report(rows=len(rows), sent=tuple(sent), skipped=tuple(skipped),
                  failed=tuple(failed))


# --------------------------------------------------------------------------- #
# The data files
# --------------------------------------------------------------------------- #
def _lines(path: Path) -> list:
    path = Path(path)
    if not path.is_file():
        raise MailError(f"file not found: {path}")
    out = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(),
                                  start=1):
        text = line.strip()
        if not text or text.startswith(";") or text.startswith("//"):
            continue
        out.append((number, line.rstrip()))
    return out


def read_template(path=TEMPLATE_FILE) -> Template:
    """Read ``subject: ...``, a ``--`` line, then the body."""
    subject, body, seen_rule = None, [], False
    for number, line in _lines(path):
        if not seen_rule:
            if line.strip() == "--":
                seen_rule = True
                continue
            if line.strip().lower().startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
                if not subject:
                    raise BadTemplate(f"{Path(path).name}:{number}: the "
                                      f"subject is empty")
                continue
            raise BadTemplate(f"{Path(path).name}:{number}: expected "
                              f"'subject: ...' or a '--' line")
        body.append(line)
    if subject is None:
        raise BadTemplate(f"{Path(path).name}: no subject line")
    if not seen_rule:
        raise BadTemplate(f"{Path(path).name}: no '--' line before the body")
    text = "\n".join(body).strip()
    if not text:
        raise BadTemplate(f"{Path(path).name}: the body is empty")
    template = Template(subject, text)
    template.fields                       # a bad placeholder fails here
    return template


def read_recipients(path=RECIPIENTS_FILE) -> list:
    """Read ``name<TAB>address<TAB>field=value ...`` lines."""
    out = []
    for number, line in _lines(path):
        parts = line.split("\t")
        if len(parts) < 2:
            raise MailError(f"{Path(path).name}:{number}: expected a name, a "
                            f"tab, and an address")
        name, address = parts[0], parts[1].strip()
        try:
            out.append(parse_recipient(name, address,
                                       [part for part in parts[2:]]))
        except MailError as error:
            raise MailError(f"{Path(path).name}:{number}: {error}") from None
    if not out:
        raise MailError(f"{Path(path).name}: no recipients")
    return out


def read_attachments(path=ATTACHMENTS_FILE) -> tuple:
    """Read one path per line, in either separator style."""
    return tuple(line.strip() for _, line in _lines(path))


# --------------------------------------------------------------------------- #
# Cross-checks
# --------------------------------------------------------------------------- #
def audit(template: Template, recipients, report: Report,
          attachments=()) -> list:
    """Nine checks, each re-derived from the messages rather than restated."""
    rows = list(recipients)
    unique, _ = dedupe(rows)
    known = [str(recipient.address) for recipient in rows]
    by_address = {str(recipient.address).casefold(): recipient
                  for recipient in unique}

    def one_recipient_per_message() -> bool:
        if not report.sent:
            return False
        for message in report.sent:
            if not isinstance(message.to, Address):
                return False
            if "," in str(message.to) or ";" in str(message.to):
                return False
        return True

    def nobody_sees_anybody_else() -> bool:
        for message in report.sent:
            others = [address for address in known
                      if address.casefold() != str(message.to).casefold()]
            if addresses_in(message.text(), others):
                return False
        return True

    def every_placeholder_was_filled() -> bool:
        for message in report.sent:
            if "{{" in message.subject + message.body:
                return False
            if "}}" in message.subject + message.body:
                return False
        return True

    def each_address_appears_once() -> bool:
        sent = [str(message.to).casefold() for message in report.sent]
        failed = [entry.address.casefold() for entry in report.failed]
        return len(set(sent + failed)) == len(sent + failed)

    def every_row_is_accounted_for() -> bool:
        if not report.adds_up():
            return False
        covered = ({str(message.to).casefold() for message in report.sent} |
                   {entry.address.casefold() for entry in report.skipped} |
                   {entry.address.casefold() for entry in report.failed})
        return covered == {recipient.address.key() for recipient in rows}

    def the_merge_reached_the_text() -> bool:
        wanted = template.fields
        for message in report.sent:
            recipient = by_address.get(str(message.to).casefold())
            if recipient is None:
                return False
            for name in wanted:
                value = recipient.value(name)
                if value is None:
                    return False
                if value not in message.text():
                    return False
        return True

    def every_attachment_is_a_bare_name() -> bool:
        for name in list(attachments) + [name for message in report.sent
                                         for name in message.attachments]:
            if not name:
                return False
            if "/" in name or "\\" in name:
                return False
            if any(character in FORBIDDEN_IN_NAME for character in name):
                return False
        return True

    def the_subject_was_personalised() -> bool:
        if not placeholders(template.subject):
            return True
        return len({message.subject for message in report.sent}) > 1

    def a_duplicate_became_a_reason() -> bool:
        return all(entry.reason for entry in report.skipped + report.failed)

    return [
        ("every message names exactly one recipient",
         one_recipient_per_message()),
        ("no message names anybody but its own recipient",
         nobody_sees_anybody_else()),
        ("no placeholder survived rendering", every_placeholder_was_filled()),
        ("no address is sent to twice", each_address_appears_once()),
        ("every row read is sent, skipped, or failed with a reason",
         every_row_is_accounted_for()),
        ("each message carries that recipient's own values",
         the_merge_reached_the_text()),
        ("every attachment name is a bare file name",
         every_attachment_is_a_bare_name()),
        ("the subject differs between recipients when it holds a field",
         the_subject_was_personalised()),
        ("every skip and every failure says why",
         a_duplicate_became_a_reason()),
    ]


def problems(checks) -> list:
    return [name for name, okay in checks if not okay]


def cross_checks(template: Template, recipients, report: Report,
                 attachments=()) -> bool:
    """Every check, as one answer."""
    return not problems(audit(template, recipients, report, attachments))


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _wrap(text: str, width: int = 70) -> list:
    out, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        out.append(line)
    return out


def run_demo() -> int:
    template = read_template()
    recipients = read_recipients()
    attachments = read_attachments()
    names = [attachment_name(path) for path in attachments]
    unique, repeats = dedupe(recipients)

    print("=" * 74)
    print(" MAIL MERGE LAB - one message per person, and one address in To")
    print("=" * 74)

    print(f"\n  the template asks for {len(template.fields)} field(s): "
          f"{', '.join(template.fields)}")
    print(f"    subject: {template.subject}")
    for line in _wrap(template.body)[:4]:
        print(f"    {line}")

    print(f"\n  {len(recipients)} row(s) read, {len(unique)} unique address(es):")
    for recipient in recipients:
        print(f"    {str(recipient):<34} {recipient.keys()}")

    print(f"\n  the legacy line, {LEGACY_TO}")
    everyone = ", ".join(str(recipient.address) for recipient in recipients)
    print(f"    it produces one message whose To header is {len(recipients)} "
          f"addresses long:")
    for line in _wrap("To: " + everyone, 66):
        print(f"      {line}")
    print(f"    so each of the {len(recipients)} people learns the other "
          f"{len(recipients) - 1}")

    print(f"\n  {LEGACY_FILENAME}")
    for path in attachments:
        legacy = str(path).split("\\")[-1]
        print(f"    {path:<26} legacy {legacy!r}  ours {attachment_name(path)!r}")

    transport = RecordingTransport()
    report = send_campaign(template, recipients, transport, attachments=names)
    print(f"\n  a real campaign: {report.summary()}")
    for message in report.sent:
        print(f"    {message.envelope()}")
    for entry in report.skipped:
        print(f"    skipped {entry.address}: {entry.reason}")

    print(f"\n  one message, rendered for {report.sent[0].to}:")
    print(f"    subject: {report.sent[0].subject}")
    for line in _wrap(report.sent[0].body, 66):
        print(f"    {line}")
    print(f"    attachments: {', '.join(report.sent[0].attachments)}")
    print(f"    the To header holds {len(str(report.sent[0].to))} characters "
          f"and no comma: {',' not in str(report.sent[0].to)}")
    print(f"    two subjects differ: "
          f"{report.sent[0].subject != report.sent[1].subject}")

    print(f"\n  a template that one recipient cannot fill:")
    gap = unique[:1] + [Recipient(unique[1].name, unique[1].address,
                                  (("first_name", "Grace"),))]
    try:
        template.check(gap)
    except BadTemplate as error:
        print(f"    the campaign refuses to start: {error}")

    print(f"\n  a server that refuses one mailbox:")
    refusing = RefusingTransport([str(unique[2].address)])
    partial = send_campaign(template, recipients, refusing, attachments=names)
    print(f"    {partial.summary()}")
    for entry in partial.failed:
        print(f"    failed {entry.address}: {entry.reason}")
    print(f"    the other {len(partial.sent)} still arrived")

    checks = audit(template, recipients, report, names)
    print()
    for name, okay in checks:
        print(f"  {'PASS' if okay else 'FAIL'}  {name}")
    print(f"  {sum(1 for _, okay in checks if okay)}/{len(checks)} checks pass")

    print("\nCross-checks OK: " +
          f"{len(recipients)} rows name {len(unique)} unique address(es), the "
          f"legacy To header holds all {len(recipients)} and leaks each to the "
          f"other {len(recipients) - 1}, our {len(report.sent)} message(s) name "
          f"one address each, {len(report.skipped)} duplicate is skipped with a "
          f"reason, a template missing a field is refused before the first "
          f"send, a refused mailbox leaves the other {len(partial.sent)} "
          f"delivered, {len(names)} attachment name(s) lose their directory on "
          f"both separator styles, and "
          f"{sum(1 for _, okay in checks if okay)}/{len(checks)} checks hold")

    print("\nDemo completed successfully.")
    return 0
