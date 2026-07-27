import csv

from config import REPORT_FOLDER

class ReportGenerator:

    def generate(self, summary):

        REPORT_FOLDER.mkdir(parents=True, exist_ok=True)

        report = REPORT_FOLDER / "log_summary.csv"

        with open(report, "w", newline="", encoding="utf-8") as file:

            writer = csv.writer(file)

            writer.writerow(
                [
                    "Log Level",
                    "Count"
                ]
            )

            for level, count in summary.items():

                writer.writerow(
                    [
                        level,
                        count
                    ]
                )

        print(f"\nReport saved to:\n{report}")