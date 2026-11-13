"""Tests for Number_Guessing_Game: game rules, solver, seeds, statistics."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))

import guessing                                         # noqa: E402
import main as cli                                      # noqa: E402
from guessing import (                                  # noqa: E402
    CORRECT,
    HIGH_FEEDBACK,
    LOW,
    HIGH,
    LOW_FEEDBACK,
    Game,
    GuessingError,
    Statistics,
    bisect_move,
    optimal_attempts,
    play_seeded,
    random_secret,
    run_demo,
    solve,
    solve_linearly,
)


# --------------------------------------------------------------------------- #
# Game rules
# --------------------------------------------------------------------------- #
def test_guess_below_the_secret_returns_low():
    assert Game(42).guess(20) == LOW_FEEDBACK


def test_guess_above_the_secret_returns_high():
    assert Game(42).guess(80) == HIGH_FEEDBACK


def test_correct_guess_finishes_the_game():
    game = Game(42)
    assert game.guess(42) == CORRECT
    assert game.finished and game.solved
    assert game.attempts == 1


def test_feedback_narrows_the_interval():
    game = Game(42)
    game.guess(50)
    assert (game.low, game.high) == (1, 49)
    game.guess(25)
    assert (game.low, game.high) == (26, 49)
    assert game.candidates == 24


def test_correct_guess_collapses_the_interval():
    game = Game(42)
    game.guess(42)
    assert (game.low, game.high) == (42, 42)
    assert game.candidates == 1


def test_len_counts_guesses():
    game = Game(42)
    game.guess(10)
    game.guess(20)
    assert len(game) == 2


def test_repr_mentions_the_interval():
    assert "1..100" in repr(Game(42))


def test_play_helper_runs_until_finished():
    game = Game(42)
    assert game.play([50, 25, 37, 43, 40, 41, 42]) == CORRECT
    assert game.attempts == 7
    assert game.play([99]) == ""               # no-op once finished


def test_guess_after_the_game_is_over():
    game = Game(42)
    game.guess(42)
    with pytest.raises(GuessingError, match="already over"):
        game.guess(41)


def test_repeated_guess_is_rejected():
    game = Game(42)
    game.guess(25)
    with pytest.raises(GuessingError, match="already guessed"):
        game.guess(25)


def test_guess_outside_the_range_is_rejected():
    with pytest.raises(GuessingError, match=r"outside 1\.\.100"):
        Game(42).guess(101)
    with pytest.raises(GuessingError, match=r"outside 1\.\.100"):
        Game(42).guess(0)


def test_non_integer_guess_is_rejected():
    with pytest.raises(GuessingError, match="must be an integer"):
        Game(42).guess(4.5)                             # type: ignore[arg-type]


def test_boolean_guess_is_rejected():
    with pytest.raises(GuessingError, match="must be an integer"):
        Game(42).guess(True)                            # type: ignore[arg-type]


def test_numeric_string_is_accepted():
    assert Game(42).guess("42") == CORRECT


def test_secret_outside_the_range_is_rejected():
    with pytest.raises(GuessingError, match="secret 0 is outside"):
        Game(0)
    with pytest.raises(GuessingError, match="secret 101 is outside"):
        Game(101)


def test_low_must_be_less_than_high():
    with pytest.raises(GuessingError, match="must be less than"):
        Game(5, 10, 10)


def test_non_integer_bounds_are_rejected():
    with pytest.raises(GuessingError, match="bounds must be integers"):
        Game(5, 1.0, 10)                                # type: ignore[arg-type]


def test_attempt_limit_must_be_positive():
    with pytest.raises(GuessingError, match="at least 1"):
        Game(42, max_attempts=0)


def test_attempt_limit_ends_the_game():
    game = Game(100, max_attempts=2)
    game.guess(50)
    game.guess(25)
    assert game.finished and not game.solved
    assert game.remaining == 0
    with pytest.raises(GuessingError, match="already over"):
        game.guess(13)


def test_remaining_is_none_without_a_limit():
    assert Game(42).remaining is None
    assert Game(42, max_attempts=5).remaining == 5


# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #
def test_bisect_move_is_the_midpoint():
    game = Game(42)
    assert bisect_move(game) == 50
    game.guess(50)
    assert bisect_move(game) == 25


def test_solve_path_for_42():
    game = solve(42)
    assert game.guesses == [50, 25, 37, 43, 40, 41, 42]
    assert game.attempts == 7


def test_solve_finds_the_edges():
    assert solve(1).attempts == 6
    assert solve(100).attempts == 7
    assert all(game.solved for game in (solve(1), solve(100)))


def test_solve_small_range():
    assert solve(2, 1, 3).attempts == 1
    assert solve(3, 1, 3).attempts == 2
    assert solve(1, 1, 2).attempts == 1


def test_solve_linearly_takes_one_guess_per_candidate():
    assert solve_linearly(42).attempts == 42
    assert solve_linearly(1).attempts == 1
    assert solve_linearly(100).attempts == 100


def test_optimal_attempts_formula():
    assert optimal_attempts(1, 100) == 7
    assert optimal_attempts(1, 2) == 1
    assert optimal_attempts(1, 3) == 2


def test_optimal_attempts_rejects_bad_range():
    with pytest.raises(GuessingError, match="must be less than"):
        optimal_attempts(5, 5)


def test_every_secret_in_range_is_solved_within_the_bound():
    for secret in range(LOW, HIGH + 1):
        game = solve(secret)
        assert game.solved
        assert game.attempts <= optimal_attempts(LOW, HIGH)


def test_solver_beats_linear_for_most_of_the_range():
    for secret in (10, 42, 73, 99):
        assert solve(secret).attempts < solve_linearly(secret).attempts


# --------------------------------------------------------------------------- #
# Seeds
# --------------------------------------------------------------------------- #
def test_random_secret_is_reproducible():
    assert random_secret(7) == random_secret(7)


def test_different_seeds_differ():
    assert random_secret(7) != random_secret(8)


def test_random_secret_is_inside_the_range():
    for seed in range(50):
        assert LOW <= random_secret(seed) <= HIGH


def test_random_secret_validates_its_input():
    with pytest.raises(GuessingError, match="seed must be an integer"):
        random_secret("seven")                          # type: ignore[arg-type]
    with pytest.raises(GuessingError, match="must be less than"):
        random_secret(1, 5, 5)


def test_play_seeded_returns_a_full_round():
    result = play_seeded(7)
    assert result["secret"] == 42
    assert result["attempts"] == len(result["guesses"])
    assert result["solved"] is True
    assert result["guesses"][-1] == result["secret"]


def test_play_seeded_is_reproducible():
    assert play_seeded(7) == play_seeded(7)


def test_bundled_rounds_match_recomputation():
    rows = json.loads((PROJECT / "data" / "rounds.json").read_text(
        encoding="utf-8"))
    assert len(rows) == 10
    for row in rows:
        assert play_seeded(row["seed"]) == row


def test_two_hundred_seeded_rounds_all_solve():
    for seed in range(200):
        result = play_seeded(seed)
        assert result["solved"]
        assert 1 <= result["attempts"] <= 7


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def test_statistics_start_empty():
    stats = Statistics()
    assert stats.played == 0
    assert stats.win_rate == 0.0
    assert stats.average == 0.0
    assert stats.distribution() == {}


def test_statistics_record_solved_games():
    stats = Statistics()
    stats.record(solve(50)).record(solve(42))
    assert stats.played == 2
    assert stats.solved == 2
    assert stats.win_rate == 1.0
    assert stats.best == 1
    assert stats.worst == 7


def test_statistics_count_unsolved_games():
    stats = Statistics()
    lost = Game(100, max_attempts=1)
    lost.guess(50)
    stats.record(lost)
    assert stats.played == 1
    assert stats.solved == 0
    assert stats.win_rate == 0.0


def test_statistics_distribution_sums_to_played():
    stats = Statistics()
    for secret in range(1, 101):
        stats.record(solve(secret))
    assert sum(stats.distribution().values()) == 100
    assert stats.distribution() == {1: 1, 2: 2, 3: 4, 4: 8,
                                    5: 16, 6: 32, 7: 37}


def test_statistics_average_is_a_mean():
    stats = Statistics()
    stats.record(solve(50)).record(solve(1)).record(solve(100))
    assert stats.average == pytest.approx(round((1 + 7 + 6) / 3, 3))


# --------------------------------------------------------------------------- #
# Demo and CLI
# --------------------------------------------------------------------------- #
def test_demo_returns_zero(capsys):
    assert run_demo() == 0
    out = capsys.readouterr().out
    assert "Cross-checks OK" in out
    assert "Demo completed successfully." in out


def test_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    run_demo()
    assert capsys.readouterr().out == first


def test_cli_demo(capsys):
    assert cli.main(["--demo"]) == 0
    assert "Demo completed successfully." in capsys.readouterr().out


def test_cli_demo_quiet(capsys):
    assert cli.main(["--demo", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_cli_default_secret(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "secret 42" in out
    assert "solved in 7 guess(es)" in out


def test_cli_explicit_secret(capsys):
    assert cli.main(["--secret", "73"]) == 0
    out = capsys.readouterr().out
    assert "secret 73" in out


def test_cli_seed_mode(capsys):
    assert cli.main(["--seed", "7"]) == 0
    out = capsys.readouterr().out
    assert "secret 42" in out


def test_cli_linear_strategy(capsys):
    assert cli.main(["--secret", "5", "--strategy", "linear"]) == 0
    out = capsys.readouterr().out
    assert "solved in 5 guess(es)" in out


def test_cli_custom_range(capsys):
    assert cli.main(["--low", "1", "--high", "1000", "--secret", "999"]) == 0
    out = capsys.readouterr().out
    assert "worst case is 10" in out


def test_cli_transcript_shows_feedback(capsys):
    assert cli.main(["--secret", "42"]) == 0
    out = capsys.readouterr().out
    assert "guess     50  high" in out
    assert "correct" in out


def test_cli_json_output(tmp_path, capsys):
    target = tmp_path / "round.json"
    assert cli.main(["--secret", "42", "--json", str(target)]) == 0
    capsys.readouterr()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["secret"] == 42
    assert payload["attempts"] == 7
    assert payload["steps"][0] == {"guess": 50, "feedback": "high",
                                   "range": "1..49"}


def test_cli_bad_secret_exits_two(capsys):
    assert cli.main(["--secret", "500"]) == 2
    assert "outside 1..100" in capsys.readouterr().err


def test_cli_bad_range_exits_two(capsys):
    assert cli.main(["--low", "10", "--high", "10"]) == 2
    assert "must be less than" in capsys.readouterr().err


def test_cli_quiet_prints_nothing(capsys):
    assert cli.main(["--secret", "42", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
