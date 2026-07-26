"""
Utility functions for Contact Book.
"""

class Utils:

    @staticmethod
    def header():
        print("\n" + "=" * 50)
        print("                 CONTACT BOOK")
        print("=" * 50)

    @staticmethod
    def menu():
        print("\n1. Add Contact")
        print("2. View Contacts")
        print("3. Search Contact")
        print("4. Update Contact")
        print("5. Delete Contact")
        print("6. Total Contacts")
        print("7. Exit")

    @staticmethod
    def pause():
        input("\nPress Enter to continue...")

    @staticmethod
    def line():
        print("-" * 50)