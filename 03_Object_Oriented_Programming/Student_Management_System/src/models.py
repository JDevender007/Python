"""
Student database model.
"""

from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)

    roll_number = Column(
        String(20),
        unique=True,
        nullable=False,
    )

    name = Column(
        String(100),
        nullable=False,
    )

    department = Column(
        String(50),
        nullable=False,
    )

    year = Column(
        Integer,
        nullable=False,
    )

    cgpa = Column(
        Float,
        nullable=False,
    )

    email = Column(
        String(100),
        unique=True,
        nullable=False,
    )

    phone = Column(
        String(15),
        unique=True,
        nullable=False,
    )

    def __repr__(self):
        return f"<Student {self.name}>"