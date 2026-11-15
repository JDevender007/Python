<div align="center">

# 📧 Email Automation

### The legacy sender built **one** message and put every address in its `To` header — `message["To"] = ", ".join(recipients)` — so each of the five people learns the other four, and the body cannot say anybody's name. It also took an attachment's file name with `file.split("\\")[-1]`, which returns the *whole path* the moment the path uses a forward slash.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

```python
message = EmailMessage()
message["From"] = sender
message["To"] = ", ".join(recipients)
message["Subject"] = subject
message.set_content(body)

if attachments:
    for file in attachments:
        with open(file, "rb") as attachment:
            data = attachment.read()
        message.add_attachment(data, maintype="application",
                               subtype="octet-stream",
                               filename=file.split("\\")[-1])

self.server.send_message(message)
```

Three defects, none of them visible on the tutorial's one-recipient run.

**1 → One message for many people is a disclosure, not a merge.** Every recipient
receives a header naming every other recipient. On a good day that is a privacy
leak; on a bad day it is a reply-all list. And it makes personalisation impossible,
because there is exactly one body: it cannot say *Ada* to Ada and *Grace* to Grace.
Here a message carries an `Address` — a frozen pair of local part and domain — so a
comma cannot get inside it. **The type makes the defect unrepresentable**, which is
worth more than a comment asking people not to do it.

**2 → `split("\\")[-1]` is a Windows rule wearing a general-purpose coat.** On a
path written with forward slashes it finds nothing to split and hands back the whole
path, so `reports/q3.pdf` becomes an attachment whose file name is
`reports/q3.pdf` — a directory as far as a mail client is concerned. The rebuild
splits on both separators, then refuses the result unless a bare file name survives.

