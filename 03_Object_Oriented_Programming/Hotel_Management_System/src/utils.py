"""
Utility functions for Hotel Management System.
"""

class Utils:

    @staticmethod
    def header():
        print("\n" + "=" * 50)
        print("          HOTEL MANAGEMENT SYSTEM")
        print("=" * 50)

    @staticmethod
    def menu():
        print("\n1. Add Room")
        print("2. View Rooms")
        print("3. Search Room")
        print("4. Book Room")
        print("5. Check-out Guest")
        print("6. Total Rooms")
        print("7. Total Guests")
        print("8. Exit")

    @staticmethod
    def pause():
        input("\nPress Enter to continue...")

    @staticmethod
    def line():
        print("-" * 50)