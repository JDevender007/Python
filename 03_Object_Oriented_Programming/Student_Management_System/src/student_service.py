"""
Business logic for Student Management System.
"""

from sqlalchemy import desc

from database import Base
from database import engine
from database import get_session
from models import Student

Base.metadata.create_all(bind=engine)

class StudentService:

    def __init__(self):
        self.session = get_session()

    def add_student(
        self,
        roll_number,
        name,
        department,
        year,
        cgpa,
        email,
        phone,
    ):

        student = Student(
            roll_number=roll_number,
            name=name,
            department=department,
            year=year,
            cgpa=cgpa,
            email=email,
            phone=phone,
        )

        self.session.add(student)
        self.session.commit()

        print("\nStudent added successfully.")

    def view_students(self):

        students = (
            self.session.query(Student)
            .order_by(Student.name)
            .all()
        )

        if not students:
            print("\nNo students found.")
            return

        for student in students:
            print("-" * 50)
            print(f"ID          : {student.id}")
            print(f"Roll Number : {student.roll_number}")
            print(f"Name        : {student.name}")
            print(f"Department  : {student.department}")
            print(f"Year        : {student.year}")
            print(f"CGPA        : {student.cgpa}")
            print(f"Email       : {student.email}")
            print(f"Phone       : {student.phone}")

    def search_student(self, keyword):

        student = (
            self.session.query(Student)
            .filter(
                (Student.roll_number == keyword)
                | (Student.name.ilike(f"%{keyword}%"))
            )
            .first()
        )

        if not student:
            print("\nStudent not found.")
            return

        print("-" * 50)
        print(f"ID          : {student.id}")
        print(f"Roll Number : {student.roll_number}")
        print(f"Name        : {student.name}")
        print(f"Department  : {student.department}")
        print(f"Year        : {student.year}")
        print(f"CGPA        : {student.cgpa}")
        print(f"Email       : {student.email}")
        print(f"Phone       : {student.phone}")

    def top_scorer(self):

        student = (
            self.session.query(Student)
            .order_by(desc(Student.cgpa))
            .first()
        )

        if not student:
            print("\nNo student records found.")
            return

        print("\nTop Scorer")
        print("-" * 50)
        print(f"Name : {student.name}")
        print(f"CGPA : {student.cgpa}")

    def total_students(self):

        total = self.session.query(Student).count()

        print(f"\nTotal Students : {total}")