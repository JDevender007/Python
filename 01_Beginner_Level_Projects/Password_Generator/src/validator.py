"""
validator.py

Handles all user input validation.
"""

class InputValidator:
    """Validate user inputs."""

    MIN_LENGTH = 4
    MAX_LENGTH = 64

    @staticmethod
    def get_password_length() -> int:
        """
        Ask the user for a valid password length.
        """

        while True:

            value = input(
                f"Password Length ({InputValidator.MIN_LENGTH}-{InputValidator.MAX_LENGTH}): "
            ).strip()

            if not value.isdigit():
                print("Error: Enter numbers only.\n")
                continue

            length = int(value)

            if length < InputValidator.MIN_LENGTH:
                print(
                    f"Error: Minimum length is {InputValidator.MIN_LENGTH}.\n"
                )
                continue

            if length > InputValidator.MAX_LENGTH:
                print(
                    f"Error: Maximum length is {InputValidator.MAX_LENGTH}.\n"
                )
                continue

            return length

    @staticmethod
    def ask_yes_no(message: str) -> bool:
        """
        Ask a Yes/No question.
        """

        while True:

            answer = input(message).strip().lower()

            if answer in ("y", "yes"):
                return True

            if answer in ("n", "no"):
                return False

            print("Error: Enter y or n.\n")

    @staticmethod
    def validate_character_selection(
        uppercase: bool,
        lowercase: bool,
        digits: bool,
        symbols: bool,
    ) -> None:
        """
        Ensure at least one character type is selected.
        """

        if not any(
            [uppercase, lowercase, digits, symbols]
        ):
            raise ValueError(
                "Select at least one character type."
            )