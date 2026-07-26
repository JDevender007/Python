"""
Business logic for Contact Book.
"""

from sqlalchemy import or_

from database import Base
from database import engine
from database import get_session
from models import Contact

Base.metadata.create_all(bind=engine)

class ContactService:

    def __init__(self):
        self.session = get_session()

    def add_contact(
        self,
        first_name,
        last_name,
        phone,
        email,
        address,
    ):
        contact = Contact(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            address=address,
        )

        self.session.add(contact)
        self.session.commit()

        print("\nContact added successfully.")

    def view_contacts(self):
        contacts = (
            self.session.query(Contact)
            .order_by(Contact.first_name)
            .all()
        )

        if not contacts:
            print("\nNo contacts found.")
            return

        print()

        for contact in contacts:
            print(f"ID       : {contact.id}")
            print(
                f"Name     : {contact.first_name} {contact.last_name}"
            )
            print(f"Phone    : {contact.phone}")
            print(f"Email    : {contact.email}")
            print(f"Address  : {contact.address}")
            print("-" * 40)

    def search_contact(self, keyword):
        contacts = (
            self.session.query(Contact)
            .filter(
                or_(
                    Contact.first_name.ilike(f"%{keyword}%"),
                    Contact.last_name.ilike(f"%{keyword}%"),
                    Contact.phone.ilike(f"%{keyword}%"),
                    Contact.email.ilike(f"%{keyword}%"),
                )
            )
            .all()
        )

        if not contacts:
            print("\nNo matching contact found.")
            return

        print()

        for contact in contacts:
            print(f"ID       : {contact.id}")
            print(
                f"Name     : {contact.first_name} {contact.last_name}"
            )
            print(f"Phone    : {contact.phone}")
            print(f"Email    : {contact.email}")
            print(f"Address  : {contact.address}")
            print("-" * 40)

    def update_contact(
        self,
        contact_id,
        first_name,
        last_name,
        phone,
        email,
        address,
    ):
        contact = (
            self.session.query(Contact)
            .filter(Contact.id == contact_id)
            .first()
        )

        if not contact:
            print("\nContact not found.")
            return

        contact.first_name = first_name
        contact.last_name = last_name
        contact.phone = phone
        contact.email = email
        contact.address = address

        self.session.commit()

        print("\nContact updated successfully.")

    def delete_contact(self, contact_id):
        contact = (
            self.session.query(Contact)
            .filter(Contact.id == contact_id)
            .first()
        )

        if not contact:
            print("\nContact not found.")
            return

        self.session.delete(contact)
        self.session.commit()

        print("\nContact deleted successfully.")

    def total_contacts(self):
        count = self.session.query(Contact).count()

        print(f"\nTotal Contacts : {count}")