"""
Business logic for Hotel Management System.
"""

from datetime import datetime

from database import Base
from database import engine
from database import get_session

from models import Guest
from models import Room

Base.metadata.create_all(bind=engine)

class HotelService:

    def __init__(self):
        self.session = get_session()

    def add_room(
        self,
        room_number,
        room_type,
        price,
    ):
        room = Room(
            room_number=room_number,
            room_type=room_type.title(),
            price_per_night=price,
        )

        self.session.add(room)
        self.session.commit()

        print("\nRoom added successfully.")

    def view_rooms(self):
        rooms = (
            self.session.query(Room)
            .order_by(Room.room_number)
            .all()
        )

        if not rooms:
            print("\nNo rooms available.")
            return

        for room in rooms:
            print("-" * 50)
            print(f"Room Number : {room.room_number}")
            print(f"Room Type   : {room.room_type}")
            print(f"Price       : ${room.price_per_night:.2f}")
            print(f"Status      : {room.status}")

    def search_room(self, room_number):
        room = (
            self.session.query(Room)
            .filter(Room.room_number == room_number)
            .first()
        )

        if not room:
            print("\nRoom not found.")
            return

        print("-" * 50)
        print(f"Room Number : {room.room_number}")
        print(f"Room Type   : {room.room_type}")
        print(f"Price       : ${room.price_per_night:.2f}")
        print(f"Status      : {room.status}")

    def book_room(
        self,
        guest_name,
        phone,
        email,
        room_number,
    ):
        room = (
            self.session.query(Room)
            .filter(Room.room_number == room_number)
            .first()
        )

        if not room:
            print("\nRoom not found.")
            return

        if room.status == "Occupied":
            print("\nRoom already occupied.")
            return

        guest = Guest(
            guest_name=guest_name,
            phone=phone,
            email=email,
            room_id=room.id,
        )

        room.status = "Occupied"

        self.session.add(guest)
        self.session.commit()

        print("\nRoom booked successfully.")

    def checkout_guest(self, room_number):
        room = (
            self.session.query(Room)
            .filter(Room.room_number == room_number)
            .first()
        )

        if not room:
            print("\nRoom not found.")
            return

        guest = (
            self.session.query(Guest)
            .filter(Guest.room_id == room.id)
            .first()
        )

        if not guest:
            print("\nGuest not found.")
            return

        guest.check_out_date = datetime.now()
        room.status = "Available"

        self.session.commit()

        print("\nGuest checked out successfully.")

    def total_rooms(self):
        print(
            f"\nTotal Rooms : {self.session.query(Room).count()}"
        )

    def total_guests(self):
        print(
            f"Total Guests : {self.session.query(Guest).count()}"
        )

    def close(self):
        self.session.close()