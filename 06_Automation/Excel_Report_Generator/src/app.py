from __future__ import annotations

import tkinter as tk

from tkinter import ttk
from tkinter import messagebox

from src.config import (
    WINDOW_TITLE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WIDTH,
    MIN_HEIGHT,
    TITLE_FONT,
)

from src.colors import (
    BACKGROUND,
    SURFACE,
    TEXT,
)

from src.controls import ControlPanel
from src.excel_handler import ExcelHandler
from src.report_generator import ReportGenerator
from src.chart_generator import ChartGenerator


class ExcelReportGeneratorApp:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(WINDOW_TITLE)

        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self.root.minsize(
            MIN_WIDTH,
            MIN_HEIGHT,
        )

        self.root.configure(
            bg=BACKGROUND,
        )

        self.fullscreen = False

        self.excel = ExcelHandler()

        self.report = ReportGenerator()

        self.chart = ChartGenerator()

        self.create_variables()

        self.create_layout()

        self.create_left_panel()

        self.create_center_panel()

        self.create_right_panel()

        self.bind_shortcuts()

    def create_variables(self):

        self.file_var = tk.StringVar(value="No File Selected")

        self.rows_var = tk.StringVar(value="0")

        self.columns_var = tk.StringVar(value="0")

        self.status_var = tk.StringVar(value="Ready")

        self.progress_var = tk.IntVar(value=0)

    def create_layout(self):

        self.main = tk.Frame(
            self.root,
            bg=BACKGROUND,
        )

        self.main.pack(
            fill="both",
            expand=True,
        )

        self.left = tk.Frame(
            self.main,
            bg=BACKGROUND,
            width=300,
        )

        self.left.pack(
            side="left",
            fill="y",
            padx=10,
            pady=10,
        )

        self.center = tk.Frame(
            self.main,
            bg=BACKGROUND,
        )

        self.center.pack(
            side="left",
            fill="both",
            expand=True,
            padx=10,
            pady=10,
        )

        self.right = tk.Frame(
            self.main,
            bg=BACKGROUND,
            width=300,
        )

        self.right.pack(
            side="right",
            fill="y",
            padx=10,
            pady=10,
        )

    def create_left_panel(self):

        self.controls = ControlPanel(
            self.left,
            self,
        )

        self.controls.pack(
            fill="both",
            expand=True,
        )

    def create_center_panel(self):

        tk.Label(
            self.center,
            text="Excel Report Generator",
            font=TITLE_FONT,
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
            pady=(0, 15),
        )

        self.output = tk.Text(
            self.center,
            wrap="none",
        )

        self.output.pack(
            fill="both",
            expand=True,
        )

    def create_right_panel(self):

        tk.Label(
            self.right,
            text="Information",
            font=TITLE_FONT,
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
            pady=(0, 15),
        )

        self.create_card(
            "Excel File",
            self.file_var,
        )

        self.create_card(
            "Rows",
            self.rows_var,
        )

        self.create_card(
            "Columns",
            self.columns_var,
        )

        self.create_card(
            "Status",
            self.status_var,
        )

        ttk.Progressbar(
            self.right,
            maximum=100,
            variable=self.progress_var,
        ).pack(
            fill="x",
            pady=20,
        )

    def create_card(
        self,
        title,
        variable,
    ):

        frame = tk.Frame(
            self.right,
            bg=SURFACE,
            padx=10,
            pady=10,
        )

        frame.pack(
            fill="x",
            pady=6,
        )

        tk.Label(
            frame,
            text=title,
            bg=SURFACE,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(
            anchor="w",
        )

        tk.Label(
            frame,
            textvariable=variable,
            bg=SURFACE,
            fg=TEXT,
            wraplength=250,
            justify="left",
        ).pack(
            anchor="w",
        )

    def bind_shortcuts(self):

        self.root.bind(
            "<Control-o>",
            lambda event: self.open_excel(),
        )

        self.root.bind(
            "<Control-e>",
            lambda event: self.export_report(),
        )

        self.root.bind(
            "<F11>",
            lambda event: self.toggle_fullscreen(),
        )

        self.root.bind(
            "<Escape>",
            lambda event: self.exit_fullscreen(),
        )

    def open_excel(self):

        file = self.excel.open_file()

        if not file:

            return

        dataframe = self.excel.load()

        self.dataframe = dataframe

        self.file_var.set(file)

        self.rows_var.set(str(len(dataframe)))

        self.columns_var.set(str(len(dataframe.columns)))

        self.status_var.set("Excel Loaded")

        self.output.delete(
            "1.0",
            tk.END,
        )

        self.output.insert(
            tk.END,
            dataframe.head(20).to_string(),
        )

    def preview_data(self):

        if not hasattr(
            self,
            "dataframe",
        ):

            return

        self.output.delete(
            "1.0",
            tk.END,
        )

        self.output.insert(
            tk.END,
            self.dataframe.to_string(),
        )

    def generate_summary(self):

        if not hasattr(
            self,
            "dataframe",
        ):

            return

        summary = self.report.generate_summary(
            self.dataframe,
        )

        self.output.delete(
            "1.0",
            tk.END,
        )

        self.output.insert(
            tk.END,
            summary.to_string(),
        )

        self.status_var.set("Summary Generated")

    def generate_missing_report(self):

        if not hasattr(
            self,
            "dataframe",
        ):

            return

        report = self.report.generate_missing_report(
            self.dataframe,
        )

        self.output.delete(
            "1.0",
            tk.END,
        )

        self.output.insert(
            tk.END,
            report.to_string(),
        )

        self.status_var.set("Missing Report Generated")

    def create_bar_chart(self):

        if not hasattr(
            self,
            "dataframe",
        ):

            return

        column = self.dataframe.columns[0]

        figure = self.chart.create_bar_chart(
            self.dataframe,
            column,
        )

        figure.show()

        self.status_var.set("Bar Chart Generated")

    def create_pie_chart(self):

        if not hasattr(
            self,
            "dataframe",
        ):

            return

        column = self.dataframe.columns[0]

        figure = self.chart.create_pie_chart(
            self.dataframe,
            column,
        )

        figure.show()

        self.status_var.set("Pie Chart Generated")

    def export_report(self):

        if not hasattr(
            self,
            "dataframe",
        ):

            return

        file = self.excel.save(
            self.dataframe,
        )

        if file:

            self.status_var.set("Report Exported")

            messagebox.showinfo(
                "Export",
                "Report exported successfully.",
            )

    def clear_all(self):

        self.output.delete(
            "1.0",
            tk.END,
        )

        self.file_var.set("No File Selected")

        self.rows_var.set("0")

        self.columns_var.set("0")

        self.status_var.set("Ready")

        self.progress_var.set(0)

    def toggle_fullscreen(self):

        self.fullscreen = not self.fullscreen

        self.root.attributes(
            "-fullscreen",
            self.fullscreen,
        )

    def exit_fullscreen(self):

        self.fullscreen = False

        self.root.attributes(
            "-fullscreen",
            False,
        )

    def run(self):

        self.root.mainloop()


def main():

    app = ExcelReportGeneratorApp()

    app.run()


if __name__ == "__main__":

    main()
