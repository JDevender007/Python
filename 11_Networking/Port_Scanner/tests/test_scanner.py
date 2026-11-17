"""Tests for the scan lab: three states, evidence strength and latency."""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

import main as cli  # noqa: E402
import scanner  # noqa: E402
from scanner import (  # noqa: E402
    LEGACY_CLASSIFY,
    LEGACY_LATENCY,
    SERVICES,
    STATE_OF,
    STRENGTH,
    Policy,
    Probe,
    ScanError,
    Verdict,
    answered_latency_ms,
    audit,
    check_attempts,
    classify,
    divide_half_up,
    is_port,
    legacy_closed,
    legacy_latency_ms,
    load_policy,
    load_probes,
    measure,
    outcome_of,
    ports_by_state,
    render_verdicts,
    report,
    require_answer_latency,
    require_attempts,
    require_port,
    require_timeout_latency,
    retried_ports,
    run_demo,
    state_counts,
    strongest,
    wait_ms,
)

POLICY = Policy(timeout_ms=800, retries=2)


def probe(port: int, attempt: int, outcome: str, latency: int) -> Probe:
    return Probe(port=port, attempt=attempt, outcome=outcome, latency_ms=latency)


# --------------------------------------------------------------------------- #
# arithmetic and validation helpers
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "top,bottom,expected", [(111, 10, 11), (4911, 16, 307), (5, 2, 3), (1, 3, 0),
                            (2, 3, 1), (-5, 2, -3), (0, 7, 0)]
)
def test_divide_half_up(top, bottom, expected):
    assert divide_half_up(top, bottom) == expected


@pytest.mark.parametrize("bottom", [0, -1])
def test_divide_half_up_refuses_bad_denominators(bottom):
    with pytest.raises(ScanError, match="denominator must be positive"):
        divide_half_up(1, bottom)


@pytest.mark.parametrize("bad", [True, 1.5, "10"])
def test_divide_half_up_refuses_non_integers(bad):
    with pytest.raises(ScanError, match="must be an integer"):
        divide_half_up(bad, 2)


@pytest.mark.parametrize("port", [1, 22, 443, 65535])
def test_real_ports_are_accepted(port):
    assert is_port(port) is True
    assert require_port(port) == port


@pytest.mark.parametrize("port", [0, -1, 65536, "22", True, None, 22.0])
def test_impossible_ports_are_refused(port):
    assert is_port(port) is False
    with pytest.raises(ScanError, match="1..65535"):
        require_port(port)


@pytest.mark.parametrize("text,expected", [("open", "open"), (" TIMEOUT ", "timeout")])
def test_outcome_of_normalises(text, expected):
    assert outcome_of(text) == expected


@pytest.mark.parametrize("text", ["", "closed", "filtered", "rst"])
def test_outcome_of_refuses_anything_else(text):
    with pytest.raises(ScanError):
        outcome_of(text)


def test_each_outcome_maps_to_its_own_state():
    assert STATE_OF == {"open": "open", "refused": "closed", "timeout": "filtered"}


def test_evidence_is_ordered_open_refused_timeout():
    assert STRENGTH["open"] > STRENGTH["refused"] > STRENGTH["timeout"]


# --------------------------------------------------------------------------- #
# policy
# --------------------------------------------------------------------------- #
def test_load_policy_reads_the_bundled_file():
    policy = load_policy()
    assert (policy.timeout_ms, policy.retries) == (800, 2)


def test_load_policy_refuses_a_missing_file(tmp_path):
    with pytest.raises(ScanError, match="file not found"):
        load_policy(tmp_path / "nope.csv")


def test_load_policy_refuses_two_rows(tmp_path):
    path = tmp_path / "policy.csv"
    path.write_text("timeout_ms,retries\n800,2\n900,2\n", encoding="utf-8")
    with pytest.raises(ScanError, match="exactly one row"):
        load_policy(path)


@pytest.mark.parametrize("body", ["0,2\n", "800,0\n", "800,6\n"])
def test_load_policy_refuses_impossible_values(tmp_path, body):
    path = tmp_path / "policy.csv"
    path.write_text("timeout_ms,retries\n" + body, encoding="utf-8")
    with pytest.raises(ScanError):
        load_policy(path)


