"""
game.py

Core game logic for the Number Guessing Game.
"""

import random

class NumberGuessingGame:
    """Generate and validate the secret number."""

    def __init__(self, minimum: int, maximum: int):
        """
        Initialize the game.

        Args:
            minimum: Minimum possible number.
            maximum: Maximum possible number.
        """

        self.minimum = minimum
        self.maximum = maximum
        self.secret_number = random.randint(
            self.minimum,
            self.maximum,
        )

    def check_guess(self, guess: int) -> str:
        """
        Compare the player's guess with the secret number.

        Returns:
            'high' if guess is too high.
            'low' if guess is too low.
            'correct' if guess is correct.
        """

        if guess > self.secret_number:
            return "high"

        if guess < self.secret_number:
            return "low"

        return "correct"

    def reveal(self) -> int:
        """
        Return the secret number.
        """

        return self.secret_number