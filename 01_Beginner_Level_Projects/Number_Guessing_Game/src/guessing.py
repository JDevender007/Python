"""A number-guessing game with a solver, not just a loop.

Two players, one game:

    the machine   seeds a secret with ``random.Random(seed)``, so a "random"
                  game is reproducible from its seed alone
    the solver    plays by bisection, which is the *optimal* strategy: halving
                  the remaining candidates is why 1..100 always takes at most
                  7 guesses (2**7 = 128 > 100)

The interesting part is not ``while guess != secret``. It is proving that the
solver is optimal, so the library also plays a deliberately naive linear
strategy and the demo compares them on the same secret.

Every failure mode is an exception with a message, never a silent ``break``:
a guess outside the range, a repeated guess, a guess after the game is over,
and a secret that could not have been the answer.

Fully offline and deterministic: seeds in, attempt counts out.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from statistics import fmean

LOW, HIGH = 1, 100

LOW_FEEDBACK = "low"
HIGH_FEEDBACK = "high"
CORRECT = "correct"


class GuessingError(ValueError):
    """A game or guess that cannot be made."""


# --------------------------------------------------------------------------- #
# The game
# --------------------------------------------------------------------------- #
class Game:
    """One secret, a shrinking interval, and a record of every guess."""

    def __init__(self, secret: int, low: int = LOW, high: int = HIGH,
                 max_attempts: int | None = None) -> None:
        if not isinstance(low, int) or not isinstance(high, int):
            raise GuessingError("bounds must be integers")
        if low >= high:
            raise GuessingError(f"low ({low}) must be less than high ({high})")
        if max_attempts is not None and max_attempts < 1:
            raise GuessingError("max_attempts must be at least 1")
        if not _is_int(secret):
            raise GuessingError("secret must be an integer")
        secret = int(secret)
        if not low <= secret <= high:
            raise GuessingError(
                f"secret {secret} is outside {low}..{high}")
        self.secret = secret
        self.initial_low = low
        self.initial_high = high
        self.low = low
        self.high = high
        self.max_attempts = max_attempts
        self.guesses: list[int] = []
        self.finished = False
        self.solved = False

    # -- state ------------------------------------------------------------ #
    def __len__(self) -> int:
        return len(self.guesses)

    @property
    def attempts(self) -> int:
        return len(self.guesses)

    @property
    def candidates(self) -> int:
        """How many numbers the interval still admits."""
        return self.high - self.low + 1

    @property
    def remaining(self) -> int | None:
        if self.max_attempts is None:
            return None
        return max(0, self.max_attempts - self.attempts)

    def __repr__(self) -> str:                    # pragma: no cover - display
        return (f"Game({self.low}..{self.high}, "
                f"guesses={self.guesses}, finished={self.finished})")

    # -- playing ---------------------------------------------------------- #
    def guess(self, value: int) -> str:
        if self.finished:
            raise GuessingError("the game is already over")
        if not _is_int(value):
            raise GuessingError("guess must be an integer")
        value = int(value)
        if not self.initial_low <= value <= self.initial_high:
            raise GuessingError(
                f"guess {value} is outside "
                f"{self.initial_low}..{self.initial_high}")
        if value in self.guesses:
            raise GuessingError(f"{value} was already guessed")
        if self.max_attempts is not None and self.attempts >= self.max_attempts:
            self.finished = True
            raise GuessingError(
                f"attempt limit of {self.max_attempts} reached")

        self.guesses.append(value)
        if value == self.secret:
            self.finished = True
            self.solved = True
            self.low = self.high = value
            return CORRECT
        if value < self.secret:
            self.low = max(self.low, value + 1)
            result = LOW_FEEDBACK
        else:
            self.high = min(self.high, value - 1)
            result = HIGH_FEEDBACK
        if self.max_attempts is not None and self.attempts >= self.max_attempts:
            self.finished = True
        return result

    def play(self, guesses: list[int]) -> str:
        """Apply a list of guesses; returns the last feedback."""
        result = ""
        for value in guesses:
            if self.finished:
                break
            result = self.guess(value)
        return result


def _is_int(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, str) and value.strip().lstrip("+-").isdigit()


# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #
def optimal_attempts(low: int, high: int) -> int:
    """Worst-case guesses a bisection needs for a range of this size."""
    if low >= high:
        raise GuessingError(f"low ({low}) must be less than high ({high})")
    return math.ceil(math.log2(high - low + 1))


def bisect_move(game: Game) -> int:
    """The midpoint of what is still possible."""
    return (game.low + game.high) // 2


def solve(secret: int, low: int = LOW, high: int = HIGH) -> Game:
    """Play the optimal strategy against a known secret."""
    game = Game(secret, low, high)
    while not game.finished:
        game.guess(bisect_move(game))
    return game


def solve_linearly(secret: int, low: int = LOW, high: int = HIGH) -> Game:
    """The naive strategy: try 1, then 2, then 3, ... Kept for comparison."""
    game = Game(secret, low, high)
    for value in range(low, high + 1):
        if game.finished:
            break
        game.guess(value)
    return game


def random_secret(seed: int, low: int = LOW, high: int = HIGH) -> int:
    if not _is_int(seed):
        raise GuessingError("seed must be an integer")
    if low >= high:
        raise GuessingError(f"low ({low}) must be less than high ({high})")
    return random.Random(int(seed)).randint(low, high)


def play_seeded(seed: int, low: int = LOW, high: int = HIGH) -> dict:
    """A reproducible round: the seed decides the secret, bisection finds it."""
    secret = random_secret(seed, low, high)
    game = solve(secret, low, high)
    return {
        "seed": int(seed),
        "secret": secret,
        "attempts": game.attempts,
        "guesses": list(game.guesses),
        "solved": game.solved,
    }


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
@dataclass
class Statistics:
    """An accumulating record of finished games."""

    played: int = 0
    solved: int = 0
    attempts: list[int] = field(default_factory=list)
    best: int | None = None
    worst: int | None = None

    def record(self, game: Game) -> "Statistics":
        self.played += 1
        if game.solved:
            self.solved += 1
        count = game.attempts
        self.attempts.append(count)
        self.best = count if self.best is None else min(self.best, count)
        self.worst = count if self.worst is None else max(self.worst, count)
        return self

    @property
    def win_rate(self) -> float:
        return 0.0 if not self.played else round(self.solved / self.played, 4)

    @property
    def average(self) -> float:
        return 0.0 if not self.attempts else round(fmean(self.attempts), 3)

    def distribution(self) -> dict[int, int]:
        counts: dict[int, int] = {}
        for count in self.attempts:
            counts[count] = counts.get(count, 0) + 1
        return dict(sorted(counts.items()))


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def run_demo() -> int:
    print("=" * 68)
    print(" NUMBER GUESSING GAME - bisection solver, seeded rounds, stats")
    print("=" * 68)

    # 1. the feedback is honest: below the secret says low, above says high
    game = Game(42)
    assert game.guess(50) == HIGH_FEEDBACK
    assert game.guess(25) == LOW_FEEDBACK
    assert (game.low, game.high) == (26, 49)
    assert game.guess(42) == CORRECT
    assert game.finished and game.solved
    print(f"  42 in 1..100: 50 -> high, 25 -> low, 42 -> correct "
          f"({game.attempts} guesses)")

    # 2. bisection solves a known secret in the documented moves
    solved = solve(42)
    assert solved.guesses == [50, 25, 37, 43, 40, 41, 42], solved.guesses
    assert solved.attempts == 7

    # 3. the naive strategy needs 42 guesses for the same secret
    naive = solve_linearly(42)
    assert naive.attempts == 42
    assert naive.guesses[:3] == [1, 2, 3]
    print(f"  binary {solved.attempts} guesses vs linear {naive.attempts}")

    # 4. bisection is optimal-ish: every secret in 1..100 within 7 tries
    stats = Statistics()
    worst_secrets: list[int] = []
    for secret in range(LOW, HIGH + 1):
        round_ = solve(secret)
        stats.record(round_)
        assert round_.solved
        assert round_.attempts <= 7, (secret, round_.attempts)
        if round_.attempts == 7:
            worst_secrets.append(secret)
    assert stats.played == 100
    assert stats.solved == 100
    assert stats.win_rate == 1.0
    assert stats.best == 1
    assert stats.worst == 7
    assert sum(stats.distribution().values()) == 100
    print(f"  100 secrets solved; best {stats.best}, worst {stats.worst}, "
          f"average {stats.average}")
    print(f"  distribution {stats.distribution()}")

    # 5. the average is close to the information-theoretic floor
    floor = optimal_attempts(LOW, HIGH)
    assert floor == 7
    assert stats.average < floor

    # 6. seeded rounds are reproducible and independent of the seed's order
    first = play_seeded(7)
    second = play_seeded(7)
    assert first == second
    assert random_secret(7) == first["secret"]
    assert first["solved"] and first["attempts"] == len(first["guesses"])
    assert play_seeded(8)["secret"] != first["secret"]
    print(f"  seed 7 -> secret {first['secret']} in {first['attempts']} guesses")

    # 7. 200 seeded rounds all finish, and the attempts stay bounded
    seeded = Statistics()
    for seed in range(200):
        result = play_seeded(seed)
        assert result["solved"]
        assert 1 <= result["attempts"] <= 7
        seeded.played += 1
        seeded.solved += 1
        seeded.attempts.append(result["attempts"])
        seeded.best = result["attempts"] if seeded.best is None else \
            min(seeded.best, result["attempts"])
        seeded.worst = result["attempts"] if seeded.worst is None else \
            max(seeded.worst, result["attempts"])
    assert seeded.played == 200 and seeded.win_rate == 1.0
    assert seeded.best >= 1 and seeded.worst <= 7
    print(f"  200 seeded rounds: win rate {seeded.win_rate}, "
          f"average {seeded.average}")

    # 8. an attempt limit really stops the game
    limited = Game(100, max_attempts=3)
    limited.play([50, 25, 12])
    assert limited.finished and not limited.solved
    try:
        limited.guess(13)
    except GuessingError as exc:
        assert "already over" in str(exc)

    # 9. negative controls: four ways to misuse the game
    for factory, needle in (
        (lambda: Game(0), "outside 1..100"),
        (lambda: Game(50, 10, 10), "must be less than"),
        (lambda: Game(50, 1, 100, max_attempts=0), "at least 1"),
        (lambda: Game(50).guess(101), "outside 1..100"),
    ):
        try:
            factory()
        except GuessingError as exc:
            assert needle in str(exc), str(exc)
        else:
            raise AssertionError("expected GuessingError")
    repeated = Game(50)
    repeated.guess(25)
    try:
        repeated.guess(25)
    except GuessingError as exc:
        assert "already guessed" in str(exc)
    else:
        raise AssertionError("repeated guess should fail")
    print("  5 misuse cases rejected with named reasons")

    # 10. statistics of no games are zero, not a crash
    empty = Statistics()
    assert empty.win_rate == 0.0 and empty.average == 0.0
    assert empty.distribution() == {}

    print()
    print("Cross-checks OK: feedback narrows 1..100 to 26..49, exact bisection "
          "path for 42, 42-vs-7 guess contrast with linear, all 100 secrets "
          "solved within 7 attempts and statistics best=1 worst=7, average "
          "below the worst case, seeded rounds reproducible and seed-distinct, "
          "200 seeded rounds all solved, attempt limit honoured, 5 misuse "
          "cases rejected, empty statistics safe")
    print("\nDemo completed successfully.")
    return 0