def test_load_policy_refuses_a_missing_column(tmp_path):
    path = tmp_path / "policy.csv"
    path.write_text("timeout_ms\n800\n", encoding="utf-8")
    with pytest.raises(ScanError, match="missing column"):
        load_policy(path)


# --------------------------------------------------------------------------- #
# probes
# --------------------------------------------------------------------------- #
def test_load_probes_reads_the_bundled_scan():
    probes = load_probes(policy=POLICY)
    assert len(probes) == 16
    assert [p.port for p in probes][:4] == [21, 22, 23, 23]
    assert probes[0] == probe(21, 1, "refused", 4)
    assert probes[-1] == probe(8443, 2, "open", 26)


def test_load_probes_refuses_a_missing_file(tmp_path):
    with pytest.raises(ScanError, match="file not found"):
        load_probes(tmp_path / "nope.csv", policy=POLICY)


def test_load_probes_refuses_an_empty_scan(tmp_path):
    path = tmp_path / "scan.csv"
    path.write_text("port,attempt,outcome,latency_ms\n", encoding="utf-8")
    with pytest.raises(ScanError, match="holds no probes"):
        load_probes(path, policy=POLICY)


def test_load_probes_refuses_an_unknown_outcome(tmp_path):
    path = tmp_path / "scan.csv"
    path.write_text("port,attempt,outcome,latency_ms\n22,1,reset,3\n", encoding="utf-8")
    with pytest.raises(ScanError, match="outcome must be one of"):
        load_probes(path, policy=POLICY)


def test_load_probes_refuses_an_out_of_range_port(tmp_path):
    path = tmp_path / "scan.csv"
    path.write_text("port,attempt,outcome,latency_ms\n70000,1,open,3\n", encoding="utf-8")
    with pytest.raises(ScanError, match="1..65535"):
        load_probes(path, policy=POLICY)


def test_load_probes_refuses_a_negative_latency(tmp_path):
    path = tmp_path / "scan.csv"
    path.write_text("port,attempt,outcome,latency_ms\n22,1,open,-3\n", encoding="utf-8")
    with pytest.raises(ScanError, match="must not be negative"):
        load_probes(path, policy=POLICY)


def test_load_probes_refuses_a_timeout_that_returned_early(tmp_path):
    path = tmp_path / "scan.csv"
    path.write_text("port,attempt,outcome,latency_ms\n22,1,timeout,4\n", encoding="utf-8")
    with pytest.raises(ScanError, match="is not a timeout"):
        load_probes(path, policy=POLICY)


def test_load_probes_refuses_an_answer_at_the_timeout(tmp_path):
    path = tmp_path / "scan.csv"
    path.write_text("port,attempt,outcome,latency_ms\n22,1,open,800\n", encoding="utf-8")
    with pytest.raises(ScanError, match="is not before"):
        load_probes(path, policy=POLICY)


def test_load_probes_refuses_a_late_first_attempt(tmp_path):
    path = tmp_path / "scan.csv"
    path.write_text("port,attempt,outcome,latency_ms\n22,2,open,4\n", encoding="utf-8")
    with pytest.raises(ScanError, match="not 1..n"):
        load_probes(path, policy=POLICY)


def test_load_probes_refuses_a_gap_in_attempts(tmp_path):
    path = tmp_path / "scan.csv"
    path.write_text(
        "port,attempt,outcome,latency_ms\n22,1,timeout,800\n22,3,open,4\n",
        encoding="utf-8",
    )
    with pytest.raises(ScanError, match="not 1..n"):
        load_probes(path, policy=POLICY)


def test_load_probes_refuses_more_attempts_than_the_policy(tmp_path):
    path = tmp_path / "scan.csv"
    path.write_text(
        "port,attempt,outcome,latency_ms\n"
        "22,1,timeout,800\n22,2,timeout,800\n22,3,open,4\n",
        encoding="utf-8",
    )
    with pytest.raises(ScanError, match="exceed the policy"):
        load_probes(path, policy=POLICY)


def test_require_timeout_latency_accepts_the_policy_wait():
    assert require_timeout_latency(800, 800) == 800


def test_require_timeout_latency_refuses_a_fast_timeout():
    with pytest.raises(ScanError, match="is not a timeout"):
        require_timeout_latency(800, 799)


def test_require_answer_latency_accepts_an_early_answer():
    assert require_answer_latency(800, 799) == 799


def test_require_answer_latency_refuses_a_late_answer():
    with pytest.raises(ScanError, match="is not before"):
        require_answer_latency(800, 800)


