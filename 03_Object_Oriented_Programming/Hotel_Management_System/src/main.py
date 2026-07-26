"""
Entry point for Hotel Management System.
"""

from hotel_service import HotelService
from utils import Utils
from validator import Validator

service = HotelService()

def add_room():
    print("\nAdd Room")

    room_number = input("Room Number : ")

    while not Validator.validate_room_number(room_number):
        print("Invalid room number.")
        room_number = input("Room Number : ")

    room_type = input(
        "Room Type (Single/Double/Deluxe/Suite) : "
    )

    while not Validator.validate_room_type(room_type):
        print("Invalid room type.")
        room_type = input(
            "Room Type (Single/Double/Deluxe/Suite) : "
        )

    price = input("Price Per Night : ")

    while not Validator.validate_price(price):
        print("Invalid price.")
        price = input("Price Per Night : ")

    service.add_room(
        room_number,
        room_type,
        float(price),
    )

def book_room():
    print("\nBook Room")

    guest_name = input("Guest Name : ")

    while not Validator.validate_name(guest_name):
        print("Invalid name.")
        guest_name = input("Guest Name : ")

    phone = input("Phone : ")

    while not Validator.validate_phone(phone):
        print("Invalid phone number.")
        phone = input("Phone : ")

    email = input("Email : ")

    while not Validator.validate_email(email):
        print("Invalid email.")
        email = input("Email : ")

    room_number = input("Room Number : ")

    service.book_room(
        guest_name,
        phone,
        email,
        room_number,
    )

def checkout():
    room_number = input("\nRoom Number : ")
    service.checkout_guest(room_number)

def main():

    while True:

        Utils.header()
        Utils.menu()

        choice = input("\nEnter Choice : ")

        if choice == "1":
            add_room()

        elif choice == "2":
            service.view_rooms()

        elif choice == "3":
            room = input("\nRoom Number : ")
            service.search_room(room)

        elif choice == "4":
            book_room()

        elif choice == "5":
            checkout()

        elif choice == "6":
            service.total_rooms()

        elif choice == "7":
            service.total_guests()

        elif choice == "8":
            print("\nThank you.")
            service.close()
            break

        else:
            print("\nInvalid choice.")

        Utils.pause()

if __name__ == "__main__":
    main()