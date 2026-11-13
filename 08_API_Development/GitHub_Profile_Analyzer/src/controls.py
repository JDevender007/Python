"""
GitHub Profile Analyzer - Controls Module
Custom Tkinter widgets and controls.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional, List, Dict, Any
from .config import COLORS
from .utils import format_number, format_date, format_datetime, get_language_color


class ModernButton(tk.Button):
    """Modern styled button."""

    def __init__(self, parent, text: str, command: Callable = None,
                 style: str = "primary", **kwargs):
        bg_color = COLORS["accent"] if style == "primary" else COLORS["button_bg"]
        fg_color = COLORS["bg"] if style == "primary" else COLORS["fg"]
        hover_color = COLORS["accent_hover"] if style == "primary" else COLORS["border"]

        super().__init__(
            parent,
            text=text,
            command=command,
            bg=bg_color,
            fg=fg_color,
            activebackground=hover_color,
            activeforeground=fg_color,
            font=("Segoe UI", 10, "bold" if style == "primary" else "normal"),
            relief="flat",
            bd=0,
            padx=20,
            pady=8,
            cursor="hand2",
            **kwargs
        )
        self.default_bg = bg_color
        self.hover_bg = hover_color
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        self.config(bg=self.hover_bg)

    def _on_leave(self, event):
        self.config(bg=self.default_bg)


class ModernEntry(tk.Entry):
    """Modern styled entry field."""

    def __init__(self, parent, placeholder: str = "", **kwargs):
        super().__init__(
            parent,
            bg=COLORS["input_bg"],
            fg=COLORS["input_fg"],
            insertbackground=COLORS["accent"],
            font=("Segoe UI", 11),
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            **kwargs
        )
        self.placeholder = placeholder
        self.placeholder_color = COLORS["text_secondary"]
        self.default_fg = COLORS["input_fg"]
        self._has_placeholder = False

        if placeholder:
            self._show_placeholder()

        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _show_placeholder(self):
        self.insert(0, self.placeholder)
        self.config(fg=self.placeholder_color)
        self._has_placeholder = True

    def _on_focus_in(self, event):
        if self._has_placeholder:
            self.delete(0, tk.END)
            self.config(fg=self.default_fg)
            self._has_placeholder = False

    def _on_focus_out(self, event):
        if not self.get():
            self._show_placeholder()

    def get_value(self) -> str:
        if self._has_placeholder:
            return ""
        return self.get()


class ModernFrame(tk.Frame):
    """Modern styled frame."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)


class ModernLabel(tk.Label):
    """Modern styled label."""

    def __init__(self, parent, text: str, style: str = "normal", **kwargs):
        styles = {
            "normal": {"font": ("Segoe UI", 10), "fg": COLORS["fg"]},
            "title": {"font": ("Segoe UI", 22, "bold"), "fg": COLORS["accent"]},
            "subtitle": {"font": ("Segoe UI", 13, "bold"), "fg": COLORS["fg"]},
            "secondary": {"font": ("Segoe UI", 9), "fg": COLORS["text_secondary"]},
            "success": {"font": ("Segoe UI", 10, "bold"), "fg": COLORS["success"]},
            "error": {"font": ("Segoe UI", 10, "bold"), "fg": COLORS["error"]},
            "warning": {"font": ("Segoe UI", 10, "bold"), "fg": COLORS["warning"]},
            "large": {"font": ("Segoe UI", 18), "fg": COLORS["fg"]},
            "stat": {"font": ("Segoe UI", 24, "bold"), "fg": COLORS["accent"]},
            "stat_label": {"font": ("Segoe UI", 9), "fg": COLORS["text_secondary"]},
        }
        style_config = styles.get(style, styles["normal"])
        super().__init__(parent, text=text, bg=COLORS["bg"], **style_config, **kwargs)