def test_require_attempts_accepts_one_and_two():
    assert require_attempts(POLICY, [2, 1]) == [1, 2]


def test_require_attempts_refuses_a_gap():
    with pytest.raises(ScanError, match="not 1..n"):
        require_attempts(Policy(800, 3), [1, 3])


def test_require_attempts_refuses_too_many():
    with pytest.raises(ScanError, match="exceed the policy"):
        require_attempts(POLICY, [1, 2, 3])


def test_check_attempts_refuses_a_duplicate():
    with pytest.raises(ScanError, match="not 1..n"):
        check_attempts([probe(22, 1, "open", 3), probe(22, 1, "open", 3)], POLICY)


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
def test_strongest_evidence_wins():
    assert strongest([probe(8443, 1, "timeout", 800), probe(8443, 2, "open", 26)]).outcome == "open"
    assert strongest([probe(1, 1, "timeout", 800), probe(1, 2, "refused", 5)]).outcome == "refused"


def test_strongest_breaks_a_tie_with_the_later_attempt():
    rows = [probe(1, 1, "refused", 5), probe(1, 2, "refused", 6)]
    assert strongest(rows).attempt == 2


def test_strongest_refuses_an_empty_group():
    with pytest.raises(ScanError, match="at least one probe"):
        strongest([])


def test_classify_returns_one_verdict_per_port_in_order():
    verdicts = classify(load_probes(policy=POLICY))
    assert [verdict.port for verdict in verdicts] == [
        21, 22, 23, 25, 53, 80, 110, 143, 443, 3306, 5432, 8080, 8443
    ]
    assert len(verdicts) == 13


def test_classify_pins_the_three_states():
    verdicts = classify(load_probes(policy=POLICY))
    grouped = ports_by_state(verdicts)
    assert grouped["open"] == [22, 80, 443, 8443]
    assert grouped["closed"] == [21, 25, 110, 143, 3306, 8080]
    assert grouped["filtered"] == [23, 53, 5432]


def test_a_retried_port_keeps_the_attempt_count():
    verdicts = {verdict.port: verdict for verdict in classify(load_probes(policy=POLICY))}
    assert verdicts[23].attempts == 2
    assert verdicts[23].state == "filtered"
    assert verdicts[8443].attempts == 2
    assert verdicts[8443].state == "open"
    assert verdicts[22].attempts == 1


def test_a_filtered_verdict_has_not_answered():
    verdicts = {verdict.port: verdict for verdict in classify(load_probes(policy=POLICY))}
    assert verdicts[23].answered is False
    assert verdicts[21].answered is True
    assert verdicts[22].answered is True


def test_state_counts_adds_up_to_the_ports():
    counts = state_counts(classify(load_probes(policy=POLICY)))
    assert counts == {"open": 4, "closed": 6, "filtered": 3}
    assert sum(counts.values()) == 13


def test_state_counts_refuses_an_unknown_state():
    with pytest.raises(ScanError, match="unknown state"):
        state_counts([Verdict(1, "unknown", 1, "open")])


# --------------------------------------------------------------------------- #
# the legacy reports
# --------------------------------------------------------------------------- #
def test_legacy_calls_everything_not_open_closed():
    probes = load_probes(policy=POLICY)
    verdicts = classify(probes)
    assert legacy_closed(verdicts, probes) == [21, 23, 25, 53, 110, 143, 3306, 5432, 8080]
    assert len(legacy_closed(verdicts, probes)) == 9


def test_legacy_hides_the_three_filtered_ports():
    probes = load_probes(policy=POLICY)
    filtered = ports_by_state(classify(probes))["filtered"]
    assert set(filtered) <= set(legacy_closed(classify(probes), probes))


def test_retried_ports_are_the_ones_with_two_attempts():
    assert retried_ports(load_probes(policy=POLICY)) == [23, 5432, 8443]


def test_retried_ports_of_a_single_pass_scan_is_empty():
    assert retried_ports([probe(22, 1, "open", 3)]) == []


def test_answered_latency_ignores_timeouts():
    assert answered_latency_ms(load_probes(policy=POLICY)) == 11


def test_answered_latency_is_zero_without_answers():
    assert answered_latency_ms([probe(23, 1, "timeout", 800)]) == 0


