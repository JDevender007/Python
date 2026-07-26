"""
Utility functions.
"""

class Utils:

    @staticmethod
    def header():
        print("\n" + "=" * 50)
        print("      STUDENT MANAGEMENT SYSTEM")
        print("=" * 50)

    @staticmethod
    def menu():
        print("\n1. Add Student")
        print("2. View Students")
        print("3. Search Student")
        print("4. Top Scorer")
        print("5. Total Students")
        print("6. Exit")

    @staticmethod
    def pause():
        input("\nPress Enter to continue...")

    @staticmethod
    def line():
        print("-" * 50)