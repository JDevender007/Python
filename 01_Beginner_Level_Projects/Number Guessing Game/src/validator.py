"""
validator.py

Input validation for the Number Guessing Game.
"""

class InputValidator:
    """Validate user input."""

    @staticmethod
    def get_menu_choice() -> int:
        """
        Get the game difficulty.
        """

        while True:

            try:

                print("\nSelect Difficulty")
                print("1. Easy")
                print("2. Medium")
                print("3. Hard")

                choice = int(input("\nChoice: "))

                if choice in (1, 2, 3):
                    return choice

                print("Please enter 1, 2 or 3.")

            except ValueError:
                print("Enter a valid number.")

    @staticmethod
    def get_guess(minimum: int, maximum: int) -> int:
        """
        Read and validate the player's guess.
        """

        while True:

            try:

                guess = int(
                    input(f"Enter your guess ({minimum}-{maximum}): ")
                )

                if minimum <= guess <= maximum:
                    return guess

                print(
                    f"Please enter a number between {minimum} and {maximum}."
                )

            except ValueError:
                print("Enter a valid integer.")