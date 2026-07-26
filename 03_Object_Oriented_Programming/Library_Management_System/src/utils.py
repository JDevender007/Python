"""
Utility functions.
"""

class Utils:

    @staticmethod
    def header():
        print("=" * 50)
        print("      LIBRARY MANAGEMENT SYSTEM")
        print("=" * 50)

    @staticmethod
    def menu():
        print("\n1. Add Book")
        print("2. View Books")
        print("3. Search Book")
        print("4. Update Book")
        print("5. Delete Book")
        print("6. Issue Book")
        print("7. Return Book")
        print("8. View Issued Books")
        print("9. Total Books")
        print("10. Exit")

    @staticmethod
    def pause():
        input("\nPress Enter to continue...")