**3 → `send_email` returns `None`, so nobody knows what happened.** One call for N
people means the caller cannot tell how many arrived; a failure in the middle raises
out of a loop that has already delivered the earlier messages, and the exception does
not say which ones. The rebuild returns a `Report` that accounts for every row it was
given: **sent**, **skipped** (a duplicate address, with the reason) or **failed**
(the transport's reason).

```text
read_recipients()   name<TAB>address<TAB>field=value ...
read_template()     subject: ...  /  --  /  body with {{placeholders}}
send_campaign()     dedupe -> check the template against *everyone* -> render -> send
                    every row ends up sent, skipped, or failed with a reason
```

The template is checked **before** the first message goes out. A merge that renders
for the first three people and raises on the fourth has already sent three messages
by the time it fails, so a missing field is a refusal, not a traceback.

The transport is an interface, not SMTP: `RecordingTransport` records envelopes and
`RefusingTransport` fails chosen mailboxes on purpose. Neither opens a socket, so the
demonstration is deterministic and offline.

| | legacy | here |
|---|---|---|
| five rows, four distinct addresses | five names in one `To` | four messages, one address each |
| what each recipient sees | everybody's address | nobody's but their own |
| `{{first_name}}` | one body for all | each message says its own name |
| `reports/q3.pdf` | file name `reports/q3.pdf` | file name `q3.pdf` |
| a duplicate address | sent twice | skipped, with the reason |
| one mailbox down | one exception, no record | `3 sent, 1 skipped, 1 failed` |
| a field nobody supplies | crash on the fourth recipient | refused before the first send |

Standard library only: no `smtplib`, no `tkinter`, no network.

---

# ✨ Features

- `Address` — one mailbox as a frozen `(local, domain)` pair; refuses a comma, a
  semicolon, a space, two `@`s, a dot at either end, a domain with no dot, and
  characters no mail server would accept
- `Recipient` — a name, one address, and the values that person's mail may use
- `placeholders` — a hand-written scan that reports an unclosed `{{` at the character
  where it opened, instead of a regex quietly matching nothing
- `Template` — `fields`, `check` (against **every** recipient), `render_text`,
  `render`
- `Message` — one sender, **one** `Address`, one subject, one body, attachments
- `attachment_name` — both separators, then a refusal if what is left is not a bare
  file name
- `RecordingTransport` / `RefusingTransport` — record the envelope, or fail one
  mailbox; neither touches a network
- `dedupe` — first entry wins, the repeat becomes a `Skipped` with a reason
- `send_campaign` — dedupe, check, render, send, account
- `Report` — `counts()`, `adds_up()`, `summary()`, `reasons()`
- `audit` — nine named checks, each with a negative control in the suite
- CLI: `--template`, `--recipients`, `--attachments`, `--preview`, `--refuse`,
  `--audit`, `--json`, `--quiet`, `--demo`
- 144 passing pytest tests

---

# 📂 Folder Structure

```text
Email_Automation/
│
├── src/
│   ├── main.py    # CLI: the campaign, the preview, the audit, json
│   └── merge.py   # addresses, templates, transports, the campaign, the demo
│
├── tests/
│   └── test_merge.py
│
├── data/
│   ├── template.txt     # subject, a '--' line, then the body
│   ├── recipients.txt   # 5 rows, 4 distinct addresses
│   └── attachments.txt  # 2 paths, one of each separator style
│
├── README.md
├── requirements.txt
└── .gitignore
```

---

# 🛠️ Installation

```bash
git clone https://github.com/JDevender007/Python.git

cd 06_Automation/Email_Automation

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

---

# ▶️ Run

```bash
# Offline demo: the leaking header, the campaign, the partial failure
python src/main.py --demo

# The campaign report
python src/main.py

# Every rendered message, one per person
python src/main.py --preview

# A mailbox the server refuses
python src/main.py --refuse alan@example.com

# Every check, and the JSON
python src/main.py --audit
python src/main.py --json campaign.json

# A template and a list of your own
python src/main.py --template .\my_template.txt --recipients .\my_list.txt
```

**Exit codes:** `0` = the command ran · `1` = an audit check failed, or at least one
mailbox refused · `2` = a missing or malformed template or list, or a field some
recipient cannot fill.

---

# ⚙️ How It Works

```text
Address.parse("ada@example.com")
  ├── exactly one '@', a name before it, a domain after it with a dot
  ├── no comma, no semicolon -- those are more than one address
  └── no space, no dot at either end, no dot twice in a row

Template.check(recipients)
  ├── every field must be supplied by somebody, or the template is unusable
  └── every field must be supplied by *everybody*, or it refuses by name

send_campaign(template, rows, transport)
  ├── dedupe on the folded address; the repeat becomes a reason
  ├── check the template against the unique recipients
  ├── render and send one message at a time
  ├── a TransportError becomes a Failed entry, not an exception
  └── Report(rows=..., sent=..., skipped=..., failed=...)
```

Details worth knowing:

- **A message cannot name two people.** `Message.to` is an `Address`, not a string,
  so `", ".join(...)` has nowhere to go. `RecordingTransport.send` re-checks the
  boundary, so a hand-built object still cannot slip through.
- **The leak check looks for the *other* addresses**, not for a comma: a body that
  says "cc grace@example.com" is caught even though its `To` header is clean.
- **A duplicate is not an error.** It is a row that was read and deliberately not
  sent, and it carries a reason, so `sent + skipped + failed == rows read` always
  holds.
- **A refused mailbox does not stop the campaign.** The other messages still go out,
  and the report says which one did not.
- **The demo writes nothing.** No socket, no file, no clock: two runs print the same
  bytes.

---

# 🧪 Technologies

- Python 3 standard library: `dataclasses`, `pathlib`, `json`, `argparse`,
  `contextlib`, `re`
- pytest 9.1.1

No `smtplib`, no `tkinter`, no network.

---

# 📚 Concepts Covered

- Why one message for many recipients is a disclosure, not a convenience
- Making a defect unrepresentable with a type instead of a comment
- Windows-only path assumptions, and a separator-agnostic file name
- Mail merge as render-then-send, one message per person
- Validating a template against *every* recipient before the first send
- Accounting for every input row: sent, skipped, failed, and the reasons
- Partial failure: three delivered, one refused, all four reported
- Case-insensitive de-duplication of addresses
- Transports as interfaces, so mail logic can be tested offline
- Audits whose negative controls plant the defect where the check looks

---

# ✅ Testing

```bash
python -m pytest tests/ -q
```

**144 tests passed** covering every address rule (and nine refusals), recipients and
their fields, the placeholder scanner and its four malformed shapes, the template's
union check and its per-recipient check, rendering including a value that carries
braces, both attachment separators and six name refusals, the structural guard in
`RecordingTransport`, `RefusingTransport` including a case-insensitive refusal, the
bundled campaign's pinned counts and subjects, de-duplication, the partial-failure
report, both data readers with their line numbers, the three legacy constants, all
nine audit checks with a negative control each, the demo, and every CLI mode
including five exit-code-2 paths.

---

# 🎯 Learning Outcomes

- Explain why a shared `To` header is a privacy defect, not a style choice
- Put an invariant in a type so a bad value cannot be constructed
- Derive a file name from a path without assuming a separator
- Render one message per recipient, and prove each one carries its own values
- Validate a whole batch before doing any of it
- Report a partial failure so the caller knows exactly what happened
- Test mail logic with no server, no network and no clock

---

# 🚀 Future Improvements

- An `smtplib` transport behind the same interface, with a `--send` flag that asks
  for confirmation and reads credentials from the environment
- A plain-text and an HTML part, with the same placeholders rendered into both
- Bounce handling: a refused mailbox queued for a retry instead of a one-line failure
- Rate limiting between messages, so a real server does not throttle the campaign

---

# 👨‍💻 Author

**Devender J**

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found this project useful, consider giving this repository a star.

</div>
