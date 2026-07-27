import csv

from config import REPORT_FOLDER

class ReportGenerator:

    def generate(self, finder):

        REPORT_FOLDER.mkdir(parents=True, exist_ok=True)

        report_file = REPORT_FOLDER / "duplicate_report.csv"

        with open(report_file, "w", newline="", encoding="utf-8") as file:

            writer = csv.writer(file)

            writer.writerow(["Original File", "Duplicate File"])

            for file_hash, duplicates in finder.duplicates.items():

                original = finder.hash_map[file_hash]

                for duplicate in duplicates:

                    writer.writerow([str(original), str(duplicate)])

        print(f"\nReport saved to:\n{report_file}")