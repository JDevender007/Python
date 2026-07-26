"""
Database models for Hotel Management System.
"""

from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import relationship

from database import Base

class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String(10), unique=True, nullable=False)
    room_type = Column(String(30), nullable=False)
    price_per_night = Column(Float, nullable=False)
    status = Column(String(20), default="Available")

    guests = relationship(
        "Guest",
        back_populates="room",
        cascade="all, delete-orphan",
    )

class Guest(Base):
    __tablename__ = "guests"

    id = Column(Integer, primary_key=True, index=True)
    guest_name = Column(String(100), nullable=False)
    phone = Column(String(10), nullable=False)
    email = Column(String(100), nullable=False)

    room_id = Column(Integer, ForeignKey("rooms.id"))

    check_in_date = Column(DateTime, default=datetime.now)
    check_out_date = Column(DateTime)

    room = relationship("Room", back_populates="guests")