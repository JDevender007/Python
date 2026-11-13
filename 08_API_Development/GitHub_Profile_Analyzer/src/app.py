"""
GitHub Profile Analyzer - Main Application Module
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser
from typing import List, Optional, Dict
from .config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, MIN_WIDTH, MIN_HEIGHT,
    COLORS, GITHUB_GREEN, GITHUB_BLUE, GITHUB_PURPLE, GITHUB_ORANGE, GITHUB_RED
)
from .tracker import GitHubTracker, create_tracker
from .exporter import GitHubExporter, create_exporter
from .controls import (
    ModernFrame, ModernLabel, ModernButton, ModernEntry, ModernCombobox,
    ModernTreeview, ProgressDialog, ExportDialog, StatCard, LanguageBar,
    RepoCard, EventCard
)
from .utils import format_number, format_date, format_datetime, get_language_color
from .logger import logger


class GitHubProfileAnalyzerApp:
    """Main application class for GitHub Profile Analyzer."""

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

        # GitHub logo + title
        title_frame = ModernFrame(header)
        title_frame.grid(row=0, column=0, sticky="w")

        ModernLabel(title_frame, text="🐙", style="title").pack(side="left", padx=(0, 10))
        ModernLabel(title_frame, text="GitHub Profile Analyzer", style="title").pack(side="left")

        # Search section
        search_frame = ModernFrame(header)
        search_frame.grid(row=0, column=1, sticky="e")

        ModernLabel(search_frame, text="Username:", style="secondary").pack(side="left", padx=5)
        self.username_entry = ModernEntry(search_frame, placeholder="Enter GitHub username")
        self.username_entry.pack(side="left", padx=5, ipady=5, ipadx=10)
        self.username_entry.bind("<Return>", lambda e: self.analyze_user())

        ModernButton(search_frame, text="Analyze", command=self.analyze_user, style="primary").pack(side="left", padx=5)
        ModernButton(search_frame, text="Rate Limit", command=self.check_rate_limit, style="secondary").pack(side="left", padx=5)

        # Rate limit indicator
        self.rate_limit_label = ModernLabel(search_frame, text="Rate Limit: Unknown", style="secondary")
        self.rate_limit_label.pack(side="left", padx=20)

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

        self.create_overview_tab()
        self.create_repos_tab()
        self.create_languages_tab()
        self.create_activity_tab()
        self.create_settings_tab()

    def create_overview_tab(self):
        self.overview_tab = ModernFrame(self.notebook)
        self.notebook.add(self.overview_tab, text="  Overview  ")
        self.overview_tab.grid_rowconfigure(1, weight=1)
        self.overview_tab.grid_columnconfigure(0, weight=1)

        # Profile header
        self.profile_frame = ModernFrame(self.overview_tab)
        self.profile_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        self.profile_frame.grid_columnconfigure(1, weight=1)

        # Avatar placeholder
        self.avatar_label = ModernLabel(self.profile_frame, text="👤", style="large")
        self.avatar_label.grid(row=0, column=0, rowspan=3, padx=20, pady=10)

        # Profile info
        self.profile_name = ModernLabel(self.profile_frame, text="", style="title")
        self.profile_name.grid(row=0, column=1, sticky="w")

        self.profile_bio = ModernLabel(self.profile_frame, text="", style="secondary", wraplength=500, justify="left")
        self.profile_bio.grid(row=1, column=1, sticky="w", pady=5)

        self.profile_meta = ModernLabel(self.profile_frame, text="", style="secondary")
        self.profile_meta.grid(row=2, column=1, sticky="w")

        # Stat cards
        stats_frame = ModernFrame(self.overview_tab)
        stats_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.stat_repos = StatCard(stats_frame, "Repositories", "0", "📁")
        self.stat_repos.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.stat_stars = StatCard(stats_frame, "Total Stars", "0", "⭐")
        self.stat_stars.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.stat_forks = StatCard(stats_frame, "Total Forks", "0", "🍴")
        self.stat_forks.grid(row=0, column=2, padx=10, pady=10, sticky="ew")

        self.stat_followers = StatCard(stats_frame, "Followers", "0", "👥")
        self.stat_followers.grid(row=0, column=3, padx=10, pady=10, sticky="ew")

        # Action buttons
        btn_frame = ModernFrame(self.overview_tab)
        btn_frame.grid(row=2, column=0, pady=10)
        ModernButton(btn_frame, text="Refresh", command=self.refresh_data, style="primary").pack(side="left", padx=5)
        ModernButton(btn_frame, text="Export Profile", command=self.export_profile, style="secondary").pack(side="left", padx=5)
        ModernButton(btn_frame, text="View on GitHub", command=self.open_profile, style="secondary").pack(side="left", padx=5)

    def create_repos_tab(self):
        self.repos_tab = ModernFrame(self.notebook)
        self.notebook.add(self.repos_tab, text="  Repositories  ")
        self.repos_tab.grid_rowconfigure(1, weight=1)
        self.repos_tab.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ModernFrame(self.repos_tab)
        toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=10)

        ModernLabel(toolbar, text="Sort by:", style="secondary").pack(side="left", padx=5)
        self.sort_var = tk.StringVar(value="stars")
        ModernCombobox(toolbar, values=["stars", "forks", "updated", "created", "name", "size"],
                       textvariable=self.sort_var, width=12).pack(side="left", padx=5)
        self.sort_var.trace("w", lambda *args: self.sort_repos())

        ModernLabel(toolbar, text="Filter:", style="secondary").pack(side="left", padx=(20, 5))
        self.filter_var = tk.StringVar(value="all")
        ModernCombobox(toolbar, values=["all", "original", "forked", "archived"],
                       textvariable=self.filter_var, width=12).pack(side="left", padx=5)
        self.filter_var.trace("w", lambda *args: self.filter_repos())

        ModernButton(toolbar, text="Export", command=self.export_repos, style="secondary").pack(side="right", padx=5)

        # Repos list
        list_frame = ModernFrame(self.repos_tab)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.repos_canvas = tk.Canvas(list_frame, bg=COLORS["bg"], highlightthickness=0)
        self.repos_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.repos_canvas.yview)
        self.repos_inner = ModernFrame(self.repos_canvas)

        self.repos_inner.bind(
            "<Configure>",
            lambda e: self.repos_canvas.configure(scrollregion=self.repos_canvas.bbox("all"))
        )

        self.repos_canvas.create_window((0, 0), window=self.repos_inner, anchor="nw")
        self.repos_canvas.configure(yscrollcommand=self.repos_scrollbar.set)

        self.repos_canvas.grid(row=0, column=0, sticky="nsew")
        self.repos_scrollbar.grid(row=0, column=1, sticky="ns")

        self.repos_canvas.bind("<MouseWheel>", self._on_repos_scroll)

    def _on_repos_scroll(self, event):
        self.repos_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_languages_tab(self):
        self.languages_tab = ModernFrame(self.notebook)
        self.notebook.add(self.languages_tab, text="  Languages  ")
        self.languages_tab.grid_rowconfigure(0, weight=1)
        self.languages_tab.grid_columnconfigure(0, weight=1)

        list_frame = ModernFrame(self.languages_tab)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.languages_canvas = tk.Canvas(list_frame, bg=COLORS["bg"], highlightthickness=0)
        self.languages_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.languages_canvas.yview)
        self.languages_inner = ModernFrame(self.languages_canvas)

        self.languages_inner.bind(
            "<Configure>",
            lambda e: self.languages_canvas.configure(scrollregion=self.languages_canvas.bbox("all"))
        )

        self.languages_canvas.create_window((0, 0), window=self.languages_inner, anchor="nw")
        self.languages_canvas.configure(yscrollcommand=self.languages_scrollbar.set)

        self.languages_canvas.grid(row=0, column=0, sticky="nsew")
        self.languages_scrollbar.grid(row=0, column=1, sticky="ns")

        self.languages_canvas.bind("<MouseWheel>", self._on_languages_scroll)

        # Export button
        btn_frame = ModernFrame(self.languages_tab)
        btn_frame.grid(row=1, column=0, pady=10)
        ModernButton(btn_frame, text="Export Stats", command=self.export_stats, style="secondary").pack(side="left", padx=5)

    def _on_languages_scroll(self, event):
        self.languages_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_activity_tab(self):
        self.activity_tab = ModernFrame(self.notebook)
        self.notebook.add(self.activity_tab, text="  Activity  ")
        self.activity_tab.grid_rowconfigure(1, weight=1)
        self.activity_tab.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ModernFrame(self.activity_tab)
        toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=10)

        ModernButton(toolbar, text="Load Events", command=self.load_events, style="primary").pack(side="left", padx=5)
        ModernButton(toolbar, text="Load Followers", command=self.load_followers, style="secondary").pack(side="left", padx=5)
        ModernButton(toolbar, text="Load Following", command=self.load_following, style="secondary").pack(side="left", padx=5)

        # Events list
        list_frame = ModernFrame(self.activity_tab)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.events_canvas = tk.Canvas(list_frame, bg=COLORS["bg"], highlightthickness=0)
        self.events_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.events_canvas.yview)
        self.events_inner = ModernFrame(self.events_canvas)

        self.events_inner.bind(
            "<Configure>",
            lambda e: self.events_canvas.configure(scrollregion=self.events_canvas.bbox("all"))
        )

        self.events_canvas.create_window((0, 0), window=self.events_inner, anchor="nw")
        self.events_canvas.configure(yscrollcommand=self.events_scrollbar.set)

        self.events_canvas.grid(row=0, column=0, sticky="nsew")
        self.events_scrollbar.grid(row=0, column=1, sticky="ns")

        self.events_canvas.bind("<MouseWheel>", self._on_events_scroll)

    def _on_events_scroll(self, event):
        self.events_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_settings_tab(self):
        self.settings_tab = ModernFrame(self.notebook)
        self.notebook.add(self.settings_tab, text="  Settings  ")
        self.settings_tab.grid_rowconfigure(0, weight=1)
        self.settings_tab.grid_columnconfigure(0, weight=1)

        content = ModernFrame(self.settings_tab)
        content.pack(fill="both", expand=True, padx=40, pady=40)

        ModernLabel(content, text="Settings", style="title").pack(anchor="w", pady=(0, 20))

        # GitHub Token
        token_frame = ModernFrame(content)
        token_frame.pack(fill="x", pady=10)
        ModernLabel(token_frame, text="GitHub Token:", style="subtitle").pack(anchor="w")
        ModernLabel(token_frame, text="Add a personal access token for higher rate limits (5000/hr vs 60/hr)", style="secondary").pack(anchor="w", pady=(0, 5))
        self.token_entry = ModernEntry(token_frame, placeholder="ghp_xxxxxxxxxxxxxxxxxxxx")
        self.token_entry.pack(fill="x", pady=5, ipady=5)
        ModernButton(token_frame, text="Save Token", command=self.save_token, style="primary").pack(pady=5)

        # Theme info
        ModernLabel(content, text="Theme: GitHub Dark (Fixed)", style="subtitle").pack(anchor="w", pady=(20, 5))
        ModernLabel(content, text="This application uses a GitHub-inspired dark theme.", style="secondary").pack(anchor="w")

        # Cache
        cache_frame = ModernFrame(content)
        cache_frame.pack(fill="x", pady=20)
        ModernButton(cache_frame, text="Clear Cache", command=self.clear_cache, style="secondary").pack(side="left", padx=5)
        ModernButton(cache_frame, text="Clear History", command=self.clear_history, style="secondary").pack(side="left", padx=5)

        # About
        ModernLabel(content, text="About", style="subtitle").pack(anchor="w", pady=(20, 5))
        ModernLabel(content, text="GitHub Profile Analyzer v1.0.0\nBuilt with Python, Tkinter, and GitHub REST API", style="secondary").pack(anchor="w")

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

    def bind_shortcuts(self):
        self.root.bind("<Control-f>", lambda e: self.username_entry.focus())
        self.root.bind("<Control-r>", lambda e: self.refresh_data())
        self.root.bind("<Control-e>", lambda e: self.export_profile())
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

    def analyze_user(self):
        username = self.username_entry.get_value().strip()
        if not username:
            messagebox.showwarning("Empty Username", "Please enter a GitHub username")
            return

        self.progress_var.set(0)
        self.clear_profile_display()

        def run_analysis():
            # Fetch user
            user = self.tracker.fetch_user(username)
            if not user:
                self.root.after(0, lambda: messagebox.showerror("Error", f"User '{username}' not found"))
                return

            # Fetch repos
            repos = self.tracker.fetch_repos(username)
            if not repos and self.tracker.is_fetching:
                return

            # Fetch rate limit
            self.tracker.fetch_rate_limit()

            # Update UI
            self.root.after(0, lambda: self.display_profile(user, repos))

        threading.Thread(target=run_analysis, daemon=True).start()

    def clear_profile_display(self):
        self.profile_name.config(text="Loading...")
        self.profile_bio.config(text="")
        self.profile_meta.config(text="")
        self.stat_repos.update_value("0")
        self.stat_stars.update_value("0")
        self.stat_forks.update_value("0")
        self.stat_followers.update_value("0")
        self.clear_repos_display()
        self.clear_languages_display()

    def display_profile(self, user, repos):
        self.profile_name.config(text=f"{user.display_name} (@{user.login})")
        self.profile_bio.config(text=user.bio or "No bio available")
        
        meta = f"📍 {user.location or 'Unknown'} | 🏢 {user.company or 'N/A'} | 🔗 {user.blog or 'N/A'} | 📅 Joined {format_date(user.created_at)}"
        self.profile_meta.config(text=meta)

        stats = self.tracker.get_stats()
        if stats:
            self.stat_repos.update_value(format_number(stats.total_repos))
            self.stat_stars.update_value(format_number(stats.total_stars))
            self.stat_forks.update_value(format_number(stats.total_forks))
        self.stat_followers.update_value(format_number(user.followers))

        self.display_repos(repos)
        self.display_languages(stats.languages if stats else {})
        self.check_rate_limit()

    def display_repos(self, repos: List):
        self.clear_repos_display()

        if not repos:
            ModernLabel(self.repos_inner, text="No repositories found", style="secondary").pack(pady=50)
            return

        for i, repo in enumerate(repos):
            card = RepoCard(self.repos_inner, repo)
            card.pack(fill="x", padx=10, pady=5)

    def clear_repos_display(self):
        for widget in self.repos_inner.winfo_children():
            widget.destroy()

    def display_languages(self, languages: Dict[str, int]):
        self.clear_languages_display()

        if not languages:
            ModernLabel(self.languages_inner, text="No language data available", style="secondary").pack(pady=50)
            return

        total = sum(languages.values())
        sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)

        for lang, count in sorted_langs:
            percentage = (count / total * 100) if total > 0 else 0
            bar = LanguageBar(self.languages_inner, lang, percentage, count)
            bar.pack(fill="x", padx=20, pady=5)

    def clear_languages_display(self):
        for widget in self.languages_inner.winfo_children():
            widget.destroy()

    def sort_repos(self):
        if not self.tracker.repos:
            return

        sort_key = self.sort_var.get()
        reverse = sort_key in ["stars", "forks", "size_kb"]

        if sort_key == "stars":
            sorted_repos = sorted(self.tracker.repos, key=lambda x: x.stars, reverse=True)
        elif sort_key == "forks":
            sorted_repos = sorted(self.tracker.repos, key=lambda x: x.forks, reverse=True)
        elif sort_key == "updated":
            sorted_repos = sorted(self.tracker.repos, key=lambda x: x.updated_at, reverse=True)
        elif sort_key == "created":
            sorted_repos = sorted(self.tracker.repos, key=lambda x: x.created_at, reverse=True)
        elif sort_key == "name":
            sorted_repos = sorted(self.tracker.repos, key=lambda x: x.name.lower())
        elif sort_key == "size":
            sorted_repos = sorted(self.tracker.repos, key=lambda x: x.size_kb, reverse=True)
        else:
            sorted_repos = self.tracker.repos

        self.display_repos(sorted_repos)

    def filter_repos(self):
        if not self.tracker.repos:
            return

        filter_type = self.filter_var.get()
        if filter_type == "all":
            filtered = self.tracker.repos
        elif filter_type == "original":
            filtered = [r for r in self.tracker.repos if not r.fork]
        elif filter_type == "forked":
            filtered = [r for r in self.tracker.repos if r.fork]
        elif filter_type == "archived":
            filtered = [r for r in self.tracker.repos if r.archived]
        else:
            filtered = self.tracker.repos

        self.display_repos(filtered)

    def load_events(self):
        if not self.tracker.user:
            messagebox.showwarning("No User", "Please analyze a user first")
            return

        def run_events():
            events = self.tracker.fetch_events(self.tracker.user.login)
            self.root.after(0, lambda: self.display_events(events))

        threading.Thread(target=run_events, daemon=True).start()

    def display_events(self, events: List):
        for widget in self.events_inner.winfo_children():
            widget.destroy()

        if not events:
            ModernLabel(self.events_inner, text="No events found", style="secondary").pack(pady=50)
            return

        for event in events:
            card = EventCard(self.events_inner, event)
            card.pack(fill="x", padx=10, pady=5)

    def load_followers(self):
        if not self.tracker.user:
            messagebox.showwarning("No User", "Please analyze a user first")
            return

        def run_followers():
            followers = self.tracker.fetch_followers(self.tracker.user.login)
            self.root.after(0, lambda: self.show_followers_dialog(followers))

        threading.Thread(target=run_followers, daemon=True).start()

    def show_followers_dialog(self, followers: List):
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Followers of {self.tracker.user.login}")
        dialog.geometry("500x600")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)

        ModernLabel(dialog, text=f"Followers ({len(followers)})", style="title").pack(pady=20)

        canvas = tk.Canvas(dialog, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        inner = ModernFrame(canvas)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=20)
        scrollbar.pack(side="right", fill="y")

        for follower in followers:
            frame = ModernFrame(inner)
            frame.pack(fill="x", padx=10, pady=5)
            ModernLabel(frame, text=f"@{follower.login}", style="subtitle").pack(side="left")
            ModernLabel(frame, text=follower.name or "", style="secondary").pack(side="left", padx=10)

    def load_following(self):
        if not self.tracker.user:
            messagebox.showwarning("No User", "Please analyze a user first")
            return

        def run_following():
            following = self.tracker.fetch_following(self.tracker.user.login)
            self.root.after(0, lambda: self.show_following_dialog(following))

        threading.Thread(target=run_following, daemon=True).start()

    def show_following_dialog(self, following: List):
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Following ({len(following)})")
        dialog.geometry("500x600")
        dialog.configure(bg=COLORS["bg"])
        dialog.transient(self.root)

        ModernLabel(dialog, text=f"Following ({len(following)})", style="title").pack(pady=20)

        canvas = tk.Canvas(dialog, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        inner = ModernFrame(canvas)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=20)
        scrollbar.pack(side="right", fill="y")

        for user in following:
            frame = ModernFrame(inner)
            frame.pack(fill="x", padx=10, pady=5)
            ModernLabel(frame, text=f"@{user.login}", style="subtitle").pack(side="left")
            ModernLabel(frame, text=user.name or "", style="secondary").pack(side="left", padx=10)

    def check_rate_limit(self):
        rate = self.tracker.fetch_rate_limit()
        if rate:
            self.rate_limit_label.config(text=f"Rate Limit: {rate.remaining}/{rate.limit} (resets in {rate.reset_in_seconds//60}m)")

    def refresh_data(self):
        if not self.tracker.user:
            messagebox.showwarning("No User", "Please analyze a user first")
            return

        username = self.tracker.user.login
        self.progress_var.set(0)

        def run_refresh():
            self.tracker.clear_cache()
            self.tracker.fetch_user(username)
            self.tracker.fetch_repos(username, force_refresh=True)
            self.tracker.fetch_rate_limit()
            self.root.after(0, lambda: self.display_profile(self.tracker.user, self.tracker.repos))

        threading.Thread(target=run_refresh, daemon=True).start()

    def export_profile(self):
        if not self.tracker.user:
            messagebox.showwarning("No Data", "Please analyze a user first")
            return

        def export_callback(filepath: str, fmt: str):
            if fmt in ("csv", "both"):
                self.exporter.export_user_profile(self.tracker.user, filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                self.exporter.export_user_profile_json(self.tracker.user, filepath if fmt == "json" else None)
            messagebox.showinfo("Export Complete", "Profile exported successfully!")

        ExportDialog(self.root, export_callback)

    def export_repos(self):
        if not self.tracker.repos:
            messagebox.showwarning("No Data", "No repositories to export")
            return

        def export_callback(filepath: str, fmt: str):
            if fmt in ("csv", "both"):
                self.exporter.export_repositories(self.tracker.repos, filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                self.exporter.export_repositories_json(self.tracker.repos, filepath if fmt == "json" else None)
            messagebox.showinfo("Export Complete", "Repositories exported successfully!")

        ExportDialog(self.root, export_callback)

    def export_stats(self):
        stats = self.tracker.get_stats()
        if not stats:
            messagebox.showwarning("No Data", "No statistics to export")
            return

        def export_callback(filepath: str, fmt: str):
            if fmt in ("csv", "both"):
                self.exporter.export_statistics(stats, filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                self.exporter.export_statistics_json(stats, filepath if fmt == "json" else None)
            messagebox.showinfo("Export Complete", "Statistics exported successfully!")

        ExportDialog(self.root, export_callback)

    def save_token(self):
        token = self.token_entry.get_value().strip()
        if token:
            # Update tracker with new token
            self.tracker.client.token = token
            self.tracker.client.session.headers["Authorization"] = f"token {token}"
            messagebox.showinfo("Token Saved", "GitHub token updated. Rate limits increased to 5000/hour.")
        else:
            messagebox.showwarning("Empty Token", "Please enter a GitHub token")

    def clear_cache(self):
        self.tracker.clear_cache()
        messagebox.showinfo("Cache Cleared", "All cached data has been cleared")

    def clear_history(self):
        # No history in this app currently
        messagebox.showinfo("History", "No conversion history to clear")

    def open_profile(self):
        if self.tracker.user:
            webbrowser.open(self.tracker.user.html_url)

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
    app = GitHubProfileAnalyzerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()