<div align="center">

# ⚙️ Automation

### Five projects that each looked like "write a loop and call a library" — and each one turned out to be a question about *what a result is*. Is `4` a count of the renames you asked for or of the renames that happened? Can one message have five `To` addresses and still be personal? Is a mean without its denominator a number? Is `len(a) == len(b)` a backup? Is `False` an explanation? The rebuild keeps each defect executable, then removes the reason it was possible.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Offline](https://img.shields.io/badge/Network-None-lightgrey?style=for-the-badge)
![Projects](https://img.shields.io/badge/Projects-5-success?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

</div>

---

# 📖 About

Each of these five projects began as a `tkinter` tool that called one library function and returned a number. They all run on the bundled data exactly as the original does, and every one of them reports something that is wrong the moment the input is not the tutorial's input — and the failure is never a typo. It is a definition: of what was being counted, of what was being reported, of what was being kept.

**The lesson of each project is different, on purpose.** Five variations on "validate the input" would teach nothing; five different ways an automation reports the wrong thing teach the subject.

- **Bulk_File_Renamer** — *a rename is a plan, and a plan is a value.* `for old, new in zip(files, names)` renames four of six files and returns `4`: `zip` truncates in silence. `with_name(new + old.suffix)` turns `report.pdf` into `report.pdf.pdf`, and a case-only rename targets a name that already "exists" on Windows and macOS. `history.clear()` throws away the previous undo *before* this batch starts, so a failure leaves the folder half-renamed with no record of the half that worked. The rebuild computes the whole plan first — every file covered, every name checked against the rules Windows actually enforces, a name that would land on a staying file numbered instead of used, no two entries ending up with the same name — then re-checks it against the folder as it is *now*, applies it with one reversible record per rename, and undoes a chain `notes.txt → a.txt → b.txt` newest-first in one pass.
- **Email_Automation** — *one message to many people is a disclosure, not a merge.* `message["To"] = ", ".join(recipients)` gives each of five people the other four addresses, and one body cannot say *Ada* to Ada and *Grace* to Grace. `file.split("\\")[-1]` is a Windows rule in a general-purpose coat: on `reports/q3.pdf` it returns the whole path. And `send_email` returns `None`, so a failure halfway through a loop has already delivered the earlier messages without saying which. The rebuild makes a comma impossible inside an address (`Address` is a frozen local-part/domain pair), splits on both separators then refuses anything that is not a bare file name, checks the template against **every** recipient before the first message leaves, and returns a `Report` where each row is **sent**, **skipped** with a reason, or **failed** with the transport's reason.
- **Excel_Report_Generator** — *a mean without its denominator is not a number.* `dataframe.describe(include="all")` averages only the values that happen to be there and hides the divisor in a separate `count` row, in a frame that unions two shapes and blanks where they do not meet. `dtypes.values` reports storage, not meaning — an id of digits is `object`, and one bad cell casts a whole price column to text. And money in a float is wrong before it is ever rounded: `0.10 + 0.20` is `0.30000000000000004`, and `round(318.5)` is `318` because `round` is half-to-even. The rebuild prints every mean as `mean 3.19 over 8 of 12 rows`, decides a column's kind by looking at every value and refuses one that mixes money with counts, keeps every amount in integer cents, and rounds half away from zero with `divide_half_up(2548, 8) == 319`.
- **Folder_Backup_Tool** — *a count of paths is not a copy of a folder.* `len(source_files) == len(backup_files)` passes a backup whose bytes are wrong: five paths beside five paths, the same sizes, and one file edited in place. `rglob("*")` counts directories too. `current_timestamp()` plus `copytree(..., dirs_exist_ok=True)` makes two backups in one second a **merge** rather than a collision, so a file the source no longer has survives inside the snapshot. And `while self.running: time.sleep(interval); callback()` cannot be stopped by a flag set during the sleep. The rebuild verifies by path, then size, then digest, naming the file and the kind of difference; chooses a name against the names already taken (`-2`, `-3`); diffs two trees into added / changed / removed / unchanged; and replaces the polling thread with arithmetic — `due(0, 60, 10) == ()`.
- **PDF_Merger** — *`False` is not an explanation, a list is not a file, and a prefix is not a page.* `except Exception: return False` collapses six different failures into one bit, so the message is "merge failed", which is the one message that is never true. `len(pdf_files) >= 2` validates the list, not the files: two paths that do not exist pass it, and so does a text file renamed `.pdf`. And `data.count(b"/Type /Page")` is one too many for **every** document with a page tree, because `/Type /Pages` starts with the same fifteen bytes. The rebuild writes real PDF bytes by hand, reads them back, gives six damages six sentences, refuses duplicates and an output that is one of the inputs, and counts page objects by comparing the whole `/Type` name with the stream excluded.

**Every count is exact and every claim is checkable.** Cents, digests, pages, renames, recipients and bytes are integers or byte strings, each demo prints the number it derived, and each project's `audit()`/`problems()` re-derives the result from the data instead of restating the summary it just printed.

Standard library only: no `pandas`, no `openpyxl`, no `pypdf`, no `shutil`, no `threading`, no `smtplib`, no `tkinter`, no network, no API keys, no downloads.

---

# 🎓 Learning Objectives

- Tell the number of things *asked for* from the number of things *done*
- Plan a mutation as a value, check it against the world twice, then apply it reversibly
- Number a colliding name instead of using it, and never merge into an existing folder
- Make a defect unrepresentable in a type rather than forbidden in a comment
- Keep a template check before the first side effect, so a failure sends nothing
- Print a mean with the divisor that produced it, or refuse to print it
- Keep money as integer cents and round half away from zero on purpose
- Verify a copy by content, and name the path and the kind of difference
- Replace a polling thread with arithmetic a window can bound
- Carry a reason instead of a boolean, all the way out to the caller
- Count a name whole, so a prefix cannot inflate a total
- Write an `audit()` that returns every check, then force each one to fail

---

# 📁 Projects

No. | Project | Description | Tests | Status
--: | --- | --- | --: | :---:
01 | Bulk_File_Renamer | A plan that covers every file: Windows name rules, collisions numbered, case-only renames, undo walked before it moves. | 110 | ✅
02 | Email_Automation | One message per recipient, an `Address` a comma cannot enter, the template checked before the first send, sent/skipped/failed. | 144 | ✅
03 | Excel_Report_Generator | Every mean printed with its `n`, column kinds decided from the data, money in cents, `318.5 → 319` where `round()` says 318. | 136 | ✅
04 | Folder_Backup_Tool | Verified by path, size and digest; names that never merge; a four-way diff; a schedule as arithmetic. | 147 | ✅
05 | PDF_Merger | Real PDF bytes written and read; six damages, six reasons; `/Type /Page` counted whole, not as a prefix. | 168 | ✅

**Total: 705 tests.**

---

# 🧠 Concepts Covered

- Idempotent, reversible file operations and the difference between a plan and its application
- Filename rules that are platform facts: reserved names, trailing dots, case-insensitive targets
- Undo as a recorded chain, applied in reverse, pre-walked before the first move
- Personalisation versus broadcast, and privacy as a data-model decision
- Address parsing that cannot produce a comma inside an address
- Template validation across the whole recipient set before any send
- Reports that account for every input: sent, skipped, failed
- Statistical honesty: the denominator, the gap threshold, the meaning of a column
- Integer cents, half-up rounding, and why `0.1 + 0.2` is a bug in a total
- Content verification by digest, and the four kinds of difference
- Incremental backup as a diff: added, changed, removed, unchanged
- Scheduling as arithmetic; why a stop flag cannot interrupt a `sleep`
- Failure as a sentence: `PdfError`, `Reading`, `Problem`, `Report`
- Magic numbers, cross-reference tables, and validation before the first side effect
- Prefix versus whole token in text matching, and streams versus dictionaries
- Audits whose negative controls plant the defect where the check actually looks

---

# 🗂️ Repository Structure

```text
06_Automation/

├── Bulk_File_Renamer/
│   ├── src/    renamer.py, main.py
│   ├── tests/  test_renamer.py
│   └── data/   folder.txt, names.txt
│
├── Email_Automation/
│   ├── src/    merge.py, main.py
│   ├── tests/  test_merge.py
│   └── data/   recipients.txt, template.txt, attachments.txt
│
├── Excel_Report_Generator/
│   ├── src/    reportlab.py, main.py
│   ├── tests/  test_reportlab.py
│   └── data/   sales.csv
│
├── Folder_Backup_Tool/
│   ├── src/    backup.py, main.py
│   ├── tests/  test_backup.py
│   └── data/   tree.txt, backup.txt, after.txt
│
└── PDF_Merger/
    ├── src/    pdfdocument.py, main.py
    ├── tests/  test_pdfdocument.py
    └── data/   pages.txt
```

Each project has the same shape: all logic in one library module, a thin `main.py`
argparse CLI, a `tests/` suite, deterministic data in `data/`, a pinned
`requirements.txt`, a `.gitignore`, and a `README.md` that states its own defect.

---

# ▶️ Run any project

```bash
cd 06_Automation/Folder_Backup_Tool

python src/main.py --demo          # offline, deterministic, exit 0
python src/main.py                 # the same work, printed as a report
python src/main.py --audit         # every check with PASS/FAIL
python -m pytest tests -q          # the suite
```

Every project supports `--demo`, `--quiet` with `--demo` (prints nothing), `--audit`,
`--json <path>`, and flags of its own (`--folder`, `--names`, `--source`, `--backup`,
`--file`, `--output`, `--write`, `--group`, `--csv`). Nothing touches the network, no
API key is read, and no file is downloaded: each demo runs on the bundled data, writes
nothing into the repository, and finishes in under two seconds.

---

# 🎯 Learning Outcomes

This category helps you understand:

- Why a function that returns a count can be right and still lie
- How to separate planning a change from making it, and why both need a check
- How to make a class of bug impossible with a type instead of a warning
- Why an email to five people is five messages
- What a mean is missing when it arrives without its denominator
- Why money belongs in integers, and which way a half-cent should go
- What "the backup is verified" has to mean for it to mean anything
- Why a `sleep`-first loop cannot be stopped where you asked it to stop
- Why a reason is worth more than a boolean, and how to carry one out to the caller
- Why `count(b"/Type /Page")` is always one too high
- How to write an audit whose every check has a negative control
- How to make a demonstration reproducible byte for byte

---

# 🧰 Patterns Included

Planning — `build_plan`, `check`, `validate`, `due`
Undo — reversible records, newest-first replay, pre-walked chains
Reporting — `Report`, `Verdict`, `Plan`, `Reading`, `Problem`, `Stat`
Arithmetic — integer cents, `divide_half_up`, `due(start, interval, until)`
Hashing — SHA-256 per file, short digests in a manifest
Parsing — hand-written CSV, `path<TAB>text`, `document<TAB>title`, MIME-ish headers
Encoding — `%PDF` bytes written by hand: header, objects, xref, trailer, `%%EOF`
Testing — negative controls per audit check, pinned demo output, byte-identical runs

---

# 🚀 Future Improvements

- A shared `--dry-run` that every project honours, so a plan can be printed as a diff
- A filesystem adapter, so the in-memory trees can be pointed at a real folder
- `.xlsx` output without `openpyxl`, on top of the same cents arithmetic
- Real SMTP behind the existing transport interface, with the same report
- Reading real-world PDFs, with object streams and compressed cross-references
- A retention policy for backups: keep the last N plans, prune the rest
- One shared `audit` harness, so all five report the same way

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with a clear message.
4. Push the branch.
5. Open a Pull Request.

---

# 👨‍💻 Author

**Devender J**

Python Developer | Data Analytics Enthusiast | AI & Machine Learning Learner

GitHub: **https://github.com/JDevender007**

---

<div align="center">

⭐ If you found these projects useful, consider giving this repository a star.

</div>
