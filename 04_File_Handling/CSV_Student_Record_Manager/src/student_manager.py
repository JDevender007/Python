import csv

from tabulate import tabulate

from config import CSV_FILE
from config import CSV_HEADERS

from student import Student
from logger import logger

class StudentManager:

    def __init__(self):

        CSV_FILE.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not CSV_FILE.exists():

            with open(
                CSV_FILE,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(file)

                writer.writerow(CSV_HEADERS)

    def load_students(self):

        students = []

        with open(
            CSV_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                students.append(
                    Student(
                        row["Roll No"],
                        row["Name"],
                        row["Department"],
                        int(row["Year"]),
                        float(row["Marks"])
                    )
                )

        return students

    def save_students(self, students):

        with open(
            CSV_FILE,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow(CSV_HEADERS)

            for student in students:

                writer.writerow(student.to_list())

    def add_student(self):

        students = self.load_students()

        roll = input("Roll Number : ")

        if any(s.roll_no == roll for s in students):

            print("Student already exists.")
            return

        student = Student(
            roll,
            input("Name : "),
            input("Department : "),
            int(input("Year : ")),
            float(input("Marks : "))
        )

        students.append(student)

        self.save_students(students)

        logger.info(f"Student Added : {roll}")

        print("Student added successfully.")

    def view_students(self):

        students = self.load_students()

        if not students:

            print("No records found.")
            return

        table = [
            s.to_list()
            for s in students
        ]

        print()

        print(
            tabulate(
                table,
                headers=CSV_HEADERS,
                tablefmt="grid"
            )
        )

    def search_student(self):

        roll = input("Enter Roll Number : ")

        students = self.load_students()

        for student in students:

            if student.roll_no == roll:

                print()

                print(
                    tabulate(
                        [student.to_list()],
                        headers=CSV_HEADERS,
                        tablefmt="grid"
                    )
                )

                return

        print("Student not found.")
    def update_student(self):

        roll = input("Enter Roll Number : ")

        students = self.load_students()

        for student in students:

            if student.roll_no == roll:

                student.name = input(
                    f"Name ({student.name}) : "
                ) or student.name

                student.department = input(
                    f"Department ({student.department}) : "
                ) or student.department

                year = input(
                    f"Year ({student.year}) : "
                )

                if year:
                    student.year = int(year)

                marks = input(
                    f"Marks ({student.marks}) : "
                )

                if marks:
                    student.marks = float(marks)

                self.save_students(students)

                logger.info(
                    f"Student Updated : {roll}"
                )

                print("Student updated successfully.")

                return

        print("Student not found.")

    def delete_student(self):

        roll = input("Enter Roll Number : ")

        students = self.load_students()

        updated_students = [
            student
            for student in students
            if student.roll_no != roll
        ]

        if len(updated_students) == len(students):

            print("Student not found.")

            return

        self.save_students(updated_students)

        logger.info(
            f"Student Deleted : {roll}"
        )

        print("Student deleted successfully.")

    def sort_by_name(self):

        students = sorted(
            self.load_students(),
            key=lambda student: student.name.lower()
        )

        table = [
            student.to_list()
            for student in students
        ]

        print()

        print(
            tabulate(
                table,
                headers=CSV_HEADERS,
                tablefmt="grid"
            )
        )

    def sort_by_marks(self):

        students = sorted(
            self.load_students(),
            key=lambda student: student.marks,
            reverse=True
        )

        table = [
            student.to_list()
            for student in students
        ]

        print()

        print(
            tabulate(
                table,
                headers=CSV_HEADERS,
                tablefmt="grid"
            )
        )

    def average_marks(self):

        students = self.load_students()

        if not students:

            print("No records found.")

            return

        average = sum(
            student.marks
            for student in students
        ) / len(students)

        print(f"\nAverage Marks : {average:.2f}")