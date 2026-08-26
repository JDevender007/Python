"""
GitHub Repository Scraper - Main Application Module
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import List, Dict, Optional
from .config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, MIN_WIDTH, MIN_HEIGHT,
    COLORS, DEFAULT_URL, MAX_REPOS
)
from .tracker import RepoTracker, create_tracker
from .controls import (
    ModernFrame, ModernLabel, ModernButton, ModernEntry,
    ModernTreeview, ProgressDialog, ExportDialog, RepoDetailDialog
)
from .logger import logger


class GitHubRepoScraperApp:
    """Main application class for GitHub Repository Scraper."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.tracker = create_tracker()
        self.setup_tracker_callbacks()
        self.setup_window()
        self.create_widgets()
        self.bind_shortcuts()

    def setup_tracker_callbacks(self):
        """Set up tracker callbacks for UI updates."""
        self.tracker.set_progress_callback(self.on_progress)
        self.tracker.set_status_callback(self.on_status)

    def setup_window(self):
        """Configure main window."""
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.root.configure(bg=COLORS["bg"])

        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        """Create and layout all widgets."""
        self.create_header()
        self.create_toolbar()
        self.create_main_area()
        self.create_status_bar()

    def create_header(self):
        """Create header section."""
        header_frame = ModernFrame(self.root)
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        header_frame.grid_columnconfigure(1, weight=1)

        ModernLabel(header_frame, text="GitHub Repository Scraper", style="title").grid(row=0, column=0, sticky="w")

        controls_frame = ModernFrame(header_frame)
        controls_frame.grid(row=0, column=1, sticky="e", padx=20)

        # Mode selector
        self.mode_var = tk.StringVar(value="trending")
        mode_frame = ModernFrame(controls_frame)
        mode_frame.pack(side="left", padx=10)

        ModernLabel(mode_frame, text="Mode:", style="secondary").pack(side="left", padx=5)
        ttk.Combobox(
            mode_frame, textvariable=self.mode_var,
            values=["trending", "user"],
            state="readonly", width=12, font=("Segoe UI", 9)
        ).pack(side="left", padx=5)

        # Language/username entry
        self.param_entry = ModernEntry(controls_frame, placeholder="Language (e.g., python) or username")
        self.param_entry.pack(side="left", padx=5, ipady=5)

        # Since selector (for trending)
        self.since_var = tk.StringVar(value="daily")
        self.since_combo = ttk.Combobox(
            controls_frame, textvariable=self.since_var,
            values=["daily", "weekly", "monthly"],
            state="readonly", width=10, font=("Segoe UI", 9)
        )
        self.since_combo.pack(side="left", padx=5)

        self.mode_var.trace("w", self._on_mode_change)

    def _on_mode_change(self, *args):
        """Handle mode change."""
        mode = self.mode_var.get()
        if mode == "trending":
            self.param_entry.config(state="normal")
            self.param_entry.placeholder = "Language (e.g., python, javascript)"
            self.since_combo.config(state="readonly")
        else:
            self.param_entry.config(state="normal")
            self.param_entry.placeholder = "GitHub username"
            self.since_combo.config(state="disabled")

    def create_toolbar(self):
        """Create toolbar with action buttons."""
        toolbar = ModernFrame(self.root)
        toolbar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        buttons = [
            ("Scrape", self.scrape, "primary"),
            ("Scrape Details", self.scrape_details, "primary"),
            ("Stop", self.stop_scraping, "secondary"),
            ("Clear Data", self.clear_data, "secondary"),
            ("Export", self.show_export_dialog, "primary"),
        ]

        for text, command, style in buttons:
            ModernButton(toolbar, text=text, command=command, style=style).pack(side="left", padx=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            toolbar, variable=self.progress_var, mode="determinate",
            style="Modern.Horizontal.TProgressbar"
        )
        self.progress_bar.pack(side="right", fill="x", expand=True, padx=20)

    def create_main_area(self):
        """Create main table area."""
        main_frame = ModernFrame(self.root)
        main_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

        columns = [
            "rank", "name", "owner", "language", "stars",
            "forks", "today_stars", "description"
        ]

        self.tree = ModernTreeview(main_frame, columns=columns)
        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(main_frame, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=hsb.set)

        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Return>", self.on_double_click)

        self.tree.column("rank", width=60, anchor="center", stretch=False)
        self.tree.column("name", width=250, anchor="w")
        self.tree.column("owner", width=120, anchor="w")
        self.tree.column("language", width=100, anchor="center", stretch=False)
        self.tree.column("stars", width=80, anchor="center", stretch=False)
        self.tree.column("forks", width=80, anchor="center", stretch=False)
        self.tree.column("today_stars", width=100, anchor="center", stretch=False)
        self.tree.column("description", width=350, anchor="w")

    def create_status_bar(self):
        """Create status bar."""
        status_frame = ModernFrame(self.root)
        status_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=10)

        self.status_label = ModernLabel(status_frame, text="Ready", style="secondary")
        self.status_label.pack(side="left")

        self.repo_count_label = ModernLabel(status_frame, text="Repositories: 0", style="secondary")
        self.repo_count_label.pack(side="right")

    def bind_shortcuts(self):
        """Bind keyboard shortcuts."""
        self.root.bind("<Control-s>", lambda e: self.scrape())
        self.root.bind("<Control-d>", lambda e: self.scrape_details())
        self.root.bind("<Control-e>", lambda e: self.show_export_dialog())
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
        """Handle progress updates from tracker."""
        self.root.after(0, lambda: self._update_progress_ui(current, total, message))

    def _update_progress_ui(self, current: int, total: int, message: str):
        self.progress_var.set((current / total * 100) if total > 0 else 0)
        self.status_label.config(text=message)

    def on_status(self, message: str):
        """Handle status updates from tracker."""
        self.root.after(0, lambda: self.status_label.config(text=message))

    def scrape(self):
        """Start scraping based on selected mode."""
        if self.tracker.is_scraping:
            messagebox.showwarning("Busy", "Scraping already in progress")
            return

        mode = self.mode_var.get()
        param = self.param_entry.get_value().strip()
        since = self.since_var.get()

        self.progress_var.set(0)
        self.tree.delete(*self.tree.get_children())

        def run_scrape():
            if mode == "trending":
                repos = self.tracker.scrape_trending(
                    DEFAULT_URL, language=param, since=since
                )
            else:
                if not param:
                    self.root.after(0, lambda: messagebox.showwarning("Missing Username", "Please enter a GitHub username"))
                    return
                repos = self.tracker.scrape_user_repos(param)

            self.root.after(0, lambda: self.populate_table(repos))

        threading.Thread(target=run_scrape, daemon=True).start()

    def scrape_details(self):
        """Start scraping detailed information."""
        if self.tracker.is_scraping:
            messagebox.showwarning("Busy", "Scraping already in progress")
            return

        if not self.tracker.get_repos():
            messagebox.showwarning("No Data", "Please scrape repositories first")
            return

        def run_details():
            self.tracker.scrape_details()
            self.root.after(0, lambda: self.populate_table(self.tracker.get_detailed_repos()))

        threading.Thread(target=run_details, daemon=True).start()

    def stop_scraping(self):
        """Stop current scraping operation."""
        self.tracker.stop()

    def clear_data(self):
        """Clear all data."""
        if messagebox.askyesno("Clear Data", "Clear all scraped data?"):
            self.tracker.clear()
            self.tree.delete(*self.tree.get_children())
            self.repo_count_label.config(text="Repositories: 0")
            self.status_label.config(text="Ready")
            self.progress_var.set(0)

    def populate_table(self, repos: List[Dict]):
        """Populate the treeview with repository data."""
        self.tree.delete(*self.tree.get_children())

        for idx, repo in enumerate(repos):
            values = [
                repo.get("rank", ""),
                repo.get("name", ""),
                repo.get("owner", "") if repo.get("owner") else "",
                repo.get("language", "") if repo.get("language") else "",
                format_number(repo.get("stars")) if repo.get("stars") else "",
                format_number(repo.get("forks")) if repo.get("forks") else "",
                format_number(repo.get("today_stars")) if repo.get("today_stars") else "",
                repo.get("description", "")[:100] + "..." if repo.get("description", "") and len(repo.get("description", "")) > 100 else repo.get("description", ""),
            ]
            tag = "odd" if idx % 2 else "even"
            self.tree.insert("", "end", values=values, tags=(tag,))

        self.repo_count_label.config(text=f"Repositories: {len(repos)}")
        self.status_label.config(text=f"Loaded {len(repos)} repositories")
        self.progress_var.set(100)

    def on_double_click(self, event):
        """Handle double-click on repository row."""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        rank = item["values"][0]

        repos = self.tracker.get_detailed_repos()
        repo = next((r for r in repos if r.get("rank") == rank), None)

        if repo:
            RepoDetailDialog(self.root, repo)

    def show_export_dialog(self):
        """Show export dialog."""
        repos = self.tracker.get_detailed_repos()
        if not repos:
            messagebox.showwarning("No Data", "No data to export. Please scrape first.")
            return

        def export_callback(filepath: str, fmt: str):
            if fmt in ("csv", "both"):
                self.tracker.export_csv(filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                self.tracker.export_json(filepath if fmt == "json" else None)
            messagebox.showinfo("Export Complete", f"Data exported successfully!")

        ExportDialog(self.root, export_callback)

    def on_closing(self):
        """Handle window closing."""
        if self.tracker.is_scraping:
            if messagebox.askyesno("Quit", "Scraping in progress. Are you sure you want to quit?"):
                self.tracker.stop()
                self.root.destroy()
        else:
            self.root.destroy()


def format_number(num: Optional[int]) -> str:
    """Format number with K/M suffix."""
    if num is None:
        return "N/A"
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num/1_000:.1f}k"
    return str(num)


def main():
    """Main entry point."""
    root = tk.Tk()
    app = GitHubRepoScraperApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()