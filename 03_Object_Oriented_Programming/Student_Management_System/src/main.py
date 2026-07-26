"""
Entry point for Student Management System.
"""

from student_service import StudentService
from validator import Validator
from utils import Utils

service = StudentService()

def add_student():
    print("\nAdd Student")

    roll_number = input("Roll Number : ").strip()
    while not Validator.validate_roll(roll_number):
        print("Invalid roll number.")
        roll_number = input("Roll Number : ").strip()

    name = input("Name        : ").strip()
    while not Validator.validate_name(name):
        print("Invalid name.")
        name = input("Name        : ").strip()

    department = input("Department  : ").strip()
    while not Validator.validate_department(department):
        print("Invalid department.")
        department = input("Department  : ").strip()

    year = input("Year        : ").strip()
    while not Validator.validate_year(year):
        print("Year must be between 1 and 4.")
        year = input("Year        : ").strip()

    cgpa = input("CGPA        : ").strip()
    while not Validator.validate_cgpa(cgpa):
        print("CGPA must be between 0 and 10.")
        cgpa = input("CGPA        : ").strip()

    email = input("Email       : ").strip()
    while not Validator.validate_email(email):
        print("Invalid email address.")
        email = input("Email       : ").strip()

    phone = input("Phone       : ").strip()
    while not Validator.validate_phone(phone):
        print("Phone must contain exactly 10 digits.")
        phone = input("Phone       : ").strip()

    service.add_student(
        roll_number,
        name,
        department,
        int(year),
        float(cgpa),
        email,
        phone,
    )

def search_student():
    keyword = input("\nSearch : ").strip()
    service.search_student(keyword)

def main():
    while True:
        Utils.header()
        Utils.menu()

        choice = input("\nEnter Choice : ").strip()

        if choice == "1":
            add_student()

        elif choice == "2":
            service.view_students()

        elif choice == "3":
            search_student()

        elif choice == "4":
            service.top_scorer()

        elif choice == "5":
            service.total_students()

        elif choice == "6":
            print("\nThank you for using Student Management System.")
            break

        else:
            print("\nInvalid choice.")

        Utils.pause()


if __name__ == "__main__":
    main()