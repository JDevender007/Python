"""
Entry point for Contact Book.
"""

from contact_service import ContactService
from utils import Utils
from validator import Validator

service = ContactService()

def add_contact():
    print("\nAdd Contact")

    first_name = input("First Name : ").strip()

    while not Validator.validate_name(first_name):
        print("Invalid first name.")
        first_name = input("First Name : ").strip()

    last_name = input("Last Name  : ").strip()

    while not Validator.validate_name(last_name):
        print("Invalid last name.")
        last_name = input("Last Name  : ").strip()

    phone = input("Phone      : ").strip()

    while not Validator.validate_phone(phone):
        print("Phone must contain exactly 10 digits.")
        phone = input("Phone      : ").strip()

    email = input("Email      : ").strip()

    while not Validator.validate_email(email):
        print("Invalid email address.")
        email = input("Email      : ").strip()

    address = input("Address    : ").strip()

    service.add_contact(
        first_name,
        last_name,
        phone,
        email,
        address,
    )

def update_contact():
    contact_id = int(input("\nContact ID : "))

    first_name = input("First Name : ")
    last_name = input("Last Name  : ")
    phone = input("Phone      : ")
    email = input("Email      : ")
    address = input("Address    : ")

    service.update_contact(
        contact_id,
        first_name,
        last_name,
        phone,
        email,
        address,
    )

def delete_contact():
    contact_id = int(input("\nContact ID : "))
    service.delete_contact(contact_id)


def search_contact():
    keyword = input("\nSearch : ")
    service.search_contact(keyword)

def main():

    while True:

        Utils.header()
        Utils.menu()

        choice = input("\nEnter Choice : ")

        if choice == "1":
            add_contact()

        elif choice == "2":
            service.view_contacts()

        elif choice == "3":
            search_contact()

        elif choice == "4":
            update_contact()

        elif choice == "5":
            delete_contact()

        elif choice == "6":
            service.total_contacts()

        elif choice == "7":
            print("\nThank you for using Contact Book.")
            break

        else:
            print("\nInvalid choice.")

        Utils.pause()

if __name__ == "__main__":
    main()