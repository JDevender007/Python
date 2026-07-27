import csv

from config import REPORT_FOLDER
from config import CSV_HEADERS

class ReportGenerator:

    def generate(self, students):

        REPORT_FOLDER.mkdir(
            parents=True,
            exist_ok=True
        )

        report = REPORT_FOLDER / "student_report.csv"

        with open(
            report,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow(CSV_HEADERS)

            for student in students:

                writer.writerow(
                    student.to_list()
                )

        print(f"\nReport saved to:\n{report}")