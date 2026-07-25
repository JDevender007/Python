"""
score.py

Manage the best score.
"""

from pathlib import Path

class ScoreManager:

    FILE = Path("data/best_score.txt")

    @classmethod
    def load_best_score(cls):

        cls.FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        cls.FILE.touch(
            exist_ok=True,
        )

        value = cls.FILE.read_text().strip()

        if value == "":
            return None

        return int(value)

    @classmethod
    def save_best_score(cls, attempts: int):

        best = cls.load_best_score()

        if best is None or attempts < best:

            cls.FILE.write_text(
                str(attempts),
                encoding="utf-8",
            )

            return True

        return False