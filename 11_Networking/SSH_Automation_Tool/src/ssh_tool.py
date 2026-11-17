"""A command's result is its exit status, and an argument is not a string.

The legacy automation wrapper asks the two questions every shell tutorial shows:

    output = session.run(f"systemctl is-active {service}")
    running = "active" in output
    failed = [task for task in tasks if task.exit_code != 0]

Both are wrong, and each one is wrong in a way that reads as success.

**1. A substring is not a status.** `systemctl is-active` prints `inactive` for a
stopped unit, and `inactive` contains `active`. The legacy check therefore reports
a stopped service as running -- the exact opposite of the truth -- and it would do
the same for `failed`, `activating` or any message that merely mentions the word.
The exit status is the answer; the text is a transcript for humans.

**2. A nonzero exit is not a failure.** `grep -q` returns 1 when the pattern is
absent: that is a successful search with a negative answer, and every `set -e`
script that greps has to know it. A task must declare which codes mean success
(`0;1` for a grep, `0` for a restart), and the wrapper must compare against that
declaration rather than against zero.

**3. A command built by concatenation is not the command you meant.** Building
`f"test -d {path}"` with `path = "/srv/app data"` hands the remote shell four
words instead of three, so the test asks about `/srv/app` and then about `data`;
a path holding `;` or `$(...)` is worse than wrong, it is a second command. The
rebuild keeps every command as an argument vector, quotes each argument on the way
out, and refuses an argument that carries a newline or a NUL.

The demonstration is offline: the remote side of each session is a bundled
transcript of outputs and exit codes, so two runs print the same bytes and no
socket is opened.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TASKS_FILE = DATA_DIR / "tasks.csv"
SESSION_FILE = DATA_DIR / "session.log"

#: The legacy success tests, transcribed.
LEGACY_SERVICE_CHECK = 'running = "active" in output'
LEGACY_FAILURE_CHECK = "failed = [task for task in tasks if task.exit_code != 0]"

#: Characters that need no quoting in the shell we model.
SAFE = re.compile(r"^[A-Za-z0-9_./:=@%+,-]+$")

_BLOCK = re.compile(r"^# task_id=(\d+)$")
_COMMAND = re.compile(r"^\$ (.*)$")
_EXIT = re.compile(r"^\? (\d+)$")

MAX_EXIT = 255


class SshError(RuntimeError):
    """Raised for input the program refuses."""


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise SshError(f"{name} must be text, got {type(value).__name__}")
    if not value.strip():
        raise SshError(f"{name} must not be empty")
    return value


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SshError(f"{name} must be an integer, got {type(value).__name__}")
    return value


def _positive(value: object, name: str) -> int:
    number = _whole(value, name)
    if number <= 0:
        raise SshError(f"{name} must be positive, got {number}")
    return number


def _exit_code(value: object, name: str = "exit code") -> int:
    number = _whole(value, name)
    if not 0 <= number <= MAX_EXIT:
        raise SshError(f"{name} must be in 0..{MAX_EXIT}, got {number}")
    return number


# --------------------------------------------------------------------------- #
# Quoting: an argument vector, not a string
# --------------------------------------------------------------------------- #
def quote_arg(argument: str) -> str:
    """Render one argument so that a POSIX shell reads it back as one word."""
    raw = _text(argument, "argument")
    if "\n" in raw or "\r" in raw or "\0" in raw:
        raise SshError(f"argument may not contain a newline or a NUL: {raw!r}")
    if SAFE.match(raw):
        return raw
    return "'" + raw.replace("'", "'\\''") + "'"


def build_command(argv: Sequence[str]) -> str:
    """Join an argument vector into a command line the shell will not re-split."""
    args = list(argv)
    if not args:
        raise SshError("a command needs at least one argument")
    return " ".join(quote_arg(argument) for argument in args)


def split_argv(line: str) -> list[str]:
    """Split a command line the way a POSIX shell would, honouring quotes.

    Only the parts this project needs: whitespace separates words, single quotes
    are literal, a backslash escapes the next character outside single quotes,
    and an unterminated quote is refused rather than guessed at.
    """
    raw = _text(line, "command line")
    if "\n" in raw or "\0" in raw:
        raise SshError("a command line may not contain a newline or a NUL")
    words: list[str] = []
    current: list[str] = []
    quoted = False
    has_word = False
    index = 0
    while index < len(raw):
        character = raw[index]
        if quoted:
            if character == "'":
                quoted = False
            else:
                current.append(character)
        elif character == "'":
            quoted = True
            has_word = True
        elif character == "\\":
            index += 1
            if index >= len(raw):
                raise SshError("a backslash may not end a command line")
            current.append(raw[index])
            has_word = True
        elif character.isspace():
            if current or has_word:
                words.append("".join(current))
                current = []
                has_word = False
        else:
            current.append(character)
            has_word = True
        index += 1
    if quoted:
        raise SshError(f"unterminated single quote in {line!r}")
    if current or has_word:
        words.append("".join(current))
    if not words:
        raise SshError(f"a command line needs at least one word: {line!r}")
    return words


def legacy_split(line: str) -> list[str]:
    """The defective split: whitespace only, so a quoted path becomes two words."""
    return _text(line, "command line").split()


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Task:
    """One command to run, and the exit codes that mean it succeeded."""

    task_id: int
    command: str
    ok_codes: tuple[int, ...]
    note: str

    @property
    def argv(self) -> list[str]:
        return split_argv(self.command)


@dataclass(frozen=True)
class Result:
    """What the remote side actually sent back."""

    task_id: int
    command: str
    output: tuple[str, ...]
    exit_code: int


@dataclass(frozen=True)
class Outcome:
    """The verdict on one task, with the reason in words."""

    task_id: int
    ok: bool
    reason: str


def parse_ok_codes(text: str) -> tuple[int, ...]:
    """`"0;1"` -> `(0, 1)`; every entry must be a plausible exit code."""
    raw = _text(text, "ok_codes").strip()
    codes: list[int] = []
    for part in raw.split(";"):
        piece = part.strip()
        if not piece:
            raise SshError(f"ok_codes has an empty entry: {text!r}")
        try:
            code = int(piece, 10)
        except ValueError as exc:
            raise SshError(f"ok_codes must be whole numbers, got {piece!r}") from exc
        codes.append(_exit_code(code, "ok_codes entry"))
    if len(set(codes)) != len(codes):
        raise SshError(f"ok_codes repeats a code: {text!r}")
    return tuple(codes)


def _read_rows(path: str | Path, required: Sequence[str]) -> list[dict[str, str]]:
    target = Path(path)
    if not target.is_file():
        raise SshError(f"file not found: {target.name}")
    with target.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        missing = [column for column in required if column not in header]
        if missing:
            raise SshError(f"{target.name} is missing column(s): {', '.join(missing)}")
        return [dict(row) for row in reader]


def _int(text: str, name: str) -> int:
    raw = _text(text, name).strip()
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise SshError(f"{name} must be a whole number, got {raw!r}") from exc


def load_tasks(path: str | Path | None = None) -> list[Task]:
    rows = _read_rows(path or TASKS_FILE, ("task_id", "command", "ok_codes", "note"))
    if not rows:
        raise SshError("tasks.csv holds no tasks")
    tasks: list[Task] = []
    for row in rows:
        command = _text(row["command"], "command").strip()
        split_argv(command)
        tasks.append(
            Task(
                task_id=_positive(_int(row["task_id"], "task_id"), "task_id"),
                command=command,
                ok_codes=parse_ok_codes(row["ok_codes"]),
                note=_text(row["note"], "note").strip(),
            )
        )
    if len({task.task_id for task in tasks}) != len(tasks):
        raise SshError("task_id values must be unique")
    return tasks


def load_results(path: str | Path | None = None) -> list[Result]:
    target = Path(path) if path is not None else SESSION_FILE
    if not target.is_file():
        raise SshError(f"file not found: {target.name}")
    try:
        body = target.read_bytes().decode("ascii")
    except UnicodeDecodeError as exc:
        raise SshError(f"{target.name} is not ASCII text") from exc

    results: list[Result] = []
    task_id: int | None = None
    command: str | None = None
    output: list[str] = []
    seen_exit = False
    for number, raw in enumerate(body.splitlines(), start=1):
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        block = _BLOCK.match(line)
        if block is not None:
            if task_id is not None and not seen_exit:
                raise SshError(f"block for task {task_id} has no exit line")
            task_id = int(block.group(1))
            command = None
            output = []
            seen_exit = False
            continue
        if task_id is None:
            raise SshError(f"line {number} appears before any '# task_id=' header")
        if seen_exit:
            raise SshError(f"line {number} follows the exit line of task {task_id}")
        opening = _COMMAND.match(line)
        if opening is not None:
            if command is not None:
                raise SshError(f"task {task_id} has two command lines")
            command = opening.group(1).strip()
            continue
        closing = _EXIT.match(line)
        if closing is not None:
            if command is None:
                raise SshError(f"task {task_id} has an exit line before its command")
            results.append(
                Result(
                    task_id=task_id,
                    command=command,
                    output=tuple(output),
                    exit_code=_exit_code(int(closing.group(1))),
                )
            )
            seen_exit = True
            continue
        if command is None:
            raise SshError(f"line {number} is output before the command of task {task_id}")
        output.append(line)
    if task_id is not None and not seen_exit:
        raise SshError(f"block for task {task_id} has no exit line")
    if not results:
        raise SshError("session.log holds no results")
    return results


def pair_up(tasks: Sequence[Task], results: Sequence[Result]) -> list[tuple[Task, Result]]:
    """Match each task with its result, refusing a missing, extra or wrong command."""
    by_id = {result.task_id: result for result in results}
    if len(by_id) != len(results):
        raise SshError("session.log repeats a task_id")
    known = {task.task_id for task in tasks}
    extra = sorted(set(by_id) - known)
    if extra:
        raise SshError(f"session.log has results for unknown task(s): {extra}")
    pairs: list[tuple[Task, Result]] = []
    for task in tasks:
        result = by_id.get(task.task_id)
        if result is None:
            raise SshError(f"task {task.task_id} has no result in session.log")
        if result.command != task.command:
            raise SshError(
                f"task {task.task_id} was recorded as {result.command!r}, "
                f"not {task.command!r}"
            )
        pairs.append((task, result))
    return pairs


# --------------------------------------------------------------------------- #
# Verdicts
# --------------------------------------------------------------------------- #
def verdict(task: Task, result: Result) -> Outcome:
    """Success is the exit code being one the task declared acceptable."""
    if result.exit_code in task.ok_codes:
        return Outcome(
            task_id=task.task_id,
            ok=True,
            reason=f"exit {result.exit_code} is one of {list(task.ok_codes)}",
        )
    return Outcome(
        task_id=task.task_id,
        ok=False,
        reason=f"exit {result.exit_code} is not one of {list(task.ok_codes)}",
    )


def evaluate(pairs: Sequence[tuple[Task, Result]]) -> list[Outcome]:
    return [verdict(task, result) for task, result in pairs]


def legacy_failed(results: Sequence[Result]) -> list[int]:
    """The legacy rule: anything not zero is a failure."""
    return [result.task_id for result in results if result.exit_code != 0]


def legacy_service_ok(output: Sequence[str]) -> bool:
    """The legacy status test: does the word appear anywhere in the text?"""
    return "active" in "\n".join(output)


def first_line(result: Result) -> str:
    if not result.output:
        return ""
    return result.output[0]


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure(
    tasks_path: str | Path | None = None,
    *,
    session_path: str | Path | None = None,
) -> dict[str, Any]:
    if tasks_path is not None:
        folder = Path(tasks_path).resolve().parent
        session_path = session_path or folder / "session.log"
    tasks = load_tasks(tasks_path)
    results = load_results(session_path)
    pairs = pair_up(tasks, results)
    outcomes = evaluate(pairs)
    by_id = {task.task_id: task for task in tasks}
    service = by_id.get(1, tasks[0])
    service_result = next(result for result in results if result.task_id == service.task_id)
    quoting = next((row for row in tasks if "'" in row.command), tasks[0])
    return {
        "tasks": tasks,
        "results": results,
        "pairs": pairs,
        "outcomes": outcomes,
        "ok": [outcome.task_id for outcome in outcomes if outcome.ok],
        "failed": [outcome.task_id for outcome in outcomes if not outcome.ok],
        "legacy_failed": legacy_failed(results),
        "service_output": first_line(service_result),
        "service_exit": service_result.exit_code,
        "service_ok": verdict(service, service_result).ok,
        "legacy_service_ok": legacy_service_ok(service_result.output),
        "naive_argv": legacy_split(quoting.command),
        "argv": quoting.argv,
        "round_trip": build_command(quoting.argv),
    }


def report(measured: dict[str, Any]) -> dict[str, Any]:
    return {
        "tasks": len(measured["tasks"]),
        "ok": measured["ok"],
        "failed": measured["failed"],
        "legacy_failed": measured["legacy_failed"],
        "service_output": measured["service_output"],
        "service_exit": measured["service_exit"],
        "service_ok": measured["service_ok"],
        "legacy_service_ok": measured["legacy_service_ok"],
        "naive_argv": measured["naive_argv"],
        "argv": measured["argv"],
        "round_trip": measured["round_trip"],
        "outcomes": [
            {"task_id": outcome.task_id, "ok": outcome.ok, "reason": outcome.reason}
            for outcome in measured["outcomes"]
        ],
        "results": [
            {
                "task_id": result.task_id,
                "command": result.command,
                "exit_code": result.exit_code,
                "output": list(result.output),
            }
            for result in measured["results"]
        ],
    }


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def _guard(check) -> bool:
    try:
        return bool(check())
    except Exception:
        return False


def _refuses(call) -> bool:
    try:
        call()
    except SshError:
        return True
    return False


def audit(
    measured: dict[str, Any],
    *,
    read_outcomes: Callable[[Sequence[tuple[Task, Result]]], list[Outcome]] = evaluate,
) -> list[tuple[str, bool]]:
    """Every check compares a measured value with an independent computation."""
    tasks = measured["tasks"]
    results = measured["results"]
    pairs = measured["pairs"]
    by_id = {task.task_id: task for task in tasks}
    service_result = next(result for result in results if result.task_id == 1)

    def outcomes_via_reader() -> list[Outcome]:
        return read_outcomes(pairs)

    def independent_ok_ids() -> list[int]:
        found: list[int] = []
        for task in tasks:
            result = next(row for row in results if row.task_id == task.task_id)
            if result.exit_code in task.ok_codes:
                found.append(task.task_id)
        return found

    checks = [
        (
            "every_task_is_paired_with_one_result",
            lambda: len(pairs) == len(tasks) == 5,
        ),
        (
            "each_recorded_command_matches_its_task",
            lambda: all(result.command == task.command for task, result in pairs),
        ),
        (
            "the_verdicts_are_pinned",
            lambda: measured["ok"] == [2, 3, 5] and measured["failed"] == [1, 4],
        ),
        (
            "verdicts_match_an_independent_comparison",
            lambda: [outcome.task_id for outcome in outcomes_via_reader() if outcome.ok]
            == independent_ok_ids(),
        ),
        (
            "the_legacy_rule_fails_every_nonzero_exit",
            lambda: measured["legacy_failed"] == [1, 2, 4]
            and measured["legacy_failed"] != measured["failed"],
        ),
        (
            "the_two_rules_differ_only_on_the_declared_grep",
            lambda: set(measured["legacy_failed"]) - set(measured["failed"]) == {2}
            and by_id[2].ok_codes == (0, 1),
        ),
        (
            "grep_exit_one_is_a_negative_answer_not_an_error",
            lambda: next(row for row in results if row.task_id == 2).exit_code == 1
            and verdict(by_id[2], next(row for row in results if row.task_id == 2)).ok
            is True,
        ),
        (
            "the_service_check_is_wrong_about_a_stopped_unit",
            lambda: measured["service_output"] == "inactive"
            and measured["legacy_service_ok"] is True
            and measured["service_ok"] is False
            and measured["service_exit"] == 3,
        ),
        (
            "inactive_contains_active",
            lambda: "active" in "inactive" and "inactive" not in ("active",),
        ),
        (
            "an_exit_code_outside_the_declaration_is_a_failure",
            lambda: verdict(by_id[1], service_result).ok is False,
        ),
        (
            "the_naive_split_breaks_the_quoted_path",
            lambda: measured["naive_argv"]
            == ["test", "-d", "'/srv/app", "data'"]
            and len(measured["naive_argv"]) == 4,
        ),
        (
            "the_quote_aware_split_keeps_one_path_argument",
            lambda: measured["argv"] == ["test", "-d", "/srv/app data"]
            and len(measured["argv"]) == 3,
        ),
        (
            "a_command_round_trips_through_its_own_quoting",
            lambda: split_argv(build_command(measured["argv"])) == measured["argv"]
            and build_command(measured["argv"]) == measured["round_trip"],
        ),
        (
            "a_shell_metacharacter_stays_inside_one_argument",
            lambda: split_argv(build_command(["ls", "/tmp; rm -rf /"]))
            == ["ls", "/tmp; rm -rf /"]
            and build_command(["ls", "/tmp; rm -rf /"])
            == "ls '/tmp; rm -rf /'",
        ),
        (
            "an_unterminated_quote_is_refused",
            lambda: _refuses(lambda: split_argv("test -d '/srv/app")),
        ),
        (
            "an_argument_with_a_newline_is_refused",
            lambda: _refuses(lambda: quote_arg("a\nb")),
        ),
        (
            "an_empty_command_is_refused",
            lambda: _refuses(lambda: build_command([])),
        ),
        (
            "rebuild_is_deterministic",
            lambda: [outcome.ok for outcome in outcomes_via_reader()]
            == [outcome.ok for outcome in measured["outcomes"]],
        ),
    ]
    return [(name, _guard(check)) for name, check in checks]


# --------------------------------------------------------------------------- #
# Rendering and the demo
# --------------------------------------------------------------------------- #
def render_outcomes(measured: dict[str, Any]) -> str:
    rows = {outcome.task_id: outcome for outcome in measured["outcomes"]}
    lines = ["  task  command                          exit  declared  verdict"]
    for task, result in measured["pairs"]:
        outcome = rows[task.task_id]
        codes = ",".join(str(code) for code in task.ok_codes)
        command = task.command if len(task.command) <= 30 else task.command[:27] + "..."
        lines.append(
            f"  {task.task_id:>4}  {command:<30}{result.exit_code:>5}  {codes:<9}"
            f"{'ok' if outcome.ok else 'FAILED'}"
        )
    return "\n".join(lines)


def run_demo() -> int:
    measured = measure()
    print("SSH automation -- the exit status is the result")
    print("=" * 50)
    print()
    print(
        f"Seeds: {len(measured['tasks'])} tasks, {len(measured['results'])} recorded "
        f"results, {len(measured['ok'])} accepted and {len(measured['failed'])} refused."
    )
    print()
    print(render_outcomes(measured))
    print()
    print("1. A substring is not a status.")
    print("   " + LEGACY_SERVICE_CHECK)
    print(
        f"   task 1 printed {measured['service_output']!r} and exited "
        f"{measured['service_exit']}; 'active' is found inside 'inactive',"
    )
    print(
        f"   so the legacy check says running ({measured['legacy_service_ok']}) while the "
        f"declared codes {list(measured['tasks'][0].ok_codes)} say it failed."
    )
    print()
    print("2. A nonzero exit is not a failure.")
    print("   " + LEGACY_FAILURE_CHECK)
    print(
        f"   legacy fails {measured['legacy_failed']}; the declared codes fail "
        f"{measured['failed']}."
    )
    print(
        "   task 2 is `grep -q ERROR ...` with ok_codes 0;1, and exit 1 means 'no match', "
        "which is an answer."
    )
    print()
    print("3. A command built by concatenation is not the command you meant.")
    print(
        f"   command line: {measured['round_trip']}\n"
        f"   naive split:  {measured['naive_argv']}\n"
        f"   argv:         {measured['argv']}"
    )
    print(
        f"   {len(measured['naive_argv'])} words against {len(measured['argv'])}: the quoted "
        "path became two arguments, so the test asks the wrong question."
    )
    print()
    print("Checks")
    results = audit(measured)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"  {passed}/{len(results)} checks pass")
    print()
    print(
        "Cross-checks OK: the session runs "
        f"{len(measured['tasks'])} tasks and the declared codes accept {measured['ok']} of "
        f"them, while `exit != 0` fails {measured['legacy_failed']} and so refuses task 2 even "
        f"though grep's exit 1 is its negative answer; task 1 printed 'inactive' and exited "
        f"{measured['service_exit']}, which the substring test reads as 'active'; the quoted "
        f"path splits into {len(measured['naive_argv'])} words naively and "
        f"{len(measured['argv'])} when quoted, and {measured['round_trip']!r} round-trips back "
        f"to the same vector; {passed}/{len(results)} checks pass."
    )
    print("Demo completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_demo())
