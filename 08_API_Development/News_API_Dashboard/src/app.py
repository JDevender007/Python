"""
News API Dashboard - Main Application Module
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser
from typing import List, Optional, Dict
from .config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, MIN_WIDTH, MIN_HEIGHT,
    COLORS, COUNTRIES, CATEGORIES, SORT_OPTIONS
)
from .tracker import NewsTracker, create_tracker
from .exporter import NewsExporter, create_exporter
from .controls import (
    ModernFrame, ModernLabel, ModernButton, ModernEntry, ModernCombobox,
    ModernTreeview, ProgressDialog, ExportDialog, ArticleCard, SourceCard
)
from .utils import format_number, format_relative_time
from .logger import logger


class NewsDashboardApp:
    """Main application class for News API Dashboard."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.tracker = create_tracker()
        self.exporter = create_exporter()
        self.setup_tracker_callbacks()
        self.setup_window()
        self.create_widgets()
        self.bind_shortcuts()

    def setup_tracker_callbacks(self):
        self.tracker.set_progress_callback(self.on_progress)
        self.tracker.set_status_callback(self.on_status)

    def setup_window(self):
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.root.configure(bg=COLORS["bg"])
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        self.create_header()
        self.create_main_content()
        self.create_status_bar()

    def create_header(self):
        header = ModernFrame(self.root)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        header.grid_columnconfigure(1, weight=1)

        # Title
        ModernLabel(header, text="📰 News API Dashboard", style="title").grid(row=0, column=0, sticky="w")

        # Controls
        controls_frame = ModernFrame(header)
        controls_frame.grid(row=0, column=1, sticky="e")

        # Search
        ModernLabel(controls_frame, text="Search:", style="secondary").pack(side="left", padx=5)
        self.search_entry = ModernEntry(controls_frame, placeholder="Search news...")
        self.search_entry.pack(side="left", padx=5, ipady=5)
        self.search_entry.bind("<Return>", lambda e: self.search_news())

        # Country
        self.country_var = tk.StringVar(value="us")
        country_combo = ModernCombobox(
            controls_frame,
            values=[f"{v} ({k})" for k, v in COUNTRIES.items()],
            textvariable=self.country_var,
            width=20
        )
        country_combo.pack(side="left", padx=5)
        country_combo.bind("<<ComboboxSelected>>", lambda e: self.on_country_change())

        # Category
        self.category_var = tk.StringVar(value="general")
        cat_combo = ModernCombobox(
            controls_frame,
            values=[c.title() for c in CATEGORIES],
            textvariable=self.category_var,
            width=15
        )
        cat_combo.pack(side="left", padx=5)
        cat_combo.bind("<<ComboboxSelected>>", lambda e: self.on_category_change())

        # Action buttons
        ModernButton(controls_frame, text="Search", command=self.search_news, style="primary").pack(side="left", padx=5)
        ModernButton(controls_frame, text="Top Headlines", command=self.load_headlines, style="secondary").pack(side="left", padx=5)
        ModernButton(controls_frame, text="Sources", command=self.load_sources, style="secondary").pack(side="left", padx=5)

    def create_main_content(self):
        # Notebook for tabs
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Modern.TNotebook",
            background=COLORS["bg"],
            borderwidth=0,
        )
        style.configure(
            "Modern.TNotebook.Tab",
            background=COLORS["card_bg"],
            foreground=COLORS["text_secondary"],
            padding=[20, 10],
            font=("Segoe UI", 10),
        )
        style.map(
            "Modern.TNotebook.Tab",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", COLORS["bg"])],
        )

        self.notebook = ttk.Notebook(self.root, style="Modern.TNotebook")
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.root.grid_rowconfigure(1, weight=1)

        self.create_headlines_tab()
        self.create_search_tab()
        self.create_sources_tab()
        self.create_bookmarks_tab()

    def create_headlines_tab(self):
        self.headlines_tab = ModernFrame(self.notebook)
        self.notebook.add(self.headlines_tab, text="  Top Headlines  ")
        self.headlines_tab.grid_rowconfigure(1, weight=1)
        self.headlines_tab.grid_columnconfigure(0, weight=1)

        # Category filter bar
        filter_frame = ModernFrame(self.headlines_tab)
        filter_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)

        ModernLabel(filter_frame, text="Category:", style="secondary").pack(side="left", padx=5)
        self.hl_category_var = tk.StringVar(value="general")
        cat_combo = ModernCombobox(
            filter_frame,
            values=[c.title() for c in CATEGORIES],
            textvariable=self.hl_category_var,
            width=15
        )
        cat_combo.pack(side="left", padx=5)
        cat_combo.bind("<<ComboboxSelected>>", lambda e: self.load_headlines())

        ModernButton(filter_frame, text="Refresh", command=self.load_headlines, style="secondary").pack(side="right", padx=5)

        # Articles list
        list_frame = ModernFrame(self.headlines_tab)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.hl_canvas = tk.Canvas(list_frame, bg=COLORS["bg"], highlightthickness=0)
        self.hl_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.hl_canvas.yview)
        self.hl_inner = ModernFrame(self.hl_canvas)

        self.hl_inner.bind(
            "<Configure>",
            lambda e: self.hl_canvas.configure(scrollregion=self.hl_canvas.bbox("all"))
        )

        self.hl_canvas.create_window((0, 0), window=self.hl_inner, anchor="nw")
        self.hl_canvas.configure(yscrollcommand=self.hl_scrollbar.set)

        self.hl_canvas.grid(row=0, column=0, sticky="nsew")
        self.hl_scrollbar.grid(row=0, column=1, sticky="ns")

        self.hl_canvas.bind("<MouseWheel>", self._on_hl_scroll)

    def _on_hl_scroll(self, event):
        self.hl_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_search_tab(self):
        self.search_tab = ModernFrame(self.notebook)
        self.notebook.add(self.search_tab, text="  Search Everything  ")
        self.search_tab.grid_rowconfigure(1, weight=1)
        self.search_tab.grid_columnconfigure(0, weight=1)

        # Search controls
        search_frame = ModernFrame(self.search_tab)
        search_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)

        ModernLabel(search_frame, text="Query:", style="secondary").pack(side="left", padx=5)
        self.search_q_entry = ModernEntry(search_frame, placeholder="Search for news...")
        self.search_q_entry.pack(side="left", fill="x", expand=True, padx=5, ipady=5)
        self.search_q_entry.bind("<Return>", lambda e: self.search_everything())

        # Sort by
        ModernLabel(search_frame, text="Sort:", style="secondary").pack(side="left", padx=(20, 5))
        self.sort_var = tk.StringVar(value="publishedAt")
        sort_combo = ModernCombobox(
            search_frame,
            values=[s.title() for s in SORT_OPTIONS],
            textvariable=self.sort_var,
            width=15
        )
        sort_combo.pack(side="left", padx=5)

        # Date range
        ModernLabel(search_frame, text="From:", style="secondary").pack(side="left", padx=(20, 5))
        self.from_entry = ModernEntry(search_frame, placeholder="YYYY-MM-DD", width=12)
        self.from_entry.pack(side="left", padx=5)

        ModernLabel(search_frame, text="To:", style="secondary").pack(side="left", padx=(10, 5))
        self.to_entry = ModernEntry(search_frame, placeholder="YYYY-MM-DD", width=12)
        self.to_entry.pack(side="left", padx=5)

        # Language
        ModernLabel(search_frame, text="Lang:", style="secondary").pack(side="left", padx=(20, 5))
        self.lang_var = tk.StringVar(value="en")
        lang_combo = ModernCombobox(
            search_frame,
            values=["en", "es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ar"],
            textvariable=self.lang_var,
            width=8
        )
        lang_combo.pack(side="left", padx=5)

        ModernButton(search_frame, text="Search", command=self.search_everything, style="primary").pack(side="left", padx=5)
        ModernButton(search_frame, text="Export", command=self.export_search_results, style="secondary").pack(side="left", padx=5)

        # Results list
        list_frame = ModernFrame(self.search_tab)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.search_canvas = tk.Canvas(list_frame, bg=COLORS["bg"], highlightthickness=0)
        self.search_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.search_canvas.yview)
        self.search_inner = ModernFrame(self.search_canvas)

        self.search_inner.bind(
            "<Configure>",
            lambda e: self.search_canvas.configure(scrollregion=self.search_canvas.bbox("all"))
        )

        self.search_canvas.create_window((0, 0), window=self.search_inner, anchor="nw")
        self.search_canvas.configure(yscrollcommand=self.search_scrollbar.set)

        self.search_canvas.grid(row=0, column=0, sticky="nsew")
        self.search_scrollbar.grid(row=0, column=1, sticky="ns")

        self.search_canvas.bind("<MouseWheel>", self._on_search_scroll)

    def _on_search_scroll(self, event):
        self.search_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_sources_tab(self):
        self.sources_tab = ModernFrame(self.notebook)
        self.notebook.add(self.sources_tab, text="  Sources  ")
        self.sources_tab.grid_rowconfigure(1, weight=1)
        self.sources_tab.grid_columnconfigure(0, weight=1)

        # Filter bar
        filter_frame = ModernFrame(self.sources_tab)
        filter_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)

        ModernLabel(filter_frame, text="Country:", style="secondary").pack(side="left", padx=5)
        self.src_country_var = tk.StringVar(value="us")
        country_combo = ModernCombobox(
            filter_frame,
            values=[f"{v} ({k})" for k, v in COUNTRIES.items()],
            textvariable=self.src_country_var,
            width=20
        )
        country_combo.pack(side="left", padx=5)

        ModernLabel(filter_frame, text="Category:", style="secondary").pack(side="left", padx=(20, 5))
        self.src_cat_var = tk.StringVar(value="general")
        cat_combo = ModernCombobox(
            filter_frame,
            values=["all"] + [c.title() for c in CATEGORIES],
            textvariable=self.src_cat_var,
            width=15
        )
        cat_combo.pack(side="left", padx=5)

        ModernButton(filter_frame, text="Load Sources", command=self.load_sources, style="primary").pack(side="right", padx=5)
        ModernButton(filter_frame, text="Export", command=self.export_sources, style="secondary").pack(side="right", padx=5)

        # Sources list
        list_frame = ModernFrame(self.sources_tab)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.src_canvas = tk.Canvas(list_frame, bg=COLORS["bg"], highlightthickness=0)
        self.src_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.src_canvas.yview)
        self.src_inner = ModernFrame(self.src_canvas)

        self.src_inner.bind(
            "<Configure>",
            lambda e: self.src_canvas.configure(scrollregion=self.src_canvas.bbox("all"))
        )

        self.src_canvas.create_window((0, 0), window=self.src_inner, anchor="nw")
        self.src_canvas.configure(yscrollcommand=self.src_scrollbar.set)

        self.src_canvas.grid(row=0, column=0, sticky="nsew")
        self.src_scrollbar.grid(row=0, column=1, sticky="ns")

        self.src_canvas.bind("<MouseWheel>", self._on_src_scroll)

    def _on_src_scroll(self, event):
        self.src_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_bookmarks_tab(self):
        self.bookmarks_tab = ModernFrame(self.notebook)
        self.notebook.add(self.bookmarks_tab, text="  Bookmarks  ")
        self.bookmarks_tab.grid_rowconfigure(0, weight=1)
        self.bookmarks_tab.grid_columnconfigure(0, weight=1)

        ModernLabel(self.bookmarks_tab, text="🔖 Bookmarked Articles", style="title").pack(pady=30)
        ModernLabel(self.bookmarks_tab, text="Bookmark feature coming soon!", style="secondary").pack()

    def create_status_bar(self):
        status_frame = ModernFrame(self.root)
        status_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)

        self.status_label = ModernLabel(status_frame, text="Ready", style="secondary")
        self.status_label.pack(side="left")

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            status_frame, variable=self.progress_var, mode="determinate", length=200
        )
        self.progress_bar.pack(side="right", padx=20)

        # Article count
        self.count_label = ModernLabel(status_frame, text="Articles: 0", style="secondary")
        self.count_label.pack(side="right", padx=20)

    def bind_shortcuts(self):
        self.root.bind("<Control-f>", lambda e: self.search_entry.focus())
        self.root.bind("<Control-r>", lambda e: self.load_headlines())
        self.root.bind("<Control-e>", lambda e: self.export_current_tab())
        self.root.bind("<Control-s>", lambda e: self.search_everything())
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.exit_fullscreen)
        self.fullscreen = False

    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def exit_fullscreen(self, event=None):
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)

    def on_progress(self, current: int, total: int, message: str):
        self.root.after(0, lambda: self._update_progress_ui(current, total, message))

    def _update_progress_ui(self, current: int, total: int, message: str):
        self.progress_var.set((current / total * 100) if total > 0 else 0)
        self.status_label.config(text=message)

    def on_status(self, message: str):
        self.root.after(0, lambda: self.status_label.config(text=message))

    def load_headlines(self):
        self.progress_var.set(0)
        self.clear_articles_display(self.hl_inner)

        country = self.country_var.get().split("(")[-1].rstrip(")") if "(" in self.country_var.get() else "us"
        category = self.hl_category_var.get().lower()

        def run_load():
            articles = self.tracker.fetch_top_headlines(
                country=country,
                category=category,
                page_size=20
            )
            self.root.after(0, lambda: self.display_articles(self.hl_inner, articles))

        threading.Thread(target=run_load, daemon=True).start()

    def on_country_change(self):
        # Update headlines when country changes
        self.load_headlines()

    def on_category_change(self):
        # Update headlines when category changes
        self.load_headlines()

    def search_news(self):
        query = self.search_entry.get_value().strip()
        if not query:
            messagebox.showwarning("Empty Search", "Please enter a search term")
            return

        self.progress_var.set(0)
        self.notebook.select(self.search_tab)
        self.clear_articles_display(self.search_inner)

        def run_search():
            articles = self.tracker.fetch_everything(
                q=query,
                page_size=20
            )
            self.root.after(0, lambda: self.display_articles(self.search_inner, articles))

        threading.Thread(target=run_search, daemon=True).start()

    def search_everything(self):
        q = self.search_q_entry.get_value().strip()
        if not q:
            # Use top headlines if no query
            self.load_headlines()
            return

        self.progress_var.set(0)
        self.notebook.select(self.search_tab)
        self.clear_articles_display(self.search_inner)

        sort_by = self.sort_var.get()
        from_date = self.from_entry.get_value().strip()
        to_date = self.to_entry.get_value().strip()
        language = self.lang_var.get()

        def run_search():
            articles = self.tracker.fetch_everything(
                q=q,
                sort_by=sort_by,
                from_date=from_date if from_date else None,
                to_date=to_date if to_date else None,
                language=language,
                page_size=20
            )
            self.root.after(0, lambda: self.display_articles(self.search_inner, articles))

        threading.Thread(target=run_search, daemon=True).start()

    def load_sources(self):
        self.progress_var.set(0)
        self.notebook.select(self.sources_tab)
        self.clear_sources_display()

        country = self.src_country_var.get().split("(")[-1].rstrip(")") if "(" in self.src_country_var.get() else "us"
        category = self.src_cat_var.get().lower() if self.src_cat_var.get().lower() != "all" else None

        def run_load():
            sources = self.tracker.fetch_sources(
                country=country,
                category=category
            )
            self.root.after(0, lambda: self.display_sources(sources))

        threading.Thread(target=run_load, daemon=True).start()

    def display_articles(self, container: tk.Frame, articles: List):
        self.clear_articles_display(container)

        if not articles:
            ModernLabel(container, text="No articles found", style="secondary").pack(pady=50)
            self.count_label.config(text="Articles: 0")
            return

        for article in articles:
            def make_callback(art):
                return lambda: self.open_article(art)

            card = ArticleCard(container, article, on_click=make_callback(article))
            card.pack(fill="x", padx=10, pady=5)

        self.count_label.config(text=f"Articles: {len(articles)}")

    def clear_articles_display(self, container: tk.Frame):
        for widget in container.winfo_children():
            widget.destroy()

    def display_sources(self, sources: List):
        self.clear_sources_display()

        if not sources:
            ModernLabel(self.src_inner, text="No sources found", style="secondary").pack(pady=50)
            return

        for source in sources:
            card = SourceCard(self.src_inner, source)
            card.pack(fill="x", padx=10, pady=5)

    def clear_sources_display(self):
        for widget in self.src_inner.winfo_children():
            widget.destroy()

    def open_article(self, article):
        webbrowser.open(article.url)

    def export_current_tab(self):
        current_tab = self.notebook.index(self.notebook.select())
        tab_names = ["headlines", "search", "sources", "bookmarks"]

        if current_tab == 0:  # Headlines
            articles = self.tracker.get_headlines()
            self.export_articles(articles, "headlines")
        elif current_tab == 1:  # Search
            articles = self.tracker.get_all_articles()
            self.export_articles(articles, "search")
        elif current_tab == 2:  # Sources
            sources = self.tracker.get_sources_list()
            self.export_sources(sources)

    def export_articles(self, articles: List, prefix: str = "articles"):
        if not articles:
            messagebox.showwarning("No Data", "No articles to export")
            return

        def export_callback(filepath: str, fmt: str):
            if fmt in ("csv", "both"):
                self.exporter.export_articles(articles, filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                self.exporter.export_articles_json(articles, filepath if fmt == "json" else None)
            messagebox.showinfo("Export Complete", f"{len(articles)} articles exported successfully!")

        ExportDialog(self.root, export_callback)

    def export_search_results(self):
        articles = self.tracker.get_all_articles()
        self.export_articles(articles, "search")

    def export_sources(self, sources: List = None):
        if sources is None:
            sources = self.tracker.get_sources_list()

        if not sources:
            messagebox.showwarning("No Data", "No sources to export")
            return

        def export_callback(filepath: str, fmt: str):
            if fmt in ("csv", "both"):
                self.exporter.export_sources(sources, filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                self.exporter.export_sources_json(sources, filepath if fmt == "json" else None)
            messagebox.showinfo("Export Complete", f"{len(sources)} sources exported successfully!")

        ExportDialog(self.root, export_callback)

    def on_closing(self):
        if self.tracker.is_fetching:
            if messagebox.askyesno("Quit", "Fetching in progress. Quit anyway?"):
                self.tracker.stop()
                self.tracker.close()
                self.root.destroy()
        else:
            self.tracker.close()
            self.root.destroy()


import threading


def main():
    root = tk.Tk()
    app = NewsDashboardApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()