def test_legacy_latency_counts_the_waiting():
    assert legacy_latency_ms(load_probes(policy=POLICY)) == 307


def test_the_two_latencies_differ_by_the_waiting_divided_out():
    probes = load_probes(policy=POLICY)
    assert legacy_latency_ms(probes) - answered_latency_ms(probes) == 296


def test_wait_ms_sums_only_the_timeouts():
    assert wait_ms(load_probes(policy=POLICY)) == 4800


# --------------------------------------------------------------------------- #
# measure and report
# --------------------------------------------------------------------------- #
def test_measure_pins_the_seed():
    measured = measure()
    assert len(measured["probes"]) == 16
    assert len(measured["verdicts"]) == 13
    assert measured["counts"] == {"open": 4, "closed": 6, "filtered": 3}
    assert measured["answered_ms"] == 11
    assert measured["legacy_ms"] == 307
    assert measured["wait_ms"] == 4800
    assert measured["timeouts"] == 6
    assert measured["retried"] == [23, 5432, 8443]


def test_measure_reads_the_policy_beside_the_scan(tmp_path):
    (tmp_path / "policy.csv").write_text("timeout_ms,retries\n100,1\n", encoding="utf-8")
    (tmp_path / "scan.csv").write_text(
        "port,attempt,outcome,latency_ms\n22,1,open,7\n23,1,timeout,100\n", encoding="utf-8"
    )
    measured = measure(tmp_path / "scan.csv")
    assert measured["counts"] == {"open": 1, "closed": 0, "filtered": 1}
    assert measured["answered_ms"] == 7


def test_measure_accepts_an_explicit_policy_path(tmp_path):
    (tmp_path / "scan.csv").write_text(
        "port,attempt,outcome,latency_ms\n22,1,open,7\n", encoding="utf-8"
    )
    other = tmp_path / "other_policy.csv"
    other.write_text("timeout_ms,retries\n50,2\n", encoding="utf-8")
    measured = measure(tmp_path / "scan.csv", policy_path=other)
    assert measured["policy"].timeout_ms == 50
    assert measured["counts"] == {"open": 1, "closed": 0, "filtered": 0}


def test_report_is_json_safe():
    payload = report(measure())
    text = json.dumps(payload, sort_keys=True)
    assert "Policy(" not in text
    assert payload["ports"] == 13
    assert payload["probes"] == 16
    assert payload["open"] == [22, 80, 443, 8443]
    assert payload["filtered"] == [23, 53, 5432]
    assert payload["legacy_closed_count"] == 9
    assert payload["answered_ms"] == 11
    assert payload["legacy_ms"] == 307
    assert payload["verdicts"][2] == {
        "port": 23, "state": "filtered", "attempts": 2, "evidence": "timeout"
    }


def test_render_verdicts_names_the_services():
    rendered = render_verdicts(measure())
    assert "22     ssh" in rendered
    assert "8443   https-alt" in rendered
    assert "filtered" in rendered
    assert "13 ports" in rendered


def test_every_service_name_is_a_known_port():
    assert sorted(SERVICES) == [21, 22, 23, 25, 53, 80, 110, 143, 443, 3306, 5432, 8080, 8443]


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
def test_audit_passes_every_check():
    results = audit(measure())
    assert len(results) == 18
    assert all(ok for _, ok in results)


def test_audit_names_are_unique():
    names = [name for name, _ in audit(measure())]
    assert len(names) == len(set(names))


def test_audit_negative_control_collapsing_classifier():
    def collapsing(probes):
        rows = []
        for verdict in classify(probes):
            state = "closed" if verdict.state == "filtered" else verdict.state
            rows.append(Verdict(verdict.port, state, verdict.attempts, verdict.evidence))
        return rows

    results = dict(audit(measure(), read_verdicts=collapsing))
    assert results["counts_match_an_independent_tally"] is False
    assert results["the_three_states_are_all_represented"] is True


def test_audit_negative_control_classifier_that_merges_ports():
    def merged(probes):
        return classify(probes)[:-1]

    results = dict(audit(measure(), read_verdicts=merged))
    assert results["every_port_gets_exactly_one_verdict"] is False
    assert results["counts_match_an_independent_tally"] is False


def test_audit_negative_control_classifier_that_raises():
    def broken(probes):
        raise ScanError("boom")

    results = dict(audit(measure(), read_verdicts=broken))
    assert results["every_port_gets_exactly_one_verdict"] is False
    assert results["rebuild_is_deterministic"] is False


