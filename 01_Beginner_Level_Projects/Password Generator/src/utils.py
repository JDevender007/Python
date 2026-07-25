"""
utils.py

Common utility functions used throughout the project.
"""

import os


class Console:
    """Console helper methods."""

    @staticmethod
    def clear() -> None:
        """
        Clear the terminal screen.
        """

        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def line(length: int = 50) -> None:
        """
        Print a horizontal line.
        """

        print("=" * length)

    @staticmethod
    def title(title: str) -> None:
        """
        Display a formatted title.
        """

        Console.line()
        print(title.center(50))
        Console.line()

    @staticmethod
    def success(message: str) -> None:
        """
        Display a success message.
        """

        print(f"\n[SUCCESS] {message}")

    @staticmethod
    def error(message: str) -> None:
        """
        Display an error message.
        """

        print(f"\n[ERROR] {message}")

    @staticmethod
    def info(message: str) -> None:
        """
        Display an informational message.
        """

        print(f"\n[INFO] {message}")

    @staticmethod
    def pause() -> None:
        """
        Wait for the user.
        """

        input("\nPress Enter to continue...")