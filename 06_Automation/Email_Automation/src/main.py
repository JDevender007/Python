"""Command line front end for the mail merge lab."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from merge import (                                          # noqa: E402
    BadTemplate,
    MailError,
    RecordingTransport,
    RefusingTransport,
    audit,
    attachment_name,
    dedupe,
    problems,
    read_attachments,
    read_recipients,
    read_template,
    run_demo,
    send_campaign,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mail-merge",
        description="Render one message per recipient from a template and a "
                    "recipient list, then account for every row -- offline, "
                    "with no SMTP connection.")
    parser.add_argument("--template", default=None,
                        help="a template file (default: the bundled one)")
    parser.add_argument("--recipients", default=None,
                        help="a recipient file (default: the bundled one)")
    parser.add_argument("--attachments", default=None,
                        help="a file of attachment paths")
    parser.add_argument("--preview", action="store_true",
                        help="print every rendered message")
    parser.add_argument("--refuse", action="append", default=[], metavar="ADDR",
                        help="make the transport refuse this address "
                             "(repeatable)")
    parser.add_argument("--audit", action="store_true",
                        help="print every check with its verdict")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="write the campaign to PATH as JSON")
    parser.add_argument("--quiet", action="store_true", help="print nothing")
    parser.add_argument("--demo", action="store_true",
                        help="run the offline demonstration")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        if args.quiet:
            with contextlib.redirect_stdout(io.StringIO()):
                return run_demo()
        return run_demo()

    try:
        template = read_template(args.template) if args.template \
            else read_template()
        recipients = read_recipients(args.recipients) if args.recipients \
            else read_recipients()
        raw = read_attachments(args.attachments) if args.attachments \
            else read_attachments()
        names = tuple(attachment_name(path) for path in raw)
    except MailError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    unique, skipped = dedupe(recipients)
    try:
        template.check(unique)
    except BadTemplate as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        transport = RefusingTransport(args.refuse) if args.refuse \
            else RecordingTransport()
    except MailError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    report = send_campaign(template, recipients, transport, attachments=names)

    if not args.quiet:
        print(f"  {len(recipients)} row(s): {len(unique)} unique address(es), "
              f"{len(skipped)} skipped")
        print(f"  the template asks for: {', '.join(template.fields)}")
        for message in report.sent:
            print(f"    {message.envelope()}")
        for entry in report.skipped:
            print(f"    skipped {entry.address}: {entry.reason}")
        for entry in report.failed:
            print(f"    failed  {entry.address}: {entry.reason}")
        print(f"  {report.summary()}")

    if args.preview:
        for message in report.sent:
            print()
            print(f"  --- {message.to} ---")
            print(f"  To: {message.to}")
            print(f"  Subject: {message.subject}")
            for line in message.body.splitlines():
                print(f"  {line}")
            if message.attachments:
                print(f"  Attachments: {', '.join(message.attachments)}")

    failed_checks = []
    if args.audit:
        print()
        checks = audit(template, recipients, report, names)
        for name, okay in checks:
            print(f"  {'PASS' if okay else 'FAIL'}  {name}")
        failed_checks = problems(checks)

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fields": list(template.fields),
            "template": {"subject": template.subject, "body": template.body},
            "rows": len(recipients),
            "unique": [str(recipient.address) for recipient in unique],
            "sent": [{"to": str(message.to), "subject": message.subject,
                      "attachments": list(message.attachments)}
                     for message in report.sent],
            "skipped": [{"address": entry.address, "reason": entry.reason}
                        for entry in report.skipped],
            "failed": [{"address": entry.address, "reason": entry.reason}
                       for entry in report.failed],
            "adds_up": report.adds_up(),
        }
        target.write_text(json.dumps(payload, indent=2) + "\n",
                          encoding="utf-8")
        if not args.quiet:
            print(f"  wrote {len(report.sent)} message(s) to {target}")

    if failed_checks:
        print(f"  {len(failed_checks)} check(s) failed", file=sys.stderr)
        return 1
    if report.failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
