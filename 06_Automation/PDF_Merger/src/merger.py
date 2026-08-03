from __future__ import annotations

from pathlib import Path

from pypdf import PdfMerger

class PDFMergerEngine:

    def __init__(self) -> None:
        self.merger = PdfMerger()

    def merge(
        self,
        pdf_files: list[str],
        output_file: str,
        progress_callback=None,
    ) -> bool:

        try:
            self.merger = PdfMerger()

            total = len(pdf_files)

            for index, pdf in enumerate(pdf_files, start=1):
                self.merger.append(pdf)

                if progress_callback:
                    percentage = int((index / total) * 100)
                    progress_callback(percentage)

            output_path = Path(output_file)

            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with open(output_path, "wb") as file:
                self.merger.write(file)

            self.merger.close()

            return True

        except Exception:
            self.close()
            return False

    def append(self, pdf: str) -> None:
        self.merger.append(pdf)

    def write(self, output_file: str) -> None:
        with open(output_file, "wb") as file:
            self.merger.write(file)

    def close(self) -> None:
        try:
            self.merger.close()
        except Exception:
            pass

    def reset(self) -> None:
        self.close()
        self.merger = PdfMerger()

    def output_exists(self, output_file: str) -> bool:
        return Path(output_file).exists()

    def validate(self, pdf_files: list[str]) -> bool:
        return len(pdf_files) >= 2