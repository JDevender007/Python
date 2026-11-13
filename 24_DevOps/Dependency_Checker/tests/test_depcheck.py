"""Tests for the Dependency Checker project."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from depcheck import (  # noqa: E402
    BUNDLED_PYPROJECT,
    BUNDLED_REQUIREMENTS,
    BUNDLED_SNAPSHOT,
    DATA_DIR,
    EXPECTED_SEVERITY,
    EXPECTED_SNAPSHOT_TOTAL,
    EXPECTED_STATUS,
    SEVERITY_ORDER,
    STATUSES,
    CheckResult,
    DepError,
    Requirement,
    check_requirements,
    classify,
    clause_holds,
    compare_versions,
    installed_version,
    load_snapshot,
    parse_any,
    parse_pyproject,
    parse_requirement_line,
    parse_requirements_file,
    render_report,
    run_demo,
    satisfies,
    severity_counts,
    snapshot_resolver,
    status_counts,
    version_tokens,
)
from main import build_parser, main  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR_PATH = PROJECT_ROOT / "data"


def _write(tmp_path: Path, text: str, name: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Requirement line parsing
# --------------------------------------------------------------------------- #
def test_parse_pinned_line():
    req = parse_requirement_line("numpy==2.5.2")
    assert req == Requirement("numpy", "==2.5.2", "numpy==2.5.2")
    assert req.is_pinned


def test_parse_range_line():
    req = parse_requirement_line("pandas>=2.0,<3.0  # data layer")
    assert req.name == "pandas"
    assert req.specifier == ">=2.0,<3.0"
    assert not req.is_pinned
    assert req.operators == (">=", "<")


def test_parse_bare_name():
    req = parse_requirement_line("pyyaml")
    assert req.specifier == "" and not req.is_pinned


def test_parse_extras_ignored_for_version():
    req = parse_requirement_line("requests[socks,use-chardet-on-py3]>=2.0")
    assert req.name == "requests"
    assert req.specifier == ">=2.0"


def test_parse_blank_and_comment_lines():
    assert parse_requirement_line("") is None
    assert parse_requirement_line("   ") is None
    assert parse_requirement_line("# just a comment") is None
    assert parse_requirement_line("  # indented comment") is None


def test_parse_case_insensitive_name_normalisation():
    req = parse_requirement_line("PyYAML~=6.0")
    assert req.name == "PyYAML"
    assert req.operators == ("~=",)


def test_parse_rejects_editable():
    with pytest.raises(DepError, match="editable installs"):
        parse_requirement_line("-e ./local/pkg")


def test_parse_rejects_url():
    with pytest.raises(DepError, match="URL/VCS requirements"):
        parse_requirement_line("pkg @ https://example.com/pkg.tar.gz")


def test_parse_rejects_vcs_prefix():
    with pytest.raises(DepError, match="URL/VCS requirements"):
        parse_requirement_line("git+https://github.com/x/y.git#egg=y")


def test_parse_rejects_environment_marker():
    with pytest.raises(DepError, match="environment markers"):
        parse_requirement_line('uvicorn>=0.20; python_version >= "3.11"')


def test_parse_rejects_unknown_option():
    with pytest.raises(DepError, match="unsupported pip option"):
        parse_requirement_line("--index-url https://example.com/simple")


def test_parse_rejects_malformed_specifier():
    with pytest.raises(DepError, match="malformed specifier clause"):
        parse_requirement_line("numpy=>1.0")


def test_parse_rejects_non_numeric_version():
    with pytest.raises(DepError, match="invalid version in clause"):
        parse_requirement_line("numpy>=latest")


def test_parse_rejects_empty_clause():
    with pytest.raises(DepError, match="empty clause in specifier"):
        parse_requirement_line("numpy>=1.0,,<2")


def test_parse_rejects_versionless_operator():
    with pytest.raises(DepError, match="malformed specifier clause"):
        parse_requirement_line("numpy>=")


# --------------------------------------------------------------------------- #
# File parsing
# --------------------------------------------------------------------------- #
def test_bundled_files_exist():
    for path in (BUNDLED_REQUIREMENTS, BUNDLED_PYPROJECT, BUNDLED_SNAPSHOT):
        assert path.is_file(), path
    assert BUNDLED_REQUIREMENTS.parent == DATA_DIR == DATA_DIR_PATH


def test_parse_bundled_requirements():
    reqs = parse_requirements_file(BUNDLED_REQUIREMENTS)
    assert len(reqs) == 7
    names = [r.name for r in reqs]
    assert names == ["numpy", "pytest", "pandas", "scipy", "acme-widget",
                     "sample-lib", "pyyaml"]
    assert reqs[0].specifier == ">=1.24"
    assert reqs[6].specifier == ""


def test_parse_requirements_file_missing(tmp_path):
    with pytest.raises(DepError, match="file not found"):
        parse_requirements_file(tmp_path / "nope.txt")


def test_parse_requirements_skips_comments(tmp_path):
    path = _write(tmp_path, "# header\n\nnumpy>=1.0\n\n# tail\n", "req.txt")
    assert [r.name for r in parse_requirements_file(path)] == ["numpy"]


def test_parse_requirements_rejects_duplicates(tmp_path):
    path = _write(tmp_path, "numpy>=1.0\nNumpy==2.5.2\n", "req.txt")
    with pytest.raises(DepError, match="duplicate requirement"):
        parse_requirements_file(path)


def test_parse_requirements_rejects_empty_file(tmp_path):
    path = _write(tmp_path, "# nothing here\n\n", "req.txt")
    with pytest.raises(DepError, match="no requirements found"):
        parse_requirements_file(path)


def test_parse_requirements_reports_line_number(tmp_path):
    path = _write(tmp_path, "numpy>=1.0\nbad line here!!\n", "req.txt")
    with pytest.raises(DepError, match=r"req\.txt:2"):
        parse_requirements_file(path)


def test_parse_requirements_bad_line_first_error(tmp_path):
    # the general malformed-name check fires before any specifier detail
    path = _write(tmp_path, "===1.0\n", "req.txt")
    with pytest.raises(DepError, match="malformed requirement"):
        parse_requirements_file(path)


def test_parse_pyproject_bundled():
    reqs = parse_pyproject(BUNDLED_PYPROJECT)
    assert [(r.name, r.specifier) for r in reqs] == [
        ("numpy", ">=1.24"), ("pandas", ">=2.0"), ("acme-widget", "==1.0.0")]


def test_parse_pyproject_missing(tmp_path):
    with pytest.raises(DepError, match="file not found"):
        parse_pyproject(tmp_path / "nope.toml")


def test_parse_pyproject_invalid_toml(tmp_path):
    path = _write(tmp_path, "[project\nbroken", "p.toml")
    with pytest.raises(DepError, match="invalid TOML"):
        parse_pyproject(path)


def test_parse_pyproject_missing_project_section(tmp_path):
    path = _write(tmp_path, "[tool.x]\na = 1\n", "p.toml")
    with pytest.raises(DepError, match=r"missing \[project\] section"):
        parse_pyproject(path)


def test_parse_pyproject_missing_dependencies(tmp_path):
    path = _write(tmp_path, "[project]\nname = 'x'\n", "p.toml")
    with pytest.raises(DepError, match="missing 'dependencies' key"):
        parse_pyproject(path)


def test_parse_pyproject_dependencies_not_a_list(tmp_path):
    path = _write(tmp_path, "[project]\ndependencies = 'numpy'\n", "p.toml")
    with pytest.raises(DepError, match="must be a list"):
        parse_pyproject(path)


def test_parse_pyproject_non_string_entry(tmp_path):
    path = _write(tmp_path, "[project]\ndependencies = [1]\n", "p.toml")
    with pytest.raises(DepError, match="must be a string"):
        parse_pyproject(path)


def test_parse_any_dispatch():
    assert parse_any(BUNDLED_PYPROJECT)[0].name == "numpy"
    assert parse_any(BUNDLED_REQUIREMENTS)[0].name == "numpy"


# --------------------------------------------------------------------------- #
# Version comparison and specifiers
# --------------------------------------------------------------------------- #
def test_version_tokens():
    assert version_tokens("1.2.3") == [1, 2, 3]
    assert version_tokens("2.11.0+cu128") == [2, 11, 0, "cu", 128]


def test_compare_versions_ordering():
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("1.0", "1.0.0") == 0      # zero padding
    assert compare_versions("2.10", "2.9") == 1       # numeric, not lexical
    assert compare_versions("1.0.0", "2.0.0") == -1
    assert compare_versions("2.5.2", "2.5.2+local") == -1


def test_clause_holds_all_operators():
    assert clause_holds("2.5.2", "==2.5.2")
    assert not clause_holds("2.5.2", "==2.5.3")
    assert clause_holds("2.5.2", "!=2.5.3")
    assert clause_holds("2.5.2", ">=2.0")
    assert clause_holds("2.5.2", "<=2.5.2")
    assert clause_holds("2.5.2", ">2.0")
    assert clause_holds("2.5.2", "<3.0")
    assert not clause_holds("2.5.2", "<2.5.2")


def test_clause_holds_compatible_release():
    assert clause_holds("6.0.3", "~=6.0")
    assert clause_holds("6.2.1", "~=6.0")
    assert not clause_holds("7.0.0", "~=6.0")
    assert not clause_holds("5.9", "~=6.0")


def test_clause_holds_wildcard():
    assert clause_holds("1.2.3", "==1.2.*")
    assert clause_holds("1.2", "==1.2.*")
    assert not clause_holds("1.3.0", "==1.2.*")
    assert clause_holds("1.3.0", "!=1.2.*")
    assert clause_holds("9.9.9", "==*")


def test_clause_holds_rejects_bad_wildcard():
    with pytest.raises(DepError, match="wildcard only valid"):
        clause_holds("1.0", ">=1.*")


def test_clause_holds_rejects_unknown_operator():
    with pytest.raises(DepError, match="malformed specifier clause"):
        clause_holds("1.0", "=1.0")


def test_satisfies_multi_clause_and_logic():
    assert satisfies("2.3.3", ">=2.0,<3.0")
    assert not satisfies("3.0", ">=2.0,<3.0")
    assert not satisfies("1.9", ">=2.0,<3.0")
    assert satisfies("1.0", "")          # no constraint always holds


# --------------------------------------------------------------------------- #
# Classification and severity
# --------------------------------------------------------------------------- #
def _resolver(mapping):
    return snapshot_resolver(mapping)


def test_classify_ok():
    result = classify(Requirement("numpy", ">=1.24"), "2.5.2")
    assert result.status == "ok"
    assert result.severity == "none"
    assert "satisfies" in result.detail


def test_classify_unpinned():
    result = classify(Requirement("pyyaml", ""), "6.0.3")
    assert result.status == "unpinned"
    assert result.severity == "low"


def test_classify_missing_pinned_is_high():
    result = classify(Requirement("acme-widget", "==1.0.0"), None)
    assert result.status == "missing"
    assert result.severity == "high"
    assert result.installed is None


def test_classify_missing_unpinned_is_medium():
    result = classify(Requirement("sample-lib", ">=2.0"), None)
    assert result.status == "missing"
    assert result.severity == "medium"


def test_classify_conflict_exact_is_high():
    result = classify(Requirement("scipy", "==0.1.0"), "1.18.0")
    assert result.status == "conflict"
    assert result.severity == "high"


def test_classify_conflict_range_is_medium():
    result = classify(Requirement("pandas", "<1.0"), "2.3.3")
    assert result.status == "conflict"
    assert result.severity == "medium"


def test_check_with_fixed_resolver_is_deterministic():
    snapshot = load_snapshot()
    resolver = _resolver(snapshot)
    reqs = parse_requirements_file(BUNDLED_REQUIREMENTS)
    first = check_requirements(reqs, resolver=resolver)
    second = check_requirements(reqs, resolver=resolver)
    assert first == second
    assert all(isinstance(r, CheckResult) for r in first)


def test_check_unknown_package_is_missing():
    results = check_requirements([Requirement("nope-pkg", ">=1")],
                                 resolver=lambda name: None)
    assert results[0].status == "missing"


def test_severity_and_status_counts():
    snapshot = load_snapshot()
    reqs = parse_requirements_file(BUNDLED_REQUIREMENTS) \
        + parse_pyproject(BUNDLED_PYPROJECT)
    results = check_requirements(reqs, resolver=_resolver(snapshot))
    statuses = status_counts(results)
    severities = severity_counts(results)
    assert statuses == EXPECTED_STATUS
    assert severities == EXPECTED_SEVERITY
    assert sum(statuses.values()) == EXPECTED_SNAPSHOT_TOTAL
    assert sum(severities.values()) == EXPECTED_SNAPSHOT_TOTAL
    assert set(statuses) == set(STATUSES)
    assert set(severities) == set(SEVERITY_ORDER)


def test_result_to_dict():
    payload = classify(Requirement("numpy", ">=1.24"), "2.5.2").to_dict()
    json.dumps(payload)
    assert payload["name"] == "numpy"
    assert payload["specifier"] == ">=1.24"
    assert payload["status"] == "ok"


def test_installed_version_reads_local_metadata():
    assert installed_version("pytest") is not None
    assert installed_version("acme-widget") is None


def test_snapshot_resolver_case_insensitive():
    resolver = _resolver({"PyYAML": "6.0.3"})
    assert resolver("pyyaml") == "6.0.3"
    assert resolver("PYyaml") == "6.0.3"
    assert resolver("other") is None


def test_load_snapshot_valid():
    snapshot = load_snapshot()
    assert set(snapshot) == {"numpy", "pytest", "pandas", "scipy", "pyyaml"}


def test_load_snapshot_rejects_bad_files(tmp_path):
    with pytest.raises(DepError, match="bundled sample not found"):
        load_snapshot(tmp_path / "nope.json")
    bad = _write(tmp_path, "{broken", "s.json")
    with pytest.raises(DepError, match="invalid JSON"):
        load_snapshot(bad)
    empty = _write(tmp_path, "{}", "s.json")
    with pytest.raises(DepError, match="non-empty"):
        load_snapshot(empty)
    not_str = _write(tmp_path, '{"a": 1}', "s.json")
    with pytest.raises(DepError, match="must be strings"):
        load_snapshot(not_str)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def test_render_report_sections():
    reqs = parse_requirements_file(BUNDLED_REQUIREMENTS)
    results = check_requirements(reqs, resolver=_resolver(load_snapshot()))
    text = render_report(results)
    assert "DEPENDENCY CHECK" in text
    assert "Status       :" in text
    assert "Severity     :" in text
    assert "Needs attention:" in text
    assert "acme-widget" in text


def test_render_report_orders_by_severity():
    results = [
        classify(Requirement("low-pkg", ""), "1.0"),
        classify(Requirement("high-pkg", "==1.0"), None),
        classify(Requirement("ok-pkg", ">=1"), "2.0"),
    ]
    text = render_report(results)
    positions = [text.index(n) for n in ("high-pkg", "low-pkg", "ok-pkg")]
    assert positions == sorted(positions), \
        "rows must be severity-ranked (high first)"


def test_render_report_no_attention_needed():
    results = [classify(Requirement("numpy", ">=1.0"), "2.5.2")]
    assert "(none)" in render_report(results)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_run_demo_direct(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK:" in out
    assert "Demo completed successfully." in out
    assert "PASS 1" in out and "PASS 2" in out


def test_run_demo_is_idempotent(capsys):
    assert run_demo() == 0
    assert run_demo() == 0
    assert capsys.readouterr().out.count("Demo completed successfully.") == 2


def test_run_demo_missing_bundled(tmp_path, monkeypatch):
    import depcheck
    monkeypatch.setattr(depcheck, "BUNDLED_REQUIREMENTS",
                        tmp_path / "nope.txt")
    with pytest.raises(DepError, match="bundled sample not found"):
        run_demo()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_demo_exits_zero(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Demo completed successfully." in out
    assert "Cross-checks OK:" in out


def test_cli_demo_quiet_prints_nothing(capsys):
    assert main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_demo_with_missing_bundle_still_exits_zero(tmp_path, monkeypatch,
                                                       capsys):
    import depcheck
    monkeypatch.setattr(depcheck, "BUNDLED_REQUIREMENTS",
                        tmp_path / "nope.txt")
    assert main(["--demo"]) == 0
    assert "Error:" in capsys.readouterr().err


def test_cli_file_check(capsys):
    assert main(["--file", str(BUNDLED_REQUIREMENTS)]) == 0
    out = capsys.readouterr().out
    assert "DEPENDENCY CHECK" in out and "Done." in out
    assert "acme-widget" in out


def test_cli_pyproject_check(capsys):
    assert main(["--file", str(BUNDLED_PYPROJECT)]) == 0
    assert "DEPENDENCY CHECK" in capsys.readouterr().out


def test_cli_json_output(tmp_path, capsys):
    out_json = tmp_path / "deps.json"
    code = main(["--file", str(BUNDLED_REQUIREMENTS),
                 "--json", str(out_json), "--quiet"])
    assert code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    # requirements.txt only: 2 ok, 2 conflict, 2 missing, 1 unpinned
    assert payload["status_counts"] == {"ok": 2, "conflict": 2,
                                        "missing": 2, "unpinned": 1}
    assert len(payload["results"]) == 7
    assert payload["severity_counts"]["high"] == 2   # scipy + acme-widget


def test_cli_missing_file(tmp_path, capsys):
    assert main(["--file", str(tmp_path / "nope.txt")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_invalid_requirements(tmp_path, capsys):
    bad = _write(tmp_path, "-e ./pkg\n", "req.txt")
    assert main(["--file", str(bad)]) == 2
    assert "editable installs" in capsys.readouterr().err


def test_cli_requires_action(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_cli_quiet_suppresses_report(capsys):
    assert main(["--file", str(BUNDLED_REQUIREMENTS), "--quiet"]) == 0
    assert "DEPENDENCY CHECK" not in capsys.readouterr().out


def test_build_parser_defaults():
    args = build_parser().parse_args(["--demo"])
    assert args.file is None
    assert not args.quiet
