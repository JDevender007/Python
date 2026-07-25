"""
statistics.py

Save every completed game.
"""

from pathlib import Path
from datetime import datetime

class StatisticsManager:

    FILE = Path("data/game_history.txt")

    @classmethod
    def save(
        cls,
        difficulty: str,
        attempts: int,
        secret_number: int,
    ):

        cls.FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        cls.FILE.touch(
            exist_ok=True,
        )

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        with cls.FILE.open(
            "a",
            encoding="utf-8",
        ) as file:

            file.write(
                f"[{timestamp}] "
                f"{difficulty} | "
                f"Attempts: {attempts} | "
                f"Number: {secret_number}\n"
            )

    @classmethod
    def show(cls):

        if not cls.FILE.exists():

            print("\nNo history found.")
            return

        print("\nGame History")
        print("-" * 50)

        content = cls.FILE.read_text(
            encoding="utf-8",
        )

        if content.strip():
            print(content)
        else:
            print("History is empty.")