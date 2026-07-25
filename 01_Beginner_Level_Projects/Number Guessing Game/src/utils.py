"""
utils.py

Utility functions for the Number Guessing Game.
"""

import os


class Console:
    """Console helper methods."""

    @staticmethod
    def clear() -> None:
        """Clear the terminal."""

        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def line(length: int = 50) -> None:
        """Print a separator."""

        print("=" * length)

    @staticmethod
    def title(title: str) -> None:
        """Print a formatted title."""

        Console.line()
        print(title.center(50))
        Console.line()

    @staticmethod
    def success(message: str) -> None:
        """Success message."""

        print(f"\n[SUCCESS] {message}")

    @staticmethod
    def error(message: str) -> None:
        """Error message."""

        print(f"\n[ERROR] {message}")

    @staticmethod
    def info(message: str) -> None:
        """Information message."""

        print(f"\n[INFO] {message}")