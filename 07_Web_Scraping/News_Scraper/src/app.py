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
    DEFAULT_URL,
)

from src.colors import (
    BACKGROUND,
    SURFACE,
    TEXT,
)

from src.controls import ControlPanel
from src.scraper import NewsScraper
from src.parser import NewsParser
from src.exporter import NewsExporter


class NewsScraperApp:

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

        self.scraper = NewsScraper()

        self.parser = NewsParser()

        self.exporter = NewsExporter()

        self.articles = []

        self.create_variables()

        self.create_layout()

        self.create_left_panel()

        self.create_center_panel()

        self.create_right_panel()

        self.bind_shortcuts()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close,
        )

    def create_variables(self):

        self.url_var = tk.StringVar(value=DEFAULT_URL)

        self.status_var = tk.StringVar(value="Ready")

        self.count_var = tk.StringVar(value="0")

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
            width=280,
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
            text="News Scraper",
            font=TITLE_FONT,
            bg=BACKGROUND,
            fg=TEXT,
        ).pack(
            anchor="w",
            pady=(0, 10),
        )

        url_frame = tk.Frame(
            self.center,
            bg=SURFACE,
            padx=10,
            pady=10,
        )

        url_frame.pack(
            fill="x",
            pady=(0, 10),
        )

        tk.Label(
            url_frame,
            text="News URL",
            bg=SURFACE,
            fg=TEXT,
        ).pack(
            anchor="w",
        )

        self.url_entry = tk.Entry(
            url_frame,
            textvariable=self.url_var,
            bg="#202020",
            fg=TEXT,
            insertbackground=TEXT,
        )

        self.url_entry.pack(
            fill="x",
            pady=(5, 0),
        )

        result_frame = tk.Frame(
            self.center,
            bg=SURFACE,
        )

        result_frame.pack(
            fill="both",
            expand=True,
        )

        self.output = tk.Text(
            result_frame,
            wrap="none",
            bg="#202020",
            fg=TEXT,
            insertbackground=TEXT,
        )

        self.output.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar = ttk.Scrollbar(
            result_frame,
            orient="vertical",
            command=self.output.yview,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        self.output.configure(
            yscrollcommand=scrollbar.set,
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
            "Articles",
            self.count_var,
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
            "<Control-s>",
            lambda event: self.scrape_news(),
        )

        self.root.bind(
            "<Control-e>",
            lambda event: self.export_csv(),
        )

        self.root.bind(
            "<Control-j>",
            lambda event: self.export_json(),
        )

        self.root.bind(
            "<F11>",
            lambda event: self.toggle_fullscreen(),
        )

        self.root.bind(
            "<Escape>",
            lambda event: self.exit_fullscreen(),
        )

    def scrape_news(self):

        url = self.url_var.get().strip()

        if not url:

            messagebox.showwarning(
                "URL Required",
                "Enter a news website URL.",
            )

            return

        self.controls.disable()

        self.progress_var.set(10)

        self.status_var.set("Fetching webpage...")

        self.root.update_idletasks()

        try:

            html = self.scraper.fetch_page(url)

            self.progress_var.set(60)

            self.status_var.set("Parsing articles...")

            self.root.update_idletasks()

            self.articles = self.parser.parse(
                html,
                url,
            )

            self.progress_var.set(100)

            self.count_var.set(str(len(self.articles)))

            self.display_articles()

            self.status_var.set("Scraping completed")

        except Exception as error:

            self.progress_var.set(0)

            self.status_var.set("Scraping failed")

            messagebox.showerror(
                "Scraping Error",
                str(error),
            )

        finally:

            self.controls.enable()

    def display_articles(self):

        self.output.delete(
            "1.0",
            tk.END,
        )

        if not self.articles:

            self.output.insert(
                tk.END,
                "No articles found.",
            )

            return

        for index, article in enumerate(
            self.articles,
            start=1,
        ):

            self.output.insert(
                tk.END,
                f"{index}. {article['title']}\n",
            )

            if article["date"]:

                self.output.insert(
                    tk.END,
                    f"Date: {article['date']}\n",
                )

            if article["link"]:

                self.output.insert(
                    tk.END,
                    f"Link: {article['link']}\n",
                )

            if article["summary"]:

                self.output.insert(
                    tk.END,
                    f"Summary: {article['summary']}\n",
                )

            self.output.insert(
                tk.END,
                "\n",
            )

    def export_csv(self):

        if not self.articles:

            messagebox.showwarning(
                "No Data",
                "Scrape articles before exporting.",
            )

            return

        file = self.exporter.export_csv(self.articles)

        if file:

            self.status_var.set("CSV exported successfully")

            messagebox.showinfo(
                "Export Complete",
                "News data exported to CSV.",
            )

    def export_json(self):

        if not self.articles:

            messagebox.showwarning(
                "No Data",
                "Scrape articles before exporting.",
            )

            return

        file = self.exporter.export_json(self.articles)

        if file:

            self.status_var.set("JSON exported successfully")

            messagebox.showinfo(
                "Export Complete",
                "News data exported to JSON.",
            )

    def clear_results(self):

        self.articles = []

        self.output.delete(
            "1.0",
            tk.END,
        )

        self.count_var.set("0")

        self.progress_var.set(0)

        self.status_var.set("Ready")

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

    def on_close(self):

        self.scraper.close()

        self.root.destroy()

    def run(self):

        self.root.mainloop()


def main():

    app = NewsScraperApp()

    app.run()


if __name__ == "__main__":

    main()
