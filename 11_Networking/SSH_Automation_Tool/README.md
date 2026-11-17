# SSH Automation Tool

A remote command has **one** authoritative result: its exit status. The legacy wrapper asks
two questions that look the same and are not:

```python
output = session.run(f"systemctl is-active {service}")
running = "active" in output
failed = [task for task in tasks if task.exit_code != 0]
```

**1. A substring is not a status.** `systemctl is-active` prints `inactive` for a stopped unit,
and `inactive` contains `active`. In the bundled session task 1 prints `inactive`, exits `3`,
and the legacy check reports the service as **running** -- the exact opposite of the truth. The
same test would accept `failed`, `activating`, or any log line that merely mentions the word.

**2. A nonzero exit is not a failure.** `grep -q` returns `1` when the pattern is absent: that is
a successful search with a negative answer, and every `set -e` script that greps has to know it.
A task must **declare** the codes that mean success -- `0;1` for a grep, `0` for a restart -- and
the verdict must compare against that declaration. Here the legacy rule fails tasks
`[1, 2, 4]` while the declared codes fail only `[1, 4]`; the extra one is task 2, whose exit `1`
is `grep`'s way of saying "no match".

**3. A command built by concatenation is not the command you meant.**
`f"test -d {path}"` with `path = "/srv/app data"` hands the remote shell **four** words instead of
three, so the test asks about `/srv/app` and then about `data`. A path holding `;` or `$(...)` is
worse than wrong: it is a second command.

The rebuild keeps every command as an argument vector, splits a command line the way a POSIX
shell would (single quotes and backslash escapes, refusing an unterminated quote), quotes each
argument on the way out, and refuses an argument carrying a newline or a NUL. The remote side of
each session is a bundled transcript of outputs and exit codes, so two runs print the same bytes
and no socket is opened.

## What this project teaches

- The exit status is the answer; the text is a transcript for humans
- Why `"active" in output` is wrong for `inactive`, `failed` and `activating` alike
- Exit `1` from `grep -q` as a negative answer, not an error
- Declaring a success set per task (`0`, `0;1`) instead of hard-coding zero
- Command as an argument vector, and quoting every argument on the way out
- Splitting with quote awareness: `'/srv/app data'` is one word, not two
- Why a shell metacharacter inside one argument is a quoting problem, not an escaping problem
- Refusing an unterminated quote, a trailing backslash, and a newline in an argument
- Pairing each task with exactly one recorded result, and refusing a mismatch by name
- Auditing verdicts against an independent comparison, with negative controls

## How to run

```
python src/main.py --demo
python src/main.py --demo --quiet
python src/main.py --file data/tasks.csv --json out.json
python src/main.py --file data/tasks.csv --audit
python -m pytest tests -q
```

`--file` names the task CSV; `session.log` is read from the same folder. Exit code `2` means the
input was refused -- a missing column, a duplicated task id, a command with an unterminated
quote, a declared code outside `0..255`, a transcript block with no exit line, a result for an
unknown task, or a recorded command that does not match its task.

## Project structure

```
SSH_Automation_Tool/
├── README.md
├── requirements.txt        # pytest==9.1.1
├── .gitignore
├── data/
│   ├── tasks.csv           # 5 tasks with declared success codes
│   └── session.log         # 5 blocks: command, output, exit status
├── src/
│   ├── ssh_tool.py         # quoting, parsing, verdicts, checks, demo
│   └── main.py             # argparse only
└── tests/
    └── test_ssh_tool.py    # 130 tests
```

## What the demo shows

| task | command | exit | declared | verdict |
| --: | --- | --: | --- | --- |
| 1 | `systemctl is-active nginx` | **3** | `0` | **FAILED** |
| 2 | `grep -q ERROR /var/log/app.log` | **1** | `0;1` | **ok** |
| 3 | `df -h /` | 0 | `0` | ok |
| 4 | `test -d '/srv/app data'` | **1** | `0` | **FAILED** |
| 5 | `systemctl restart nginx` | 0 | `0` | ok |

- The declared codes accept `[2, 3, 5]`; the `exit != 0` rule fails `[1, 2, 4]` and so refuses
  task 2, whose exit `1` is `grep`'s negative answer
- Task 1 printed `inactive` and exited `3`: the substring test says running, the declared codes
  say failed, and only one of them is the truth
- `test -d '/srv/app data'` is **3** arguments when split with quote awareness and **4** when
  split on whitespace (`'/srv/app` and `data'`), so the naive version tests a different path
- `build_command(["test", "-d", "/srv/app data"])` returns `test -d '/srv/app data'` and splits
  back to the identical vector; `ls '/tmp; rm -rf /'` keeps the semicolon inside one argument
- 18/18 audit checks pass, with negative controls that hand the audit a verdict reader which
  calls everything a failure and watch exactly the comparison check flip

## Requirements

Python 3.10+, standard library only (`csv`, `re`, `pathlib`, `argparse`, `dataclasses`). Tests
need pytest==9.1.1.

---
**Devender J** -- https://github.com/JDevender007
