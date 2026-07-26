"""
utils.py

Utility functions.
"""

from os import system

def clear_screen():

    system("cls")

def pause():

    input("\nPress Enter to continue...")

def header(title):

    clear_screen()

    print("=" * 50)
    print(title.center(50))
    print("=" * 50)