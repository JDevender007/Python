"""
strength.py

Evaluates password strength.
"""

import string

class PasswordStrength:
    """Password strength evaluator."""

    @staticmethod
    def calculate(password: str) -> tuple[int, str]:
        """
        Calculate password strength.

        Returns:
            (score, rating)
        """

        score = 0

        # Length
        if len(password) >= 8:
            score += 1

        if len(password) >= 12:
            score += 1

        # Lowercase
        if any(character.islower() for character in password):
            score += 1

        # Uppercase
        if any(character.isupper() for character in password):
            score += 1

        # Digits
        if any(character.isdigit() for character in password):
            score += 1

        # Symbols
        if any(character in string.punctuation for character in password):
            score += 1

        # Rating
        if score <= 2:
            rating = "Weak"

        elif score <= 4:
            rating = "Medium"

        elif score == 5:
            rating = "Strong"

        else:
            rating = "Very Strong"

        return score, rating

    @staticmethod
    def display(score: int, rating: str) -> None:
        """
        Display password strength.
        """

        print("\nPassword Strength")
        print("-" * 20)

        print(f"Score  : {score}/6")
        print(f"Rating : {rating}")