class ModernCombobox(ttk.Combobox):
    """Modern styled combobox."""

    def __init__(self, parent, values: List[str] = None, **kwargs):
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Modern.TCombobox",
            fieldbackground=COLORS["input_bg"],
            background=COLORS["card_bg"],
            foreground=COLORS["input_fg"],
            arrowcolor=COLORS["accent"],
            borderwidth=1,
            relief="flat",
        )

        super().__init__(
            parent,
            values=values or [],
            state="readonly",
            font=("Segoe UI", 11),
            style="Modern.TCombobox",
            **kwargs
        )


class ModernTreeview(ttk.Treeview):
    """Modern styled treeview/table."""

    def __init__(self, parent, columns: List[str], **kwargs):
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Modern.Treeview",
            background=COLORS["card_bg"],
            foreground=COLORS["fg"],
            fieldbackground=COLORS["card_bg"],
            borderwidth=0,
            rowheight=32,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Modern.Treeview.Heading",
            background=COLORS["table_header"],
            foreground=COLORS["accent"],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", COLORS["table_selected"])],
            foreground=[("selected", COLORS["accent"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["scrollbar"],
            troughcolor=COLORS["card_bg"],
            borderwidth=0,
            arrowcolor=COLORS["fg"],
        )

        super().__init__(
            parent,
            columns=columns,
            show="headings",
            style="Modern.Treeview",
            **kwargs
        )

        for col in columns:
            self.heading(col, text=col.replace("_", " ").title())
            self.column(col, width=120, anchor="w", stretch=True)

        self.tag_configure("odd", background=COLORS["table_row_alt"])
        self.tag_configure("even", background=COLORS["card_bg"])


class ProgressDialog(tk.Toplevel):
    """Progress dialog for long-running operations."""

    def __init__(self, parent, title: str = "Processing", message: str = "Please wait..."):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x150")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.transient(parent)
        self.grab_set()

        self.cancelled = False

        ModernLabel(self, text=message, style="normal").pack(pady=20)

        self.progress = ttk.Progressbar(
            self, mode="indeterminate", style="Modern.Horizontal.TProgressbar"
        )
        self.progress.pack(fill="x", padx=20, pady=10)
        self.progress.start(10)

        btn_frame = ModernFrame(self)
        btn_frame.pack(pady=10)
        ModernButton(btn_frame, text="Cancel", command=self._cancel, style="secondary").pack()

        self.center_window()

    def _cancel(self):
        self.cancelled = True
        self._update_status("Cancelling...")

    def _update_status(self, message: str):
        for widget in self.winfo_children():
            if isinstance(widget, tk.Label):
                widget.config(text=message)
                break

    def update_progress(self, current: int, total: int, message: str = ""):
        self.progress.stop()
        self.progress.config(mode="determinate", maximum=total, value=current)
        if message:
            self._update_status(message)

    def center_window(self):
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")


class ExportDialog(tk.Toplevel):
    """Dialog for export options."""

    def __init__(self, parent, callback: Callable[[str, str], None]):
        super().__init__(parent)
        self.title("Export Data")
        self.geometry("400x250")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.transient(parent)
        self.grab_set()
        self.callback = callback

        ModernLabel(self, text="Export Options", style="title").pack(pady=20)

        self.format_var = tk.StringVar(value="csv")

        formats_frame = ModernFrame(self)
        formats_frame.pack(pady=10)

        for text, value in [("CSV", "csv"), ("JSON", "json"), ("Both", "both")]:
            tk.Radiobutton(
                formats_frame, text=text, variable=self.format_var, value=value,
                bg=COLORS["bg"], fg=COLORS["fg"], selectcolor=COLORS["card_bg"],
                activebackground=COLORS["bg"], activeforeground=COLORS["accent"],
                font=("Segoe UI", 10)
            ).pack(anchor="w", padx=20, pady=5)

        btn_frame = ModernFrame(self)
        btn_frame.pack(pady=20)

        ModernButton(btn_frame, text="Export", command=self._export, style="primary").pack(side="left", padx=10)
        ModernButton(btn_frame, text="Cancel", command=self.destroy, style="secondary").pack(side="left", padx=10)

        self.center_window()

    def _export(self):
        fmt = self.format_var.get()
        filepath = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}" if fmt != "both" else ".csv",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Export File"
        )
        if filepath:
            self.callback(filepath, fmt)
        self.destroy()

    def center_window(self):
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")


