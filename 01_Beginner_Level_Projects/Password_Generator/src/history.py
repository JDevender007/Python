"""
history.py

Saves generated passwords to a history file.
"""

from pathlib import Path
from datetime import datetime


class PasswordHistory:
    """Manage password history."""

    HISTORY_FILE = Path("data/password_history.txt")

    @classmethod
    def save(cls, password: str) -> None:
        """
        Save a password with the current timestamp.
        """

        # Create the data folder if it doesn't exist
        cls.HISTORY_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Create the history file if it doesn't exist
        cls.HISTORY_FILE.touch(
            exist_ok=True,
        )

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        with cls.HISTORY_FILE.open(
            mode="a",
            encoding="utf-8",
        ) as file:

            file.write(
                f"[{timestamp}] {password}\n"
            )

    @classmethod
    def show(cls) -> None:
        """
        Display all saved passwords.
        """

        if not cls.HISTORY_FILE.exists():
            print("\nNo password history found.")
            return

        print("\nPassword History")
        print("-" * 50)

        with cls.HISTORY_FILE.open(
            mode="r",
            encoding="utf-8",
        ) as file:

            content = file.read()

            if not content.strip():
                print("History is empty.")
                return

            print(content)

    @classmethod
    def clear(cls) -> None:
        """
        Delete all password history.
        """

        if cls.HISTORY_FILE.exists():

            cls.HISTORY_FILE.write_text(
                "",
                encoding="utf-8",
            )

            print("Password history cleared.")

        else:

            print("History file does not exist.")