def test_audit_detects_a_tampered_count():
    measured = measure()
    measured["counts"] = {"open": 4, "closed": 9, "filtered": 0}
    assert dict(audit(measured))["the_three_states_are_all_represented"] is False


def test_audit_detects_a_tampered_by_state_list():
    measured = measure()
    measured["by_state"] = {"open": [22, 80, 443], "closed": [], "filtered": [23, 53, 5432]}
    assert dict(audit(measured))["the_open_ports_are_pinned"] is False


def test_audit_detects_a_tampered_legacy_closed_list():
    measured = measure()
    measured["legacy_closed"] = [21, 23, 25]
    assert dict(audit(measured))["the_legacy_report_collapses_filtered_into_closed"] is False


def test_audit_detects_a_tampered_latency():
    measured = measure()
    measured["answered_ms"] = 12
    results = dict(audit(measured))
    assert results["the_answered_latency_is_pinned"] is False
    assert results["the_legacy_latency_counts_the_waiting"] is False


def test_audit_detects_a_tampered_wait():
    measured = measure()
    measured["wait_ms"] = 4000
    assert dict(audit(measured))["a_timeout_is_not_a_latency"] is False


def test_audit_detects_a_tampered_retry_list():
    measured = measure()
    measured["retried"] = [23]
    assert dict(audit(measured))["only_three_ports_were_retried"] is False


# --------------------------------------------------------------------------- #
# demo and CLI
# --------------------------------------------------------------------------- #
def test_run_demo_returns_zero_and_ends_with_the_contract(capsys):
    assert run_demo() == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == "Demo completed successfully."
    assert lines[-2].startswith("Cross-checks OK: ")


def test_run_demo_is_byte_identical(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    second = capsys.readouterr().out
    assert first == second


def test_demo_prints_the_pinned_numbers(capsys):
    run_demo()
    out = capsys.readouterr().out
    assert "here: 4 open, 6 closed, 3 filtered" in out
    assert "legacy: 4 open, 9 closed, 0 filtered" in out
    assert "answered probes average 11 ms over 10 responses" in out
    assert "the legacy average is 307 ms" in out
    assert "18/18 checks pass" in out
    assert "FAIL" not in out


def test_demo_is_ascii_and_silent_on_stderr():
    err = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(err):
        run_demo()
    assert err.getvalue() == ""


def test_the_legacy_snippets_are_kept_as_text():
    assert "set(ports) - open_ports" in LEGACY_CLASSIFY
    assert "round(sum(row.latency_ms" in LEGACY_LATENCY


def test_cli_demo_exits_zero():
    assert cli.main(["--demo"]) == 0


def test_cli_demo_quiet_prints_nothing(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_json_writes_a_report(tmp_path):
    target = tmp_path / "report.json"
    assert cli.main(["--json", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["counts"] == {"open": 4, "closed": 6, "filtered": 3}
    assert payload["legacy_closed_count"] == 9


def test_cli_json_creates_the_parent_folder(tmp_path):
    target = tmp_path / "nested" / "report.json"
    assert cli.main(["--json", str(target)]) == 0
    assert target.is_file()


def test_cli_audit_passes():
    assert cli.main(["--audit"]) == 0


def test_cli_missing_file_exits_two(capsys):
    assert cli.main(["--file", "no/such/scan.csv"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_early_timeout_exits_two(tmp_path, capsys):
    folder = tmp_path / "seeds"
    folder.mkdir()
    (folder / "policy.csv").write_text("timeout_ms,retries\n800,2\n", encoding="utf-8")
    (folder / "scan.csv").write_text(
        "port,attempt,outcome,latency_ms\n23,1,timeout,4\n", encoding="utf-8"
    )
    assert cli.main(["--file", str(folder / "scan.csv")]) == 2
    assert "not a timeout" in capsys.readouterr().err


def test_cli_prints_the_summary(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "4 open, 6 closed, 3 filtered; legacy calls 9 closed" in out


def test_cli_quiet_json_still_writes(tmp_path):
    target = tmp_path / "quiet.json"
    assert cli.main(["--quiet", "--json", str(target)]) == 0
    assert target.is_file()


def test_module_exposes_the_state_table():
    assert scanner.STATE_OF is STATE_OF
