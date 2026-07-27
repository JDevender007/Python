import csv

from config import REPORT_FOLDER

class ReportGenerator:

    def generate(self, synchronizer):

        REPORT_FOLDER.mkdir(parents=True, exist_ok=True)

        report_path = REPORT_FOLDER / "sync_report.csv"

        with open(report_path, "w", newline="", encoding="utf-8") as file:

            writer = csv.writer(file)

            writer.writerow(
                [
                    "Source File",
                    "Destination File"
                ]
            )

            for source, destination in synchronizer.synced_files:

                writer.writerow(
                    [
                        source,
                        destination
                    ]
                )

        print(f"\nReport saved to:\n{report_path}")