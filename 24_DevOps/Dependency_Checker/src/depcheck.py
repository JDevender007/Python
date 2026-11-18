"""Dependency Checker: compare requirement lists against local metadata.

Parses ``requirements.txt``-style lists and pyproject ``[project]``
dependencies, then compares each requirement with the version **locally
installed** (``importlib.metadata``) - severity-classified as ok, conflict,
missing, or unpinned. Strictly offline: no pip, no index queries, no
downloads; installed versions are read from local package metadata only.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Callable

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
OPERATORS = ("==", "!=", ">=", "<=", "~=", ">", "<")
NAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
COMMENT_RE = re.compile(r"(^|\s)#.*$")

STATUS_OK = "ok"
STATUS_CONFLICT = "conflict"
STATUS_MISSING = "missing"
STATUS_UNPINNED = "unpinned"
STATUSES = (STATUS_OK, STATUS_CONFLICT, STATUS_MISSING, STATUS_UNPINNED)

SEVERITY_ORDER = ("none", "low", "medium", "high")


class DepError(RuntimeError):
    """Raised for missing files, malformed requirements, and bad flags."""


# --------------------------------------------------------------------------- #
# Requirement parsing
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Requirement:
    """One parsed requirement: name + raw specifier + source line."""

    name: str
    specifier: str          # e.g. ">=1.24,<2" or ""
    line: str = ""

    @property
    def is_pinned(self) -> bool:
        return "==" in self.specifier and not self.specifier.startswith("!=")

    @property
    def operators(self) -> tuple[str, ...]:
        # match operator tokens in order; a substring scan would report
        # ">" inside ">=2.0" as well, which is wrong
        return tuple(re.findall(r"===|==|!=|>=|<=|~=|>|<", self.specifier))


def parse_requirement_line(text: str) -> Requirement | None:
    """Parse one requirements line -> Requirement, or None for blanks/comments.

    Raises DepError for directives this offline checker does not support
    (``-e``, URLs/VCS, environment markers) and for malformed names/specs.
    """
    stripped = COMMENT_RE.sub("", text).strip()
    if not stripped:
        return None
    if stripped.startswith(("-e ", "-e\t", "--editable")):
        raise DepError(f"editable installs are not supported: {text.strip()!r}")
    # options come first: "--index-url https://..." is an option, not a URL
    if stripped.startswith("-"):
        raise DepError(f"unsupported pip option: {stripped!r}")
    if "://" in stripped or stripped.startswith(("git+", "hg+", "svn+")):
        raise DepError(f"URL/VCS requirements are not supported: "
                       f"{stripped!r}")
    if ";" in stripped:
        raise DepError(f"environment markers are not supported: "
                       f"{stripped!r}")

    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)"
                     r"(\s*\[[^\]]*\])?"
                     r"\s*(.*)$", stripped)
    if not match:
        raise DepError(f"malformed requirement: {stripped!r}")
    name, extras, rest = match.group(1), match.group(2), match.group(3)
    if not NAME_RE.match(name):
        raise DepError(f"invalid package name: {name!r}")

    specifier = " ".join(rest.split())   # normalise whitespace
    if specifier:
        _validate_specifier(specifier)
    # extras like [tls] are accepted but do not affect the version check
    _ = extras
    return Requirement(name=name, specifier=specifier, line=text.strip())


def _validate_specifier(spec: str) -> None:
    """Reject nonsense specifiers early: '>=', '1.0', 'foo', '>=1.0@x'."""
    for clause in (c.strip() for c in spec.split(",")):
        if not clause:
            raise DepError(f"empty clause in specifier {spec!r}")
        match = re.match(r"^(===|==|!=|>=|<=|~=|>|<)\s*(.+)$", clause)
        if not match:
            raise DepError(f"malformed specifier clause: {clause!r}")
        op, version = match.group(1), match.group(2).strip()
        if not version or version[0] in "=<>!~":
            # ">=" alone matches as ">" + "=" - that is a missing version
            raise DepError(f"malformed specifier clause: {clause!r}")
        if op in ("==", "==="):
            base = version.rstrip("*").strip()
        else:
            base = version
        if version == "*":
            continue
        if not re.match(r"^\d", base):
            raise DepError(f"invalid version in clause {clause!r}")
        if not re.match(r"^[0-9][0-9A-Za-z.*+!_-]*$", base):
            raise DepError(f"invalid version in clause {clause!r}")


def parse_requirements_file(path: str | Path) -> list[Requirement]:
    """Parse a requirements.txt-style file (blank/comment lines skipped)."""
    source = Path(path)
    if not source.is_file():
        raise DepError(f"file not found: {source}")
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise DepError(f"could not read {source.name}: {exc}") from exc

    requirements: list[Requirement] = []
    seen: set[str] = set()
    for line_no, line in enumerate(text.splitlines(), start=1):
        try:
            requirement = parse_requirement_line(line)
        except DepError as exc:
            raise DepError(f"{source.name}:{line_no}: {exc}") from exc
        if requirement is None:
            continue
        key = requirement.name.lower()
        if key in seen:
            raise DepError(f"{source.name}:{line_no}: duplicate requirement "
                           f"{requirement.name!r}")
        seen.add(key)
        requirements.append(requirement)
    if not requirements:
        raise DepError(f"no requirements found in {source.name}")
    return requirements


def parse_pyproject(path: str | Path) -> list[Requirement]:
    """Parse ``[project] dependencies = [...]`` from a pyproject.toml."""
    source = Path(path)
    if not source.is_file():
        raise DepError(f"file not found: {source}")
    try:
        data = tomllib.loads(source.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise DepError(f"invalid TOML in {source.name}: {exc}") from exc
    project = data.get("project")
    if not isinstance(project, dict):
        raise DepError(f"{source.name}: missing [project] section")
    deps = project.get("dependencies")
    if deps is None:
        raise DepError(f"{source.name}: missing 'dependencies' key")
    if not isinstance(deps, list):
        raise DepError(f"{source.name}: 'dependencies' must be a list")

    requirements: list[Requirement] = []
    for index, item in enumerate(deps):
        if not isinstance(item, str):
            raise DepError(f"{source.name}: dependency #{index + 1} must be "
                           f"a string, got {type(item).__name__}")
        try:
            requirement = parse_requirement_line(item)
        except DepError as exc:
            raise DepError(f"{source.name}: dependency #{index + 1}: "
                           f"{exc}") from exc
        if requirement is None:
            raise DepError(f"{source.name}: dependency #{index + 1} is empty")
        requirements.append(requirement)
    return requirements


def parse_any(path: str | Path) -> list[Requirement]:
    """Dispatch on extension: .toml -> pyproject, otherwise requirements.txt."""
    source = Path(path)
    if source.suffix.lower() == ".toml":
        return parse_pyproject(source)
    return parse_requirements_file(source)


# --------------------------------------------------------------------------- #
# Version comparison and specifier matching (PEP 440 subset, no pip)
# --------------------------------------------------------------------------- #
def version_tokens(version: str) -> list[Any]:
    """Tokenise a version into comparable parts (ints where numeric).

    Numeric and alphabetic runs are split apart, so ``2.11.0+cu128``
    becomes ``[2, 11, 0, "cu", 128]`` and each run stays comparable with
    the matching run of another version.
    """
    parts: list[Any] = []
    for chunk in re.split(r"[.\-+]", version.strip()):
        for token in re.findall(r"\d+|[A-Za-z]+", chunk):
            parts.append(int(token) if token.isdigit() else token)
    return parts


def compare_versions(left: str, right: str) -> int:
    """-1/0/1 comparing two PEP 440-ish versions (numeric segments)."""
    a, b = version_tokens(left), version_tokens(right)
    # pad the shorter token list with 0s so 1.0 == 1.0.0
    length = max(len(a), len(b))
    pad = [0] * length
    a = a + pad[len(a):]
    b = b + pad[len(b):]
    for x, y in zip(a, b):
        if type(x) is not type(y):
            x, y = str(x), str(y)
        if x < y:
            return -1
        if x > y:
            return 1
    return 0


def _parse_clause(clause: str) -> tuple[str, str]:
    match = re.match(r"^(===|==|!=|>=|<=|~=|>|<)\s*(.+)$", clause.strip())
    if not match:
        raise DepError(f"malformed specifier clause: {clause!r}")
    op, version = match.group(1), match.group(2).strip()
    if not version or version[0] in "=<>!~":
        raise DepError(f"malformed specifier clause: {clause!r}")
    return op, version


def clause_holds(version: str, clause: str) -> bool:
    """Check one 'OP VERSION' clause against an installed version."""
    op, target = _parse_clause(clause)
    if target == "*":
        return True
    if target.endswith(".*"):                 # e.g. ==1.2.*
        prefix = target[:-2]
        if op == "==":
            return version == prefix or version.startswith(prefix + ".")
        if op == "!=":
            return not (version == prefix or version.startswith(prefix + "."))
        raise DepError(f"wildcard only valid with ==/!=: {clause!r}")
    cmp = compare_versions(version, target)
    if op == "==":
        return cmp == 0
    if op == "!=":
        return cmp != 0
    if op == ">=":
        return cmp >= 0
    if op == "<=":
        return cmp <= 0
    if op == ">":
        return cmp > 0
    if op == "<":
        return cmp < 0
    if op == "~=":                            # ~=1.2.3 -> >=1.2.3, <1.3
        if cmp < 0:
            return False
        segments = target.split(".")
        if len(segments) < 2:
            raise DepError(f"~= needs at least two segments: {clause!r}")
        head = segments[:-1]
        bumped = [str(int(head[0]) + 1)] + head[1:] if len(head) == 1 \
            else head[:-1] + [str(int(head[-1]) + 1)]
        return compare_versions(version, ".".join(bumped)) < 0
    raise DepError(f"unsupported operator {op!r}")


def satisfies(version: str, specifier: str) -> bool:
    """All clauses of *specifier* must hold (comma-separated AND logic)."""
    if not specifier:
        return True
    clauses = [c.strip() for c in specifier.split(",") if c.strip()]
    return all(clause_holds(version, clause) for clause in clauses)


# --------------------------------------------------------------------------- #
# Checking against locally installed versions
# --------------------------------------------------------------------------- #
def installed_version(name: str) -> str | None:
    """Locally installed version via importlib.metadata (never a network
    call); None when the package is not installed."""
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


@dataclass(frozen=True)
class CheckResult:
    """Verdict for one requirement."""

    name: str
    specifier: str
    installed: str | None
    status: str            # ok | conflict | missing | unpinned
    severity: str          # none | low | medium | high
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "specifier": self.specifier or "(any)",
            "installed": self.installed,
            "status": self.status,
            "severity": self.severity,
            "detail": self.detail,
        }


def classify(requirement: Requirement, installed: str | None) -> CheckResult:
    """Severity-classify one requirement against its installed version."""
    spec = requirement.specifier
    if installed is None:
        if requirement.is_pinned:
            severity = "high"
            detail = f"not installed (pinned {spec})"
        else:
            severity = "medium"
            detail = f"not installed (needs {spec or 'any version'})"
        return CheckResult(requirement.name, spec, None,
                           STATUS_MISSING, severity, detail)
    if not spec:
        return CheckResult(requirement.name, spec, installed,
                           STATUS_UNPINNED, "low",
                           f"installed {installed}, no version constraint")
    if satisfies(installed, spec):
        return CheckResult(requirement.name, spec, installed,
                           STATUS_OK, "none",
                           f"installed {installed} satisfies {spec}")
    exact = any(c.strip().startswith(("==", "==="))
                for c in spec.split(","))
    severity = "high" if exact else "medium"
    return CheckResult(requirement.name, spec, installed,
                       STATUS_CONFLICT, severity,
                       f"installed {installed} violates {spec}")


def check_requirements(
    requirements: list[Requirement],
    resolver: Callable[[str], str | None] | None = None,
) -> list[CheckResult]:
    """Check every requirement; resolver defaults to local metadata.

    Pass a ``resolver`` (e.g. a fixed mapping) to make checks fully
    deterministic regardless of what is installed on the machine.
    """
    lookup = resolver or installed_version
    return [classify(req, lookup(req.name)) for req in requirements]


def severity_counts(results: list[CheckResult]) -> dict[str, int]:
    counts = {level: 0 for level in SEVERITY_ORDER}
    for result in results:
        counts[result.severity] += 1
    return counts


def status_counts(results: list[CheckResult]) -> dict[str, int]:
    counts = {status: 0 for status in STATUSES}
    for result in results:
        counts[result.status] += 1
    return counts


def snapshot_resolver(snapshot: dict[str, str]) -> Callable[[str], str | None]:
    """Build a deterministic resolver from a {package: version} mapping."""
    lowered = {k.lower(): v for k, v in snapshot.items()}
    return lambda name: lowered.get(name.lower())


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_report(results: list[CheckResult], title: str = "DEPENDENCY CHECK"
                  ) -> str:
    """Human-readable severity report used by the CLI and the demo."""
    statuses = status_counts(results)
    severities = severity_counts(results)
    lines = [
        title,
        "=" * 68,
        f"Requirements : {len(results)}",
        "Status       : " + " | ".join(f"{s} {statuses[s]}"
                                       for s in STATUSES),
        "Severity     : " + " | ".join(f"{lv} {severities[lv]}"
                                       for lv in SEVERITY_ORDER),
        "",
        f"  {'package':<16} {'specifier':<14} {'installed':<12} "
        f"{'status':<10} severity",
        f"  {'-' * 16} {'-' * 14} {'-' * 12} {'-' * 10} {'-' * 8}",
    ]
    ranked = sorted(results,
                    key=lambda r: (-SEVERITY_ORDER.index(r.severity),
                                   r.name.lower()))
    for result in ranked:
        lines.append(
            f"  {result.name:<16} {(result.specifier or '(any)'):<14} "
            f"{(result.installed or '-'):<12} {result.status:<10} "
            f"{result.severity}")
    offenders = [r for r in ranked if r.severity in ("medium", "high")]
    lines += ["", "Needs attention:"]
    if offenders:
        for result in offenders:
            lines.append(f"  [{result.severity.upper():<6}] "
                         f"{result.name}: {result.detail}")
    else:
        lines.append("  (none)")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Bundled data + offline demo
# --------------------------------------------------------------------------- #
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BUNDLED_REQUIREMENTS = DATA_DIR / "requirements.txt"
BUNDLED_PYPROJECT = DATA_DIR / "pyproject.toml"
BUNDLED_SNAPSHOT = DATA_DIR / "installed.json"

# Expected snapshot results (asserted by the demo - fully deterministic,
# because the resolver is a bundled JSON mapping, not the live machine).
EXPECTED_SNAPSHOT_TOTAL = 10          # 7 requirements + 3 pyproject deps
EXPECTED_STATUS = {STATUS_OK: 4, STATUS_CONFLICT: 2,
                   STATUS_MISSING: 3, STATUS_UNPINNED: 1}
EXPECTED_SEVERITY = {"none": 4, "low": 1, "medium": 2, "high": 3}


def load_snapshot(path: Path | None = None) -> dict[str, str]:
    """Load the bundled {package: version} snapshot (deterministic input)."""
    source = path or BUNDLED_SNAPSHOT
    if not source.is_file():
        raise DepError(f"bundled sample not found: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DepError(f"invalid JSON in {source.name}: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise DepError(f"{source.name}: snapshot must be a non-empty "
                       f"object of package -> version")
    if not all(isinstance(k, str) and isinstance(v, str)
               for k, v in data.items()):
        raise DepError(f"{source.name}: snapshot entries must be strings")
    return data


def run_demo() -> int:
    """Parse both bundled dependency lists and check them twice: once
    against the local machine, once against the bundled snapshot with
    deterministic assertions. Fully offline - no pip, no index."""
    print("=" * 68)
    print(" DEPENDENCY CHECKER - offline demo")
    print(" requirements.txt + pyproject.toml vs local metadata; no pip.")
    print("=" * 68)

    for path in (BUNDLED_REQUIREMENTS, BUNDLED_PYPROJECT):
        if not path.is_file():
            raise DepError(f"bundled sample not found: {path}")

    # --- pass 1: live local metadata (informational) ---------------------- #
    live_reqs = parse_requirements_file(BUNDLED_REQUIREMENTS)
    live_results = check_requirements(live_reqs)
    print(f"\nParsed {len(live_reqs)} requirements from "
          f"{BUNDLED_REQUIREMENTS.name} "
          f"(live local metadata: {installed_version('numpy') or 'n/a'} "
          f"numpy)")
    print()
    print(render_report(live_results, "PASS 1 - requirements.txt vs "
                                      "this machine"))

    # --- pass 2: bundled snapshot (deterministic) ------------------------- #
    snapshot = load_snapshot()
    resolver = snapshot_resolver(snapshot)
    py_reqs = parse_pyproject(BUNDLED_PYPROJECT)
    all_reqs = parse_requirements_file(BUNDLED_REQUIREMENTS) + py_reqs
    results = check_requirements(all_reqs, resolver=resolver)
    print()
    print(render_report(results, "PASS 2 - bundled snapshot "
                                 "(deterministic)"))

    # --- cross-checks the demo asserts ------------------------------------ #
    statuses = status_counts(results)
    severities = severity_counts(results)
    assert len(results) == EXPECTED_SNAPSHOT_TOTAL, "expected 10 checks"
    assert statuses == EXPECTED_STATUS, f"status mix changed: {statuses}"
    assert severities == EXPECTED_SEVERITY, f"severity mix changed: {severities}"

    by_name = {(r.name, r.specifier): r for r in results}
    assert by_name[("numpy", ">=1.24")].status == STATUS_OK
    assert by_name[("pytest", ">=6")].status == STATUS_OK
    assert by_name[("pyyaml", "")].status == STATUS_UNPINNED
    assert by_name[("pyyaml", "")].severity == "low"
    assert by_name[("scipy", "==0.1.0")].status == STATUS_CONFLICT
    assert by_name[("scipy", "==0.1.0")].severity == "high"  # exact pin
    assert by_name[("pandas", "<1.0")].status == STATUS_CONFLICT
    assert by_name[("pandas", "<1.0")].severity == "medium"  # range
    assert by_name[("acme-widget", "==1.0.0")].status == STATUS_MISSING
    assert by_name[("acme-widget", "==1.0.0")].severity == "high"
    assert by_name[("sample-lib", ">=2.0")].severity == "medium"
    assert by_name[("acme-widget", "==1.0.0")].installed is None
    assert sum(1 for r in results if r.name == "pandas") == 2, \
        "pandas checked once per source list"

    # pyproject part parses to exactly the three bundled strings
    assert [r.name for r in py_reqs] == ["numpy", "pandas", "acme-widget"]
    assert py_reqs[1].specifier == ">=2.0"

    # specifier engine spot checks (no pip involved)
    assert satisfies("2.5.2", ">=1.24,<3")
    assert not satisfies("0.9", ">=1.24")
    assert satisfies("6.0.3", "~=6.0")
    assert satisfies("1.2.3", "==1.2.*")
    assert compare_versions("1.0", "1.0.0") == 0
    assert compare_versions("2.10", "2.9") == 1

    # deterministic re-check: identical verdicts
    again = check_requirements(all_reqs, resolver=resolver)
    assert again == results, "re-check not deterministic"

    # local pass must never fabricate installs: snapshot packages that are
    # truly absent locally stay absent (no network lookups possible)
    assert installed_version("acme-widget") is None

    print(f"\nCross-checks OK: {len(results)} checks "
          f"({statuses[STATUS_OK]} ok, {statuses[STATUS_CONFLICT]} conflict, "
          f"{statuses[STATUS_MISSING]} missing, "
          f"{statuses[STATUS_UNPINNED]} unpinned), severity mix "
          f"high {severities['high']}/medium {severities['medium']}, "
          f"specifier engine verified, deterministic re-check, "
          f"no index queries")
    print("Demo completed successfully.")
    return 0
