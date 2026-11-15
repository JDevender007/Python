"""Tests for Email_Automation: one message per person, because a shared To
header is a disclosure, and a file name is not a path."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import main as cli                                            # noqa: E402
import merge as module                                        # noqa: E402
from merge import (                                           # noqa: E402
    ATTACHMENTS_FILE,
    DEFAULT_SENDER,
    LEGACY_FILENAME,
    LEGACY_SEND,
    LEGACY_TO,
    MAX_ATTACHMENT_NAME,
    RECIPIENTS_FILE,
    Address,
    BadAddress,
    BadTemplate,
    Failed,
    MailError,
    Message,
    Recipient,
    RecordingTransport,
    RefusingTransport,
    Report,
    Skipped,
    Template,
    Transport,
    TransportError,
    addresses_in,
    attachment_name,
    audit,
    cross_checks,
    dedupe,
    parse_recipient,
    placeholders,
    problems,
    read_attachments,
    read_recipients,
    read_template,
    run_demo,
    send_campaign,
)

ADDRESSES = ("ada@example.com", "grace@example.com", "alan@example.com",
             "katherine@example.com")


def a_file(folder: Path, text: str, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(text.encode("utf-8"))
    return path


def setup():
    template = read_template()
    recipients = read_recipients()
    names = tuple(attachment_name(path) for path in read_attachments())
    transport = RecordingTransport()
    report = send_campaign(template, recipients, transport, attachments=names)
    return template, recipients, names, transport, report


def who(name: str = "Ada", address: str = "ada@example.com", **fields):
    pairs = tuple(fields.items()) if fields else (("first_name", name),)
    return Recipient(name, Address.parse(address), pairs)


# --------------------------------------------------------------------------- #
# Addresses
# --------------------------------------------------------------------------- #
def test_an_address_parses_into_a_local_part_and_a_domain():
    address = Address.parse("ada@example.com")
    assert (address.local, address.domain) == ("ada", "example.com")


def test_an_address_is_printed_whole():
    assert str(Address.parse("ada@example.com")) == "ada@example.com"


def test_an_address_drops_surrounding_space():
    assert str(Address.parse("  ada@example.com  ")) == "ada@example.com"


def test_an_address_needs_exactly_one_at():
    with pytest.raises(BadAddress, match="exactly one '@'"):
        Address.parse("ada.example.com")


def test_two_ats_are_refused():
    with pytest.raises(BadAddress, match="exactly one '@'"):
        Address.parse("ada@ex@ample.com")


def test_a_comma_is_refused_because_it_is_two_addresses():
    with pytest.raises(BadAddress, match="more than one address"):
        Address.parse("ada@example.com, grace@example.com")


def test_a_semicolon_is_refused_too():
    with pytest.raises(BadAddress, match="more than one address"):
        Address.parse("ada@example.com; grace@example.com")


def test_an_empty_address_is_refused():
    with pytest.raises(BadAddress, match="cannot be empty"):
        Address.parse("   ")


def test_an_address_needs_a_name_before_the_at():
    with pytest.raises(BadAddress, match="before the '@'"):
        Address.parse("@example.com")


def test_an_address_needs_a_domain():
    with pytest.raises(BadAddress, match="after the '@'"):
        Address.parse("ada@")


def test_a_space_inside_an_address_is_refused():
    with pytest.raises(BadAddress, match="cannot hold a space"):
        Address.parse("ada lovelace@example.com")


def test_a_domain_needs_a_dot():
    with pytest.raises(BadAddress, match="a domain needs a dot"):
        Address.parse("ada@localhost")


def test_a_leading_dot_in_the_name_is_refused():
    with pytest.raises(BadAddress, match="a dot may not sit"):
        Address.parse(".ada@example.com")


def test_a_trailing_dot_in_the_name_is_refused():
    with pytest.raises(BadAddress, match="a dot may not sit"):
        Address.parse("ada.@example.com")


def test_a_double_dot_in_the_name_is_refused():
    with pytest.raises(BadAddress, match="a dot may not sit"):
        Address.parse("a..da@example.com")


def test_a_double_dot_in_the_domain_is_refused():
    with pytest.raises(BadAddress, match="a dot may not sit"):
        Address.parse("ada@example..com")


def test_an_illegal_character_is_refused():
    with pytest.raises(BadAddress, match="is not allowed in an address"):
        Address.parse("a!da@example.com")


def test_a_plus_tag_is_allowed():
    assert str(Address.parse("ada+lists@example.com")) == "ada+lists@example.com"


def test_the_key_folds_case():
    assert Address.parse("ADA@Example.com").key() == "ada@example.com"


def test_an_address_that_is_not_text_is_refused():
    with pytest.raises(BadAddress, match="must be text"):
        Address.parse(7)


# --------------------------------------------------------------------------- #
# Recipients
# --------------------------------------------------------------------------- #
def test_a_recipient_holds_its_fields_in_order():
    recipient = parse_recipient("Ada", "ada@example.com",
                                ["first_name=Ada", "product=Pro"])
    assert recipient.keys() == ("first_name", "product")


def test_a_recipient_looks_a_field_up_by_name():
    recipient = parse_recipient("Ada", "ada@example.com", ["first_name=Ada"])
    assert recipient.value("first_name") == "Ada" and recipient.value("nope") is None


def test_a_recipient_prints_its_name_and_address():
    assert str(parse_recipient("Ada", "ada@example.com", [])) == \
        "Ada <ada@example.com>"


def test_a_recipient_needs_a_name():
    with pytest.raises(MailError, match="needs a name"):
        parse_recipient("  ", "ada@example.com", [])


def test_a_field_without_an_equals_sign_is_refused():
    with pytest.raises(MailError, match="looks like name=value"):
        parse_recipient("Ada", "ada@example.com", ["first_name"])


def test_a_field_name_must_be_lowercase():
    with pytest.raises(MailError, match="is not a field name"):
        parse_recipient("Ada", "ada@example.com", ["FirstName=Ada"])


def test_a_field_with_an_empty_value_is_refused():
    with pytest.raises(MailError, match="an empty value"):
        parse_recipient("Ada", "ada@example.com", ["first_name=  "])


def test_a_field_given_twice_is_refused():
    with pytest.raises(MailError, match="gives 'first_name' twice"):
        parse_recipient("Ada", "ada@example.com",
                        ["first_name=Ada", "first_name=Grace"])


# --------------------------------------------------------------------------- #
# Placeholders
# --------------------------------------------------------------------------- #
def test_a_text_without_placeholders_asks_for_nothing():
    assert placeholders("hello") == ()


def test_one_placeholder_is_found():
    assert placeholders("hi {{name}}") == ("name",)


def test_placeholders_keep_the_order_they_appear_in():
    assert placeholders("{{a}} then {{b}} then {{a}}") == ("a", "b", "a")


def test_a_digit_inside_a_field_name_is_allowed():
    assert placeholders("{{line1}}") == ("line1",)


def test_an_unclosed_placeholder_is_refused():
    with pytest.raises(BadTemplate, match="never closes"):
        placeholders("hi {{name")


def test_a_stray_close_is_refused():
    with pytest.raises(BadTemplate, match="ends nothing"):
        placeholders("hi name}}")


def test_a_field_name_with_a_space_is_refused():
    with pytest.raises(BadTemplate, match="is not a field name"):
        placeholders("{{first name}}")


def test_a_field_name_starting_with_a_digit_is_refused():
    with pytest.raises(BadTemplate, match="is not a field name"):
        placeholders("{{1name}}")


def test_placeholders_need_text():
    with pytest.raises(BadTemplate, match="must be text"):
        placeholders(None)


# --------------------------------------------------------------------------- #
# The template
# --------------------------------------------------------------------------- #
def test_the_bundled_template_asks_for_three_fields():
    assert read_template().fields == ("first_name", "product", "discount")


def test_template_fields_are_deduplicated_in_order():
    assert Template("{{a}}", "{{b}} {{a}}").fields == ("a", "b")


def test_check_accepts_the_bundled_recipients():
    read_template().check(read_recipients())


def test_check_refuses_a_campaign_with_no_recipients():
    with pytest.raises(BadTemplate, match="at least one recipient"):
        Template("{{a}}", "body").check([])


def test_check_refuses_a_template_that_asks_for_nothing():
    with pytest.raises(BadTemplate, match="asks for nothing"):
        Template("hello", "body").check([who()])


def test_check_names_a_field_no_recipient_supplies():
    with pytest.raises(BadTemplate, match="no recipient supplies 'product'"):
        Template("{{product}}", "body").check([who()])


def test_check_names_the_recipient_missing_a_field():
    template = Template("{{a}} {{b}}", "body")
    with pytest.raises(BadTemplate, match="grace@example.com has no value for "
                                         "'b'"):
        template.check([who(a="x", b="y"), who("Grace", "grace@example.com",
                                               a="x")])


def test_a_template_with_a_bad_placeholder_fails_when_it_is_read(tmp_path):
    path = a_file(tmp_path, "subject: {{ok\n--\nbody\n", "template.txt")
    with pytest.raises(BadTemplate, match="never closes"):
        read_template(path)


def test_render_text_fills_one_placeholder():
    assert Template("{{a}}", "b").render_text("hi {{a}}", who(a="Ada")) == \
        "hi Ada"


def test_render_text_fills_every_occurrence():
    assert Template("{{a}}", "b").render_text("{{a}} and {{a}}", who(a="Ada")) \
        == "Ada and Ada"


def test_render_text_refuses_a_missing_value():
    with pytest.raises(BadTemplate, match="has no value for 'b'"):
        Template("{{a}}", "b").render_text("{{b}}", who(a="Ada"))


def test_render_builds_one_message():
    message = Template("{{a}}", "{{a}}").render(who(a="Ada"))
    assert message.subject == "Ada" and message.body == "Ada"


def test_render_uses_the_default_sender():
    assert str(Template("{{a}}", "b").render(who(a="x")).sender) == \
        DEFAULT_SENDER


def test_render_takes_a_sender_and_attachments():
    message = Template("{{a}}", "b").render(who(a="x"), "hi@example.com",
                                            ["q3.pdf"])
    assert str(message.sender) == "hi@example.com"
    assert message.attachments == ("q3.pdf",)


def test_render_refuses_a_value_that_carries_braces():
    template = Template("{{a}}", "body")
    with pytest.raises(BadTemplate, match="survived rendering"):
        template.render(who(a="{{oops}}"))


def test_a_message_envelope_names_both_ends():
    message = Template("{{a}}", "b").render(who(a="Ada"))
    assert message.envelope() == ("team@example.com -> ada@example.com  |  Ada")


def test_a_message_text_holds_its_own_address():
    message = Template("{{a}}", "b").render(who(a="Ada"))
    assert "ada@example.com" in message.text()


def test_addresses_in_finds_only_known_addresses():
    found = addresses_in("write to Grace@Example.com", ADDRESSES)
    assert found == {"grace@example.com"}


def test_addresses_in_finds_nothing_in_plain_text():
    assert addresses_in("no addresses here", ADDRESSES) == set()


# --------------------------------------------------------------------------- #
# Attachments
# --------------------------------------------------------------------------- #
def test_a_forward_slash_path_gives_the_file_name():
    assert attachment_name("reports/q3.pdf") == "q3.pdf"


def test_a_backslash_path_gives_the_file_name():
    assert attachment_name("C:\\Mail\\brand\\logo.png") == "logo.png"


def test_a_bare_name_is_returned_whole():
    assert attachment_name("logo.png") == "logo.png"


def test_the_legacy_split_keeps_a_forward_slash_path_whole():
    """The defect, executable: split on the backslash only."""
    assert "reports/q3.pdf".split("\\")[-1] == "reports/q3.pdf"


def test_a_path_ending_in_a_separator_names_no_file():
    with pytest.raises(MailError, match="does not name a file"):
        attachment_name("reports/")


def test_a_dot_path_names_no_file():
    with pytest.raises(MailError, match="does not name a file"):
        attachment_name("..")


def test_an_empty_path_is_refused():
    with pytest.raises(MailError, match="needs a path"):
        attachment_name("")


def test_a_forbidden_character_is_refused():
    with pytest.raises(MailError, match="cannot hold"):
        attachment_name("dir/a:b.pdf")


def test_a_control_character_is_refused():
    with pytest.raises(MailError, match="control character"):
        attachment_name("a\tb.pdf")


def test_a_name_longer_than_the_limit_is_refused():
    with pytest.raises(MailError, match=f"at most {MAX_ATTACHMENT_NAME}"):
        attachment_name("x" * (MAX_ATTACHMENT_NAME + 1))


# --------------------------------------------------------------------------- #
# Transports
# --------------------------------------------------------------------------- #
def test_a_recording_transport_keeps_the_messages():
    transport = RecordingTransport()
    transport.send(Template("{{a}}", "b").render(who(a="Ada")))
    assert transport.addresses() == ("ada@example.com",) and len(transport) == 1


def test_a_recording_transport_refuses_something_that_is_not_a_message():
    with pytest.raises(TransportError, match="sends a Message"):
        RecordingTransport().send("ada@example.com")


def test_a_recording_transport_refuses_a_message_with_a_text_address():
    fake = Message(sender=Address.parse(DEFAULT_SENDER),
                   to="ada@example.com, grace@example.com",
                   subject="x", body="y")
    with pytest.raises(TransportError, match="one address object"):
        RecordingTransport().send(fake)


def test_a_refusing_transport_refuses_the_named_address():
    transport = RefusingTransport(["alan@example.com"])
    with pytest.raises(TransportError, match="the server refused"):
        transport.send(Template("{{a}}", "b").render(who("Alan",
                                                         "alan@example.com",
                                                         a="Alan")))
    assert len(transport) == 0


def test_a_refusing_transport_compares_case_insensitively():
    transport = RefusingTransport(["ALAN@example.com"])
    with pytest.raises(TransportError, match="mailbox unavailable"):
        transport.send(Template("{{a}}", "b").render(who("Alan",
                                                         "alan@example.com",
                                                         a="Alan")))


def test_a_refusing_transport_delivers_everything_else():
    transport = RefusingTransport(["alan@example.com"])
    transport.send(Template("{{a}}", "b").render(who(a="Ada")))
    assert transport.addresses() == ("ada@example.com",)


def test_the_base_transport_does_not_deliver():
    with pytest.raises(NotImplementedError):
        Transport().send(None)


# --------------------------------------------------------------------------- #
# The campaign
# --------------------------------------------------------------------------- #
def test_the_bundled_campaign_sends_four_messages():
    template, recipients, names, transport, report = setup()
    assert len(report.sent) == 4 and len(transport) == 4


def test_the_bundled_campaign_skips_one_row():
    *_, report = setup()
    assert [entry.address for entry in report.skipped] == ["ADA@example.com"]


def test_the_bundled_campaign_fails_nothing():
    *_, report = setup()
    assert report.failed == () and report.adds_up()


def test_the_report_counts_every_row():
    *_, report = setup()
    assert report.counts() == (5, 4, 1, 0)


def test_the_report_summary_is_pinned():
    *_, report = setup()
    assert report.summary() == "4 sent, 1 skipped, 0 failed, 5 row(s) read"


def test_every_message_names_one_of_the_distinct_addresses():
    *_, report = setup()
    assert [str(message.to) for message in report.sent] == list(ADDRESSES)


def test_every_message_carries_its_own_name():
    *_, report = setup()
    assert [message.subject.split(",")[0] for message in report.sent] == \
        ["Ada", "Grace", "Alan", "Katherine"]


def test_no_message_mentions_another_recipient():
    *_, report = setup()
    for message in report.sent:
        others = [address for address in ADDRESSES
                  if address != str(message.to)]
        assert addresses_in(message.text(), others) == set()


def test_a_duplicate_address_is_skipped_with_a_reason():
    *_, report = setup()
    assert "second entry for the same address" in report.skipped[0].reason


def dedupe_names(recipients):
    unique, dropped = dedupe(recipients)
    return [str(entry.address) for entry in unique], \
        [entry.reason for entry in dropped]


def test_dedupe_keeps_the_first_entry():
    recipients = [who("Ada", "ada@example.com", a="one"),
                  who("Ada Again", "ADA@example.com", a="two")]
    unique, reasons = dedupe_names(recipients)
    assert unique == ["ada@example.com"] and len(reasons) == 1


def test_dedupe_keeps_addresses_that_differ():
    unique, reasons = dedupe_names([who(), who("Grace", "grace@example.com")])
    assert unique == ["ada@example.com", "grace@example.com"] and reasons == []


def test_a_campaign_refuses_to_start_when_a_recipient_cannot_be_filled():
    template = Template("{{a}} {{missing}}", "body")
    transport = RecordingTransport()
    with pytest.raises(BadTemplate, match="no recipient supplies 'missing'"):
        send_campaign(template, [who(a="x")], transport)
    assert len(transport) == 0


def test_a_refused_mailbox_leaves_the_others_delivered():
    template, recipients, names, _, _ = setup()
    report = send_campaign(template, recipients,
                           RefusingTransport(["alan@example.com"]),
                           attachments=names)
    assert len(report.sent) == 3 and len(report.failed) == 1
    assert report.failed[0].address == "alan@example.com"
    assert report.adds_up()


def test_a_failure_records_the_transport_reason():
    template, recipients, names, _, _ = setup()
    report = send_campaign(template, recipients, RefusingTransport(ADDRESSES),
                           attachments=names)
    assert all("mailbox unavailable" in entry.reason
               for entry in report.failed)


def test_every_message_carries_the_attachments():
    *_, report = setup()
    assert all(message.attachments == ("q3-summary.pdf", "logo.png")
               for message in report.sent)


def test_a_report_that_loses_a_row_does_not_add_up():
    *_, report = setup()
    assert not replace(report, rows=6).adds_up()


def test_the_report_lists_its_reasons():
    *_, report = setup()
    assert report.reasons() == (report.skipped[0].reason,)


# --------------------------------------------------------------------------- #
# The data files
# --------------------------------------------------------------------------- #
def test_the_bundled_template_is_pinned():
    template = read_template()
    assert template.subject == \
        "{{first_name}}, your {{product}} trial ends Friday"
    assert "{{discount}}%" in template.body


def test_the_bundled_recipients_hold_five_rows():
    assert len(read_recipients()) == 5


def test_the_bundled_recipients_hold_four_distinct_addresses():
    assert len({recipient.address.key() for recipient in read_recipients()}) == 4


def test_every_bundled_recipient_carries_the_three_fields():
    assert all(recipient.keys() == ("first_name", "product", "discount")
               for recipient in read_recipients())


def test_the_bundled_attachments_use_both_separators():
    paths = read_attachments()
    assert paths == ("reports/q3-summary.pdf", "C:\\Mail\\brand\\logo.png")


def test_read_template_refuses_a_missing_file(tmp_path):
    with pytest.raises(MailError, match="file not found"):
        read_template(tmp_path / "nope.txt")


def test_read_template_needs_a_subject(tmp_path):
    with pytest.raises(BadTemplate, match="no subject line"):
        read_template(a_file(tmp_path, "--\nbody\n", "template.txt"))


def test_read_template_needs_the_rule_line(tmp_path):
    with pytest.raises(BadTemplate, match="no '--' line"):
        read_template(a_file(tmp_path, "subject: hi\n", "template.txt"))


def test_read_template_refuses_a_line_it_cannot_place(tmp_path):
    with pytest.raises(BadTemplate, match="expected 'subject: ...'"):
        read_template(a_file(tmp_path, "subject: hi\nbody\n", "template.txt"))


def test_read_template_refuses_an_empty_body(tmp_path):
    with pytest.raises(BadTemplate, match="the body is empty"):
        read_template(a_file(tmp_path, "subject: hi\n--\n\n", "template.txt"))


def test_read_template_refuses_an_empty_subject(tmp_path):
    with pytest.raises(BadTemplate, match="the subject is empty"):
        read_template(a_file(tmp_path, "subject:\n--\nbody\n", "template.txt"))


def test_read_template_refuses_a_line_before_the_subject(tmp_path):
    with pytest.raises(BadTemplate, match="expected 'subject: ...'"):
        read_template(a_file(tmp_path, "hello\n--\nbody\n", "template.txt"))


def test_read_template_skips_comments(tmp_path):
    path = a_file(tmp_path, "; a note\nsubject: hi\n--\nbody\n", "template.txt")
    assert read_template(path).subject == "hi"


def test_read_recipients_refuses_a_missing_file(tmp_path):
    with pytest.raises(MailError, match="file not found"):
        read_recipients(tmp_path / "nope.txt")


def test_read_recipients_names_a_line_without_a_tab(tmp_path):
    with pytest.raises(MailError, match="recipients.txt:1: expected a name"):
        read_recipients(a_file(tmp_path, "ada@example.com\n", "recipients.txt"))


def test_read_recipients_names_a_bad_address_line(tmp_path):
    with pytest.raises(MailError, match="recipients.txt:1: .*exactly one '@'"):
        read_recipients(a_file(tmp_path, "Ada\tada.example.com\n",
                               "recipients.txt"))


def test_read_recipients_refuses_a_file_with_no_rows(tmp_path):
    with pytest.raises(MailError, match="no recipients"):
        read_recipients(a_file(tmp_path, "; nothing\n", "recipients.txt"))


def test_read_attachments_reads_one_path_per_line(tmp_path):
    path = a_file(tmp_path, "a/q3.pdf\nb\\logo.png\n", "attachments.txt")
    assert read_attachments(path) == ("a/q3.pdf", "b\\logo.png")


def test_the_bundled_files_are_pinned_on_disk():
    assert RECIPIENTS_FILE.read_text(encoding="utf-8").count("\t") == 20
    assert ATTACHMENTS_FILE.read_text(encoding="utf-8").count("\n") == 3


# --------------------------------------------------------------------------- #
# The legacy lines
# --------------------------------------------------------------------------- #
def test_the_legacy_lines_are_pinned():
    assert LEGACY_TO == 'message["To"] = ", ".join(recipients)'
    assert LEGACY_FILENAME == 'filename=file.split("\\\\")[-1]'
    assert LEGACY_SEND == "self.server.send_message(message)"


def test_the_legacy_join_puts_five_addresses_in_one_header():
    everyone = ", ".join(str(recipient.address) for recipient in
                         read_recipients())
    assert everyone.count("@") == 5 and everyone.count(",") == 4


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
CHECK_NAMES = [
    "every message names exactly one recipient",
    "no message names anybody but its own recipient",
    "no placeholder survived rendering",
    "no address is sent to twice",
    "every row read is sent, skipped, or failed with a reason",
    "each message carries that recipient's own values",
    "every attachment name is a bare file name",
    "the subject differs between recipients when it holds a field",
    "every skip and every failure says why",
]


def test_the_audit_holds_nine_named_checks():
    template, recipients, names, _, report = setup()
    assert [name for name, _ in audit(template, recipients, report, names)] == \
        CHECK_NAMES


def test_the_audit_passes_on_the_bundled_campaign():
    template, recipients, names, _, report = setup()
    assert problems(audit(template, recipients, report, names)) == []


def test_cross_checks_answers_one_boolean():
    template, recipients, names, _, report = setup()
    assert cross_checks(template, recipients, report, names) is True


def test_the_audit_is_repeatable():
    template, recipients, names, _, report = setup()
    assert audit(template, recipients, report, names) == \
        audit(template, recipients, report, names)


def test_the_audit_catches_a_message_with_a_text_address():
    template, recipients, names, _, report = setup()
    broken = replace(report, sent=(Message(Address.parse(DEFAULT_SENDER),
                                           "ada@example.com, grace@example.com",
                                           "x", "y"),))
    assert CHECK_NAMES[0] in problems(audit(template, recipients, broken, names))


def test_the_audit_catches_a_leaked_address():
    template, recipients, names, _, report = setup()
    leaky = replace(report.sent[0],
                    body=report.sent[0].body + " (cc grace@example.com)")
    broken = replace(report, sent=(leaky,) + report.sent[1:])
    assert CHECK_NAMES[1] in problems(audit(template, recipients, broken, names))


def test_the_audit_catches_a_placeholder_left_in_the_text():
    template, recipients, names, _, report = setup()
    broken = replace(report.sent[0], body="hello {{first_name}}")
    broken = replace(report, sent=(broken,) + report.sent[1:])
    assert CHECK_NAMES[2] in problems(audit(template, recipients, broken, names))


def test_the_audit_catches_a_message_sent_twice():
    template, recipients, names, _, report = setup()
    broken = replace(report, sent=report.sent + report.sent[:1])
    assert CHECK_NAMES[3] in problems(audit(template, recipients, broken, names))


def test_the_audit_catches_a_row_that_vanished():
    template, recipients, names, _, report = setup()
    broken = replace(report, sent=report.sent[:2], skipped=report.skipped)
    assert CHECK_NAMES[4] in problems(audit(template, recipients, broken, names))


def test_the_audit_catches_a_message_without_the_recipient_s_value():
    template, recipients, names, _, report = setup()
    broken = replace(report.sent[0], subject="your trial", body="hello")
    broken = replace(report, sent=(broken,) + report.sent[1:])
    assert CHECK_NAMES[5] in problems(audit(template, recipients, broken, names))


def test_the_audit_catches_an_attachment_that_is_a_path():
    template, recipients, names, _, report = setup()
    assert CHECK_NAMES[6] in problems(
        audit(template, recipients, report, ("reports/q3.pdf",)))


def test_the_audit_catches_a_subject_that_was_never_personalised():
    template, recipients, names, _, report = setup()
    same = tuple(replace(message, subject="your trial ends Friday")
                 for message in report.sent)
    broken = replace(report, sent=same)
    assert CHECK_NAMES[7] in problems(audit(template, recipients, broken, names))


def test_the_audit_catches_a_skip_without_a_reason():
    template, recipients, names, _, report = setup()
    broken = replace(report, skipped=(Skipped("ada@example.com", ""),))
    assert CHECK_NAMES[8] in problems(audit(template, recipients, broken, names))


def test_the_audit_accepts_a_plain_subject():
    template = Template("Monthly note", "hi {{a}}")
    recipients = [who(a="Ada")]
    report = send_campaign(template, recipients, RecordingTransport())
    assert CHECK_NAMES[7] not in problems(audit(template, recipients, report))


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out and "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_demo_prints_no_non_ascii(capsys):
    run_demo()
    assert all(ord(character) < 128 for character in capsys.readouterr().out)


def test_demo_shows_the_leaking_header(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "it produces one message whose To header is 5" in out
    assert "so each of the 5 people learns the other 4" in out


def test_demo_shows_both_separator_styles(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "legacy 'reports/q3-summary.pdf'  ours 'q3-summary.pdf'" in out
    assert "legacy 'logo.png'  ours 'logo.png'" in out


def test_demo_shows_the_campaign_and_the_partial_failure(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "4 sent, 1 skipped, 0 failed, 5 row(s) read" in out
    assert "3 sent, 1 skipped, 1 failed, 5 row(s) read" in out
    assert "the other 3 still arrived" in out


def test_demo_shows_all_nine_checks(capsys):
    run_demo()
    assert "9/9 checks pass" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_lists_the_sent_messages(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "  5 row(s): 4 unique address(es), 1 skipped" in out
    assert "team@example.com -> ada@example.com" in out
    assert "  4 sent, 1 skipped, 0 failed, 5 row(s) read" in out


def test_cli_preview_prints_one_message_per_person(capsys):
    assert cli.main(["--preview"]) == 0
    out = capsys.readouterr().out
    assert out.count("  To: ") == 4
    assert "  Subject: Grace, your Analytics Pro trial ends Friday" in out
    assert "  Attachments: q3-summary.pdf, logo.png" in out


def test_cli_audit_prints_every_verdict(capsys):
    assert cli.main(["--audit"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 9 and "FAIL" not in out


def test_cli_refuse_exits_one(capsys):
    assert cli.main(["--refuse", "alan@example.com"]) == 1
    out = capsys.readouterr().out
    assert "failed  alan@example.com" in out


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_json_writes_the_campaign(tmp_path, capsys):
    target = tmp_path / "campaign.json"
    assert cli.main(["--json", str(target), "--quiet"]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["rows"] == 5 and payload["adds_up"] is True
    assert payload["unique"] == list(ADDRESSES)
    assert payload["sent"][0]["subject"] == \
        "Ada, your Analytics Pro trial ends Friday"
    assert payload["skipped"][0]["address"] == "ADA@example.com"


def test_cli_reads_another_template_and_list(tmp_path, capsys):
    template = a_file(tmp_path, "subject: hi {{who}}\n--\nhello {{who}}\n",
                      "template.txt")
    recipients = a_file(tmp_path, "Ada\tada@example.com\twho=Ada\n",
                        "recipients.txt")
    assert cli.main(["--template", str(template),
                     "--recipients", str(recipients)]) == 0
    out = capsys.readouterr().out
    assert "  1 row(s): 1 unique address(es), 0 skipped" in out
    assert "team@example.com -> ada@example.com  |  hi Ada" in out


def test_cli_a_missing_template_exits_two(tmp_path, capsys):
    assert cli.main(["--template", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_a_template_a_recipient_cannot_fill_exits_two(tmp_path, capsys):
    template = a_file(tmp_path, "subject: hi {{a}} {{b}}\n--\nbody\n",
                      "template.txt")
    recipients = a_file(tmp_path, "Ada\tada@example.com\ta=1\n",
                        "recipients.txt")
    assert cli.main(["--template", str(template),
                     "--recipients", str(recipients)]) == 2
    assert "no recipient supplies 'b'" in capsys.readouterr().err


def test_cli_one_recipient_missing_a_field_exits_two(tmp_path, capsys):
    """The field exists for somebody, so the union check passes and the
    per-recipient check is what refuses the campaign."""
    template = a_file(tmp_path, "subject: hi {{a}} {{b}}\n--\nbody\n",
                      "template.txt")
    recipients = a_file(tmp_path,
                        "Ada\tada@example.com\ta=1\tb=2\n"
                        "Grace\tgrace@example.com\ta=3\n",
                        "recipients.txt")
    assert cli.main(["--template", str(template),
                     "--recipients", str(recipients)]) == 2
    assert "grace@example.com has no value for 'b'" in capsys.readouterr().err