class StatCard(tk.Frame):
    """Statistic display card."""

    def __init__(self, parent, title: str, value: str = "0", icon: str = "", **kwargs):
        super().__init__(parent, bg=COLORS["card_bg"], **kwargs)
        self.create_widgets(title, value, icon)

    def create_widgets(self, title: str, value: str, icon: str):
        if icon:
            ModernLabel(self, text=icon, style="large").pack(pady=(15, 5))

        self.value_label = ModernLabel(self, text=value, style="stat")
        self.value_label.pack()

        ModernLabel(self, text=title, style="stat_label").pack(pady=(0, 15))

    def update_value(self, value: str):
        self.value_label.config(text=value)


class LanguageBar(tk.Frame):
    """Language percentage bar."""

    def __init__(self, parent, language: str, percentage: float, count: int, **kwargs):
        super().__init__(parent, bg=COLORS["card_bg"], **kwargs)
        self.language = language
        self.percentage = percentage
        self.count = count
        self.color = get_language_color(language)
        self.create_widgets()

    def create_widgets(self):
        # Language name and count
        header = ModernFrame(self)
        header.pack(fill="x", padx=10, pady=5)

        ModernLabel(header, text=self.language, style="subtitle").pack(side="left")
        ModernLabel(header, text=f"{self.count} repos", style="secondary").pack(side="right")

        # Progress bar
        bar_frame = ModernFrame(self)
        bar_frame.pack(fill="x", padx=10, pady=(0, 10))

        bar_bg = tk.Frame(bar_frame, bg=COLORS["border"], height=8)
        bar_bg.pack(fill="x")
        bar_bg.pack_propagate(False)

        self.bar_fill = tk.Frame(bar_bg, bg=self.color, height=8)
        self.bar_fill.place(relx=0, rely=0, relwidth=self.percentage / 100, relheight=1)

        # Percentage label
        ModernLabel(bar_frame, text=f"{self.percentage:.1f}%", style="secondary").pack(anchor="e", padx=10)

    def update_percentage(self, percentage: float):
        self.percentage = percentage
        self.bar_fill.place(relx=0, rely=0, relwidth=percentage / 100, relheight=1)


class RepoCard(tk.Frame):
    """Repository display card."""

    def __init__(self, parent, repo, **kwargs):
        super().__init__(parent, bg=COLORS["card_bg"], **kwargs)
        self.repo = repo
        self.create_widgets()

    def create_widgets(self):
        main_frame = ModernFrame(self)
        main_frame.pack(fill="x", padx=15, pady=12)

        # Top row: name, stars, forks
        top_frame = ModernFrame(main_frame)
        top_frame.pack(fill="x")

        repo_link = ModernLabel(top_frame, text=self.repo.name, style="subtitle")
        repo_link.pack(side="left")
        repo_link.bind("<Button-1>", lambda e: self.open_repo())
        repo_link.config(cursor="hand2")

        # Stars
        ModernLabel(top_frame, text=f"⭐ {format_number(self.repo.stars)}", style="secondary").pack(side="right", padx=10)
        # Forks
        ModernLabel(top_frame, text=f"🍴 {format_number(self.repo.forks)}", style="secondary").pack(side="right", padx=10)
        # Language
        if self.repo.language:
            lang_frame = ModernFrame(top_frame)
            lang_frame.pack(side="right", padx=10)
            color_indicator = tk.Frame(lang_frame, bg=self.repo.language_color, width=12, height=12)
            color_indicator.pack(side="left", padx=(0, 5))
            ModernLabel(lang_frame, text=self.repo.language, style="secondary").pack(side="left")

        # Description
        if self.repo.description:
            desc = self.repo.description[:150] + "..." if len(self.repo.description) > 150 else self.repo.description
            ModernLabel(main_frame, text=desc, style="secondary", wraplength=600, justify="left").pack(anchor="w", pady=(5, 0))

        # Bottom info
        bottom_frame = ModernFrame(main_frame)
        bottom_frame.pack(fill="x", pady=(8, 0))

        ModernLabel(bottom_frame, text=f"Updated: {format_date(self.repo.updated_at)}", style="secondary").pack(side="left")
        if self.repo.fork:
            ModernLabel(bottom_frame, text="🍴 Fork", style="warning").pack(side="left", padx=10)
        if self.repo.archived:
            ModernLabel(bottom_frame, text="📦 Archived", style="warning").pack(side="left", padx=10)
        if self.repo.private:
            ModernLabel(bottom_frame, text="🔒 Private", style="warning").pack(side="left", padx=10)
        if self.repo.license_name:
            ModernLabel(bottom_frame, text=f"📄 {self.repo.license_name}", style="secondary").pack(side="left", padx=10)

        # Topics
        if self.repo.topics:
            topics_frame = ModernFrame(main_frame)
            topics_frame.pack(fill="x", pady=(5, 0))
            for topic in self.repo.topics[:8]:
                topic_label = ModernLabel(topics_frame, text=f"#{topic}", style="secondary")
                topic_label.pack(side="left", padx=3)

    def open_repo(self):
        import webbrowser
        webbrowser.open(self.repo.html_url)


class EventCard(tk.Frame):
    """Event display card."""

    def __init__(self, parent, event, **kwargs):
        super().__init__(parent, bg=COLORS["card_bg"], **kwargs)
        self.event = event
        self.create_widgets()

    def create_widgets(self):
        main_frame = ModernFrame(self)
        main_frame.pack(fill="x", padx=15, pady=10)

        # Event type and repo
        header = ModernFrame(main_frame)
        header.pack(fill="x")

        ModernLabel(header, text=self.event.display_type, style="subtitle").pack(side="left")

        repo_label = ModernLabel(header, text=self.event.repo_name, style="secondary")
        repo_label.pack(side="left", padx=10)
        repo_label.bind("<Button-1>", lambda e: self.open_repo())
        repo_label.config(cursor="hand2")

        # Time
        time_text = format_datetime(self.event.created_at)
        ModernLabel(header, text=time_text, style="secondary").pack(side="right")

        # Payload details
        if self.event.payload:
            details = ModernFrame(main_frame)
            details.pack(fill="x", pady=(5, 0))

            if self.event.type == "PushEvent":
                commits = self.event.payload.get("commits", [])
                if commits:
                    ModernLabel(details, text=f"📝 {len(commits)} commit(s)", style="secondary").pack(side="left")
                    for commit in commits[:3]:
                        ModernLabel(details, text=f"  • {commit.get('message', '')[:50]}", style="secondary").pack(anchor="w")

            elif self.event.type == "IssuesEvent":
                action = self.event.payload.get("action", "")
                issue = self.event.payload.get("issue", {})
                ModernLabel(details, text=f"🐛 {action}: {issue.get('title', '')[:60]}", style="secondary").pack(anchor="w")

            elif self.event.type == "PullRequestEvent":
                action = self.event.payload.get("action", "")
                pr = self.event.payload.get("pull_request", {})
                ModernLabel(details, text=f"🔀 {action}: {pr.get('title', '')[:60]}", style="secondary").pack(anchor="w")

            elif self.event.type == "ReleaseEvent":
                release = self.event.payload.get("release", {})
                ModernLabel(details, text=f"📦 Released: {release.get('tag_name', '')}", style="secondary").pack(anchor="w")

    def open_repo(self):
        import webbrowser
        webbrowser.open(self.event.repo_url)